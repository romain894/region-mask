"""Verify a wheel from outside the checkout, using existing scientific dependencies."""

import argparse
from pathlib import Path
import subprocess
import sysconfig
import tempfile
import tomllib
import venv
from zipfile import ZipFile
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path, nargs="?", help="Defaults to this project's current dist/ wheel")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    project = tomllib.loads((repo / "pyproject.toml").read_text())["project"]
    wheel = (args.wheel or repo / "dist" / f"region_mask-{project['version']}-py3-none-any.whl").resolve()
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "region_mask/mask.py" in names
        assert not any(name.startswith("region_mask/notebooks/") for name in names)
        assert "region_mask/notebook.py" not in names
        assert all(name.startswith("region_mask/") or ".dist-info/" in name for name in names), names

    sdist = wheel.parent / f"region_mask-{project['version']}.tar.gz"
    with tarfile.open(sdist) as archive:
        for notebook in (repo / "notebooks").glob("*.py"):
            member = f"region_mask-{project['version']}/notebooks/{notebook.name}"
            assert archive.extractfile(member).read() == notebook.read_bytes(), member

    with tempfile.TemporaryDirectory(prefix="region-mask-wheel-") as directory:
        root = Path(directory)
        environment = root / "venv"
        # Avoid downloading/re-resolving scientific dependencies for an artifact test.
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin" / "python"
        site = Path(subprocess.check_output(
            [str(python), "-I", "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True, cwd=root).strip())
        # Add dependency files, without activating the checkout's editable .pth
        # hooks. The wheel installed into this venv remains first on sys.path.
        (site / "smoke_dependencies.pth").write_text(sysconfig.get_path("purelib") + "\n")
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", "--ignore-installed", str(wheel)],
                       cwd=root, check=True)
        subprocess.run([str(python), "-I", "-c", '''
from pathlib import Path
import sys
import region_mask
from region_mask.countries import generate_countries
from region_mask.oceans import generate_oceans
from region_mask.land_ocean import generate_land_ocean
from region_mask.merge import generate_merge
from region_mask.pipeline import run_stage
from region_mask.mask import rasterize_region
import numpy as np
from rasterio.transform import from_bounds
from shapely.geometry import box

assert Path(region_mask.__file__).is_relative_to(Path(sys.prefix)), region_mask.__file__
transform = from_bounds(0, 0, 1, 1, 1, 1)
base = np.ones((1, 1), dtype=np.float32)
profile = dict(driver="GTiff", width=1, height=1, count=1, dtype=base.dtype,
               crs="EPSG:4326", transform=transform, nodata=np.nan)
actual = rasterize_region(box(0, 0, .5, 1), "fixture", profile, 1, 1, 0, 1,
                          base, transform, box(0, 0, 1, 1)).compute(scheduler="synchronous")
np.testing.assert_array_equal(actual, [[.5]])
print("Installed wheel imports and analytic raster check passed:", region_mask.__file__)
'''], cwd=root, check=True)
        subprocess.run([str(environment / "bin" / "region-mask"), "--help"], cwd=root, check=True)
        assert not (environment / "bin" / "region-mask-notebook").exists()
    print("Wheel smoke test passed.")


if __name__ == "__main__":
    main()
