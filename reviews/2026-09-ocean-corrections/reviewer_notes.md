# Initial review findings

Read alongside [the generated atlas](report.md) and
[the recomputed artifact report](related/ocean-corrected-metrics/report.md).
The latter intentionally omits expensive global coverage diagnostics; the
previous report retains those historical measurements using the old area method.

## Sequential attribution

| Step | Result |
| --- | --- |
| Historical method rerun | Spatially identical to pinned baseline |
| Explicit water repair | No additional spatial change |
| Country clipping | Approximately 0.587261 km² removed |
| Coarse eastern seam | Approximately 62.348891 km² transferred between labels |
| New gap inference | Approximately 600.074675 km² transferred between labels |
| Gibraltar | Approximately 1072.914537 km² transferred between labels |

Transfers count the area once, not the sum of both affected regions' changes.
These effects depend on order; they are not independent causal allocations.
The final experiment reproduces every region geometry in the previous full run.

## Measurement verification

The Baltic's apparent added area falls from approximately 3,214 m² under the
old measurement to 0.00000312 m². Actual removal measures 3,310.322106 m².
Caspian removal measures 115.383557 m², replacing the earlier 166.6 m² estimate.

An independent check with increasingly finely densified cylindrical equal-area
projection converges toward the new integrated measurements:

| Removed region | 0.01° subdivision (m²) | 0.001° (m²) | 0.0001° (m²) | New integration (m²) |
| --- | ---: | ---: | ---: | ---: |
| Baltic | 3318.423649 | 3310.335587 | 3310.322126 | 3310.322106 |
| Caspian | 117.852439 | 115.387246 | 115.383552 | 115.383557 |

These digits demonstrate numerical convergence, not geographical precision.
Coordinate uncertainty is not known, and no small feature is silently deleted.

## Do not approve panels 01–02 yet

The existing mapping puts Natural Earth `Smith Sound`, feature `1159119367`,
into Arctic Ocean. Its source geometry lies at roughly 51–53°N, 127–128°W on
the British Columbia coast. The new gap method extends that label. This is
an existing mapping error exposed and propagated by the geometry correction,
not evidence that those water bodies belong to the Arctic.
The gap-inference step adds approximately 259.20 km² to the Arctic label within
the British Columbia review window (-130, 50, -125, 54).

[BC's official Smith Inlet record](https://apps.gov.bc.ca/pub/bcgnws/names/27040.html)
places it at the head of Smith Sound at 51°18′N, 127°17′W.
Review the feature's identity and intended group before changing the mapping.
Neither production geometry nor group definitions have been changed in this
review step. Other atlas panels remain unapproved pending geographic review.

The [contact sheet](contact.png) was inspected for complete panels and readable
layout, with Gibraltar and the first British Columbia panel checked at full size.
This is not a claim of authoritative verification of all 29 locations.
