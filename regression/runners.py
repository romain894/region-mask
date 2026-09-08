"""Replaceable producers. Comparators know nothing about notebooks or modules.

A runner is a callable ``run(context: RunContext) -> None``. It reads the staged
inputs and writes the configured artifact paths under ``context.workspace``.
Select another implementation with ``--runner your_package:function``.
"""

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .common import sha256, write_json


@dataclass
class RunContext:
    repo: Path
    workspace: Path
    report_dir: Path
    config: dict
    settings: dict
    timeout: int = 1800
    stages: list = field(default_factory=list)
    sources: dict = field(default_factory=dict)


NOTEBOOKS = (
    "generate_shp_countries_ne_10m.ipynb",
    "generate_shp_oceans_ne_10m.ipynb",
    "merge_shp_ne_10m.ipynb",
    "generate_shp_land_ocean_ne_10m.ipynb",
    "generate_mask.ipynb",
)


def notebook_runner(context):
    """Execute original computation cells in fresh kernels using the current Python.

    Only the mask notebook's post-export illustration cells are omitted: they
    assume an Italy region that does not exist in the land/ocean product.
    No geometry, numeric computation or export cell is rewritten.
    """
    import nbformat
    from jupyter_client import AsyncKernelManager
    from nbclient import NotebookClient

    work = context.workspace
    work.mkdir(parents=True, exist_ok=True)
    (work / ".env").write_text("# Regression configuration is supplied explicitly by the runner.\n")
    env = {
        **context.settings,
        "NE_ADMIN_COUNTRIES_PATH": "data/ne_10m/ne_10m_admin_0_countries/ne_10m_admin_0_countries.shp",
        "NE_GEO_MARINE_POLYS_PATH": "data/ne_10m/ne_10m_geography_marine_polys/ne_10m_geography_marine_polys.shp",
        "NE_GEO_OCEAN_PATH": "data/ne_10m/ne_10m_ocean/ne_10m_ocean.shp",
        "CODES_ID_PATH": "data/codes_id.csv",
        "COUNTRIES_FROM_NE_PATH": context.config["shapefiles"][0],
        "OCEANS_FROM_NE_PATH": context.config["shapefiles"][1],
        "NE_COUNTRIES_OCEANS_PATH": context.config["shapefiles"][2],
        "NE_LAND_OCEAN_PATH": context.config["shapefiles"][3],
        "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(work / ".matplotlib"),
        "IPYTHONDIR": str(work / ".ipython"),
    }
    sources = context.report_dir / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    for name in NOTEBOOKS:
        shutil.copyfile(context.repo / name, sources / name)
        context.sources[name] = sha256(sources / name)

    def execute(name, label, extra=None, mask=False):
        original = nbformat.read(sources / name, as_version=4)
        cells = []
        export_found = False
        for cell in original.cells:
            # Recreate cells to drop old execution counts, outputs and widget state.
            if cell.cell_type == "code":
                cells.append(nbformat.v4.new_code_cell(cell.source))
                if mask and "gdf.drop(shape_file_geometry_field, axis=1).to_csv(csv_file_path)" in cell.source:
                    export_found = True
                    break
            elif cell.cell_type == "markdown":
                cells.append(nbformat.v4.new_markdown_cell(cell.source))
        if mask and not export_found:
            raise RuntimeError("Mask export marker changed; update the notebook adapter explicitly")
        bootstrap = (
            "import os, webbrowser\n"
            f"os.environ.update({{k: str(v) for k, v in {env | (extra or {})!r}.items()}})\n"
            "webbrowser.open = lambda *args, **kwargs: False\n"
        )
        cells.insert(0, nbformat.v4.new_code_cell(bootstrap))
        if mask:
            # Auxiliary diagnostic output, with no claim of equivalence to an unavailable raw baseline.
            cells.append(nbformat.v4.new_code_cell(
                "from pathlib import Path\n"
                "Path('diagnostics').mkdir(exist_ok=True)\n"
                "_reg_raw = da.copy(data=raster_3d)\n"
                "_reg_raw.attrs = dict(da.attrs, regression_stage='before_normalization')\n"
                "_reg_raw.to_netcdf(Path('diagnostics') / ('raw_' + Path(mask_file_path).name), "
                "engine='netcdf4', encoding=encoding)\n"
                "client.close()\ncluster.close()\n"
            ))
        notebook = nbformat.v4.new_notebook(cells=cells)
        manager = AsyncKernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
        stage = {"name": label, "notebook": name, "status": "running"}
        context.stages.append(stage)
        started = time.monotonic()
        print(f"Generating {label} ...", flush=True)
        def cell_started(cell, cell_index, **kwargs):
            stage["current_cell"] = cell_index
            stage["current_cell_first_line"] = cell.source.splitlines()[0] if cell.source else ""
            write_json(context.report_dir / "stages.json", context.stages)

        client = NotebookClient(notebook, km=manager, timeout=context.timeout, startup_timeout=60,
                                resources={"metadata": {"path": str(work)}}, record_timing=True,
                                on_cell_start=cell_started)
        try:
            log_dir = context.report_dir / "execution"
            log_dir.mkdir(exist_ok=True)
            with (log_dir / f"{label}.kernel.log").open("w") as stream:
                client.execute(cwd=str(work), cleanup_kc=True,
                               env={**os.environ, **{k: str(v) for k, v in (env | (extra or {})).items()}},
                               stdout=stream, stderr=subprocess.STDOUT)
            stage["status"] = "passed"
        except Exception as exc:
            stage.update(status="failed", error=str(exc))
            raise
        finally:
            stage["seconds"] = round(time.monotonic() - started, 3)
            # A supplied KernelManager is not owned by nbclient, so close it explicitly.
            if manager.has_kernel:
                import asyncio
                asyncio.run(manager.shutdown_kernel(now=True))
            log_dir = context.report_dir / "execution"
            log_dir.mkdir(exist_ok=True)
            nbformat.write(notebook, log_dir / f"{label}.ipynb")
            write_json(context.report_dir / "stages.json", context.stages)
        print(f"Generated {label} ({stage['seconds']:.1f}s)", flush=True)

    for name, label in zip(NOTEBOOKS[:4], ["countries", "oceans", "countries_oceans", "land_ocean"]):
        execute(name, label)
    for path, label in [(context.config["shapefiles"][2], "mask_countries_oceans"),
                        (context.config["shapefiles"][3], "mask_land_ocean")]:
        execute(NOTEBOOKS[4], label, {"MASK_SHAPE_FILE_PATH": path}, mask=True)
