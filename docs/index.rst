Region Mask
===========

Region Mask prepares Natural Earth country/ocean shapefiles and generates
fractional masks as NetCDF arrays with dimensions ``(region, lat, lon)``.
Use the installed Python API, command-line stages, or the accompanying marimo examples.

.. warning::

   Fractional intersections still use planar longitude/latitude areas, not
   geodesic areas; normalization limitations remain. Ocean labelling now uses
   the corrected method described below. Regression agreement establishes
   reproducibility, not geographical correctness or authoritative boundaries.

.. toctree::
   :maxdepth: 2

   installation
   usage
   notebooks
   ocean_method
   ocean_review
   api
   development

Source and research archive
---------------------------

* `Repository <https://github.com/romain894/region-mask>`_
* `Zenodo archive <https://doi.org/10.5281/zenodo.19007672>`_

Code is GPL-3.0-only. Data licenses are separate: see the repository README
and the license accompanying each dataset. The Python distributions do not
contain shapefiles, masks, private configuration, or regression baselines.
