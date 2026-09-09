"""Topology-preserving ocean labelling and explicit regional boundary corrections.

The detailed water polygon defines the footprint; coarse marine polygons only
provide labels. Gap separators inferred from sampled coastlines are approximate,
not new authoritative hydrographic boundaries. See docs/ocean_method.rst.
"""

import logging

import geopandas as gpd
import numpy as np
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import LineString, MultiPoint, Polygon, box
from shapely.ops import split, transform


# WGS84 approximations of the named capes in IHO S-23 (1953), Mediterranean
# western limit. The line is extended into land; no finite-width buffer removes water.
# Source: https://iho.int/uploads/user/pubs/standards/s-23/S-23_Ed3_1953_EN.pdf
GIBRALTAR_CAPES = ((-6.035, 36.183), (-5.922, 35.790))
GIBRALTAR_WINDOW = (-6.3, 35.6, -5.1, 36.4)
GAP_SAMPLE_METRES = 500.0
AREA_TOLERANCE_DEG2 = 1e-9  # Numerical topology check, not a minimum feature size.


def polygonal(geometry):
    """Repair invalid input, retaining every polygon and hole, without buffering."""
    if geometry is None or geometry.is_empty:
        return Polygon()
    geometry = shapely.make_valid(geometry)
    if geometry.geom_type == "Polygon":
        return geometry
    if geometry.geom_type not in ("MultiPolygon", "GeometryCollection"):
        return Polygon()
    parts = []
    for part in geometry.geoms:
        if part.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
            cleaned = polygonal(part)
            if not cleaned.is_empty:
                parts.append(cleaned)
    return shapely.union_all(parts) if parts else Polygon()


def ocean_domain(ocean, countries=None):
    """Use repaired detailed ocean; optionally remove overlap with country land.

    Never replace this by world-minus-countries: that floods islands absent from
    admin-0. Countries themselves are not edited. Inputs must be EPSG:4326.
    """
    if ocean.crs is None or ocean.crs.to_epsg() != 4326:
        raise ValueError("Ocean domain requires EPSG:4326")
    water = polygonal(shapely.union_all([polygonal(g) for g in ocean.geometry]))
    if countries is not None:
        if countries.crs != ocean.crs:
            raise ValueError("Countries and ocean CRS must match")
        land = shapely.union_all([polygonal(g) for g in countries.geometry])
        overlap = water.intersection(land).area
        logging.info("Removing country/ocean overlap: %.12g square degrees", overlap)
        water = polygonal(water.difference(land))
    return water


def apply_gibraltar(regions, water):
    """Replace all labels inside a local strait window with a coast-to-coast cut."""
    atlantic, mediterranean = "North Atlantic Ocean", "Mediterranean Region"
    if not {atlantic, mediterranean}.issubset(regions):
        return regions
    window = box(*GIBRALTAR_WINDOW)
    a, b = np.asarray(GIBRALTAR_CAPES, dtype=float)
    direction = b - a
    cutter = LineString([a - 5 * direction, b + 5 * direction])
    halves = list(split(window, cutter).geoms)
    if len(halves) != 2:
        raise ValueError("Gibraltar separator must cross its complete correction window")
    result = {name: polygonal(g.difference(window)) for name, g in regions.items()}
    # East side is Mediterranean; selection uses signed side, not bounds ordering.
    for half in halves:
        p = half.representative_point()
        side = direction[0] * (p.y - a[1]) - direction[1] * (p.x - a[0])
        label = mediterranean if side > 0 else atlantic
        result[label] = polygonal(result[label].union(water.intersection(half)))
    return result


def _gap_pieces(gap, seeds, sample_metres):
    """Partition an ambiguous gap using locally projected sampled-boundary Voronoi.

    Inverse-project separators, then clip against the ORIGINAL water geometry;
    the high-resolution coastline is never round-tripped through a projection.
    """
    names = sorted(seeds)
    if len(names) == 1:
        return {names[0]: gap}
    center = gap.representative_point()
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m")
    forward = Transformer.from_crs(4326, crs, always_xy=True).transform
    backward = Transformer.from_crs(crs, 4326, always_xy=True, force_over=True).transform
    bounds = gap.bounds
    margin = max(0.02, bounds[2] - bounds[0], bounds[3] - bounds[1],
                 2 * max(gap.distance(seed) for seed in seeds.values()))
    window = box(bounds[0] - margin, max(-90, bounds[1] - margin),
                 bounds[2] + margin, min(90, bounds[3] + margin))
    points, owners = [], []
    for name in names:
        edge = seeds[name].boundary.intersection(window)
        if edge.is_empty:
            continue
        edge_m = transform(forward, edge)
        coords = shapely.get_coordinates(shapely.segmentize(edge_m, sample_metres))
        for xy in coords:
            # Millimetre quantization only for Voronoi sites avoids near-duplicate
            # projected vertices destabilizing GEOS; coastline coordinates are untouched.
            points.append(tuple(np.round(xy, 3)))
            owners.append(name)
    # Stable ownership for coincident samples, independent of source row order.
    unique = {}
    for xy, name in zip(points, owners):
        unique.setdefault(xy, name)
    if len(unique) < 2:
        raise ValueError("Insufficient distinct marine-boundary samples for an ambiguous gap")
    points = sorted(unique)
    extent = transform(forward, window).envelope
    cells = shapely.voronoi_polygons(MultiPoint(points), extend_to=extent, ordered=True)
    by_name = {name: [] for name in names}
    for xy, cell in zip(points, cells.geoms):
        by_name[unique[xy]].append(polygonal(cell))
    remaining = gap
    result = {}
    for name in names[:-1]:
        projected = shapely.union_all(by_name[name])
        separator = polygonal(transform(backward, shapely.segmentize(projected, sample_metres)))
        piece = polygonal(remaining.intersection(separator))
        result[name] = piece
        remaining = polygonal(remaining.difference(piece))
    result[names[-1]] = remaining
    return result


