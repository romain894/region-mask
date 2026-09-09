Natural Earth ocean partition
=============================

Purpose and scope
-----------------

The detailed Natural Earth ocean defines water coverage. The marine-polygons
layer supplies labels, not coastline precision. The existing eleven groups,
their membership and IDs, and the Indian Ocean split at 146.9167 degrees east
are retained. This is a derived research dataset, not an authoritative maritime
boundary product. No Marine Regions geometry is incorporated.

Footprint and country alignment
--------------------------------

Invalid input polygons are repaired with Shapely ``make_valid``; polygonal
components and holes are retained, without an area-based deletion threshold.
The detailed ocean is then clipped against repaired copies of prepared countries.
The country output itself is unchanged. Both regional oceans and the two-class
land/ocean product use this same water footprint.

This removes land/water overlap but does **not** guarantee complete coverage of
the world: some islands excluded by the ocean are missing from the country layer.
Replacing the ocean by the complement of countries would incorrectly flood
these islands. Remaining gaps must be reviewed as land-data issues, not assigned
automatically to a sea. Clipping also cannot make all nearby, nonintersecting
country and ocean coastline vertices identical.

Labelling coastal gaps
----------------------

The ordered Voronoi operation requires Shapely 2.1 or newer with GEOS 3.12 or
newer. Check the linked GEOS version when using a custom Shapely build.

After dissolving the original marine polygons into the existing groups:

* Close the coarse source's artificial eastern longitude seam: label vertices
  at or east of 179.9998 degrees are moved to 180 degrees. Detailed water
  coordinates are not snapped.
* Apply the Gibraltar convention below and intersect labels with detailed water.
  Unmapped labels and material cross-group source overlaps raise errors.
* Assign a gap touching just one label to that group. For isolated components,
  search an expanding neighbourhood, starting at 0.05 degrees and doubling,
  until label candidates are found.
* Split gaps with multiple candidates using sampled-boundary Voronoi cells in
  a local azimuthal-equidistant projection. Sample spacing is 500 metres.
  Sample sites alone are rounded to one millimetre to avoid near-duplicate
  vertices destabilizing the tessellation. Labels and coincident-site ownership
  are sorted for deterministic results independent of input row order.
* Inverse-project separators, densifying their projected edges at 500 metres,
  then clip against the original water geometry. The detailed coastline is not
  round-tripped through the projection. Sequential clipping conserves remaining
  water; the last sorted candidate receives any numerical remainder.

The old nearest-geometry join gave every touching group distance zero and kept
the first match, assigning an entire connected gap arbitrarily. Splitting avoids
that failure. The replacement is nevertheless an **inference**, dependent on
coarse labels, candidate selection, projection and sampling. The 500-metre
spacing is neither coastline resolution nor a guaranteed error bound. Studies
sensitive to inferred boundaries should compare smaller sampling spacings using
``partition_ocean(sample_metres=...)`` and inspect local results.

Gibraltar convention
--------------------

Within longitude/latitude bounds ``(-6.3, 35.6, -5.1, 36.4)``, replace existing
labels with a straight longitude/latitude cut through approximate cape anchors:

* Cape Trafalgar: ``(-6.035, 36.183)``;
* Cape Spartel: ``(-5.922, 35.790)``.

West is North Atlantic Ocean; east is Mediterranean Region. The line extends
into land and has no width, so no buffered strip removes water. Reapply it after
gap inference. This also removes incorrectly labelled coastal strips in the
coarse input, which gap filling alone cannot correct.

The named capes follow the western Mediterranean limit in
`IHO S-23, third edition (1953)
<https://iho.int/uploads/user/pubs/standards/s-23/S-23_Ed3_1953_EN.pdf>`_.
The numerical anchors and planar line above are an explicit project convention,
not a claim of exact digitization of official IHO coordinates or a geodesic limit.
They should be reviewed for the intended scientific application.

Validation and release review
-----------------------------

Generation rejects empty or invalid output regions, water-footprint changes,
and positive-area group overlaps above ``1e-9`` square degrees. This is a
numerical topology tolerance, not a physical accuracy claim or a minimum
retained feature size. Synthetic tests cover gap splitting, ordering, tiny water
components, holes, invalid polygons, land clipping and the Gibraltar cut.

Run ``make test`` and ``make regression``. The latter regenerates shapefiles and
NetCDF products and writes Markdown and machine-readable comparisons, including
per-region geometry differences and array changes. These scientific corrections
are expected to fail comparison with the old pinned baseline. Do not loosen
regression tolerances or silently update the baseline to hide those differences.
Review geography, water coverage and changed cells before promoting outputs.
Byte-level NetCDF reproducibility and numerical-array agreement remain distinct
checks. Passing topology tests does not establish correctness of every sea label.
