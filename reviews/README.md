# Scientific review archive

Curated evidence lives here; temporary complete runs remain in `regression-runs/`.
An archive records a candidate, not approval or baseline promotion. Keep archived
results immutable. Record later decisions separately, or archive a new candidate.

| Review | Status | Summary |
| --- | --- | --- |
| [2026-09 ocean corrections](2026-09-ocean-corrections/README.md) | Awaiting review; do not promote | Area measurement fix, controlled comparisons and 29-location atlas; Smith Sound mapping problem identified |

Create a new archive explicitly:

```bash
make archive-review RUN=regression-runs/ocean-attribution NAME=2026-09-ocean-corrections
```

Names cannot overwrite existing directories. The command validates source
snapshot checksums and local report links, then bundles Markdown, JSON, figures,
and the exact producing Python sources. Linked sibling reports are included with
rewritten relative links. Large intermediate datasets are excluded. External
web links are preserved but not checked or downloaded.

Add a row to this index when selecting another review. Commit the archive through
your normal Git workflow; the command does not stage or commit anything. Complete
generation artifacts can be retained separately for a Zenodo release.
