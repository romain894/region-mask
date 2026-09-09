"""Archive selected ocean-review evidence, never intermediate datasets.

Local inline Markdown links emitted by our report writers are checked and
rewritten. Linked sibling reports are bundled under related/; external URLs
are retained, not fetched. Archiving does not approve a candidate or stage Git.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .common import sha256

CORE = ('report.md', 'manifest.json', 'stages.json', 'total.json', 'atlas.json')
OPTIONAL = ('reviewer_notes.md', 'contact.png')
EVIDENCE = {'.md', '.json', '.png', '.svg', '.pdf'}
LINK = re.compile(r'(!?\[[^\]\n]*\]\()([^\s)]+)(\))')


def archive(run, reviews, name):
    run, reviews = Path(run).resolve(), Path(reviews).resolve()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', name):
        raise ValueError('NAME must contain only lowercase letters, digits, hyphens or underscores')
    destination = reviews / name
    if destination.exists():
        raise FileExistsError(f'Archive already exists: {destination}')
    files = {}
    original_hashes = {}

    def add(source, target):
        source = Path(source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Missing or symlinked evidence: {source}')
        source = source.resolve()
        if not source.is_relative_to(run.parent):
            raise ValueError(f'Evidence escapes review workspace: {source}')
        if target in files:
            return
        data = source.read_bytes()
        original_hashes[str(target)] = hashlib.sha256(data).hexdigest()
        # Reserve before recursion to support links between reports.
        files[target] = data
        if source.suffix == '.md':
            def replace(match):
                url = urlsplit(match[2])
                if url.scheme or url.netloc or not url.path:
                    return match[0]
                path = Path(unquote(url.path))
                if path.is_absolute():
                    raise ValueError(f'Absolute local link in {source}: {path}')
                linked = source.parent / path
                resolved = linked.resolve()
                if not resolved.is_relative_to(run.parent) or resolved.suffix not in EVIDENCE:
                    raise ValueError(f'Unsupported local evidence link in {source}: {path}')
                relative = (resolved.relative_to(run) if resolved.is_relative_to(run)
                            else Path('related') / resolved.relative_to(run.parent))
                add(linked, relative)
                rewritten = Path(os.path.relpath(relative, target.parent)).as_posix()
                if url.query:
                    rewritten += '?' + url.query
                if url.fragment:
                    rewritten += '#' + url.fragment
                return match[1] + rewritten + match[3]
            files[target] = LINK.sub(replace, data.decode()).encode()

    for filename in CORE:
        add(run / filename, Path(filename))
    for filename in OPTIONAL:
        if (run / filename).exists():
            add(run / filename, Path(filename))
    manifest = json.loads(files[Path('manifest.json')])
    if not manifest.get('reference_commit') or not manifest.get('inputs') or not manifest.get('sources'):
        raise ValueError('Ocean review manifest must identify pinned inputs and source snapshots')
    for filename, expected in manifest['sources'].items():
        relative = Path(filename)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'Unsafe source path: {filename}')
        source = run / 'sources' / relative
        if not source.is_file() or sha256(source) != expected:
            raise ValueError(f'Source snapshot checksum mismatch: {filename}')
        add(source, Path('sources') / relative)
    # Atlas figures are machine-readable links too, even when not in report.md.
    for page in json.loads(files[Path('atlas.json')]):
        relative = Path(page['figure'])
        if relative.is_absolute() or '..' in relative.parts or relative.suffix not in EVIDENCE:
            raise ValueError(f'Unsafe atlas figure: {relative}')
        add(run / relative, relative)
    for filename in ('stages.json', 'total.json'):
        json.loads(files[Path(filename)])

    summary = f'''# {name}

Status: **awaiting review — not approved for baseline promotion**.

- [Report and atlas](report.md)
- [Per-step measurements](stages.json) and [total changes](total.json)
- [Input and environment provenance](manifest.json)
- [Archive checksums](archive.json)
'''
    if Path('reviewer_notes.md') in files:
        summary += '- [Reviewer findings and known problems](reviewer_notes.md)\n'
    summary += f'''
Reference commit: `{manifest['reference_commit']}`.

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
'''
    files[Path('README.md')] = summary.encode()
    metadata = {
        'schema_version': 1, 'archived_utc': datetime.now(timezone.utc).isoformat(),
        'source_run_name': run.name, 'status': 'awaiting_review',
        'original_evidence_sha256': original_hashes,
        'archived_sha256': {p.as_posix(): hashlib.sha256(b).hexdigest() for p,b in sorted(files.items())},
        'note': 'Markdown local links may be rewritten; original and archived hashes are separate.',
    }
    files[Path('archive.json')] = (json.dumps(metadata, indent=2, sort_keys=True)+'\n').encode()
    # All link, JSON and checksum validation happens before creating the archive.
    destination.mkdir(parents=True, exist_ok=False)
    for relative, data in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--reviews', type=Path, default=Path('reviews'))
    args = parser.parse_args()
    try:
        result = archive(args.run, args.reviews, args.name)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Cannot archive review: {exc}\n')
    print(f'Archived review: {result / "README.md"}')


if __name__ == '__main__':
    main()
