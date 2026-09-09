"""Natural Earth land_ocean: original transformations, with explicit file paths.

Migrated from generate_shp_land_ocean_ne_10m.ipynb. Plot-only cells are omitted.
Operation order, schemas, mappings and historical behaviours are preserved.
"""

import chardet
import numpy as np
import geopandas as gpd
import pandas as pd
import logging
from pathlib import Path

def generate_land_ocean(countries_from_ne_path, oceans_from_ne_path, codes_id_path, full_path):
    """Generate and write the shapefile; return its GeoDataFrame.

    Inputs and output are explicit paths. No .env or working-directory changes.
    The output and its shapefile sidecars are overwritten when this is called.
    """
    Path(full_path).parent.mkdir(parents=True, exist_ok=True)

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 11
    # countries
    logging.info(f"Reading countries shapefile  from {countries_from_ne_path}")
    gdf_countries = gpd.read_file(countries_from_ne_path)

    # oceans
    logging.info(f"Reading ocean shapefile from {oceans_from_ne_path}")
    gdf_oceans = gpd.read_file(oceans_from_ne_path)

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 12
    # regions ID
    logging.info(f"Reading ids from {codes_id_path}")
    with open(codes_id_path, "rb") as f:
        result = chardet.detect(f.read())

    # from https://pandas.pydata.org/pandas-docs/stable/user_guide/io.html#na-values
    na_vals = ['-1.#IND', '1.#QNAN', '1.#IND', '-1.#QNAN', '#N/A N/A', '#N/A', 'N/A', 'n/a', 'NA', '<NA>', '#NA', 'NULL', 'null', 'NaN', '-NaN', 'nan', '-nan', 'None', '']
    # avoids errors with country code "NA":
    na_vals.remove('NA')

    codes_id = pd.read_csv(
        codes_id_path,
        encoding=result["encoding"],
        sep=None,
        engine="python",
        keep_default_na=False,
        na_values=na_vals
    )

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 14
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

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 16
    # Drop useless columns
    gdf_countries = gdf_countries.drop(columns=["ISO3_CODE", "ISO2_CODE", "ISON_CODE", "NE_ID"])

    # Merge geometries in a single one
    gdf_land = gdf_countries.dissolve()

    # Metadata
    gdf_land["NAME"] = "Land"
    gdf_land["ID"] = "L"

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 18
    # Drop useless columns
    gdf_oceans = gdf_oceans.drop(columns=["scalerank", "min_zoom", "featurecla"])

    # Merge geometries in a single one
    gdf_ocean = gdf_oceans.dissolve()

    # Metadata
    gdf_ocean["NAME"] = "Ocean"
    gdf_ocean["ID"] = "OC"
    gdf_ocean["SOURCE"] = "Natural Earth Ocean"
    gdf_ocean["NUM_ID"] = np.nan

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 20
    # Add the NUM_ID from the csv file
    lookup = codes_id.set_index("ID")["NUM_ID"]

    gdf_land["NUM_ID"] = gdf_land["ID"].map(lookup)
    gdf_land["NUM_ID"] = gdf_land["NUM_ID"].astype(str).str.strip()
    gdf_land["NUM_ID"] = pd.to_numeric(gdf_land["NUM_ID"], errors='coerce').astype('Int64')

    gdf_ocean["NUM_ID"] = gdf_ocean["ID"].map(lookup)
    gdf_ocean["NUM_ID"] = gdf_ocean["NUM_ID"].astype(str).str.strip()
    gdf_ocean["NUM_ID"] = pd.to_numeric(gdf_ocean["NUM_ID"], errors='coerce').astype('Int64')

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 22
    # Merge together the gdfs
    gdf_final = gpd.GeoDataFrame(
        pd.concat([gdf_land, gdf_ocean], ignore_index=True),
        crs="EPSG:4326"
    )

    # Original generate_shp_land_ocean_ne_10m.ipynb, cell 24
    # Save GeoDataFrame
    gdf_final.to_file(full_path)

    logging.info(f"Saved Shapefile to: {full_path}")
    return gdf_final
