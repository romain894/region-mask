"""Run producers or compare already-produced artifacts against a fixed baseline."""

import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

import pandas as pd

from .common import SIDECARS, artifact_paths, environment, export_reference, git, hashes, sha256, write_json
from .geometry import compare_shapefiles, coverage_metrics
from .netcdf import compare_netcdf
from .report import write_report
from .runners import RunContext


def _safe_relative(path):
    p = Path(path)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Artifact/input paths must be relative to the workspace: {path}")
    return p


def compare_tables(reference, candidate):
    # Read IDs literally (including Namibia's NA), and preserve serialized value differences.
    a = pd.read_csv(reference, dtype=str, keep_default_na=False)
    b = pd.read_csv(candidate, dtype=str, keep_default_na=False)
    return {"passed": a.equals(b), "changes": [] if a.equals(b) else ["CSV columns, row order or values differ"],
            "reference_shape": list(a.shape), "candidate_shape": list(b.shape)}


def compare_artifacts(reference, candidate, config, output, atol=0.0, rtol=0.0, coverage=True):
    results = {}
    for kind in ("shapefiles", "netcdf", "tables"):
        for relative in config.get(kind, []):
            print(f"Comparing {relative} ...", flush=True)
            a, b = reference / relative, candidate / relative
            try:
                paths = [str(Path(relative).with_suffix(e)) for e in SIDECARS] if kind == "shapefiles" else [relative]
                missing = [f"{label}: {p}" for label, root in [("reference", reference), ("candidate", candidate)]
                           for p in paths if not (root / p).is_file()]
                if missing:
                    raise FileNotFoundError("Missing artifacts: " + ", ".join(missing))
                checksums = {"reference": hashes(reference, paths), "candidate": hashes(candidate, paths)}
                if kind == "shapefiles":
                    result = compare_shapefiles(a, b)
                elif kind == "netcdf":
                    result = compare_netcdf(a, b, atol, rtol, output / "figures" / f"{a.stem}.png")
                else:
                    result = compare_tables(a, b)
                result["file_checksums"] = checksums
                result["byte_identical"] = checksums["reference"] == checksums["candidate"]
                results[relative] = result
            except Exception as exc:
                results[relative] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    diagnostics = {}
    if coverage:
        # Only combined products represent the full world. A countries-only gap is expected ocean.
        for relative in config.get("coverage_shapefiles", []):
            print(f"Measuring coverage {relative} ...", flush=True)
            pair = {}
            for label, root in [("reference", reference), ("candidate", candidate)]:
                comparison = results.get(relative, {})
                identical_geometries = comparison.get("passed") and all(
                    r.get("structural_equal") for r in comparison.get("regions", {}).values()
                )
                if label == "candidate" and identical_geometries and "reference" in pair:
                    pair[label] = dict(pair["reference"], reused_identical_geometry_diagnostics=True)
                else:
                    try:
                        pair[label] = coverage_metrics(root / relative)
                    except Exception as exc:
                        pair[label] = {"error": f"{type(exc).__name__}: {exc}"}
            diagnostics[relative] = pair
    auxiliary = {}
    raw_names = {p.name for root in [reference, candidate] for p in (root / "diagnostics").glob("raw_*.nc")}
    for name in sorted(raw_names):
        path, previous = candidate / "diagnostics" / name, reference / "diagnostics" / name
        try:
            if previous.is_file():
                auxiliary[name] = compare_netcdf(previous, path, atol, rtol)
            else:
                summary = compare_netcdf(path, path)
                auxiliary[name] = {"status": "no_reference", "candidate_sha256": sha256(path),
                                   "candidate_metrics": summary["variables"].get("mask", {})}
        except Exception as exc:
            auxiliary[name] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    return results, diagnostics, auxiliary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "compare"])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("baseline.json"))
    parser.add_argument("--output", type=Path, help="New report directory; must not already exist")
    parser.add_argument("--reference-ref", help="Explicit alternative Git reference; never updates baseline.json")
    parser.add_argument("--reference-dir", type=Path, help="Artifact root from a previous run/release, instead of Git")
    parser.add_argument("--candidate-dir", type=Path, help="Required for compare; artifact root with data/ underneath")
    parser.add_argument("--runner", default="regression.runners:notebook_runner")
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--require-byte-identical", action="store_true")
    parser.add_argument("--skip-coverage", action="store_true", help="Omit expensive descriptive coverage measurements")
    parser.add_argument("--workers", type=int, help="Override recorded DASK_NUM_WORKERS")
    parser.add_argument("--timeout", type=int, default=1800, help="Notebook per-cell timeout in seconds")
    args = parser.parse_args(argv)
    if args.command == "compare" and args.candidate_dir is None:
        parser.error("compare requires --candidate-dir")
    if args.command == "run" and args.candidate_dir is not None:
        parser.error("run creates its own isolated candidate directory")
    if args.reference_dir and args.reference_ref:
        parser.error("choose --reference-dir or --reference-ref, not both")
    if not (0 <= args.atol < float('inf') and 0 <= args.rtol < float('inf')):
        parser.error("tolerances must be finite and nonnegative")
    if args.workers is not None and args.workers < 1:
        parser.error("workers must be positive")
    config = json.loads(args.config.read_text())
    paths = artifact_paths(config)
    if config.get("schema_version") != 1 or not paths:
        parser.error("configuration must use schema_version=1 and declare at least one artifact")
    for p in paths + config.get("inputs", []) + config.get("coverage_shapefiles", []):
        _safe_relative(p)
    if not set(config.get("coverage_shapefiles", [])).issubset(config["shapefiles"]):
        parser.error("coverage_shapefiles must be declared in shapefiles")
    repo = args.repo.resolve()
    now = datetime.now(timezone.utc)
    started = time.monotonic()
    output = (args.output or repo / "regression-runs" / now.strftime("%Y%m%dT%H%M%S.%fZ")).resolve()
    output.mkdir(parents=True, exist_ok=False)
    print(f"Report directory: {output}", flush=True)
    reference = args.reference_dir.resolve() if args.reference_dir else output / "reference"
    revision = args.reference_ref or config["reference_commit"]
    reference_id = str(reference) if args.reference_dir else export_reference(repo, revision, paths, reference)
    settings = dict(config["settings"])
    if args.workers:
        settings["DASK_NUM_WORKERS"] = str(args.workers)
    manifest = {
        "schema_version": 1,
        "started_utc": now.isoformat(),
        "reference": reference_id,
        "reference_kind": "directory" if args.reference_dir else "git_commit",
        "reference_historical_environment": "unknown",
        "reference_sha256": hashes(reference, paths),
        "candidate_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        "candidate_worktree_status": git(repo, "status", "--short").decode(),
        "settings": settings,
        "baseline_config": config,
        "baseline_config_sha256": sha256(args.config),
        "environment": environment(),
        "runner": args.runner if args.command == "run" else "compare existing artifacts",
        "comparison_source_sha256": hashes(repo, [str(p.relative_to(repo)) for p in sorted((repo / "regression").glob("*.py"))]),
        "coverage_requested": not args.skip_coverage,
    }
    context = None
    generation_error = None
    write_json(output / "manifest.json", manifest)
    if args.command == "run":
        candidate = output / "candidate"
        candidate.mkdir()
        try:
            for relative in config["inputs"]:
                source, target = repo / relative, candidate / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copyfile(source, target)
            input_paths = [str(p.relative_to(candidate)) for p in candidate.rglob("*") if p.is_file()]
            manifest["input_sha256"] = hashes(candidate, input_paths)
            context = RunContext(repo, candidate, output, config, settings, args.timeout)
            module, function = args.runner.split(":", 1)
            # Allows an in-repository module adapter as well as installed packages.
            sys.path.insert(0, str(repo))
            runner = getattr(importlib.import_module(module), function)
            import inspect
            runner_source = inspect.getsourcefile(runner)
            if runner_source:
                manifest["runner_source"] = {"path": runner_source, "sha256": sha256(runner_source)}
            runner(context)
        except Exception:
            generation_error = traceback.format_exc()
            print(generation_error, file=sys.stderr)
    else:
        candidate = args.candidate_dir.resolve()
        manifest["input_sha256"] = None
        manifest["candidate_provenance_note"] = "Existing artifact directory; producing environment not inferred from comparison environment."
    if context:
        manifest["stages"] = context.stages
        manifest["executed_source_sha256"] = context.sources
    manifest["candidate_sha256"] = hashes(candidate, paths)
    artifacts, coverage, auxiliary = compare_artifacts(
        reference, candidate, config, output, args.atol, args.rtol, not args.skip_coverage
    )
    passed = generation_error is None and all(r["passed"] for r in artifacts.values())
    if args.require_byte_identical:
        passed &= all(r.get("byte_identical", False) for r in artifacts.values())
    # Auxiliary comparisons are only gating when both sides supply a reference.
    passed &= all(r.get("passed", True) for r in auxiliary.values())
    if not args.skip_coverage:
        passed &= all("error" not in m for pair in coverage.values() for m in pair.values())
    report = {"schema_version": 1, "passed": bool(passed), "manifest": manifest,
              "policy": {"atol": args.atol, "rtol": args.rtol, "require_byte_identical": args.require_byte_identical},
              "generation_error": generation_error, "artifacts": artifacts, "coverage": coverage,
              "auxiliary_raw_masks": auxiliary, "seconds": time.monotonic() - started}
    manifest["seconds"] = report["seconds"]
    write_json(output / "manifest.json", manifest)
    write_report(output, report)
    print(f"{'PASS' if passed else 'FAIL'}: {output / 'report.md'} ({report['seconds']:.1f}s)", flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