def partition_ocean(water, marine, *, sample_metres=GAP_SAMPLE_METRES, gibraltar=True):
    """Return a complete non-overlapping partition using ``parent_reg`` labels.

    Unmapped labels and cross-group coarse overlaps are rejected, not silently
    assigned to an 'Other' region. Isolated gaps use local nearest seed evidence.
    """
    if sample_metres <= 0 or not np.isfinite(sample_metres):
        raise ValueError("sample_metres must be positive and finite")
    if marine.crs is None or marine.crs.to_epsg() != 4326:
        raise ValueError("Marine labels require EPSG:4326")
    if marine.parent_reg.isna().any():
        raise ValueError("All marine polygons must have a mapped parent_reg")
    grouped = marine.copy()
    grouped.geometry = grouped.geometry.map(polygonal)
    grouped = grouped.dissolve(by="parent_reg").sort_index()
    logging.info("Prepared %d marine label groups; gap samples %.1f m", len(grouped), sample_metres)
    seeds = dict(zip(grouped.index, grouped.geometry))
    # Repair the coarse source's artificial eastern seam (179.999897 degrees).
    # Only label geometry changes; the detailed ocean footprint stays untouched.
    def close_seam(x, y, z=None):
        x = np.asarray(x)
        return np.where(x >= 179.9998, 180.0, x), y
    seeds = {name: polygonal(transform(close_seam, g)) for name, g in seeds.items()}
    if gibraltar:
        seeds = apply_gibraltar(seeds, water)
    names = sorted(seeds)
    for i, name in enumerate(names):
        for other in names[i + 1:]:
            overlap = seeds[name].intersection(seeds[other]).intersection(water).area
            if overlap > AREA_TOLERANCE_DEG2:
                raise ValueError(f"Conflicting coarse marine labels: {name}, {other}: {overlap} deg²")
    chunks = {name: [polygonal(water.intersection(seeds[name]))] for name in names}
    logging.info("Clipped marine labels to the detailed water footprint")
    covered = shapely.union_all([g[0] for g in chunks.values()])
    gaps = shapely.get_parts(polygonal(water.difference(covered)))
    logging.info("Assigning %d coastal gap components", len(gaps))
    tree = shapely.STRtree(list(seeds.values()))
    stats = {"single_group_gaps": 0, "ambiguous_gaps": 0, "isolated_gaps": 0}
    for gap in gaps:
        if gap.is_empty:
            continue
        indices = tree.query(gap, predicate="intersects")
        candidates = {names[int(i)]: seeds[names[int(i)]] for i in indices}
        if not candidates:
            stats["isolated_gaps"] += 1
            # Search a local neighbourhood; all qualifying groups participate,
            # rather than accepting an arbitrary first nearest-index tie.
            radius = 0.05
            while not candidates and radius <= 360:
                indices = tree.query(gap.envelope.buffer(radius), predicate="intersects")
                candidates = {names[int(i)]: seeds[names[int(i)]] for i in indices}
                radius *= 2
            if not candidates:
                raise ValueError("No marine label found for water component")
        if len(candidates) == 1:
            stats["single_group_gaps"] += 1
        else:
            stats["ambiguous_gaps"] += 1
            logging.info("Splitting ambiguous gap bounds=%s groups=%s", gap.bounds, sorted(candidates))
        for name, piece in _gap_pieces(gap, candidates, sample_metres).items():
            if not piece.is_empty:
                chunks[name].append(piece)
    regions = {name: polygonal(shapely.union_all(chunks[name])) for name in names}
    # Reapply the explicit cut after inference so no inferred gap can cross it.
    if gibraltar:
        regions = apply_gibraltar(regions, water)
    validate_partition(water, regions)
    logging.info("Ocean gap assignments: %s", stats)
    return gpd.GeoDataFrame({"parent_reg": names}, geometry=[regions[n] for n in names], crs=marine.crs)


def validate_partition(water, regions, tolerance=AREA_TOLERANCE_DEG2):
    """Reject lost/added water, invalid geometries, and positive-area overlaps."""
    values = list(regions.values())
    if not all(g.is_valid and not g.is_empty for g in values):
        raise ValueError("Ocean partition contains empty or invalid regions")
    error = shapely.union_all(values).symmetric_difference(water).area
    if error > tolerance:
        raise ValueError(f"Ocean partition changes water footprint by {error} deg²")
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            if a.intersection(b).area > tolerance:
                raise ValueError("Ocean partition contains overlapping groups")
