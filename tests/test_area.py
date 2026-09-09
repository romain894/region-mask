import unittest
import numpy as np
from pyproj import Transformer
from shapely.geometry import Polygon, box
from regression.area import area_measurement
from regression.geometry import area_km2, compare_geometry


class AreaTests(unittest.TestCase):
    def test_rectangle_against_exact_equal_area_projection(self):
        project = Transformer.from_crs(4326, '+proj=cea +datum=WGS84', always_xy=True)
        for lat in [-89, 0, 55, 88]:
            x0,y0 = project.transform(12, lat)
            x1,y1 = project.transform(13, lat+1)
            self.assertAlmostEqual(area_km2(box(12,lat,13,lat+1)),
                                   (x1-x0)*(y1-y0)/1e6, places=6)

    def test_world_not_shortest_geodesic_or_half_globe(self):
        self.assertAlmostEqual(area_km2(box(-180,-90,180,90)), 510065621.724, delta=.01)

    def test_collinear_sliver_has_zero_area(self):
        p=Polygon([(21,55),(21.125,55.25),(21.25,55.5),(21,55)])
        self.assertEqual(area_km2(p),0)

    def test_tiny_sliver_is_retained(self):
        p=Polygon([(21,55),(21.125,55.25+1e-12),(21.25,55.5),(21,55)])
        m=area_measurement(p)
        self.assertGreater(m['area_km2'],0)
        self.assertLess(m['area_km2'],1e-8)
        self.assertIn('area_numerical_uncertainty_km2',m)

    def test_ring_order_and_collinear_vertices(self):
        a=Polygon([(0,0),(2,1),(0,2)])
        b=Polygon([(0,2),(2,1),(1,.5),(0,0)])
        self.assertAlmostEqual(area_km2(a),area_km2(b),places=8)

    def test_holes_and_additivity(self):
        outer=box(0,50,2,52); hole=box(.5,50.5,1,51)
        self.assertAlmostEqual(area_km2(outer.difference(hole))+area_km2(hole),area_km2(outer),places=7)
        self.assertAlmostEqual(area_km2(box(0,50,1,52))+area_km2(box(1,50,2,52)),area_km2(outer),places=7)

    def test_net_transfer_closes_and_does_not_relax_acceptance(self):
        r=compare_geometry(box(0,0,1,1),box(.000000001,0,1,1))
        self.assertFalse(r['passed'])
        self.assertGreater(r['removed_km2'],0)
        self.assertEqual(r['net_transfer_km2'],r['added_km2']-r['removed_km2'])
