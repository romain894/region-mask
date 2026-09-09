"""Natural Earth oceans: original transformations, with explicit file paths.

Migrated from generate_shp_oceans_ne_10m.ipynb. Plot-only cells are omitted.
Operation order, schemas, mappings and historical behaviours are preserved.
"""

import geopandas as gpd
import pandas as pd
from shapely.geometry import box
import shapely
import logging
from pathlib import Path
import chardet

def generate_oceans(ne_geo_marine_polys_path, ne_geo_ocean_path, codes_id_path, oceans_from_ne_path):
    """Generate and write the shapefile; return its GeoDataFrame.

    Inputs and output are explicit paths. No .env or working-directory changes.
    The output and its shapefile sidecars are overwritten when this is called.
    """
    Path(oceans_from_ne_path).parent.mkdir(parents=True, exist_ok=True)

    # Original generate_shp_oceans_ne_10m.ipynb, cell 11
    logging.info(f"Reading shapefile for geo marine polygons from {ne_geo_marine_polys_path}")
    gdf_marine = gpd.read_file(ne_geo_marine_polys_path)
    gdf_marine['name'] = gdf_marine['name'].fillna(gdf_marine['note'])

    logging.info(f"Reading shapefile for geo ocean from {ne_geo_ocean_path}")
    gdf_ocean = gpd.read_file(ne_geo_ocean_path)

    # Original generate_shp_oceans_ne_10m.ipynb, cell 12
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

    # Original generate_shp_oceans_ne_10m.ipynb, cell 14
    # Check if all the Reference Systems are the same
    logging.info(f"Marine polys reference system: {gdf_marine.crs}")
    logging.info(f"Ocean reference system: {gdf_ocean.crs}")

    if gdf_marine.crs == gdf_ocean.crs:
        logging.info("Reference system aligned")
    else:
        raise ValueError("Reference system not aligned")

    # Original generate_shp_oceans_ne_10m.ipynb, cell 16
    raw_ocean_sea_mapping = {
        "Southern Ocean": [
            "SOUTHERN OCEAN", "Ross Sea", "Weddell Sea", "Amundsen Sea",
            "Bellingshausen Sea", "Scotia Sea", "Drake Passage", "Prydz Bay",
            "McMurdo Sound", "Marguerite Bay", "Vincennes Bay", "Davis Sea",
            "Porpoise Bay", "Lützow-Holm Bay", "Sulzberger Bay", "Ronne Entrance",
            "Bransfield Strait", "Wrigley Gulf", "Peacock Sound", "George VI Sound"
        ],
        "Southern Atlantic Ocean": [
            "South Atlantic Ocean", "Canal do Sul", "St. Helena Bay", "Lagoa dos Patos",
            "Río de la Plata", "Golfo San Matías", "Golfo San Jorge", "Bahía Blanca",
            "Bahía Grande", "Baía de Marajó", "Baía de São Marcos", "Amazon River",
        ],
        "South Pacific Ocean": [
            "South Pacific Ocean", "Tasman Sea", "Coral Sea", "Great Barrier Reef",
            "Solomon Sea", "Bismarck Sea", "Gulf of Papua", "Golfo Corcovado",
            "Bass Strait", "Cook Strait", "Torres Strait", "Bay Inútil", "Golfo de Penas",
            "Bay of Plenty", "Golfo de Guayaquil", "Estrecho de Magellanes",
            "Seno de Skyring",  "Seno Otway"
        ],
        "North Pacific Ocean": [
            "North Pacific Ocean", "Philippine Sea", "Sea of Okhotsk", "Bering Sea",
            "Gulf of Alaska", "Sea of Japan", "Yellow Sea", "Bo Hai", "East China Sea",
            "Korea Strait", "Golfo de California", "San Francisco Bay", "Davao Gulf",
            "Monterey Bay", "Cook Inlet", "Bristol Bay", "Norton Sound",  "Ragay Gulf",
            "Prince William Sound", "Shelikhova Gulf", "Tatar Strait", "Tsugaru Strait",
            "La Pérouse Strait", "East Korea Bay", "Gulf of Anadyr'", "Queen Charlotte Sound",
            "Inner Sea", "Golfo de Panamá", "Dixon Entrance", "Kronotskiy Gulf", "Uda Bay",
            "Uchiura Bay", "Golfo de Tehuantepec", "Hangzhou Bay", "Karaginskiy Gulf",
            "Gulf of Kamchatka", "Gulf of Sakhalin", "Internal Canada (B.C.) Waters",
            "Internal U.S. (Alaska) Waters", "Queen Charlotte Strait", "Hecate Strait",
            "Cordova Bay", "Yangtze River", "Columbia River", "Salish Sea", "Bohol Sea",
            "Internal Philippines Waters", "Leyte Gulf", "Surigao Strait", "Samar Sea",
            "Sibuyan Sea", "Tayabas Bay", "Baird Inlet", "Visayan Sea"
        ],
        "South China and Easter Archipelagic Seas": [
            "South China Sea", "Java Sea", "Celebes Sea", "Sulu Sea", "Banda Sea",
            "Flores Sea", "Molucca Sea", "Ceram Sea", "Makassar Strait", "Strait of Malacca",
            "Strait of Singapore", "Gulf of Thailand", "Gulf of Tonkin", "Luzon Strait",
            "Bali Sea", "Halmahera Sea", "Selat Bali", "Gulf of Tomini", "Gulf of Kau",
            "Savu Sea", "Qiongzhou Strait", "Selat Dampier", "Gulf of Buli",
            "Taiwan Strait"
        ],
        "Indian Ocean": [
            "INDIAN OCEAN", "Arabian Sea", "Red Sea", "Gulf of Aden", "Persian Gulf",
            "Gulf of Oman", "Bay of Bengal", "Andaman Sea", "Laccadive Sea",
            "Mozambique Channel", "Gulf of Mannar", "Palk Strait", "Gulf of Khambhät",
            "Gulf of Kutch", "Gulf of Masira", "Gulf of Martaban", "Bab el Mandeb",
            "Antongila Bay", "Baia de Maputo", "Gulf of Suez", "Gulf of Aqaba",
            "Shark Bay", "Geographe Bay", "Great Australian Bight", "Gulf St. Vincent",
            "Timor Sea", "Joseph Bonaparte Gulf", "Arafura Sea", "Gulf of Carpentaria",
        ],
        "Mediterranean Region": [
            "Mediterranean Sea", "Tyrrhenian Sea", "Adriatic Sea", "Ionian Sea",
            "Aegean Sea", "Sea of Crete", "Alboran Sea", "Balearic Sea", "Ligurian Sea",
            "Strait of Gibraltar", "Black Sea", "Sea of Azov", "Sea of Marmara",
            "Bosporus", "Dardanelles", "Gulf of Gabès", "Gulf of Sidra", "Golfe du Lion"
        ],
        "Baltic Sea": [
            "Baltic Sea", "Gulf of Bothnia", "Gulf of Finland", "Gulf of Riga", "Kattegat",
            "Øresund", "Mecklenburger Bucht", "Stettiner Haff", "Kaliningrad",
            "Internal Denmark Waters"
        ],
        "North Atlantic Ocean": [
            "North Atlantic Ocean", "Labrador Sea", "Gulf of Saint Lawrence",
            "Bay of Fundy", "Gulf of Maine", "Chesapeake Bay", "Gulf of Mexico",
            "Caribbean Sea", "Sargasso Sea", "North Sea", "English Channel",
            "Bay of Biscay", "Irish Sea", "Denmark Strait", "Bras d'Or Lake",
            "Skagerrak", "Strait of Belle Isle", "Massachusetts Bay", "Delaware Bay",
            "Long Island Sound", "Bristol Channel", "Inner Seas", "Bahía de Campeche",
            "Gulf of Honduras", "Straits of Florida", "Bight of Biafra",
            "Yucatan Channel", "Boca Grande", "Bight of Benin", "Canal do Norte",
            "Hamilton Inlet", "Waddenzee", "Golfo de Urabá", "Gulf of Guinea",
            "Boknafjorden", "Saint Lawrence River", "Lago de Maracaibo",
            "Albemarle Sound", "Pamlico Sound", "Lake Pontchartrain",
            "Internal Brazil Amazon River Waters", "Canal Perigoso"
        ],
        "Arctic Ocean": [
            "Arctic Ocean", "Beaufort Sea", "Chukchi Sea", "East Siberian Sea",
            "Laptev Sea", "Kara Sea", "Barents Sea", "White Sea", "Greenland Sea",
            "Lincoln Sea", "Amundsen Gulf", "Viscount Melville Sound", "Sognefjorden",
            "The North Western Passages", "Kane Basin", "Smith Sound", "Hall Basin",
            "Kennedy Channel", "Robeson Channel", "Gulf of Ob", "Yenisey Gulf",
            "Khatanga Gulf", "Franklin Bay", "M'Clure Strait", "Storfjorden", "Wager Bay",
            "Karskiye Strait", "Vil'kitskogo Strait", "Mackenzie Bay", "Gulf of Boothia",
            "Gulf of Yana", "Dmitriy Laptev Strait", "Gulf of Olen‘k", "Kangertittivaq",
            "Chaun Bay", "Husky Lakes", "Darnley Bay", "Internal Canada Arctic Waters",
            "Prince of Wales Strait", "Minto Inlet", "Richard Collinson Inlet",
            "Prince ALbert Sound", "Liddon Gulf", "Wynniatt Bay", "Hadley Bay",
            "Bathurst Inlet", "Goldsmith Channel", "Sherman Basin", "Fury and Hecla Strait",
            "Jones Sound", "Matochkin Shar Strait", "Ozero Mogotoyevo", "Guba Gusinaya",
            "Murchison Sound", "Kotzebue Sound", "Hudson Strait", "Ungava Bay",
            "Cumberland Sound", "Foxe Basin", "Hudson Bay", "James Bay", "Baffin Bay",
            "Melville Bay", "Uummannaq Fjord", "Disko Bay", "Davis Strait", "Norwegian Sea",
            "Vestfjorden", "Trondheimsfjorden", "Frobisher Bay", "Eclipse Sound"
        ],
        "Caspian Sea": [
            "Caspian Sea", "Garabogaz Bay"
        ]
    }

    # Original generate_shp_oceans_ne_10m.ipynb, cell 18
    ## Map parent region
    # Flatten and Lowercase the map for lookups
    ocean_sea_mapping = {item.lower(): category for category, items in raw_ocean_sea_mapping.items() for item in items}

    # Apply to GeoDataFrame
    gdf_marine['parent_reg'] = gdf_marine['name'].str.lower().map(ocean_sea_mapping)
    # Handle missing values
    gdf_marine['parent_reg'] = gdf_marine['parent_reg'].fillna('Other')


    ## Cut the Indian Ocean polygon that overflow into the Pacific Ocean
    # Define the cut line (146.9167°E)
    cut_lon = 146.9167
    # Get the Indian Ocean row
    indian_ocean = gdf_marine[gdf_marine['name'] == 'INDIAN OCEAN'].copy()
    if not indian_ocean.empty:
        idx = indian_ocean.index[0]
        polygon = indian_ocean['geometry'].iloc[0]
        # Create a rectangle covering the eastern part (east of 146.9167°E)
        miny, maxy = polygon.bounds[1], polygon.bounds[3]
        eastern_rect = box(cut_lon, miny, polygon.bounds[2], maxy)
        # Split the polygon using the rectangle
        western_part = polygon.difference(eastern_rect)
        eastern_part = polygon.intersection(eastern_rect)
        # Update the GeoDataFrame: keep western part as Indian Ocean
        gdf_marine.at[idx, 'geometry'] = western_part
        # Add the eastern part as a new row (South Pacific Ocean)
        if not eastern_part.is_empty:
            new_row = indian_ocean.copy()
            new_row['geometry'] = eastern_part
            new_row['parent_reg'] = "South Pacific Ocean"
            new_row['name'] = 'SOUTH PACIFIC OCEAN (EAST)'
            gdf_marine = pd.concat([gdf_marine, new_row], ignore_index=True)
    logging.info(f"Parent regions not mapped: {gdf_marine[gdf_marine["parent_reg"] == "Other"]["name"].to_list()}")


    ## Improve accuracy of marine polygons by using the more precise ocean shape
    logging.info("Intersecting: Securing the main bodies of water...")
    gdf_ocean = gdf_ocean.drop(columns=['featurecla', 'scalerank'])

    # We keep the intersection exactly as it was
    main_water = gpd.overlay(gdf_ocean, gdf_marine, how='intersection', keep_geom_type=True)
    logging.info("Difference: Isolating the missing coastal gaps flawlessly...")

    # Melt all marine polygons into a single giant shape first
    marine_union = gdf_marine.union_all()

    # Subtract that giant shape from the ocean. This guarantees NO water is deleted.
    gaps_geom = gdf_ocean.geometry.difference(marine_union)
    gaps = gpd.GeoDataFrame(geometry=gaps_geom, crs=gdf_ocean.crs)
    logging.info("Exploding gaps and cleaning up...")
    gaps_exploded = gaps.explode(index_parts=False)

    # Keep only valid polygons (drops weird lines/points that cause crashes)
    gaps_exploded = gaps_exploded[gaps_exploded.geom_type.isin(['Polygon', 'MultiPolygon'])]

    # Give every individual gap a unique index so they don't overwrite each other!
    gaps_exploded = gaps_exploded.reset_index(drop=True)

    logging.info("Nearest Neighbor: Snapping gaps to their rightful seas...")

    # TTemporarily convert to Web Mercator (meters) for accurate math
    gaps_proj = gaps_exploded.to_crs(epsg=3857)
    marine_proj = gdf_marine.to_crs(epsg=3857)

    # Find the nearest sea in metric distance
    gaps_assigned_proj = gpd.sjoin_nearest(gaps_proj, marine_proj, how='left')
    # Drop duplicate gap assignments so each gap only belongs to ONE marine region
    gaps_assigned_proj = gaps_assigned_proj[~gaps_assigned_proj.index.duplicated(keep='first')]

    gaps_assigned = gaps_exploded.copy()
    gaps_assigned['parent_reg'] = gaps_assigned_proj['parent_reg']

    logging.info("Merging and Dissolving...")

    # Use .copy() to prevent SettingWithCopyWarnings
    main_clean = main_water.copy()
    gaps_clean = gaps_assigned.copy()

    # Stack them together
    combined = pd.concat([main_clean, gaps_clean], ignore_index=True)

    # Fill the NULLs with a placeholder so .dissolve() doesn't delete them.
    combined['parent_reg'] = combined['parent_reg'].fillna("Unassigned Marine Area")

    # Dissolve into the final separated oceans
    final_oceans = combined.dissolve(by='parent_reg', as_index=False)[['parent_reg', 'geometry']]
    final_oceans = final_oceans.to_crs(gdf_ocean.crs)

    # Original generate_shp_oceans_ne_10m.ipynb, cell 20
    # Scheme definition of the final shape file

    schema = {
        "ID": "str:10",
        "NAME": "str:50",
        "ISO3_CODE": "str:3",
        "ISO2_CODE": "str:2",
        "ISON_CODE": "int",
        "NUM_ID": "int",
        "OL_NAME": "str:50",
        "SOURCE": "str:50",
        "geometry": "MultiPolygon"
    }

    # Original generate_shp_oceans_ne_10m.ipynb, cell 21
    oceans_columns_map = {
        'parent_reg': "NAME",
        'ne_id': "NE_ID"
    }

    # Original generate_shp_oceans_ne_10m.ipynb, cell 22
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

    # Original generate_shp_oceans_ne_10m.ipynb, cell 23
    final_oceans = prepare_gdf(
        final_oceans,
        oceans_columns_map
    )

    logging.info(f"Attributes in the modified Oceans shape file are: {final_oceans.columns}")

    # Original generate_shp_oceans_ne_10m.ipynb, cell 24
    # Retrieve the Oceans ID
    final_oceans["ID"] = final_oceans["NAME"].apply(
        lambda s: "OC_" + "".join(w[0].upper() for w in s.split())
    )
    # Change South China and Easter Archipelagic Seas ID
    final_oceans["ID"] = final_oceans["ID"].replace(
        "OC_SCAEAS",
        "OC_SCS"
    )

    # Original generate_shp_oceans_ne_10m.ipynb, cell 25
    # Add source
    final_oceans["SOURCE"] = "Natural Earth Oceans 10m"

    # Original generate_shp_oceans_ne_10m.ipynb, cell 26
    # Add the NUM_ID from the csv file
    lookup = codes_id.set_index("ID")["NUM_ID"]
    final_oceans["NUM_ID"] = final_oceans["ID"].map(lookup)
    final_oceans["NUM_ID"] = final_oceans["NUM_ID"].astype(str).str.strip()
    final_oceans["NUM_ID"] = pd.to_numeric(final_oceans["NUM_ID"], errors='coerce').astype('Int64')

    # Original generate_shp_oceans_ne_10m.ipynb, cell 28
    # Save GeoDataFrame
    logging.info(f"Saving the ocean shape file to {oceans_from_ne_path}...")
    final_oceans.to_file(oceans_from_ne_path)
    logging.info("Done!")
    return final_oceans
