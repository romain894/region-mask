"""Compare delivered NetCDF files, reading one first-dimension slab at a time."""

from pathlib import Path

import netCDF4
import numpy as np

from .common import plain, sha256


def compare_values(reference, candidate, atol=0.0, rtol=0.0):
    """No broadcasting, no implicit alignment, and no tolerance on missingness."""
    a, b = np.ma.asarray(reference), np.ma.asarray(candidate)
    if a.shape != b.shape:
        return {"passed": False, "error": "Array shapes differ"}
    av, bv = np.asarray(a.data), np.asarray(b.data)
    am, bm = np.ma.getmaskarray(a), np.ma.getmaskarray(b)
    numeric = av.dtype.kind in "biuf" and bv.dtype.kind in "biuf"
    if numeric:
        am = am | np.isnan(av)
        bm = bm | np.isnan(bv)
    usable = ~(am | bm)
    equal = np.ones(av.shape, dtype=bool)
    equal[usable] = av[usable] == bv[usable]
    missing_changes = int(np.count_nonzero(am != bm))
    result = {
        "count": int(av.size),
        "missing_pattern_changes": missing_changes,
        "changed_values": int(np.count_nonzero(~equal)),
        "exact_equal": bool(equal.all() and missing_changes == 0),
    }
    if not numeric:
        result["passed"] = result["exact_equal"]
        return result
    finite = usable & np.isfinite(av) & np.isfinite(bv)
    different_nonfinite = usable & ~finite & ~equal
    delta = np.zeros(av.shape, dtype=np.float64)
    delta[finite] = np.abs(av[finite].astype(np.float64) - bv[finite].astype(np.float64))
    over = np.zeros(av.shape, dtype=bool)
    # Integer/boolean variables are exact contracts, not floating-point quantities.
    if av.dtype.kind in "biu" and bv.dtype.kind in "biu":
        over = ~equal
    else:
        over[finite] = delta[finite] > atol + rtol * np.abs(av[finite].astype(np.float64))
    over |= different_nonfinite
    count_finite = int(np.count_nonzero(finite))
    result.update(
        above_tolerance=int(np.count_nonzero(over)),
        finite_count=count_finite,
        max_abs_diff=float(delta.max()) if delta.size else 0.0,
        sum_abs_diff=float(delta.sum(dtype=np.float64)),
        mean_abs_diff=float(delta.sum(dtype=np.float64) / count_finite) if count_finite else 0.0,
        max_diff_index=list(np.unravel_index(int(delta.argmax()), delta.shape)) if delta.size else None,
        zero_transitions=int(np.count_nonzero(finite & ((av == 0) != (bv == 0)))),
        one_transitions=int(np.count_nonzero(finite & ((av == 1) != (bv == 1)))),
        reference_infinities=int(np.count_nonzero(~am & np.isinf(av))),
        candidate_infinities=int(np.count_nonzero(~bm & np.isinf(bv))),
        passed=bool(missing_changes == 0 and not over.any()),
    )
    return plain(result)


def _attrs(obj):
    return plain({k: obj.getncattr(k) for k in obj.ncattrs()})


def _schema(dataset):
    return {
        "dimensions": {k: {"length": len(v), "unlimited": v.isunlimited()}
                       for k, v in dataset.dimensions.items()},
        "attributes": _attrs(dataset),
        "variables": {k: {"dimensions": list(v.dimensions), "dtype": str(v.dtype),
                          "attributes": _attrs(v)} for k, v in dataset.variables.items()},
    }


def _storage(dataset):
    return plain({
        "data_model": dataset.data_model,
        "variables": {k: {"filters": v.filters(), "chunking": v.chunking(), "endian": v.endian()}
                      for k, v in dataset.variables.items()},
    })


def _changes(a, b):
    return {k: {"reference": a.get(k), "candidate": b.get(k)}
            for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}


def _value_summary(value):
    x = np.ma.asarray(value)
    v = np.asarray(x.data)
    missing = np.ma.getmaskarray(x) | np.isnan(v)
    finite = v[~missing & np.isfinite(v)]
    return {
        "missing": int(missing.sum()),
        "infinite": int(np.count_nonzero(~missing & np.isinf(v))),
        "minimum": float(finite.min()) if finite.size else None,
        "maximum": float(finite.max()) if finite.size else None,
        "zeros": int(np.count_nonzero(finite == 0)),
        "ones": int(np.count_nonzero(finite == 1)),
        "outside_0_1": int(np.count_nonzero((finite < 0) | (finite > 1))),
        "sum_fractions": float(finite.sum(dtype=np.float64)),
    }


