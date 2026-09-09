"""Natural Earth countries: original transformations, with explicit file paths.

Migrated from generate_shp_countries_ne_10m.ipynb. Plot-only cells are omitted.
Operation order, schemas, mappings and historical behaviours are preserved.
"""

import geopandas as gpd
import logging
import pandas as pd
from shapely.geometry import box
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union
import pycountry
import chardet
from pathlib import Path

def generate_countries(ne_admin_countries_path, codes_id_path, countries_from_ne_path):
    """Generate and write the shapefile; return its GeoDataFrame.

    Inputs and output are explicit paths. No .env or working-directory changes.
    The output and its shapefile sidecars are overwritten when this is called.
    """
    Path(countries_from_ne_path).parent.mkdir(parents=True, exist_ok=True)

    # Original generate_shp_countries_ne_10m.ipynb, cell 11
    logging.info(f"Reading shapefile for NATURAL EARTH from {ne_admin_countries_path}")
    gdf_countries = gpd.read_file(ne_admin_countries_path)

    # Original generate_shp_countries_ne_10m.ipynb, cell 12
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

    # Original generate_shp_countries_ne_10m.ipynb, cell 14
    # Scheme definition of the final shape file

    schema = {
        "ID": "str:10",
        "NAME": "str:50",
        "ISO3_CODE": "str:3",
        "ISO2_CODE": "str:2",
        "ISON_CODE": "int",
        "NUM_ID": "int",
        "NE_ID": "int",
    #    "OL_NAME": "str:50",
        "SOURCE": "str:50",
        "geometry": "MultiPolygon"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 16
    # Countries
    attr_countries = [c for c in gdf_countries.columns if c != "geometry"]

    logging.info(f"Attributes in the Countries shape file are: {attr_countries}")

    # Original generate_shp_countries_ne_10m.ipynb, cell 17
    # Mapping scheme specific of Natural Earth data
    countries_columns_map = {
        'NAME_LONG': "NAME",
        'ISO_A3': "ISO3_CODE",
        'ISO_A2': "ISO2_CODE",
        'ISO_N3': "ISON_CODE",
        'NE_ID': "NE_ID"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 18
    # Mapping function

    def prepare_gdf(gdf, col_map, fixed_values=None):
        gdf = gdf.copy()

        # Keep only columns that are in the mapping (+ geometry)
        cols_to_keep = list(col_map.keys()) + ["geometry"]
        gdf = gdf[[col for col in cols_to_keep if col in gdf.columns]]

        # Rename columns
        gdf = gdf.rename(columns=col_map)

        # Create missing columns with placeholders
        for col in schema:
            if col not in gdf.columns and col != "geometry":
                gdf[col] = None

        # Apply fixed values
        if fixed_values:
            for col, val in fixed_values.items():
                gdf[col] = val

        # Keep only target columns (ORDERED by schema)
        gdf = gdf[list(schema)]

        return gdf

    # Original generate_shp_countries_ne_10m.ipynb, cell 19
    # Mapping the input gdf

    gdf_countries = prepare_gdf(
        gdf_countries,
        countries_columns_map
    )

    logging.info(f"Attributes in the modified Countries shape file are: {gdf_countries.columns}")

    # Original generate_shp_countries_ne_10m.ipynb, cell 20
    # Adding IDs to identify all the regions (even if they don't have ISO codes)

    # Build lookup from codes_id.csv
    lookup = codes_id.dropna(subset=["NE_ID"]).set_index("NE_ID")["ID"]

    # Add and fill the new column
    gdf_countries["ID"] = gdf_countries["NE_ID"].map(lookup)

    # Original generate_shp_countries_ne_10m.ipynb, cell 21
    # Change -99 values into NAN
    gdf_countries['ISO3_CODE'] = gdf_countries['ISO3_CODE'].replace({'-99': None, -99: None})
    gdf_countries['ISO2_CODE'] = gdf_countries['ISO2_CODE'].replace({'-99': None, -99: None})
    gdf_countries['ISON_CODE'] = gdf_countries['ISON_CODE'].replace({'-99': None, -99: None})

    # Original generate_shp_countries_ne_10m.ipynb, cell 24
    # Duplicate the original gdf
    gdf_countries_new = gdf_countries

    # Function to split countries
    def split_countries(gdf_cntr_original, gdf_cntr_final, cntr_name, split_box, row_attributes):
        """
        Split countries and adds a new row.

        Parameters:
            gdf_cntr_original: input original gdf with countries
            gdf_cntr_final: final gdf with countries
            cntr_name: string with big country name
            split_box: box or list of boxes that contains the areas to split
            row_attributes: list of known attributes of the country to split

        Returns:
            Updated GeoDataFrame
        """

        # Check if the target country is there or if was already processed
        if gdf_cntr_original[gdf_cntr_original["NAME"] == cntr_name].empty:
            logging.info(f"Country {cntr_name} not found, skipping")
            return None
        # elif not gdf_cntr_final[gdf_cntr_final[id] == row_attributes["ID"]].empty:
        #     logging.info(f"Country {row_attributes['ID']} already split, skipping")
        #     return None
        else:
            logging.info(f"Country {cntr_name} processing...")


            cntr = gdf_cntr_original[gdf_cntr_original["NAME"] == cntr_name]

            # Get the original country geometry
            cntr_geom = cntr.geometry.iloc[0]

            # Explode MultiPolygon into individual polygons if needed
            polygons = list(cntr_geom.geoms) if isinstance(cntr_geom, MultiPolygon) else [cntr_geom]
            polygons_gdf = gpd.GeoDataFrame(geometry=polygons, crs=gdf_cntr_original.crs)

            # Deal with both single box or list of boxes
            if not isinstance(split_box, (list, tuple)):
                split_box = [split_box]

            # Select polygons intersecting any SPLIT COUNTRY box
            split_country_parts = polygons_gdf[
                polygons_gdf.geometry.apply(
                    lambda g: any(g.intersects(b) for b in split_box)
                )
            ]

            # Merge all split parts into a single geometry
            split_country = split_country_parts.union_all()

            if split_country.is_empty:
                logging.warning(f"No geometry found for {row_attributes["NAME"]}")
                return gdf_cntr_final

            if cntr_name == row_attributes["NAME"]:
                logging.info(f"Mainland processing...")

                # Changing the geometry of the big country
                gdf_cntr_final.loc[gdf_cntr_final["NAME"] == cntr_name, "geometry"] = split_country

            else:
                logging.info(f"Splitting {row_attributes["NAME"]} from {cntr_name} ...")

                # Add the new geometry to the attributes
                row_attributes["geometry"] = split_country

                # New row definition
                new_row = gpd.GeoDataFrame(
                    [row_attributes],
                    geometry="geometry",
                    crs=gdf_countries_new.crs
                )

                # Adding the new row to the new gdf
                gdf_cntr_final = pd.concat(
                    [gdf_cntr_final, new_row],
                    ignore_index=True
                )

                if gdf_cntr_final[gdf_cntr_final["NAME"] == row_attributes["NAME"]].empty:
                    logging.info(f"Country {row_attributes["NAME"]} not found, splitting not done")
                else:
                    logging.info(f"Country {row_attributes["NAME"]} split successfully and added to the final gdf")

            return gdf_cntr_final

    # Original generate_shp_countries_ne_10m.ipynb, cell 27
    # Alaska

    # box definition
    alaska_box = [
        box(-180, 47, -127, 73),  # main Alaska
        box(171, 50, 180, 54)     # wrap-around part
    ]

    # attributes definition
    alaska_row = {
        "NAME": "Alaska (US)",
        "ISO3_CODE": "USA",
        "ID": "AK"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 28
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "United States", alaska_box, alaska_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 29
    # Hawaii

    # box definition
    hawaii_box = box(-180, 18, -154, 27)

    # attributes definition
    hawaii_row = {
        "NAME": "Hawaii (US)",
        "ISO3_CODE": "USA",
        "ID": "HI"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 30
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "United States", hawaii_box, hawaii_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 31
    # Continental US

    # box definition
    conus_box = box(-125, 24, -66.5, 50)

    # attributes definition
    conus_row = {
        "NAME": "United States",
        "ISO3_CODE": "USA",
        "ID": "US"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 32
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "United States", conus_box, conus_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 35
    # Paracel Islands

    # box definition
    paracel_box = box(110, 15, 114, 17.5)

    # attributes definition
    paracel_row = {
        "NAME": "Paracel Islands (Disputed Territory)",
        "ID": "XA"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 36
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "China", paracel_box, paracel_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 37
    # China mainland

    # box definition
    chn_box = box(70, 15, 140, 55) - paracel_box

    # attributes definition
    chn_row = {
        "NAME": "China",
        "ISO3_CODE": "CHN",
        "ID": "CN"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 38
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "China", chn_box, chn_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 41
    # French Guiana

    # box definition
    frguiana_box = box(-55, 1.5, -51, 6)

    # attributes definition
    frguiana_row = {
        "NAME": "French Guiana",
        "ISO3_CODE": "GUF",
        "ID": "GF"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 42
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", frguiana_box, frguiana_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 43
    # Guadeloupe

    # box definition
    guad_box = box(-60, 15.5, -62, 17)

    # attributes definition
    guad_row = {
        "NAME": "Guadeloupe",
        "ISO3_CODE": "GLP",
        "ID": "GP"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 44
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", guad_box, guad_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 45
    # Martinique

    # box definition
    mart_box = box(-60, 14, -62, 15)

    # attributes definition
    mart_row = {
        "NAME": "Martinique",
        "ISO3_CODE": "MTQ",
        "ID": "MQ"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 46
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", mart_box, mart_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 47
    # Saint Martin

    # box definition
    shn_box = box(-63.3, 18, -62.8, 18.2)

    # attributes definition
    shn_row = {
        "NAME": "Saint Martin",
        "ISO3_CODE": "MAF",
        "ID": "MF"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 48
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", shn_box, shn_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 49
    # Mayotte

    # box definition
    mayotte_box = box(44, -13.5, 45.5, -12.5)

    # attributes definition
    mayotte_row = {
        "NAME": "Mayotte",
        "ISO3_CODE": "MYT",
        "ID": "YT"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 50
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", mayotte_box, mayotte_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 51
    # Réunion

    # box definition
    reunion_box = box(54, -22, 56, -20)

    # attributes definition
    reunion_row = {
        "NAME": "Réunion",
        "ISO3_CODE": "REU",
        "ID": "RE"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 52
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", reunion_box, reunion_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 53
    # France (Europe)

    # box definition
    france_box = box(-70, -25, 70, 70) - frguiana_box - reunion_box - mayotte_box - guad_box - mart_box - shn_box

    # attributes definition
    france_row = {
        "NAME": "France",
        "ISO3_CODE": "FRA",
        "ID": "FR"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 54
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "France", france_box, france_row)

    gdf_countries_new.loc[gdf_countries_new['NAME'] == 'France', 'ISO3_CODE'] = 'FRA'

    # Original generate_shp_countries_ne_10m.ipynb, cell 57
    # Christmas Island

    # box definition
    chris_box = box(105, -11, 106, -10)

    # attributes definition
    chris_row = {
        "NAME": "Christmas Island",
        "ISO3_CODE": "CXR",
        "ISO2_CODE": "CX",
        "ID": "CX"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 58
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "Indian Ocean Territories", chris_box, chris_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 59
    # Cocos Keeling Island

    # box definition
    cocos_box = box(96, -13, 98, -11)

    # attributes definition
    cocos_row = {
        "NAME": "Cocos (Keeling) Islands",
        "ISO3_CODE": "CCK",
        "ISO2_CODE": "CC",
        "ID": "CC"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 60
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "Indian Ocean Territories", cocos_box, cocos_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 61
    # the original geometry is now fully contained into the two split ones, so we can drop the original row
    gdf_countries_new = gdf_countries_new.drop(gdf_countries_new[gdf_countries_new['NAME'] == 'Indian Ocean Territories'].index)

    # Original generate_shp_countries_ne_10m.ipynb, cell 64
    # Svalbard and Jan Mayen

    # box definition
    sjm_box = [
        box(9, 73, 34, 82),
        box(-10, 70, -7, 72)
    ]
    # attributes definition
    sjm_row = {
        "NAME": "Svalbard and Jan Mayen",
        "ISO3_CODE": "SJM",
        "ID": "SJ"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 65
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "Norway", sjm_box, sjm_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 66
    # Bouvet Island

    # box definition
    bou_box = box(0, -56, 5, -53)

    # attributes definition
    bou_row = {
        "NAME": "Bouvet Island",
        "ISO3_CODE": "BVT",
        "ID": "BV"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 67
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "Norway", bou_box, bou_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 68
    # Norway mainland

    # box definition
    nor_box = box(3, 57, 32, 72)

    # attributes definition
    nor_row = {
        "NAME": "Norway",
        "ID": "NO"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 69
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "Norway", nor_box, nor_row)

    gdf_countries_new.loc[gdf_countries_new['NAME'] == 'Norway', 'ISO3_CODE'] = 'NOR'

    # Original generate_shp_countries_ne_10m.ipynb, cell 72
    # Tokelau

    # box definition
    tkl_box = box(-174, -10, -170, -8)

    # attributes definition
    tkl_row = {
        "NAME": "Tokelau",
        "ISO3_CODE": "TKL",
        "ID": "TK"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 73
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "New Zealand", tkl_box, tkl_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 74
    # New Zealand

    # box definition
    nzl_box = box(-180, -90, 180, 90) - tkl_box

    # attributes definition
    nzl_row = {
        "NAME": "New Zealand",
        "ISO3_CODE": "NZL",
        "ID": "NZ"
    }

    # Original generate_shp_countries_ne_10m.ipynb, cell 75
    gdf_countries_new = split_countries(gdf_countries, gdf_countries_new, "New Zealand", nzl_box, nzl_row)

    # Original generate_shp_countries_ne_10m.ipynb, cell 77
    logging.info("Countries splitting processed finished")

    # Original generate_shp_countries_ne_10m.ipynb, cell 79
    # merging function

    def merge_countries(gdf, filter_col, filter_values, base_row_value=None, override_attributes={}):
        """
        Merges countries of selected rows, drops them, and adds a new merged row.

        Parameters:
            gdf: GeoDataFrame
            filter_col: column name to filter on (str)
            filter_values: list of values to merge
            base_row_value: value in filter_col to copy attributes from (uses first row if None)
            override_attributes: dict of attributes to override on top of the base row
        """
        rows_to_merge = gdf[gdf[filter_col].isin(filter_values)]
        merged_geometry = unary_union(rows_to_merge.geometry)

        # Pick base row for attributes
        if base_row_value:
            base_row = rows_to_merge[rows_to_merge[filter_col] == base_row_value].iloc[0]
        else:
            base_row = rows_to_merge.iloc[0]  # default to first row

        # Build new row: start from base, override what you want
        new_row = base_row.to_dict()
        new_row['geometry'] = merged_geometry
        new_row.update(override_attributes)

        gdf = gdf.drop(rows_to_merge.index)
        new_gdf = gpd.GeoDataFrame([new_row], crs=gdf.crs)
        gdf = gpd.GeoDataFrame(pd.concat([gdf, new_gdf], ignore_index=True), crs=gdf.crs)

        return gdf

    # Original generate_shp_countries_ne_10m.ipynb, cell 81
    gdf_countries_new = merge_countries(gdf_countries_new, 'NAME', ['Australia', 'Coral Sea Islands', 'Ashmore and Cartier Islands'],
                     base_row_value='Australia',
                     override_attributes={'NAME': 'Australia'})

    # Original generate_shp_countries_ne_10m.ipynb, cell 84
    gdf_countries_new = merge_countries(gdf_countries_new, 'NAME', ['Akrotiri', 'Dhekelia'],
                     override_attributes={'NAME': 'Cyprus U.K. Bases', 'ID': 'EWSB'})

    # Original generate_shp_countries_ne_10m.ipynb, cell 89
    # All the countries are sourced from Natural Earth
    gdf_countries_new["SOURCE"] = "Natural Earth Admin0 10m"

    # Original generate_shp_countries_ne_10m.ipynb, cell 90
    # Functions to assign other ISO codes from: Countries (ISO 3166-1)
    def iso3_to_iso2(code):
        if not isinstance(code, str) or not code:  # handle None/NaN
            return None
        country = pycountry.countries.get(alpha_3=code)
        return country.alpha_2 if country else None

    def iso3_to_num(code):
        if not isinstance(code, str) or not code:  # handle None/NaN
            return None
        country = pycountry.countries.get(alpha_3=code)
        return country.numeric if country else None

    # Assign codes
    gdf_countries_new["ISO2_CODE"] = gdf_countries_new["ISO3_CODE"].apply(iso3_to_iso2)
    gdf_countries_new["ISON_CODE"] = gdf_countries_new["ISO3_CODE"].apply(iso3_to_num)

    # Original generate_shp_countries_ne_10m.ipynb, cell 91
    # Add the NUM_ID from the csv file
    lookup = codes_id.set_index("ID")["NUM_ID"]
    gdf_countries_new["NUM_ID"] = gdf_countries_new["ID"].map(lookup)
    gdf_countries_new["NUM_ID"] = gdf_countries_new["NUM_ID"].astype(str).str.strip()
    gdf_countries_new["NUM_ID"] = pd.to_numeric(gdf_countries_new["NUM_ID"], errors='coerce').astype('Int64')

    # Original generate_shp_countries_ne_10m.ipynb, cell 94
    # Save GeoDataFrame
    gdf_countries_new.to_file(countries_from_ne_path)

    logging.info(f"Saved Shapefile to: {countries_from_ne_path}")
    return gdf_countries_new
