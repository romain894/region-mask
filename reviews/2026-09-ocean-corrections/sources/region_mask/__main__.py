"""Command-line access to the same functions used by the marimo notebooks."""

import argparse
import json
import logging
from pathlib import Path

from .pipeline import STAGES, environment_settings, run_stage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=(*STAGES, "all-ne"))
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Root for relative data paths")
    parser.add_argument("--config", type=Path, help="Explicit settings JSON; ignores .env and environment")
    parser.add_argument("--diagnostics-dir", type=Path, help="Also export pre-normalization masks")
    args = parser.parse_args(argv)
    settings = json.loads(args.config.read_text()) if args.config else environment_settings(args.root)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("distributed").setLevel(logging.WARNING)
    logging.getLogger("dask").setLevel(logging.WARNING)
    if args.stage == "all-ne":
        from .pipeline import DEFAULTS

        settings = DEFAULTS | settings
        for stage in ("countries", "oceans", "countries_oceans", "land_ocean"):
            run_stage(stage, root=args.root, settings=settings)
        for key in ("NE_COUNTRIES_OCEANS_PATH", "NE_LAND_OCEAN_PATH"):
            run_stage("mask", root=args.root,
                      settings=settings | {"MASK_SHAPE_FILE_PATH": settings[key]},
                      diagnostics_dir=args.diagnostics_dir)
    else:
        run_stage(args.stage, root=args.root, settings=settings, diagnostics_dir=args.diagnostics_dir)


if __name__ == "__main__":
    main()
