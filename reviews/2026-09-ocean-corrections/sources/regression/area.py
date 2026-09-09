"""Physical area of planar lon/lat polygons, without projecting polygon edges.

Integrate the WGS84 surface Jacobian over signed fan triangles. The triangles
are integration domains, not a repair or a change to the original geometry.
Unlike vertex reprojection, this cannot bend a straight, zero-width sliver into
a curved wedge. Longitude coordinates are used literally (no seam wrapping).
"""

from functools import lru_cache
import numpy as np

A = 6378137.0
F = 1 / 298.257223563
E2 = F * (2 - F)


@lru_cache
def quadrature(order):
    x, w = np.polynomial.legendre.leggauss(order)
    return (x + 1) / 2, w / 2


def _ring(coords, order):
    xy = np.asarray(coords, dtype=np.longdouble)[:, :2]
    a = xy[0]
    b, c = xy[1:-1] - a, xy[2:] - a
    cross = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    # Bounds on floating-point evaluation, not coordinate/source uncertainty.
    magnitude = np.abs(b[:, 0] * c[:, 1]) + np.abs(b[:, 1] * c[:, 0])
    active = cross != 0
    b, c, cross = b[active], c[active], cross[active]
    x, w = quadrature(order)
    total = np.longdouble(0)
    absolute = np.longdouble(0)
    u, v = x[None, :, None], x[None, None, :]
    weights = w[None, :, None] * w[None, None, :] * (1-u)
    for start in range(0, len(cross), 1024):
        end = start + 1024
        by = np.asarray(b[start:end, 1], float)[:, None, None]
        cy = np.asarray(c[start:end, 1], float)[:, None, None]
        phi = np.deg2rad(float(a[1]) + u * by + (1-u) * v * cy)
        density = np.sum(weights * np.cos(phi) / (1-E2*np.sin(phi)**2)**2, axis=(1, 2))
        terms = cross[start:end] * density * (A*A*(1-E2)*(np.pi/180)**2 / 1e6)
        total += np.sum(terms, dtype=np.longdouble)
        absolute += np.sum(np.abs(terms), dtype=np.longdouble)
    rounding = (64*np.finfo(float).eps*absolute +
                64*np.finfo(np.longdouble).eps*np.sum(magnitude)*12500)
    return abs(float(total)), float(rounding)


def _area(g, order):
    if g is None or g.is_empty:
        return 0., 0.
    if g.geom_type == 'Polygon':
        area, error = _ring(g.exterior.coords, order)
        for ring in g.interiors:
            inner, uncertainty = _ring(ring.coords, order)
            area -= inner
            error += uncertainty
        return area, error
    parts = [_area(p, order) for p in getattr(g, 'geoms', [])]
    return sum(p[0] for p in parts), sum(p[1] for p in parts)


def area_measurement(g):
    """Return area and an empirical quadrature/roundoff uncertainty in km².

    The 8/16-order discrepancy is an error indicator, not a certified bound.
    It excludes uncertainty in input coordinates, topology and geography.
    No feature is removed and the result never determines regression acceptance.
    """
    coarse, _ = _area(g, 8)
    fine, rounding = _area(g, 16)
    error = abs(fine - coarse) + rounding
    return {'area_km2': fine, 'area_numerical_uncertainty_km2': error,
            'area_numerically_resolved': abs(fine) > error}
