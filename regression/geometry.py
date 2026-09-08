"""Geometry comparisons: exact spatial checks and explanatory area metrics."""

from functools import lru_cache

import geopandas as gpd
import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import box
from shapely.ops import transform

from .common import plain

AREA_METHOD = (
    "Approximate WGS84 cylindrical equal-area area (lat_ts=30); source EPSG:4326 "
    "segments densified to <=0.25 degrees before projection. Longitude seam retained. "
    "No geometry repair for per-feature comparisons."
)
_project = Transformer.from_crs(
    "EPSG:4326", "+proj=cea +lat_ts=30 +datum=WGS84 +units=m +no_defs", always_xy=True
).transform


def area_km2(geometry):
    if geometry is None or geometry.is_empty:
        return 0.0
    return transform(_project, shapely.segmentize(geometry, 0.25)).area / 1e6


def structural_equal(a, b):
    if a is None or b is None:
        return a is b
    return bool(shapely.equals_exact(shapely.normalize(a), shapely.normalize(b), tolerance=0))


@lru_cache(maxsize=2048)
def _metrics(wkb):
    g = shapely.from_wkb(wkb)
    parts = list(shapely.get_parts(g))
    return {
        "area_km2": area_km2(g),
        "bounds": list(g.bounds),
        "geometry_type": g.geom_type,
        "valid": bool(g.is_valid),
        "validity_reason": shapely.is_valid_reason(g),
        "empty": bool(g.is_empty),
        "parts": len(parts),
        "holes": sum(len(p.interiors) for p in parts if p.geom_type == "Polygon"),
        "coordinates": int(shapely.get_num_coordinates(g)),
    }


def geometry_metrics(g):
    return _metrics(g.wkb) if g is not None else {"missing_geometry": True}


def compare_geometry(a, b):
    result = {"reference": geometry_metrics(a), "candidate": geometry_metrics(b)}
    structural = structural_equal(a, b)
    valid = a is not None and b is not None and a.is_valid and b.is_valid
    spatial = bool(a.equals(b)) if valid else None
    result.update(structural_equal=structural, spatial_equal=spatial)
    # Invalid baseline features are compared structurally, never repaired to force a pass.
    result["passed"] = bool(structural or spatial) and (
        result["reference"].get("geometry_type") == result["candidate"].get("geometry_type")
    ) and result["reference"].get("valid") == result["candidate"].get("valid")
    if valid:
        added = 0.0 if spatial else area_km2(b.difference(a))
        removed = 0.0 if spatial else area_km2(a.difference(b))
        result.update(added_km2=added, removed_km2=removed,
                      symmetric_difference_km2=added + removed)
    else:
        result["area_difference_status"] = "Unavailable for invalid/missing geometries; no repair applied."
    old_area = result["reference"].get("area_km2")
    new_area = result["candidate"].get("area_km2")
    if old_area is not None and new_area is not None:
        result["net_area_change_km2"] = new_area - old_area
        result["relative_area_change"] = (new_area - old_area) / old_area if old_area else None
    return result


def _attr(value):
    return None if pd.isna(value) else plain(value)


def compare_shapefiles(reference, candidate):
    a, b = gpd.read_file(reference), gpd.read_file(candidate)
    result = {"passed": True, "errors": [], "regions": {}, "area_method": AREA_METHOD}
    if a.crs != b.crs:
        result["errors"].append("CRS differs")
    result["crs"] = {"reference": str(a.crs), "candidate": str(b.crs)}
    result["columns"] = {"reference": list(a.columns), "candidate": list(b.columns)}
    if list(a.columns) != list(b.columns):
        result["errors"].append("Column names/order differ")
    result["attribute_dtypes"] = {
        "reference": {c: str(a[c].dtype) for c in a.columns if c != "geometry"},
        "candidate": {c: str(b[c].dtype) for c in b.columns if c != "geometry"},
    }
    if result["attribute_dtypes"]["reference"] != result["attribute_dtypes"]["candidate"]:
        result["errors"].append("Attribute dtypes differ")
    for label, frame in [("reference", a), ("candidate", b)]:
        if "ID" not in frame or frame.ID.isna().any() or frame.ID.duplicated().any():
            result["errors"].append(f"{label}: ID must exist, be non-null and unique")
    if any("ID must" in e for e in result["errors"]):
        result["passed"] = False
        return result
    result["row_order_equal"] = a.ID.to_list() == b.ID.to_list()
    a, b = a.set_index("ID"), b.set_index("ID")
    result["missing_ids"] = sorted(set(a.index) - set(b.index))
    result["added_ids"] = sorted(set(b.index) - set(a.index))
    # Area reporting is only defined for the intended geographic dataset.
    if a.crs is None or b.crs is None or a.crs.to_epsg() != 4326 or b.crs.to_epsg() != 4326:
        result["errors"].append("Area diagnostics require EPSG:4326; no implicit reprojection")
        result["passed"] = False
        return result
    for region in sorted(set(a.index) & set(b.index)):
        item = compare_geometry(a.loc[region].geometry, b.loc[region].geometry)
        item["attribute_changes"] = {
            c: {"reference": _attr(a.at[region, c]), "candidate": _attr(b.at[region, c])}
            for c in a.columns.intersection(b.columns) if c != "geometry"
            and _attr(a.at[region, c]) != _attr(b.at[region, c])
        }
        item["passed"] &= not item["attribute_changes"]
        result["regions"][str(region)] = item
    for key, frame, ids in [("removed_regions", a, result["missing_ids"]),
                            ("new_regions", b, result["added_ids"])]:
        result[key] = {str(i): geometry_metrics(frame.loc[i].geometry) for i in ids}
    result["passed"] = not (result["errors"] or result["missing_ids"] or result["added_ids"]) and all(
        r["passed"] for r in result["regions"].values()
    )
    return result


def coverage_metrics(path):
    """Descriptive quality diagnostics; known baseline defects are not test failures.

    Repairs are made on *copies* here solely to make union operations possible.
    This does not affect the strict, unrepaired comparisons above.
    """
    frame = gpd.read_file(path)
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        return {"error": "Coverage diagnostics require EPSG:4326"}
    invalid = [str(r.ID) for r in frame.itertuples() if not r.geometry.is_valid]
    geometries = shapely.make_valid(frame.geometry.values)
    polygon_parts = []

    def collect(g):
        if g.geom_type == "Polygon":
            polygon_parts.append(g)
        elif hasattr(g, "geoms"):
            for p in g.geoms:
                collect(p)

    for g in geometries:
        collect(g)
    union = shapely.union_all(polygon_parts)
    domain = box(-180, -90, 180, 90)
    # Compute intersections directly: projected-area subtraction can cancel or accumulate rounding.
    tree = shapely.STRtree(geometries)
    overlaps = []
    for i, g in enumerate(geometries):
        for j in tree.query(g, predicate="intersects"):
            if j > i:
                overlap = g.intersection(geometries[j])
                if overlap.area > 0:
                    overlaps.append(overlap)
    return {
        "invalid_ids": invalid,
        "diagnostic_repairs": "make_valid copies; polygonal parts only for footprint",
        "uncovered_world_km2": area_km2(domain.difference(union)),
        "outside_world_km2": area_km2(union.difference(domain)),
        "overlap_footprint_km2": area_km2(shapely.union_all(overlaps)),
        "coverage_is_valid_after_repair": bool(shapely.coverage_is_valid(polygon_parts)),
        "area_method": AREA_METHOD,
        "note": "Uncovered world includes any omitted land/water; it is not automatically missing ocean.",
    }
