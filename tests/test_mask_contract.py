"""Analytic mask cases exercised against the current production notebook functions.

Only the loader/``rasterize`` adapter needs changing when these functions move to
the production Python package. Expected results are independent of the algorithm.
"""

import ast
import json
import logging
from pathlib import Path
import time
import unittest

from dask import delayed
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.mask import mask
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import transform as shapely_transform


NOTEBOOK = Path(__file__).resolve().parents[1] / 'generate_mask.ipynb'


def notebook_function(name, scope):
    cells = json.loads(NOTEBOOK.read_text())['cells']
    definitions = [node for cell in cells if cell['cell_type'] == 'code'
                   for node in ast.parse(''.join(cell['source'])).body
                   if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(definitions) != 1:
        raise AssertionError(f'Expected exactly one production definition of {name}')
    tree = ast.Module(body=definitions, type_ignores=[])
    exec(compile(tree, str(NOTEBOOK), 'exec'), scope)
    return scope[name]


def rasterize(geometry, bounds=(0, 0, 2, 2), width=2, height=2):
    affine = rasterio.transform.from_bounds(*bounds, width, height)
    base = np.ones((height, width), dtype=np.float32)
    profile = {'driver': 'GTiff', 'width': width, 'height': height, 'count': 1,
               'dtype': base.dtype, 'crs': 'EPSG:4326', 'transform': affine, 'nodata': np.nan}
    scope = {**globals(), 'transform': affine, 'base_raster': base, 'raster_polygon': box(*bounds)}
    function = notebook_function('rasterize_region', scope)
    return function(geometry, 'fixture', profile, height, width, 0, 1).compute(scheduler='synchronous')


class MaskContractTests(unittest.TestCase):
    def test_fully_covered_cell_within_grid(self):
        np.testing.assert_array_equal(rasterize(box(0, 0, 1, 1)), [[0, 0], [1, 0]])

    @unittest.expectedFailure
    def test_full_grid_coverage_known_empty_complement_bug(self):
        # Existing notebook passes an empty complement to rasterio.mask, which
        # raises IndexError. Keep the intended contract visible without fixing
        # production behaviour during test setup. An eventual fix becomes an
        # unexpected success until this explicit marker is removed.
        np.testing.assert_array_equal(rasterize(box(0, 0, 2, 2)), np.ones((2, 2)))

    def test_region_outside_grid(self):
        np.testing.assert_array_equal(rasterize(box(3, 3, 4, 4)), np.zeros((2, 2)))

    def test_half_cell(self):
        actual = rasterize(box(0, 0, .5, 1), bounds=(0, 0, 1, 1), width=1, height=1)
        np.testing.assert_array_equal(actual, [[.5]])

    def test_hole(self):
        geometry = box(0, 0, 1, 1).difference(box(.25, .25, .75, .75))
        actual = rasterize(geometry, bounds=(0, 0, 1, 1), width=1, height=1)
        np.testing.assert_array_equal(actual, [[.75]])

    def test_island_inside_cell(self):
        actual = rasterize(box(.25, .25, .5, .5), bounds=(0, 0, 1, 1), width=1, height=1)
        np.testing.assert_array_equal(actual, [[.0625]])

    def test_adjacent_regions_sum_to_full_cell(self):
        left = rasterize(box(0, 0, .25, 1), bounds=(0, 0, 1, 1), width=1, height=1)
        right = rasterize(box(.25, 0, 1, 1), bounds=(0, 0, 1, 1), width=1, height=1)
        np.testing.assert_array_equal(left, [[.25]])
        np.testing.assert_array_equal(right, [[.75]])
        np.testing.assert_array_equal(left + right, [[1]])

    def test_multipart(self):
        geometry = MultiPolygon([box(0, 0, .25, 1), box(.75, 0, 1, 1)])
        actual = rasterize(geometry, bounds=(0, 0, 1, 1), width=1, height=1)
        np.testing.assert_array_equal(actual, [[.5]])

    def test_longitude_split(self):
        function = notebook_function('shift_longitude', dict(globals()))
        actual = function(box(-.5, 0, .5, 1), (-180, -90, 180, 90), split_lon=-.25)
        expected = box(359.5, 0, 359.75, 1).union(box(-.25, 0, .5, 1))
        self.assertTrue(actual.equals(expected))

    def test_antimeridian_parts_join_after_shift(self):
        function = notebook_function('shift_longitude', dict(globals()))
        geometry = MultiPolygon([box(-180, 0, -179, 1), box(179, 0, 180, 1)])
        actual = function(geometry, (-180, -90, 180, 90), split_lon=-.25)
        self.assertTrue(actual.equals(box(179, 0, 181, 1)))

    def test_current_normalization_including_uncovered_cell(self):
        cells = json.loads(NOTEBOOK.read_text())['cells']
        sources = [''.join(c['source']) for c in cells if c['cell_type'] == 'code'
                   and ''.join(c['source']).startswith('if normalize_mask:')]
        self.assertEqual(len(sources), 1)
        original = np.array([[[.25, 0]], [[.25, 0]]], dtype=np.float32)
        scope = {'normalize_mask': True, 'raster_3d': original, 'logging': logging}
        with np.errstate(invalid='ignore', divide='ignore'):
            exec(compile(sources[0], str(NOTEBOOK), 'exec'), scope)
        np.testing.assert_array_equal(scope['raster_3d_normalized'], [[[.5, np.nan]], [[.5, np.nan]]])
        np.testing.assert_array_equal(scope['raster_3d'], original)


if __name__ == '__main__':
    unittest.main()
