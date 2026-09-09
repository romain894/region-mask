"""Scientific contracts for ocean assignment, independent of saved artifacts."""

import unittest

import geopandas as gpd
import shapely
from shapely.geometry import LineString, Point, Polygon, box

from region_mask.ocean_partition import (
    apply_gibraltar, ocean_domain, partition_ocean, polygonal, validate_partition,
)


def frame(labels, geometries):
    return gpd.GeoDataFrame({"parent_reg": labels}, geometry=geometries, crs=4326)


class OceanPartitionTests(unittest.TestCase):
    def setUp(self):
        self.water = box(0, 0, .04, .04)
        self.marine = frame(["west", "east"],
                            [box(0, 0, .015, .04), box(.025, 0, .04, .04)])

    def test_ambiguous_gap_is_split_not_awarded_to_first_region(self):
        result = partition_ocean(self.water, self.marine, gibraltar=False).set_index("parent_reg")
        self.assertTrue(result.loc["west", "geometry"].covers(Point(.018, .02)))
        self.assertTrue(result.loc["east", "geometry"].covers(Point(.022, .02)))
        self.assertLess(result.union_all().symmetric_difference(self.water).area, 1e-14)
        self.assertLess(result.geometry.iloc[0].intersection(result.geometry.iloc[1]).area, 1e-14)

    def test_row_order_does_not_change_assignment(self):
        a = partition_ocean(self.water, self.marine, gibraltar=False)
        b = partition_ocean(self.water, self.marine.iloc[::-1], gibraltar=False)
        self.assertEqual(a.parent_reg.tolist(), b.parent_reg.tolist())
        for x, y in zip(a.geometry, b.geometry):
            self.assertTrue(x.equals(y))

    def test_coast_holes_and_tiny_water_components_survive(self):
        island = box(.001, .001, .002, .002)
        tiny_water = box(.05, .01, .050001, .010001)
        water = self.water.difference(island).union(tiny_water)
        result = partition_ocean(water, self.marine, gibraltar=False)
        self.assertLess(result.union_all().symmetric_difference(water).area, 1e-14)
        self.assertFalse(result.union_all().intersects(island.representative_point()))
        self.assertTrue(result.union_all().covers(tiny_water.representative_point()))

    def test_unmapped_and_conflicting_labels_fail(self):
        with self.assertRaisesRegex(ValueError, "mapped"):
            partition_ocean(self.water, frame([None], [self.water]), gibraltar=False)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            partition_ocean(self.water, frame(["a", "b"], [self.water, self.water]), gibraltar=False)

    def test_gibraltar_relabels_source_slivers_and_preserves_water(self):
        water = box(-6.2, 35.7, -5.2, 36.3).difference(box(-5.8, 36.1, -5.7, 36.2))
        regions = {"North Atlantic Ocean": water, "Mediterranean Region": Polygon()}
        result = apply_gibraltar(regions, water)
        self.assertTrue(result["North Atlantic Ocean"].covers(Point(-6.1, 35.95)))
        self.assertTrue(result["Mediterranean Region"].covers(Point(-5.6, 35.95)))
        validate_partition(water, result)

    def test_gibraltar_leaves_other_locations_unchanged(self):
        regions = {"North Atlantic Ocean": box(-40, 0, -30, 10),
                   "Mediterranean Region": box(10, 30, 20, 40)}
        water = shapely.union_all(list(regions.values()))
        result = apply_gibraltar(regions, water)
        for name in regions:
            self.assertTrue(result[name].equals(regions[name]))

    def test_country_alignment_does_not_flood_missing_admin_island(self):
        island = box(.01, .01, .02, .02)
        ocean = frame(["ocean"], [self.water.difference(island)])
        country = frame(["country"], [box(0, 0, .005, .04)])
        water = ocean_domain(ocean, country)
        self.assertEqual(water.intersection(country.geometry.iloc[0]).area, 0)
        self.assertEqual(water.intersection(island).area, 0)
        self.assertTrue(water.equals(ocean.geometry.iloc[0].difference(country.geometry.iloc[0])))

    def test_invalid_inputs_retain_both_polygonal_lobes(self):
        bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
        repaired = polygonal(bowtie)
        self.assertTrue(repaired.is_valid)
        self.assertAlmostEqual(repaired.area, .5)

    def test_wrong_crs_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "EPSG:4326"):
            ocean_domain(frame(["ocean"], [self.water]).to_crs(3857))

    def test_non_area_intersections_are_discarded(self):
        self.assertTrue(polygonal(LineString([(0, 0), (1, 1)])).is_empty)
        self.assertTrue(polygonal(Point(0, 0)).is_empty)

    def test_coarse_seam_does_not_leave_water_unassigned(self):
        water = box(179.9, 0, 180, .04)
        marine = frame(["east"], [box(179.8, 0, 179.999897, .04)])
        result = partition_ocean(water, marine, gibraltar=False)
        self.assertTrue(result.union_all().equals(water))

    def test_positive_area_loss_and_overlap_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "footprint"):
            validate_partition(self.water, {"a": box(0, 0, .01, .04)})
        with self.assertRaisesRegex(ValueError, "overlapping"):
            validate_partition(self.water, {"a": self.water, "b": box(0, 0, .01, .04)})


if __name__ == "__main__":
    unittest.main()
