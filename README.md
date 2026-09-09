![From geometries to fractional mask: example with Italy](https://raw.githubusercontent.com/romain894/region-mask/main/intro_plot.png)

# Region Mask: 3D Fractional Region Mask for Aggregating Global Gridded Data


[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19007672.svg)](https://doi.org/10.5281/zenodo.19007672)

This repository generates a **3D fractional region mask** to aggregate global gridded datasets (e.g., climate, 
hydrological, or environmental data) at a regional scale.

The mask stores, for each region and each grid cell, the **fraction of the cell area covered by the region**.  
This enables consistent and weighted regional aggregation of gridded data.

  - Output format: NetCDF  
  - Dimensions: (region, lat, lon)  
  - Values range: 0 to 1

### Credits

**Cite:** Thomas, R., & Cigna, G. & De Petrillo, E. (2026). *3D Fractional Region Mask for Aggregating Global Gridded Data.* Zenodo. https://doi.org/10.5281/zenodo.19007672

GitHub repository: https://github.com/romain894/region-mask  
Zenodo repository URL: https://zenodo.org/records/19007672  
Repository DOI: https://doi.org/10.5281/zenodo.19007672  

Romain Thomas - romain.thomas@polito.it  
Giulia Cigna - giulia.cigna@polito.it  
Elena De Petrillo - elena.depetrillo@polito.it  
Department of Environment, Land and Infrastructure Engineering, Politecnico di Torino, Turin, Italy


### Related Works

  - De Petrillo, E., Fahrländer, S. F., Tuninetti, M., Andersen, L. S., Monaco, L., Ridolfi, L., & Laio, F. (2025). 
*Country-ocean-moisture-flows-reconciled-with-ERA5-reanalysis obtained processing Lagrangian moisture connections.*
Zenodo. https://doi.org/10.5281/zenodo.10400694


### Datasets and Licenses

The repository contains the following codes and datasets which are licensed as follows:

#### Code (Python):

Python modules and notebooks in the repository are licensed under: **GPLv3** - GNU General Public License, version 3

The full license text is provided in the `LICENSE-code.txt` file.

#### Masks and Shapefiles in `/data` (Natural Earth)

The datasets based on Natural Earth are in the `/data` folder at the root of this repository and licensed as follows:

  - Shapefiles: *public domain (**CC0 1.0 Universal**)*
  - Masks: *Region Mask: 3D Fractional Region Mask © 2026 by Romain Thomas, Giulia Cigna, Elena De Petrillo **CC BY 4.0***

#### Masks and Shapefiles in `/eurostat_goas_seavox_mask/data` and `/world_bank_mask/data`

To use the masks based on the Eurostat, GOaS and SeaVox datasets or the World Bank dataset, you must comply with their respective
licenses (folders `/eurostat_goas_seavox_mask` and `world_bank_mask`) and *Region Mask: 3D Fractional Region Mask 
© 2026 by Romain Thomas, Giulia Cigna, Elena De Petrillo CC BY 4.0*


## Methodological Framework

The workflow consists of two main stages:

### 1. Geometry Harmonization

1.1. Admin 0 - Countries

Marimo notebook: `notebooks/countries.py`; implementation: `region_mask/countries.py`.

- Split countries with extra-territories (e.g., overseas or geographically detached regions)
  - List of changes from original [Natural Earth 10m - Admin 0](/data/ne_10m/ne_10m_admin_0_countries)
    
    Overseas French territories detached from France (French Guiana, Guadalupe, Martinique, Saint Martin, Mayotte and Reunion);
  
    Paracel Islands detached from China;
    
    Hawaii and Alaska detached from the United States of America;

    Indian Ocean Territories split into Christmas Island and Cocos Keeling Island;

    Svalbard and Jan Mayen and Bouvet Island detached from Norway;

    Tokelau detached from New Zealand;

    Coral Sea Islands and Ashmore and Cartier Islands merged into Australia;

    Akrotiri and Dhekelia merged into Cyprus U.K. Bases;


- Standardize metadata and identifiers

  - Note: The ISO alpha2 code of Namibia is 'NA', which is read as a NaN value by default. 
This was solved by removing the 'NA' string from the [default recognized NaN values](https://pandas.pydata.org/pandas-docs/stable/user_guide/io.html#na-values).

Output: `data/countries_from_ne_10m`


1.2. Oceans

Marimo notebook: `notebooks/oceans.py`; implementation: `region_mask/oceans.py`.

- Merge marine regions into oceans
- Standardize metadata and identifiers

Output: `data/ocean_from_ne_10m`


1.3. Complete shapefile (no empty spaces)

Marimo notebook: `notebooks/countries_oceans.py`; implementation: `region_mask/merge.py`.

- Merge countries with oceans
- Ensure consistent CRS (EPSG:4326)

Output: `data/ne_10m_oceans_countries`


1.4. Only land and ocean

Alternatively, if the target is only the land and ocean division use
Marimo notebook: `notebooks/land_ocean.py`; implementation: `region_mask/land_ocean.py`.

- Flatten countries into a single land entity
- Merge land .shp with ocean .shp
- Ensure consistent CRS (EPSG:4326)

Output: `data/ne_10m_land_ocean`

### 2. Fractional Mask Generation

Marimo notebook: `notebooks/mask.py`; implementation: `region_mask/mask.py`.

  - Align the geometries from the shape file on the desired mask bounds (split and shift along a meridian)
  - Compute the fractional coverage of each geometry for each cell of the mask:
      1. Create a Dask process for each geometry
      2. Leveraging GDAL: get cells with fractional value of 0 or 1
      3. For the other cells (0 < value < 1), calculate the fractional value
  - Normalize the mask (if `NORMALIZE_MASK` set to `true`): ensure the sum of the fractional values at each location is 1 (minor artifacts can arise from shape files miss-alignments (e.g., in estuaries)); 
    this should be used only if the shapefile is complete (countries + oceans, no empty spaces)

Output: `data/mask_countries_oceans_-0.25_90.25_0.5.nc`

### Illustrations

The following plots come from the mask generated with the Natural Earth shapefiles.

Mask of Italy:  
![Plot of the mask for Italy](https://raw.githubusercontent.com/romain894/region-mask/main/single_region_plot.png)

Sum of the regions before normalization:  
![Plot of the sum of the regions before normalization: ](https://raw.githubusercontent.com/romain894/region-mask/main/sum_of_regions.png)

Distribution of the summed regional values before normalization:
![Plot of the distribution of the summed regional values before normalization](https://raw.githubusercontent.com/romain894/region-mask/main/sum_distribution.png)

This distribution can be related to minor numerical computation errors and misalignment of the shape files. 
The cells with a value of 0.5 are the top cells as there are no geometries in the 90 - 90.25 latitude. 
The 90.25 value is linked to the bounds of the RECON dataset, linked to the bounds of UTrack (and thus ERA5).

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

### Python modules and marimo notebooks

Use Python 3.12 or later. The distribution is named `region-mask`; import it as
`region_mask` (distinct from the separate `regionmask` project). From a checkout:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install .                 # Python API and command line
.venv/bin/python -m pip install '.[notebooks]'     # Also install marimo
.venv/bin/python -m pip install -e '.[dev]'        # Editable development + all tooling
```

`pyproject.toml` defines runtime dependencies and the `notebooks`, `docs`, `legacy`,
and `dev` extras. A built wheel can be installed without a checkout. Datasets and
the Git-based regression suite are intentionally not bundled. These instructions
do not assume that this project is published on PyPI.

**Working in a cloned repository:** the notebooks already exist, so no copying
is needed. From the repository root, explicitly choose the notebook to open:

```bash
make notebook NOTEBOOK=oceans
make notebook NOTEBOOK=mask
```

`make notebook` without `NOTEBOOK=...` refuses to start and lists the available
names. An unknown name is rejected as well.

**Installed package without a clone:** download the desired `.py` file from
the [notebooks directory](https://github.com/romain894/region-mask/tree/main/notebooks)
at the tag or commit matching your package version. The project's source
distribution (`.tar.gz`) also contains `notebooks/`, without the datasets.
Save the notebook in your working directory, then open it directly:

```bash
marimo edit mask.py
```

Install the `notebooks` extra to obtain marimo. The package does not copy or
manage notebook files. Run marimo from the directory containing your `.env`
and input data; relative paths resolve against that launch directory.

The five `.py` notebooks in `notebooks/` are small interfaces to `region_mask/`.
Opening them does not generate data. Review the displayed settings, then click
**Generate and write** to overwrite the configured outputs. Run country and
ocean preparation before the combined product; run country preparation before
the land/ocean product; generate a mask after preparing its input shapefile.
Inspection plots never modify or automatically export data.

The same stages work without a notebook:

To regenerate all four Natural Earth shapefiles, both masks, and their ID CSV
tables in dependency order, run:

```bash
make generate-ne
```

This overwrites the configured production outputs (by default under `data/`).
It uses `.env` and environment overrides for paths, grid settings, normalization,
and workers. Both masks use their corresponding configured combined shapefile
paths, regardless of `MASK_SHAPE_FILE_PATH`. Generation stops on the first error.
Use `make regression` for an isolated generation and comparison report.

For a release, regenerate the production artifacts and then compare those exact
files against the pinned reference:

```bash
make generate-ne && make compare CANDIDATE=.
```

Review the generated `regression-runs/<timestamp>/report.md` before publishing
the artifacts. These commands do not publish a release or update the baseline.

Individual stages are also available:

```bash
.venv/bin/python -m region_mask countries
.venv/bin/python -m region_mask oceans
.venv/bin/python -m region_mask countries_oceans
.venv/bin/python -m region_mask land_ocean
.venv/bin/python -m region_mask mask
```

The installed `region-mask` command is equivalent to `python -m region_mask`.

These commands use defaults, overridden by `.env`, then environment variables.
`--root PATH` resolves relative paths there; `--config settings.json` supplies
explicit settings without reading `.env` or environment overrides. Unlike regression,
these generation commands **write the configured production outputs**.

Python callers can import `generate_countries`, `generate_oceans`, `generate_merge`,
`generate_land_ocean`, and `generate_mask` from their respective modules and pass
explicit paths. `generate_mask` returns a `MaskResult` with final/raw DataArrays,
shifted regions, and export paths. Put calls starting Dask workers under
`if __name__ == "__main__":` in ordinary Python scripts.

The original Jupyter notebooks are frozen in [legacy_notebooks/](legacy_notebooks/).
Other datasets' preparation notebooks remain unchanged. This migration changes
organization, configuration and display only: ocean gap assignment, country
adjustments, planar fractional areas, normalization and known limitations remain
unchanged. Scientific corrections should be separate, regression-reviewed changes.

### Documentation and distribution builds

With the `dev` extra installed:

```bash
make docs              # Sphinx HTML: docs/_build/html/index.html
make build             # Source archive and wheel: dist/
make package-check     # Build and verify wheel outside the checkout
```

See [the documentation sources](docs/index.rst) for installation, API examples,
marimo usage and development guidance. Builds do not publish anything.

### Regression testing

Before changing the processing code, reproduce the Git-tracked Natural Earth
outputs and generate a Markdown comparison report:

```bash
make test
make check-notebooks
make regression
```

See [the regression testing guide](regression/README.md) for dependencies,
artifact comparisons, baseline policy, and the replaceable producer interface.
The default runner executes the Python modules directly. Runs write to isolated, ignored
`regression-runs/` directories and do not overwrite production datasets.

GitHub Actions checks tests, notebooks, Sphinx docs and the installed wheel, then runs the complete `make regression` workflow on
each push and pull request. The workflow uploads the Markdown report, metrics,
manifest and execution logs for 30 days, including when a regression fails.

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

For the current Natural Earth workflow, launch marimo:

```bash
make notebook NOTEBOOK=oceans
```

Jupyter Lab remains available for the other datasets and legacy notebooks:

```bash
jupyter lab
```
