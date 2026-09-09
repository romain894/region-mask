Marimo notebooks
================

The five examples live in the top-level ``notebooks/`` directory, separate from
the installed Python package. They import the same scientific functions as
direct API users. The ``notebooks`` extra installs marimo, not the example files.

Working in a cloned repository
------------------------------

No copying is needed. From the repository root, explicitly select the file:

.. code-block:: bash

   make notebook NOTEBOOK=oceans
   make notebook NOTEBOOK=mask

Without ``NOTEBOOK=...``, ``make notebook`` refuses to start and lists available
names. Unknown names are rejected too.

Installed package without a clone
---------------------------------

Download the desired Python file from the repository's
`notebooks directory <https://github.com/romain894/region-mask/tree/main/notebooks>`_.
Choose the tag or commit matching your installed package version, rather than
assuming the latest development notebook is compatible. Alternatively, obtain
``notebooks/`` from the matching source distribution (``.tar.gz``), which does
not contain the datasets.

Save the example in your working directory. With the ``notebooks`` extra
installed and the environment activated, open it directly:

.. code-block:: bash

   marimo edit mask.py

Use the same command to reopen it. There is no package-specific command for
copying, opening or updating notebooks.

Configuration and execution
---------------------------

Launch marimo from the workspace containing your ``.env`` and input data:
relative data paths resolve against the **launch directory**, not the notebook's
directory. You must obtain the input data separately.

Opening a notebook does not generate data. Review its settings and click
**Generate and write** to run the stage and overwrite its configured outputs.
Region-selection controls and inspection plots do not rerun the producer.
The mask notebook also displays pre-normalization coverage diagnostics.

The unchanged Jupyter originals remain in the repository's ``legacy_notebooks/``.
They are not included in installed distributions.
