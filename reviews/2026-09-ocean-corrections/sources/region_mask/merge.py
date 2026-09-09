"""Natural Earth merge: original transformations, with explicit file paths.

Migrated from merge_shp_ne_10m.ipynb. Plot-only cells are omitted.
Operation order, schemas, mappings and historical behaviours are preserved.
"""

import geopandas as gpd
import pandas as pd
import logging
from pathlib import Path

def generate_merge(countries_from_ne_path, oceans_from_ne_path, full_path):
    """Generate and write the shapefile; return its GeoDataFrame.

    Inputs and output are explicit paths. No .env or working-directory changes.
    The output and its shapefile sidecars are overwritten when this is called.
    """
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)

    # Original merge_shp_ne_10m.ipynb, cell 11
    # countries
    logging.info(f"Reading countries shapefile  from {countries_from_ne_path}")
    gdf_countries = gpd.read_file(countries_from_ne_path)

    # oceans
    logging.info(f"Reading ocean shapefile from {oceans_from_ne_path}")
    gdf_oceans = gpd.read_file(oceans_from_ne_path)

    # Original merge_shp_ne_10m.ipynb, cell 13
    # Verify columns alignment

    if gdf_countries.columns.all() == gdf_oceans.columns.all():
        logging.info("Columns aligned")
    else:
        logging.info("Columns system not aligned")


    # Verify reference system alignment
    logging.info(f"Countries reference system: {gdf_countries.crs}")
    logging.info(f"Oceans reference system: {gdf_oceans.crs}")


    if gdf_countries.crs == gdf_oceans.crs:
        logging.info("Reference system aligned")
    else:
        logging.info("Reference system not aligned")

    # Original merge_shp_ne_10m.ipynb, cell 15
    # Merge together the gdfs
    gdf_final = gpd.GeoDataFrame(
        pd.concat([gdf_countries, gdf_oceans], ignore_index=True),
        crs="EPSG:4326"
    )

    # Original merge_shp_ne_10m.ipynb, cell 17
    # Save GeoDataFrame
    gdf_final.to_file(full_path)

    logging.info(f"Saved Shapefile to: {full_path}")
    return gdf_final
