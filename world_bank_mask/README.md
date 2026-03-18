# Build the countries shapefile based on the World Bank Official Boundaries dataset

In this folder, you can find the notebooks and default `.env.template` file to generate the shapefile with the countries using the World Bank Official Boundaries dataset.

## Input Data

  - Countries shape file: World Bank Official Boundaries dataset Creative Commons Attribution 4.0
  - Ocean shape file: World Bank Official Boundaries dataset Creative Commons Attribution 4.0
  - CSV file with custom ids (`data/codes_id.csv`): CC0 1.0 Universal (public domain)


## Output mask

The mask based on the World Bank Official Boundaries dataset is available in this repository at the following path:
`/world_bank_mask/data/mask_wb_oceans_countries_lat90.25_lon-0.25_res0.5.nc` under the following terms: 
Region Mask: 3D Fractional Region Mask © 2026 by Romain Thomas, Giulia Cigna, Elena De Petrillo CC BY 4.0 ;
© World Bank CC BY 4.0

## Input datasets licenses and attributions

- `WB_GAD_ADM0.shp`  
  World Bank [Official Boundaries - Admin 0](https://datacatalogfiles.worldbank.org/ddh-published/0038272/5/DR0095371/World%20Bank%20Official%20Boundaries%20(Shapefiles)/World%20Bank%20Official%20Boundaries%20-%20Admin%200.zip)
- `WB_GAD_ocean_mask.shp`  
  World Bank [Official Boundaries - Ocean Mask](https://datacatalogfiles.worldbank.org/ddh-published/0038272/5/DR0095371/World%20Bank%20Official%20Boundaries%20(Shapefiles)/World%20Bank%20Official%20Boundaries%20-%20Admin%200.zip)



Romain THOMAS - romain.thomas@polito.it  
Giulia CIGNA - giulia.cigna@polito.it  
DIATI - Politecnico di Torino