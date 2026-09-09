"""Explicit configuration and stage dispatch shared by notebooks and regression."""

import os
from pathlib import Path

from dotenv import dotenv_values


DEFAULTS = {
    "NE_ADMIN_COUNTRIES_PATH": "data/ne_10m/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp",
    "NE_GEO_MARINE_POLYS_PATH": "data/ne_10m/ne_10m_geography_marine_polys/ne_10m_geography_marine_polys.shp",
    "NE_GEO_OCEAN_PATH": "data/ne_10m/ne_10m_ocean/ne_10m_ocean.shp",
    "CODES_ID_PATH": "data/codes_id.csv",
    "COUNTRIES_FROM_NE_PATH": "data/countries_from_ne_10m/countries_from_ne_10m.shp",
    "OCEANS_FROM_NE_PATH": "data/oceans_from_ne_10m/oceans_from_ne_10m.shp",
    "NE_COUNTRIES_OCEANS_PATH": "data/ne_10m_oceans_countries/ne_10m_oceans_countries.shp",
    "NE_LAND_OCEAN_PATH": "data/ne_10m_land_ocean/ne_10m_land_ocean.shp",
    "MASK_SHAPE_FILE_PATH": "data/ne_10m_oceans_countries/ne_10m_oceans_countries.shp",
    "MASK_MIN_LON": "-0.25", "MASK_MIN_LAT": "-89.75",
    "MASK_MAX_LON": "359.75", "MASK_MAX_LAT": "90.25",
    "MASK_RESOLUTION": "0.5", "NORMALIZE_MASK": "true",
    "DASK_NUM_WORKERS": "4", "DASK_MEMORY_LIMIT": "2GB",
}
STAGES = ("countries", "oceans", "countries_oceans", "land_ocean", "mask")


def environment_settings(root="."):
    """Read defaults < root/.env < environment, without modifying os.environ.

    Only this convenience entry point reads .env. The Python functions and
    regression runner use explicit arguments and do not call it.
    """
    values = dotenv_values(Path(root) / ".env")
    return {key: os.environ.get(key, values.get(key) or default)
            for key, default in DEFAULTS.items()}


def run_stage(stage, *, root=".", settings=None, diagnostics_dir=None):
    """Run one stage; paths are relative to root, not the process directory.

    Calling this writes/overwrites the configured outputs. Upstream stages must
    already have been run. An explicit settings dictionary never reads .env.
    """
    root = Path(root).resolve()
    values = DEFAULTS | (settings or {})

    def path(key):
        return root / values[key]

    if stage == "countries":
        from .countries import generate_countries
        return generate_countries(path("NE_ADMIN_COUNTRIES_PATH"), path("CODES_ID_PATH"),
                                  path("COUNTRIES_FROM_NE_PATH"))
    if stage == "oceans":
        from .oceans import generate_oceans
        return generate_oceans(path("NE_GEO_MARINE_POLYS_PATH"), path("NE_GEO_OCEAN_PATH"),
                               path("CODES_ID_PATH"), path("OCEANS_FROM_NE_PATH"),
                               countries_path=path("COUNTRIES_FROM_NE_PATH"))
    if stage == "countries_oceans":
        from .merge import generate_merge
        return generate_merge(path("COUNTRIES_FROM_NE_PATH"), path("OCEANS_FROM_NE_PATH"),
                              path("NE_COUNTRIES_OCEANS_PATH"))
    if stage == "land_ocean":
        from .land_ocean import generate_land_ocean
        # Deliberately uses the original ocean, not the derived regional seas.
        return generate_land_ocean(path("COUNTRIES_FROM_NE_PATH"), path("NE_GEO_OCEAN_PATH"),
                                   path("CODES_ID_PATH"), path("NE_LAND_OCEAN_PATH"))
    if stage == "mask":
        from .mask import generate_mask
        return generate_mask(
            path("MASK_SHAPE_FILE_PATH"),
            bounds=tuple(float(values[key]) for key in
                         ("MASK_MIN_LON", "MASK_MIN_LAT", "MASK_MAX_LON", "MASK_MAX_LAT")),
            resolution=float(values["MASK_RESOLUTION"]),
            normalize_mask=str(values["NORMALIZE_MASK"]).lower() in ("true", "1", "yes"),
            num_workers=int(values["DASK_NUM_WORKERS"]), memory_limit=values["DASK_MEMORY_LIMIT"],
            diagnostics_dir=diagnostics_dir,
        )
    raise ValueError(f"Unknown stage: {stage!r}; choose from {STAGES}")
