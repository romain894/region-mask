"""Contracts for the new configuration, module adapter and thin interfaces."""

import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from region_mask.pipeline import DEFAULTS, STAGES, environment_settings, run_stage
from regression.runners import NOTEBOOKS, RunContext, module_runner


REPO = Path(__file__).resolve().parents[1]


def load_notebook(name):
    """Load an example by path, without making notebooks an installed package."""
    path = REPO / "notebooks" / (Path(name).stem + ".py")
    spec = importlib.util.spec_from_file_location("example_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipelineTests(unittest.TestCase):
    def test_environment_precedence_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            Path(directory, ".env").write_text("MASK_RESOLUTION=1\nDASK_NUM_WORKERS=2\n")
            os.environ["DASK_NUM_WORKERS"] = "3"
            original = dict(os.environ)
            settings = environment_settings(directory)
            self.assertEqual(settings["MASK_RESOLUTION"], "1")
            self.assertEqual(settings["DASK_NUM_WORKERS"], "3")
            self.assertEqual(settings["MASK_MIN_LON"], DEFAULTS["MASK_MIN_LON"])
            self.assertEqual(dict(os.environ), original)

    def test_land_ocean_uses_original_ocean(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("region_mask.land_ocean.generate_land_ocean") as generate:
                run_stage("land_ocean", root=directory)
                self.assertEqual(generate.call_args.args[1], Path(directory) / DEFAULTS["NE_GEO_OCEAN_PATH"])

    def test_mask_settings_are_explicit_and_independent_of_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = {"NORMALIZE_MASK": "false", "MASK_RESOLUTION": "1",
                        "MASK_SHAPE_FILE_PATH": "custom/regions.shp", "DASK_NUM_WORKERS": "2"}
            with patch("region_mask.mask.generate_mask") as generate, patch.dict(os.environ, {"MASK_RESOLUTION": "99"}):
                run_stage("mask", root=directory, settings=settings)
            args, kwargs = generate.call_args
            self.assertEqual(args[0], Path(directory) / "custom/regions.shp")
            self.assertEqual(kwargs["resolution"], 1.0)
            self.assertFalse(kwargs["normalize_mask"])
            self.assertEqual(kwargs["num_workers"], 2)
            self.assertEqual(kwargs["bounds"], (-.25, -89.75, 359.75, 90.25))

    def test_unknown_stage_fails(self):
        with self.assertRaises(ValueError):
            run_stage("typo")

    def test_module_runner_snapshots_sources_and_isolates_all_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = RunContext(REPO, root / "candidate", root / "report", {
                "shapefiles": [DEFAULTS[k] for k in ("COUNTRIES_FROM_NE_PATH", "OCEANS_FROM_NE_PATH",
                                                    "NE_COUNTRIES_OCEANS_PATH", "NE_LAND_OCEAN_PATH")]
            }, {"DASK_NUM_WORKERS": "1"}, timeout=12)
            with patch("regression.runners.subprocess.run") as execute:
                module_runner(context)
            self.assertEqual(execute.call_count, 6)
            self.assertEqual([stage["status"] for stage in context.stages], ["passed"] * 6)
            self.assertIn("region_mask/mask.py", context.sources)
            for call in execute.call_args_list:
                command = call.args[0]
                self.assertEqual(command[command.index("--root") + 1], str(context.workspace))
                self.assertEqual(call.kwargs["cwd"], context.report_dir / "sources")
                self.assertEqual(call.kwargs["timeout"], 12)
            for relative in context.sources:
                self.assertEqual((REPO / relative).read_bytes(), (context.report_dir / "sources" / relative).read_bytes())

    def test_notebook_imports_do_not_generate_or_start_workers(self):
        with patch("region_mask.pipeline.run_stage") as generate, patch("region_mask.mask.LocalCluster") as cluster:
            for name in NOTEBOOKS:
                notebook = load_notebook(name)
                self.assertTrue(hasattr(notebook, "app"))
            generate.assert_not_called()
            cluster.assert_not_called()

    def test_notebook_initial_execution_never_generates(self):
        with patch("region_mask.pipeline.run_stage") as generate:
            for name in NOTEBOOKS:
                with self.subTest(notebook=name):
                    notebook = load_notebook(name)
                    _, definitions = notebook.app.run()
                    self.assertNotIn("result", definitions)
            generate.assert_not_called()

    def test_notebook_buttons_call_shared_stage_and_render_results(self):
        import geopandas as gpd
        import numpy as np
        from shapely.geometry import box
        import xarray as xr
        from region_mask.mask import MaskResult

        regions = gpd.GeoDataFrame({"ID": ["fixture"], "NAME": ["Fixture"]},
                                   geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
        array = xr.DataArray(np.ones((1, 2, 2), dtype=np.float32),
                             dims=("region", "lat", "lon"),
                             coords={"region": ["fixture"], "lat": [0.5, 1.5], "lon": [0.5, 1.5]})
        mask_result = MaskResult(array, array, regions, Path("fixture.nc"), Path("fixture.csv"))
        for name, stage in zip(NOTEBOOKS, STAGES):
            with self.subTest(notebook=name):
                result = mask_result if stage == "mask" else regions
                notebook = load_notebook(name)
                with patch("region_mask.pipeline.run_stage", return_value=result) as generate:
                    _, definitions = notebook.app.run(defs={
                        "generate": SimpleNamespace(value=True), "settings": dict(DEFAULTS),
                    })
                generate.assert_called_once_with(stage, root=REPO, settings=DEFAULTS)
                self.assertIs(definitions["result"], result)

    def test_stage_names_are_stable(self):
        self.assertEqual(STAGES, ("countries", "oceans", "countries_oceans", "land_ocean", "mask"))


if __name__ == "__main__":
    unittest.main()
