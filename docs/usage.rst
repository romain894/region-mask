Python API and command line
===========================

Generate a mask directly
------------------------

.. code-block:: python

   from region_mask.mask import generate_mask

   if __name__ == "__main__":
       result = generate_mask(
           "/work/data/my_regions/my_regions.shp",
           bounds=(-0.25, -89.75, 359.75, 90.25),
           resolution=0.5,
           normalize_mask=False,
           num_workers=4,
           memory_limit="2GB",
           diagnostics_dir="/work/diagnostics",
       )
       print(result.netcdf_path)
       print(result.mask)      # Final xarray.DataArray
       print(result.raw_mask)  # Pre-normalization xarray.DataArray

The main guard is important when Dask starts worker processes. Importing the
package does not start workers. Workers are closed before the call returns.

.. warning::

   Generation writes files and overwrites existing outputs. For the example
   above, the outputs are under ``/work/data/``: a file named
   ``mask_my_regions_lat90.25_lon-0.25_res0.5.nc`` and ``ids_my_regions.csv``.
   The optional diagnostics directory receives an additional raw NetCDF file.

The returned ``MaskResult`` also contains shifted region geometries and the ID
table path. The ID table keeps the original CSV index. Array order, metadata,
float32 storage and compression are preserved from the original workflow.

Normalization divides each pixel's regional fractions by their sum. Use it
only when that is appropriate for a complete partition. Uncovered cells may
become NaN; normalization must not be used to conceal geometry defects. A shape
covering the entire raster currently triggers the known empty-complement error.

Prepare Natural Earth shapes
----------------------------

.. code-block:: python

   from region_mask.countries import generate_countries
   from region_mask.oceans import generate_oceans
   from region_mask.merge import generate_merge

   countries = generate_countries(
       "/work/data/ne_10m/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp",
       "/work/data/codes_id.csv",
       "/work/data/countries/countries.shp",
   )
   oceans = generate_oceans(
       "/work/data/ne_10m/ne_10m_geography_marine_polys/ne_10m_geography_marine_polys.shp",
       "/work/data/ne_10m/ne_10m_ocean/ne_10m_ocean.shp",
       "/work/data/codes_id.csv",
       "/work/data/oceans/oceans.shp",
       countries_path="/work/data/countries/countries.shp",
   )
   combined = generate_merge(
       "/work/data/countries/countries.shp",
       "/work/data/oceans/oceans.shp",
       "/work/data/combined/combined.shp",
   )

Each function writes its explicit output path and returns a GeoDataFrame.
``generate_land_ocean`` is the alternative two-region product: it takes the
prepared countries but the **original** Natural Earth ocean shapefile.
Both ocean products repair this detailed water geometry and subtract country
overlaps using the same method. The ``oceans`` stage requires prepared countries;
direct API callers should supply ``countries_path`` for consistent land clipping.
See :doc:`ocean_method` for boundary conventions and coverage limitations.

Stage commands
--------------

From a checkout, ``make generate-ne`` regenerates all four Natural Earth
shapefiles, both masks, and their ID tables in dependency order. The equivalent
CLI command is ``region-mask all-ne``. It overwrites configured production
outputs and stops on the first error. It respects configuration overrides,
using ``NE_COUNTRIES_OCEANS_PATH`` and ``NE_LAND_OCEAN_PATH`` for the two mask
inputs instead of ``MASK_SHAPE_FILE_PATH``.

After activating the installed environment, from a workspace containing inputs:

.. code-block:: bash

   region-mask countries
   region-mask oceans
   region-mask countries_oceans
   region-mask land_ocean
   region-mask mask

``python -m region_mask`` is equivalent to ``region-mask``. Stages do not run
their prerequisites automatically. The mask stage uses ``MASK_SHAPE_FILE_PATH``
to choose the product to rasterize.

Configuration precedence is defaults, then workspace ``.env``, then environment
variables. Relative paths resolve under ``--root`` (default: current directory).
``--config settings.json`` accepts a JSON object using the same setting names
and bypasses ``.env`` and environment overrides. Unspecified keys retain defaults:

.. code-block:: json

   {
     "MASK_SHAPE_FILE_PATH": "data/my_regions/my_regions.shp",
     "MASK_RESOLUTION": "0.5",
     "NORMALIZE_MASK": "false",
     "DASK_NUM_WORKERS": "2"
   }

.. code-block:: bash

   region-mask mask --root /work --config settings.json

Use ``run_stage(stage, root=..., settings=...)`` for equivalent explicit Python
dispatch. See :data:`region_mask.pipeline.DEFAULTS` for all configuration keys.
