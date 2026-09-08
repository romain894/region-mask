"""Serialization, provenance and immutable Git reference extraction."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path

import numpy as np

SIDECARS = (".shp", ".shx", ".dbf", ".prj", ".cpg")


def plain(value):
    """JSON-safe values; preserve NaN/Inf explicitly instead of invalid JSON."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def hashes(root, paths):
    return {str(p): sha256(Path(root) / p) for p in sorted(paths) if (Path(root) / p).is_file()}


def artifact_paths(config):
    paths = list(config["netcdf"]) + list(config.get("tables", []))
    for path in config["shapefiles"]:
        paths.extend(str(Path(path).with_suffix(ext)) for ext in SIDECARS)
    return paths


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def export_reference(repo, revision, paths, destination):
    """Read committed blobs, never the possibly modified worktree outputs."""
    commit = git(repo, "rev-parse", "--verify", f"{revision}^{{commit}}").decode().strip()
    for relative in paths:
        path = Path(destination) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(git(repo, "show", f"{commit}:{relative}"))
    return commit


def environment():
    import netCDF4
    import pyproj
    import rasterio
    import shapely

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": dict(sorted((d.metadata["Name"], d.version)
                                for d in importlib.metadata.distributions() if d.metadata["Name"])),
        "GEOS": shapely.geos_version_string,
        "GDAL_rasterio": rasterio.__gdal_version__,
        "PROJ": pyproj.proj_version_str,
        "netCDF_C": netCDF4.__netcdf4libversion__,
        "HDF5": netCDF4.__hdf5libversion__,
    }
