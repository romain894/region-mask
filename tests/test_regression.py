"""Independent tests of the comparators; no production notebook imports."""

import json
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest

import geopandas as gpd
import netCDF4
import numpy as np
from shapely.geometry import MultiPolygon, Polygon, box

from regression.common import export_reference, plain
from regression.geometry import compare_geometry, compare_shapefiles, coverage_metrics
from regression.netcdf import compare_netcdf, compare_values
from regression.__main__ import compare_artifacts
from regression.__main__ import main
from regression.report import write_report


class GeometryTests(unittest.TestCase):
    def test_same_area_different_location_fails(self):
        result = compare_geometry(box(0, 0, 1, 1), box(2, 0, 3, 1))
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(result["net_area_change_km2"], 0, places=6)
        self.assertGreater(result["symmetric_difference_km2"], 20000)

    def test_ring_start_and_orientation_are_not_changes(self):
        a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        b = Polygon([(1, 1), (1, 0), (0, 0), (0, 1)])
        self.assertTrue(compare_geometry(a, b)["passed"])

    def test_redundant_collinear_vertex_is_spatially_equal(self):
        a = box(0, 0, 1, 1)
        b = Polygon([(0, 0), (0.5, 0), (1, 0), (1, 1), (0, 1)])
        result = compare_geometry(a, b)
        self.assertTrue(result["passed"])
        self.assertFalse(result["structural_equal"])

    def test_lost_tiny_island_is_not_hidden_by_total_area(self):
        mainland, island = box(0, 0, 10, 10), box(12, 0, 12.00001, 0.00001)
        result = compare_geometry(MultiPolygon([mainland, island]), MultiPolygon([mainland]))
        self.assertFalse(result["passed"])
        self.assertGreater(result["removed_km2"], 0)

    def test_filled_hole_detected(self):
        whole = box(0, 0, 4, 4)
        hole = whole.difference(box(1, 1, 2, 2))
        result = compare_geometry(hole, whole)
        self.assertFalse(result["passed"])
        self.assertEqual(result["reference"]["holes"], 1)
        self.assertEqual(result["candidate"]["holes"], 0)

    def test_invalid_reference_is_not_silently_repaired(self):
        bow = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
        same = compare_geometry(bow, bow)
        self.assertTrue(same["passed"])
        self.assertIsNone(same["spatial_equal"])
        self.assertNotIn("symmetric_difference_km2", same)
        self.assertFalse(compare_geometry(bow, bow.buffer(0))["passed"])


class ArrayTests(unittest.TestCase):
    def test_identical(self):
        self.assertTrue(compare_values(np.array([0, .5, 1]), np.array([0, .5, 1]))["exact_equal"])

    def test_one_float32_ulp_fails_default(self):
        a = np.array([.5], dtype=np.float32)
        b = np.nextafter(a, np.float32(1))
        self.assertFalse(compare_values(a, b)["passed"])
        report = compare_values(a, b, atol=1e-7)
        self.assertTrue(report["passed"])
        self.assertEqual(report["changed_values"], 1)

    def test_tiny_fraction_transition_reported_even_with_tolerance(self):
        result = compare_values(np.array([1e-10]), np.array([0.0]), atol=1e-7)
        self.assertTrue(result["passed"])
        self.assertEqual(result["zero_transitions"], 1)

    def test_missing_pattern_never_tolerated(self):
        self.assertFalse(compare_values(np.array([np.nan]), np.array([0.0]), atol=1)["passed"])
        self.assertTrue(compare_values(np.array([np.nan]), np.array([np.nan]))["passed"])
        a = np.ma.array([10.], mask=[True])
        b = np.ma.array([99.], mask=[True])
        self.assertTrue(compare_values(a, b)["passed"])

    def test_infinity_change_detected(self):
        self.assertFalse(compare_values(np.array([np.inf]), np.array([-np.inf]))["passed"])

    def test_no_broadcast(self):
        self.assertFalse(compare_values(np.zeros((2, 1)), np.zeros((2, 2)))["passed"])

    def test_integer_variables_do_not_use_tolerance(self):
        self.assertFalse(compare_values(np.array([1]), np.array([2]), atol=10)["passed"])

    def test_strings(self):
        self.assertFalse(compare_values(np.array(['NA']), np.array(['XX']))["passed"])

    def test_zero_dimensional_json_values(self):
        self.assertEqual(plain(np.array(2.0)), 2.0)
        self.assertEqual(plain(np.float32(np.nan)), 'nan')


