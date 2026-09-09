Development and verification
============================

From a full Git checkout:

.. code-block:: bash

   python3.12 -m venv .venv
   .venv/bin/python -m pip install -e '.[dev]'
   make test
   make check-notebooks
   make docs
   make package-check
   make regression

``pyproject.toml`` is the dependency source of truth. The requirements files
remain compatibility entry points that install its extras. ``make`` defaults to
``.venv/bin/python``; set ``PYTHON=python`` when using an activated environment.

Documentation
-------------

``make docs`` builds HTML into ``docs/_build/html/`` and treats Sphinx warnings
as errors. Open ``docs/_build/html/index.html``. Autodoc imports the installed
package, so install it (usually editable) before building the docs.

Packaging
---------

``make build`` creates an sdist and builds a wheel from that sdist in ``dist/``.
Only ``region_mask`` is installed. Tests, regression
tools, datasets, historical notebooks and ``.env`` are not runtime package files.
The sdist includes this basic Sphinx documentation and the top-level
``notebooks/`` examples; neither is installed into the Python package.

``make package-check`` additionally installs the wheel into a temporary virtual
environment and checks imports, the stage command and a small
analytic raster case from outside the checkout. It also verifies that examples
are present in the sdist but absent from the wheel. It reuses the current
environment's dependencies, so this is an artifact-isolation test, not a clean
dependency-resolution or minimum-version test. Nothing is published automatically.

Scientific regression
---------------------

The repository's ``regression/baseline.json`` pins the trusted Git commit and
artifact paths. ``make regression`` generates all Natural Earth products into
an isolated, ignored ``regression-runs/`` directory and writes Markdown and JSON
reports. It does not overwrite tracked production data or update the baseline.

The wheel does not include baseline data or the Git-dependent regression CLI.
Run this workflow from a full checkout; see ``regression/README.md`` there for
comparison policies and release-report instructions. Unit tests retain the
documented expected failure for a region covering the entire raster.

GitHub Actions checks tests, notebooks, documentation and the built package,
then runs the full scientific regression. Numerical changes must be reviewed
separately from packaging or notebook changes.
