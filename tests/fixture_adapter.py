"""Exercise the future module-runner contract without any notebook dependencies."""

from tests.test_regression import netcdf_fixture


def run(context):
    path = context.workspace / context.config["netcdf"][0]
    path.parent.mkdir(parents=True, exist_ok=True)
    netcdf_fixture(path, compression=True)
    context.stages.append({"name": "fixture-module", "status": "passed", "seconds": 0})


def failing(context):
    raise RuntimeError("Intentional fixture generation failure")