def compare_netcdf(reference, candidate, atol=0.0, rtol=0.0, figure=None):
    result = {"passed": True, "atol": atol, "rtol": rtol, "variables": {}}
    result["sha256"] = {"reference": sha256(reference), "candidate": sha256(candidate)}
    result["byte_identical"] = result["sha256"]["reference"] == result["sha256"]["candidate"]
    with netCDF4.Dataset(reference) as a, netCDF4.Dataset(candidate) as b:
        if a.groups or b.groups:
            return {**result, "passed": False, "error": "Grouped NetCDF requires a group-aware comparator"}
        sa, sb = _schema(a), _schema(b)
        result["schema_changes"] = _changes(sa, sb)
        result["reference_schema"] = sa
        result["storage_changes"] = _changes(_storage(a), _storage(b))
        result["reference_storage"] = _storage(a)
        result["passed"] = not result["schema_changes"]
        difference_map = None
        for name in sorted(set(a.variables) & set(b.variables)):
            av, bv = a[name], b[name]
            if av.shape != bv.shape or av.dimensions != bv.dimensions:
                result["variables"][name] = {"passed": False, "error": "Shape/dimensions differ"}
                result["passed"] = False
                continue
            item = {"passed": True, "exact_equal": True, "changed_values": 0,
                    "missing_pattern_changes": 0, "above_tolerance": 0,
                    "max_abs_diff": 0.0, "sum_abs_diff": 0.0, "finite_count": 0,
                    "zero_transitions": 0, "one_transitions": 0}
            region_mask = av.dimensions == ("region", "lat", "lon") and name == "mask"
            if region_mask:
                item["regions"] = {}
                sums_a, sums_b = np.zeros(av.shape[1:]), np.zeros(av.shape[1:])
                missing_a, missing_b = np.zeros(av.shape[1:], dtype=bool), np.zeros(av.shape[1:], dtype=bool)
                difference_map = np.zeros(av.shape[1:])
            slices = range(av.shape[0]) if av.ndim else [None]
            for i in slices:
                va, vb = (av[...], bv[...]) if i is None else (av[i], bv[i])
                # Coordinates, IDs, and integer variables must remain exact even in tolerance mode.
                coordinate = name in av.dimensions or name in {"region", "lat", "lon"}
                metrics = compare_values(va, vb, 0 if coordinate else atol, 0 if coordinate else rtol)
                item["passed"] &= metrics["passed"]
                item["exact_equal"] &= metrics["exact_equal"]
                for key in ["changed_values", "missing_pattern_changes", "above_tolerance",
                            "sum_abs_diff", "finite_count", "zero_transitions", "one_transitions"]:
                    item[key] += metrics.get(key, 0)
                if metrics.get("max_abs_diff", 0) > item["max_abs_diff"]:
                    item["max_abs_diff"] = metrics["max_abs_diff"]
                    index = ([] if i is None else [i]) + metrics["max_diff_index"]
                    item["max_diff_index"] = index
                    item["max_diff_coordinates"] = plain({
                        d: np.asarray(a[d][j]).item() for d, j in zip(av.dimensions, index)
                        if d in a.variables and a[d].ndim == 1
                    })
                if region_mask:
                    label = str(np.asarray(a["region"][i]).item())
                    item["regions"][label] = {**metrics, "reference": _value_summary(va),
                                              "candidate": _value_summary(vb)}
                    x, y = np.ma.filled(va, np.nan).astype(float), np.ma.filled(vb, np.nan).astype(float)
                    missing_a |= ~np.isfinite(x)
                    missing_b |= ~np.isfinite(y)
                    sums_a += np.where(np.isfinite(x), x, 0)
                    sums_b += np.where(np.isfinite(y), y, 0)
                    difference_map = np.maximum(difference_map, np.nan_to_num(np.abs(x - y), nan=0, posinf=0))
            item["mean_abs_diff"] = item["sum_abs_diff"] / item["finite_count"] if item["finite_count"] else 0.0
            if region_mask:
                def summary(sums, missing):
                    valid = sums[~missing]
                    return {"cells_with_missing_or_infinite_regions": int(missing.sum()),
                            "minimum": float(valid.min()) if valid.size else None,
                            "maximum": float(valid.max()) if valid.size else None,
                            "cells_below_1_minus_1e_6": int((valid < 1 - 1e-6).sum()),
                            "cells_above_1_plus_1e_6": int((valid > 1 + 1e-6).sum())}
                item["sum_over_regions"] = {"reference": summary(sums_a, missing_a),
                                            "candidate": summary(sums_b, missing_b),
                                            "note": "float64 diagnostic sum; no assertion of global completeness"}
            result["variables"][name] = item
            result["passed"] &= item["passed"]
        if figure and difference_map is not None and np.any(difference_map):
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(11, 5))
            artist = ax.imshow(difference_map, aspect="auto", interpolation="nearest")
            ax.set(xlabel="Longitude array index", ylabel="Latitude array index",
                   title="Maximum absolute mask change across regions")
            fig.colorbar(artist, ax=ax, label="Fraction difference")
            fig.tight_layout()
            Path(figure).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(figure, dpi=150)
            plt.close(fig)
            result["figure"] = str(figure)
    return plain(result)
