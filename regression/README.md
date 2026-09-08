# Natural Earth regression testing

The committed files listed in [baseline.json](baseline.json), read from the fixed
`reference_commit`, are the trusted baseline. Tests never replace that baseline
and never write to the repository's production `data/` directory.

## Run the full regression

From the repository root, with the project environment activated:

The current notebooks require Python 3.12 or later. Coverage diagnostics require
Shapely 2.1 or later with GEOS 3.12 or later. The run manifest records the actual
environment; historical reference dependency versions were not recorded.

```bash
python -m pip install -r requirements-test.txt
make test
make regression
```

`make regression` creates the Markdown report automatically. `make regression-strict`
also requires byte-identical serialized artifacts. Run `make help` for the full
list of targets. If the project virtual environment is elsewhere, override it
with `make test PYTHON=/path/to/python`.

The full run executes country preparation, ocean preparation, both combined
shapefiles, and both 0.5° global masks. Each notebook runs in a fresh kernel using
the same Python executable as the command. The notebook source is copied before
execution; existing outputs are discarded. Production calculations are unchanged.

The result goes into a new, ignored `regression-runs/<UTC timestamp>/` directory:

```text
manifest.json        Reference revision, settings, environment, source/input/output hashes
metrics.json         Complete machine-readable comparisons and measurements
report.md            Release-ready Markdown report
reference/data/      Published artifacts extracted directly from the reference Git commit
candidate/data/      Newly generated artifacts
candidate/diagnostics/  Additional pre-normalization masks
sources/             Exact notebook sources executed
execution/           Executed notebook logs, including failures
stages.json          Execution progress and per-stage timings
figures/             Mask difference maps, when numerical changes occur
```

Exit status is **0 for pass**, **1 for regression/generation failure**. Configuration
or invocation errors may use another nonzero exit code. Full generation is the
normal acceptance check; the small unit tests diagnose the comparison machinery.
Run the full check once after a completed change, rather than after every edit.

The unit suite also exercises analytic fractional-mask and longitude-split cases
against the production functions extracted from the notebook AST, without
executing its top-level I/O. Only that small test adapter needs replacement when
functions move into the production package. One documented expected failure
currently remains: a region covering the entire raster creates an empty
complement and the notebook passes it to Rasterio, which raises an error.
This existing limitation is not fixed during regression setup. An eventual fix
will produce an unexpected success until the expected-failure marker is removed.
The full published-grid regression does not encounter that synthetic case.

Useful options:

```bash
python -m regression run --output regression-runs/migration-check
python -m regression run --workers 6
python -m regression run --require-byte-identical
```

The output directory must not already exist. Notebook cells have a configurable
`--timeout` (default 1800 seconds). The effective configuration is recorded; the
developer's `.env` is not loaded or copied. The adapter supplies a harmless empty
`.env` in the isolated workspace because the existing notebooks require one.
Browser opening is suppressed and plotting is headless. The mask notebook's
post-export illustration cells are omitted: they assume an Italy feature that
does not exist in the land/ocean dataset. All computation and publication cells
execute, including the ID CSV export. Full source snapshots and these adapter
choices are part of the provenance.

## Compare existing artifacts or two versions

No computation is needed to rerun the comparison/report stage:

```bash
python -m regression compare --candidate-dir regression-runs/migration-check/candidate
python -m regression compare --reference-dir regression-runs/old/candidate --candidate-dir regression-runs/new/candidate
python -m regression compare --candidate-dir . --reference-ref <commit>
```

An artifact directory contains the paths listed in `baseline.json`, including
their `data/` prefix. The default reference is always the fixed baseline commit,
not `HEAD` and not the current worktree. `--reference-ref` and `--reference-dir`
are explicit overrides and never modify the baseline configuration.

References supplied as directories are hashed but their historical producing
environment is not inferred. Keep their original `manifest.json` alongside them.
For an intentional scientific change, inspect the report, explain the expected
differences, publish/commit the accepted artifacts, then deliberately update the
baseline commit. Never automatically accept new output because a test failed.

## What passes

### Shapefiles

- All five expected sidecars must exist. SHA-256 is recorded for each.
- IDs must exist, be non-null, unique, and have the same membership.
- CRS, column names/order, attribute dtypes, attributes, and geometry types match.
- Valid geometries must occupy exactly the same space. Canonical structural
  equality is also reported; equivalent ring/part ordering or redundant collinear
  vertices do not create a spatial failure. Feature row order is diagnostic.
