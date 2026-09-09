Installation
============

Python 3.12 or later is required. Distribution name: ``region-mask``;
Python import name: ``region_mask``. This is distinct from the separate
``regionmask`` project.

From a source checkout
----------------------

Create an environment and install from the repository root:

.. code-block:: bash

   python3.12 -m venv .venv
   .venv/bin/python -m pip install .

For the interactive notebooks instead:

.. code-block:: bash

   .venv/bin/python -m pip install '.[notebooks]'

You can also install a built wheel without keeping the source checkout:

.. code-block:: bash

   python -m pip install /path/to/region_mask-0.1.0-py3-none-any.whl

For a wheel plus notebooks:

.. code-block:: bash

   python -m pip install '/path/to/region_mask-0.1.0-py3-none-any.whl[notebooks]'

These commands install local artifacts; they do not assume a PyPI release exists.
Use a reviewed Git revision or archived wheel for reproducible research.

Optional dependencies
---------------------

``notebooks``
   Marimo for interactive use. Not required for the Python API or stage CLI.
``docs``
   Sphinx for building this documentation.
``legacy``
   Jupyter and execution tools for the original repository notebooks.
``dev``
   All the above plus distribution build tooling. The tests themselves use
   Python's standard-library ``unittest``.

Numerical dependencies are compatibility bounds, not a reproducibility lockfile.
Record installed versions and run the regression before accepting results from
a new environment. The current bounds are not a claim that every combination
of dependency versions has been tested.

Input data
----------

No data is downloaded automatically. For the standard Natural Earth workflow,
obtain ``data/ne_10m/`` and ``data/codes_id.csv`` from the repository (or supply
your own explicit paths). Keep all shapefile sidecars together. An installed
package can also rasterize an existing shapefile with ``ID`` and ``geometry``
columns without running Natural Earth preparation.

Copy the repository's ``.env.template`` into your workspace as ``.env`` if you
want to customize the default stage paths. Direct API calls take paths as
arguments and do not read ``.env``.
