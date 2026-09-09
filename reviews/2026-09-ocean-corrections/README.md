# 2026-09-ocean-corrections

Status: **awaiting review — not approved for baseline promotion**.

- [Report and atlas](report.md)
- [Per-step measurements](stages.json) and [total changes](total.json)
- [Input and environment provenance](manifest.json)
- [Archive checksums](archive.json)
- [Reviewer findings and known problems](reviewer_notes.md)

Reference commit: `ad0760a3b3210aba51593a92bc5935f2b987feca`.

This is an immutable evidence snapshot, not an approval. A later candidate or
review decision should use a new archive or a separately dated decision record;
do not overwrite these results. Intermediate GeoPackages, source datasets and
NetCDF arrays are deliberately excluded. Linked supporting reports are bundled
under `related/`, so reviewers do not need the temporary regression workspace.

## Reproduce

The original working tree could include uncommitted code. Its actual Python
source snapshots are retained under `sources/`, with hashes verified against
the producer manifest. Do not substitute the current repository HEAD for them.
Create a separate checkout with the pinned Git history, then overlay the archived
`sources/region_mask/` and `sources/regression/` directories onto the matching
directories in that checkout. This also makes the generator's source-hash capture
record the actual archived implementation. Install the dependencies recorded in
`manifest.json`, then run from that separate checkout:

```bash
.venv/bin/python -m regression.ocean_review --output /path/to/new-review-run
```

The generator exports its inputs from the pinned commit. Ensure the checkout's
`regression/baseline.json` still names the reference commit above; if it has
changed, use a separate checkout with that baseline configuration. Supporting
reports may compare existing artifacts rather than regenerate them; consult
their own manifests. Archiving neither commits files nor changes the baseline.