- Invalid reference geometry is **not repaired** for equivalence checks. Only
  canonical structural equality can establish unchanged invalid geometry.
- Reports include areas, additions/removals, symmetric difference, bounds, parts,
  holes, vertex counts, and validity. Equal total areas alone never establish a pass.

Area diagnostics use a WGS84 cylindrical equal-area projection with standard
parallel 30°. Source segments are densified to at most 0.25° before projection.
They are approximate physical areas of the represented polygons; their method
is versioned with the comparator. They are not measurements in square degrees.
Geometries must already use the dataset's split longitude representation in
EPSG:4326; the comparator does not reinterpret seam-crossing input geometry.

Coverage diagnostics run on the explicitly configured `coverage_shapefiles`
(the two combined world products in the default configuration). They describe
uncovered world area, overlap footprint and invalid features. Explicitly repaired
copies are used only for these diagnostics, with polygonal components retained
for the footprint. Existing nonzero gaps/overlaps are recorded rather than declared
failures: baseline reproduction is different from scientific correctness. Failure
to compute a requested diagnostic is itself a failing/incomplete run.
`--skip-coverage` explicitly omits these descriptive measurements for a quick
comparison; it does not skip per-feature or NetCDF checks.

### NetCDF

The delivered file is compared at three levels:

1. Byte identity via SHA-256.
2. Dimensions and unlimited flags, variable dimensions/dtypes, all variable/global
   attributes (including fill conventions), and decoded coordinates/IDs.
3. Every decoded value and missing-value position, read in slabs to limit memory.

Default numeric tolerance is **zero**. Region order and grid coordinates must
match exactly. Compression, chunking, endianness and file model are reported as
storage differences; storage-only changes do not fail semantic equivalence.
`--require-byte-identical` adds an exact-file gate for all published artifacts,
including shapefile sidecars and ID tables. DBF headers or NetCDF serialization
can differ even if the research content is unchanged; no such difference is hidden.

Do not loosen tolerances just to obtain a pass. If a numerical difference has
been investigated, an explicit `--atol` and/or `--rtol` can document an alternative
policy. Coordinates and integer variables stay exact. Missingness must still
match, and every exact difference and zero/one transition is reported even when
within tolerance. Metadata has no default ignore list. Unexpected NetCDF groups
fail explicitly rather than being silently omitted.

Per-region reports record absolute errors, extrema, missing values, zero/one
counts, and fractions outside [0, 1]. Sums across regions are descriptive float64
reductions. They are not asserted to equal one everywhere: existing geometrical
gaps and the grid's extension to 90.25°N must remain visible.

Current notebook runs also retain the array before normalization. Existing tracked
NetCDF files have no separate raw-array baseline, so its absence is reported.
When comparing two run directories that both provide raw masks, those arrays
are compared as well and differences fail the comparison.

### CSV tables

The two published region tables are compared literally after CSV parsing,
including column and row order. IDs such as Namibia's `NA` remain strings.

## Future Python modules and marimo

The notebook-specific code is confined to `regression/runners.py`. Geometry,
NetCDF, reporting, and reference extraction are independent of it. A replacement
runner has this interface:

```python
from regression.runners import RunContext

def run(context: RunContext) -> None:
    # Inputs are already copied under context.workspace.
    # Call the future production module with explicit input/output paths and
    # context.settings. Write the artifact paths in context.config beneath
    # context.workspace. Do not write production data or reference artifacts.
    ...
```

Select it with:

```bash
python -m regression run --runner your_package.regression_adapter:run
```

The runner can populate `context.stages` and `context.sources` for provenance.
If published artifact paths change, provide a reviewed alternative `--config`;
the comparators do not depend on production module names or notebook cell order.
Marimo notebooks can remain thin interfaces to the same production functions.

## Release report

`report.md` is the human-readable report; `metrics.json` contains every per-region
measurement. PDF export is optional and outside the numerical test environment.
For example, with Pandoc and a PDF engine installed, run from the report directory:

```bash
pandoc report.md -o report.pdf
```

Publish the Markdown/PDF, JSON manifest and metrics, any referenced figures, and
the accepted NetCDF/shapefile artifacts together. A PDF alone does not preserve
the full machine-readable comparison. No publication or reference update occurs
automatically.
