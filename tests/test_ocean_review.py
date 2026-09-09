import unittest
import geopandas as gpd
from shapely.geometry import box
from regression.ocean_review import close_seam, legacy_partition, compare_frames, change_table


class OceanReviewTests(unittest.TestCase):
    def test_seam_changes_labels_not_input(self):
        g=gpd.GeoDataFrame({'parent_reg':['a']},geometry=[box(179,0,179.999897,1)],crs=4326)
        result=close_seam(g)
        self.assertEqual(result.total_bounds[2],180)
        self.assertEqual(g.total_bounds[2],179.999897)

    def test_legacy_control_conserves_simple_water(self):
        water=gpd.GeoDataFrame(geometry=[box(0,0,1,1)],crs=4326)
        labels=gpd.GeoDataFrame({'parent_reg':['a','b']},geometry=[box(0,0,.4,1),box(.6,0,1,1)],crs=4326)
        result=legacy_partition(water,labels)
        self.assertTrue(result.union_all().equals(water.geometry.iloc[0]))

    def test_membership_changes_cannot_be_hidden(self):
        a=gpd.GeoDataFrame({'parent_reg':['a']},geometry=[box(0,0,1,1)],crs=4326)
        with self.assertRaisesRegex(ValueError,'membership'):
            compare_frames(a,a.assign(parent_reg='b'))
        metrics=compare_frames(a,a)
        self.assertEqual(metrics['a']['symmetric_difference_km2'],0)
        self.assertIn('Numerical uncertainty','\n'.join(change_table(metrics)))
