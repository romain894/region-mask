# Build the countries/oceans shapefile based on the Eurostat, GOaS and SeaVox datasets

In this folder, you can find the notebooks and default `.env.template` file to generate the shapefile with the countries
and oceans using the Eurostat, GOaS and SeaVox datasets.

## Input Data:

  - Countries shape file: Eurostat dataset-specific non-commercial license © EuroGeographics for the administrative boundaries
  - Oceans shape file: Creative Commons Attribution 4.0 International
  - Caspian Sea shape file: Creative Commons Attribution 4.0 International
  - CSV file with custom ids (`data/codes_id.csv`): CC0 1.0 Universal (public domain)


## Output mask

The mask based on the Eurostat, GOaS and SeaVox datasets is available in this repository at the following path:
`/eurostat_goas_seavox_mask/eurostat_goas_seavox_mask.nc` under the following terms: 
© EuroGeographics for the administrative boundaries ; Non-commercial use only ; 
Global Oceans and Seas, version 1 (Flanders Marine Institute, 2021) CC BY 4.0 ; 
Polygon dataset of the extent of water bodies from the SeaVoX Salt and Fresh Water Body Gazetteer (v19) CC BY 4.0

## Input datasets licenses and attributions

- `CNTR_RG_01M_2020_4326.shp`  
  Countries 2020 — [Eurostat/GISCO administrative data](https://ec.europa.eu/eurostat/web/gisco/geodata/administrative-units/countries)  
  © EuroGeographics for the administrative boundaries ; Non-commercial use only

- `goas_v01.shp`  
  Global Oceans and Seas, version 1 (Flanders Marine Institute, 2021) – https://www.marineregions.org/downloads.php
  DOI: https://doi.org/10.14284/542  
  CC BY 4.0

- `SeaVoX_sea_areas_polygons_v19.shp`  
  Polygon dataset of the extent of water bodies from the SeaVoX Salt and Fresh Water Body Gazetteer (v19) (British Oceanographic Data Centre, 2023) – https://www.marineregions.org/downloads.php
  DOI: https://doi.org/10.14284/590  
  CC BY 4.0



Romain THOMAS - romain.thomas@polito.it  
Giulia CIGNA - giulia.cigna@polito.it  
DIATI - Politecnico di Torino