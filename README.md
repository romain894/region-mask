# Region Mask: 3D Fractional Region Mask for Aggregating Global Gridded Data

This repository generates a **3D fractional region mask** to aggregate global gridded datasets (e.g., climate, 
hydrological, or environmental data) at a regional scale.

The mask stores, for each region and each grid cell, the **fraction of the cell area covered by the region**.  
This enables consistent and weighted regional aggregation of gridded data.

  - Output format: NetCDF  
  - Dimensions: (region, lat, lon)  
  - Values range: 0 to 1

### Credits

**Cite:** Thomas, R., & Cigna, G. (2026). Region Mask: 3D Fractional Region Mask for Aggregating Global Gridded Data.

GitHub repository: https://github.com/romain894/region-mask  
Zenodo repository URL:   
Repository DOI:   

Romain THOMAS - romain.thomas@polito.it  
Giulia CIGNA - giulia.cigna@polito.it  
DIATI - Politecnico di Torino


### Related Works

  - Elena De Petrillo, Simon Felix Fahrländer, Marta Tuninetti, Lauren Seaby Andersen, Luca Monaco, Luca Ridolfi, and 
Francesco Laio (2025). Country-ocean-moisture-flows-reconciled-with-ERA5-reanalysis obtained processing Lagrangian 
moisture connections


### Datasets and Licenses

The repository contains the following codes and datasets which are licensed as follows:

#### Code (Python):

Notebooks in the repository are licensed under: **GPLv3** - GNU General Public License, version 3

The full license text is provided in the `LICENSE-code.txt` file.

#### Shapefiles and Masks:

  - Shapefiles in the `/data` folder of this repository: public domain (**CC0 1.0 Universal**)
  - Region Mask: 3D Fractional Region Mask (based on Natural Earth data) © 2026 by Romain Thomas, Giulia Cigna is licensed under CC BY 4.0 (`/data/mask_countries_oceans_ne_-0.25_90.25_0.5.nc`)

*To use the masks based on the Eurostat, GOaS and SeaVox datasets or the World Bank dataset, you must comply with their respective
licenses (folders `/eurostat_goas_seavox_mask` and `world_bank_mask`) and © 2026 by Romain Thomas, Giulia Cigna is licensed under CC BY 4.0*


## Methodological Framework

The workflow consists of two main stages:

### 1. Geometry Harmonization

1.1. Admin 0 - Countries

Notebook: `generate_shp_countries_ne_10m.ipynb`

- Split countries with extra-territories (e.g., overseas or geographically detached regions)
- Standardize metadata and identifiers

Output: `data/countries_from_ne_10m`


1.2. Oceans

Notebook: `generate_shp_oceans_ne_10m.ipynb`

- Merge marine regions into oceans
- Standardize metadata and identifiers

Output: `data/ocean_from_ne_10m`


1.3. Complete shapefile (no empty spaces)

Notebook: `merge_shp_ne_10m.ipynb`

- Merge countries with oceans
- Ensure consistent CRS (EPSG:4326)

Output: `data/ne_10m_oceans_countries`

### 2. Fractional Mask Generation

Notebook: `generate_mask.ipynb`

  - Align the geometries from the shape file on the desired mask bounds (split and shift along a meridian)
  - Compute the fractional coverage of each geometry for each cell of the mask:
      1. Create a Dask process for each geometry
      2. Leveraging GDAL: get cells with fractional value of 0 or 1
      3. For the other cells (0 < value < 1), calculate the fractional value
  - Normalize the mask (if `NORMALIZE_MASK` set to `true`): ensure the sum of the fractional values at each location is 1 (minor artifacts can arise from shape files miss-alignments (e.g., in estuaries)); 
    this should be used only if the shapefile is complete (countries + oceans, no empty spaces)

Output: `data/mask_countries_oceans_-0.25_90.25_0.5.nc`

Mask of Italy:  
![Plot of the mask for Italy](https://raw.githubusercontent.com/romain894/region-mask/main/single_region_plot.png)

Sum of the regions before normalisation:  
![Plot of the sum of the regions before normalisation](https://raw.githubusercontent.com/romain894/region-mask/main/sum_of_regions.png)


## Inputs

By default, we use **Natural Earth** - Free vector and raster map data @ https://naturalearthdata.com:
  - `data/ne_10m/ne_10m_geography_marine_polys/ne_10m_geography_marine_polys.shp`
  - `data/ne_10m/ne_10m_ocean/ne_10m_ocean.shp`
  - `data/ne_10m/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp`

For the mask based on the Eurostat, GOaS and SeaVox datasets, please see the directory `eurostat_goas_seavox_mask` to 
generate the shapefile and update the paths in the main `.env` file to generate the mask.

For the mask based on the World Bank dataset, please see the directory `world_bank_mask` to generate the shapefile and 
update the paths in the main `.env` file to generate the mask.

## Configuration

To set the variables and paths, copy the file `.env.template` and name it `.env`.

You can then set the environment variables in the `.env` file following the instructions in the comments.


## Mask Structure

Dimensions: (`region`, `lat`, `lon`)

Coordinates:
  - `region`: Region IDs from the shapefile
  - `lat`: Latitude coordinates
  - `lon`: Longitude coordinates

Variable:
  - `mask` (`region`, `lat`, `lon`): Fractional coverage [0–1]

Attributes:
  - `transform`: Affine transform for grid mapping
  - `crs`: Coordinate Reference System (e.g., EPSG code)
  - `resolution`: Grid resolution
  - `description`: "Fractional coverage of regions (0.0 to 1.0)"
  - `metadata`: JSON of region attributes (excluding geometry)


## Setup and installation

Create the virtual environment:

```bash
python3 -m venv .venv
```
    
Activate virtual environment:

```bash
source .venv/bin/activate
```
    
Install dependencies:

```bash
pip install -r requirements.txt
```

Launch Jupyter Lab:

```bash
jupyter lab
```