def netcdf_fixture(path, values=None, compression=False, title="reference", region_ids=("NA", "OC")):
    if values is None:
        values = np.array([[[0, .25], [.5, 1]], [[1, .75], [.5, 0]]], dtype=np.float32)
    with netCDF4.Dataset(path, "w") as f:
        for name, size in [("region", 2), ("lat", 2), ("lon", 2)]:
            f.createDimension(name, size)
        f.createVariable("region", str, ("region",))[:] = np.array(region_ids, dtype=object)
        f.createVariable("lat", "f8", ("lat",))[:] = [1, 0]
        f.createVariable("lon", "f8", ("lon",))[:] = [0, 1]
        v = f.createVariable("mask", "f4", ("region", "lat", "lon"), fill_value=np.nan, zlib=compression)
        v[:] = values
        v.crs = "EPSG:4326"
        f.title = title


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def pair(self, **kwargs):
        a, b = self.root / 'a.nc', self.root / 'b.nc'
        netcdf_fixture(a)
        netcdf_fixture(b, **kwargs)
        return compare_netcdf(a, b)

    def test_netcdf_identical(self):
        self.assertTrue(self.pair()["passed"])

    def test_storage_only_change(self):
        result = self.pair(compression=True)
        self.assertTrue(result["passed"])
        self.assertFalse(result["byte_identical"])
        self.assertTrue(result["storage_changes"])

    def test_metadata_only_change(self):
        result = self.pair(title="changed")
        self.assertFalse(result["passed"])
        self.assertTrue(result["variables"]["mask"]["exact_equal"])

    def test_labels_cannot_be_swapped(self):
        self.assertFalse(self.pair(region_ids=("OC", "NA"))["passed"])

    def test_numeric_change_located(self):
        values = np.array([[[0, .25], [.6, 1]], [[1, .75], [.5, 0]]], dtype=np.float32)
        result = self.pair(values=values)
        self.assertFalse(result["passed"])
        mask = result["variables"]["mask"]
        self.assertEqual(mask["changed_values"], 1)
        self.assertEqual(mask["max_diff_coordinates"], {"region": "NA", "lat": 0., "lon": 0.})

    def test_coordinate_tolerance_not_applied(self):
        a, b = self.root / 'a.nc', self.root / 'b.nc'
        netcdf_fixture(a)
        netcdf_fixture(b)
        with netCDF4.Dataset(b, 'a') as f:
            f['lon'][1] = 1.00001
        self.assertFalse(compare_netcdf(a, b, atol=1)["passed"])

    def shapefile(self, name, ids=("NA", "OC"), geometries=None):
        if geometries is None:
            geometries = [box(0, 0, 1, 1), box(1, 0, 2, 1)]
        p = self.root / f'{name}.shp'
        gpd.GeoDataFrame({'ID': ids, 'NAME': ['First', 'Second']}, geometry=geometries, crs=4326).to_file(p)
        return p

    def test_shapefile_swapped_labels(self):
        a, b = self.shapefile('a'), self.shapefile('b', ids=("OC", "NA"))
        self.assertFalse(compare_shapefiles(a, b)["passed"])

    def test_duplicate_ids(self):
        result = compare_shapefiles(self.shapefile('a'), self.shapefile('b', ids=("NA", "NA")))
        self.assertFalse(result["passed"])

    def test_missing_sidecar_fails(self):
        self.shapefile('a')
        self.shapefile('b')
        (self.root / 'b.prj').unlink()
        # Missing products are reportable failures, not crashes or silently skipped tests.
        config = {'shapefiles': ['b.shp'], 'netcdf': [], 'tables': []}
        results, _, _ = compare_artifacts(self.root, self.root, config, self.root, coverage=False)
        self.assertFalse(results['b.shp']['passed'])

    def test_coverage_detects_overlap(self):
        path = self.shapefile('overlap', geometries=[box(0, 0, 2, 1), box(1, 0, 3, 1)])
        self.assertGreater(coverage_metrics(path)['overlap_footprint_km2'], 10000)

    def test_reference_comes_from_commit_not_worktree(self):
        repo = self.root / 'repo'
        repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)
        git('init')
        (repo / 'reference.txt').write_text('trusted')
        git('add', 'reference.txt')
        git('-c', 'user.name=Regression test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
        (repo / 'reference.txt').write_text('modified')
        out = self.root / 'export'
        export_reference(repo, 'HEAD', ['reference.txt'], out)
        self.assertEqual((out / 'reference.txt').read_text(), 'trusted')

    def test_failure_report_is_valid_markdown_and_json(self):
        result = compare_shapefiles(self.shapefile('a'), self.shapefile('b', ids=("NA", "NA")))
        report = {
            'passed': False, 'manifest': {'reference': 'baseline', 'candidate_commit': 'candidate',
                'runner': 'fixture', 'started_utc': '2026-01-01T00:00:00Z', 'settings': {}},
            'policy': {'atol': 0, 'rtol': 0, 'require_byte_identical': False},
            'artifacts': {'bad.shp': result}, 'coverage': {},
        }
        write_report(self.root, report)
        self.assertIn('**FAIL**', (self.root / 'report.md').read_text())
        self.assertFalse(json.loads((self.root / 'metrics.json').read_text())['passed'])

    def test_report_distinguishes_worktree_from_head_and_existing_artifacts(self):
        manifest = {'reference': 'baseline', 'candidate_commit': 'head',
                    'runner': 'regression.runners:module_runner',
                    'started_utc': '2026-01-01T00:00:00Z', 'settings': {}}
        report = {'passed': True, 'manifest': manifest,
                  'policy': {'atol': 0, 'rtol': 0, 'require_byte_identical': False},
                  'artifacts': {}}
        for status, label in [(' M region_mask/mask.py\n', 'uncommitted changes present'),
                              ('', 'clean'), (None, 'unknown (not recorded)')]:
            with self.subTest(status=status):
                manifest['candidate_worktree_status'] = status
                write_report(self.root, report)
                markdown = (self.root / 'report.md').read_text()
                self.assertIn('Repository HEAD (context only): `head`', markdown)
                self.assertIn(f'**{label}**', markdown)
                self.assertIn('generated from working-tree source snapshots', markdown)
                self.assertNotIn('Candidate commit:', markdown)
        manifest['runner'] = 'compare existing artifacts'
        write_report(self.root, report)
        markdown = (self.root / 'report.md').read_text()
        self.assertIn('producing code revision is not inferred', markdown)
        self.assertNotIn('generated from working-tree source snapshots', markdown)

    def test_missing_raw_candidate_is_not_silently_skipped(self):
        reference, candidate = self.root / 'reference', self.root / 'candidate'
        (reference / 'diagnostics').mkdir(parents=True)
        candidate.mkdir()
        netcdf_fixture(reference / 'diagnostics' / 'raw_mask.nc')
        _, _, auxiliary = compare_artifacts(reference, candidate,
            {'shapefiles': [], 'netcdf': [], 'tables': []}, self.root, coverage=False)
        self.assertFalse(auxiliary['raw_mask.nc']['passed'])

    def module_run(self, runner='tests.fixture_adapter:run', strict=False):
        reference = self.root / 'reference'
        (reference / 'data').mkdir(parents=True)
        netcdf_fixture(reference / 'data' / 'mask.nc')
        config = self.root / 'config.json'
        config.write_text(json.dumps({'schema_version': 1, 'reference_commit': 'unused',
            'settings': {}, 'inputs': [], 'shapefiles': [], 'tables': [], 'netcdf': ['data/mask.nc']}))
        output = self.root / 'result'
        args = ['run', '--config', str(config), '--reference-dir', str(reference),
                '--output', str(output), '--runner', runner, '--skip-coverage']
        if strict:
            args.append('--require-byte-identical')
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = main(args)
        return code, json.loads((output / 'metrics.json').read_text())

    def test_python_module_adapter_runs_without_notebooks(self):
        code, report = self.module_run()
        self.assertEqual(code, 0)
        self.assertTrue(report['passed'])
        self.assertFalse(report['artifacts']['data/mask.nc']['byte_identical'])

    def test_cli_strict_file_policy(self):
        code, report = self.module_run(strict=True)
        self.assertEqual(code, 1)
        self.assertFalse(report['passed'])
        self.assertTrue(report['artifacts']['data/mask.nc']['passed'])

    def test_module_failure_still_generates_report(self):
        code, report = self.module_run(runner='tests.fixture_adapter:failing')
        self.assertEqual(code, 1)
        self.assertIn('Intentional fixture generation failure', report['generation_error'])
        self.assertFalse(report['artifacts']['data/mask.nc']['passed'])


if __name__ == '__main__':
    unittest.main()
