Reviewing ocean corrections
============================

Run ``make ocean-review`` (optionally ``OUTPUT=regression-runs/my-review``).
The destination must not exist. This developer workflow does not overwrite
production data, publish anything, change boundary conventions or promote a
baseline. It exports the pinned inputs, prepared countries and reference oceans
from Git. Python source snapshots, input checksums and environment information
are retained with the report. It requires a checkout with the baseline history.

Archive a selected run in Git with
``make archive-review RUN=regression-runs/my-review NAME=my-review-name``.
This creates ``reviews/my-review-name/`` with Markdown, JSON, figures and the
hashed producing sources, including linked supporting reports. It validates
local inline report links and source checksums before writing, and refuses an
existing name. Large source datasets and generated masks are excluded. External
URLs are preserved without network checks. Add the review to ``reviews/README.md``
and commit it through the normal workflow; the command never stages or commits.
An archive is immutable evidence, not approval. Later decisions belong in a
separately dated record, and baseline promotion remains an explicit action.

Outputs are ``report.md``, ``stages.json``, ``total.json``, ``atlas.json``,
per-stage GeoPackages and PNG figures. JSON preserves unrounded measurements.
The atlas includes Gibraltar and every multi-candidate gap encountered by the
current method. Source names, bounds and an unreviewed status accompany each
location. A map can be geometrically clean but geographically mislabelled.

Controlled experiments
----------------------

The sequence is pinned baseline, historical-method rerun, explicit water repair,
country clipping, coarse eastern-seam closure, new gap inference, and Gibraltar.
The historical rerun is a control: nonzero differences there cannot be attributed
to the new corrections. The production mapping and Indian Ocean split are
captured at the partition boundary so the review does not maintain a separate
copy of the group definitions.

Each comparison is conditional on preceding steps. Clipping can change gap
connectivity and therefore change a nearest-first assignment; numerical overlay
ordering can also change. These are controlled sequential effects, not independent
causal contributions that apply in every order. Invalid geometries retain the
strict comparator's unavailable-area-difference status rather than being repaired
to force a comparison.

Area measurements
-----------------

The old method reprojected densified vertices and measured the resulting polygon.
Different vertex subdivisions can turn an almost collinear sliver into a curved
wedge. The revised method integrates the WGS84 surface element directly over
the original straight longitude/latitude polygons:

.. math::

   dA = \frac{a^2(1-e^2)\cos\phi}{(1-e^2\sin^2\phi)^2}\,d\lambda\,d\phi.

This is the product of meridional and parallel metric scales; see the ellipsoid
formulae in `EPSG Guidance Note 7 <https://gdal.org/en/stable/proj_list/guid7.html>`_.
Coordinates are integrated as given, without shortest-path seam wrapping or
reinterpretation as geodesic edges. Signed fan triangles preserve polygon edges,
with hole areas subtracted. Extended-precision determinants reduce cancellation
for almost collinear triangles. Nothing is snapped or deleted.

The area uses 16-order Gaussian quadrature. Its discrepancy from 8-order
quadrature plus a floating-point roundoff estimate is reported as numerical
uncertainty. This is an empirical error indicator, **not a certified bound**,
and excludes coordinate uncertainty and uncertainty in geographical labels.
Large cancellation or poor convergence must be reviewed, not hidden.

Reports distinguish added, removed, net (added minus removed), and changed
(added plus removed) area. Differences of independently integrated full-region
areas remain available in JSON as an additional closure check. Exact spatial
equality, not an area threshold, continues to determine regression acceptance.

Synthetic tests exercise known rectangles, the whole ellipsoid, degenerate and
tiny slivers, equivalent vertices, holes, additivity and strict acceptance.
Existing reports are historical artifacts and are not rewritten automatically.

Initial review finding: Smith Sound
----------------------------------------

The pinned marine feature ``ne_id=1159119367``, named ``Smith Sound``, has bounds
approximately ``(-128.1021, 51.2974, -126.6914, 52.8426)``. The current name-based
mapping assigns it to Arctic Ocean, although those coordinates are on the
British Columbia coast. The `BC Geographical Names Office's Smith Inlet record
<https://apps.gov.bc.ca/pub/bcgnws/names/27040.html>`_ locates Smith Inlet at the
head of Smith Sound near 51.30 N, 127.29 W, corroborating the local identification.

The atlas's first two ambiguous-gap panels expose propagation of this existing
label into neighbouring water. These changes must not be approved merely because
their topology is valid. Review feature identity and location, not just names;
an explicit feature-ID mapping with geographical assertions is a possible next
correction. This review deliberately does not change the mapping or baseline.
