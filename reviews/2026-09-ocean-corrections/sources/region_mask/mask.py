"""Shared fractional rasterization, extracted without scientific changes.

Fractions remain planar (longitude/latitude) intersection areas. The historical
empty-complement failure and uncovered-cell normalization are intentional here.
"""

from dataclasses import dataclass
from pathlib import Path
import logging
import time

import dask
from dask import delayed
from dask.distributed import Client, LocalCluster
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.io import MemoryFile
from shapely.geometry import box, Polygon
from shapely.ops import transform as shapely_transform
import xarray as xr

def shift_longitude(geom, _bounds, split_lon=-0.25):
    """
    Splits geometries crossing the 0.25 meridian and shifts the
    left-hand part to the 360 range.
    """
    if geom is None:
        return None

    # Define the two parts of the world based on the 0.25 split line
    # Left part: from -180 up to the split line
    # Right part: from the split line up to 180
    left_half = box(_bounds[0], _bounds[1], split_lon, 90)
    right_half = box(split_lon, -90, _bounds[2], _bounds[3])

    # Intersect the geometry with each half to cut it
    part_to_shift = geom.intersection(left_half)
    part_to_keep = geom.intersection(right_half)

    # Shift the part that was to the left of the split line by 360 degrees
    if not part_to_shift.is_empty:
        part_to_shift = shapely_transform(lambda x, y, z=None: (x + 360, y), part_to_shift)

    # Combine the parts back together
    if part_to_shift.is_empty:
        return part_to_keep
    if part_to_keep.is_empty:
        return part_to_shift

    return part_to_shift.union(part_to_keep)


@delayed
def rasterize_region(shape, region_id, profile, height, width, i, n_regions, base_raster, transform, raster_polygon):
    start_time = time.time()
    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            # write a raster with dummy data in the temporary file, this is needed for rasterio to calculate the mask
            dataset.write(base_raster, 1)
            logging.info(f"Generating raster mask for row region id: {region_id} ({i + 1}/{n_regions})")

            logging.debug(f"Region id {region_id}: checking shape validity...")
            # Ensure shape is valid
            if not shape.is_valid:
                shape = shape.buffer(0)
                logging.warning(f"Shape not valid for region id: {region_id}")

            logging.debug(f"Region id {region_id}: handling MultiPolygon geometries...")
            # Handle MultiPolygon geometries
            if shape.geom_type == 'MultiPolygon':
                shapes = list(shape.geoms)
            else:
                shapes = [shape]

            logging.debug(f"Region id {region_id}: creating the complementary geometry...")
            # Create the complementary geometry (outside the shape)
            complementary_shape = raster_polygon.difference(shape)

            logging.debug(f"Region id {region_id}: creating the mask for fully inside the original shape...")
            # Mask for fully inside the original shape (all_touched=True)
            mask_inside, _ = mask(
                dataset, [shape],
                all_touched=True, invert=False, filled=True, nodata=0
            )

            logging.debug(f"Region id {region_id}: creating the mask for fully outside the original shape...")
            # Mask for fully outside the original shape (fully inside the complementary shape)
            mask_outside, _ = mask(
                dataset, [complementary_shape],
                all_touched=True, invert=False, filled=True, nodata=0
            )

            logging.debug(f"Region id {region_id}: processing masks with numpy...")
            # Fully inside: pixels with value 1 in mask_inside
            fully_inside = np.isclose(mask_inside[0], 1, atol=1e-6)

            # Fully outside: pixels with value 1 in mask_outside
            fully_outside = np.isclose(mask_outside[0], 1, atol=1e-6)

            raster_2d = np.full((height, width), np.nan, dtype=np.float32)

            # Set values: 1 (fully in), 0 (fully out), NaN (partially in)
            raster_2d[:, :] = np.where(fully_inside, 1, 0)
            raster_2d[:, :][fully_inside & fully_outside] = np.nan

            logging.debug(f"Region id {region_id}: calculating fractional area for partially covered pixels...")
            # Calculate fractional area for partially covered pixels (NaN)
            for y in range(height):
                # The time.sleep(0) allows for async tasks of Dask to run on the worker and thus keep the worker marked as 
                # alive (it avoids Dask killing the worker after timeout)
                time.sleep(0)
                for x in range(width):
                    if np.isnan(raster_2d[y, x]):
                        # Get pixel bounds using the affine transform
                        x0, y0 = transform * (x, y)
                        x1, y1 = transform * (x + 1, y + 1)

                        pixel_bounds = box(
                            min(x0, x1),
                            min(y0, y1),
                            max(x0, x1),
                            max(y0, y1)
                        )

                        total_intersection_area = 0.0
                        for single_shape in shapes:
                            intersection = single_shape.intersection(pixel_bounds)
                            if not intersection.is_empty:
                                total_intersection_area += intersection.area
                        frac = total_intersection_area / pixel_bounds.area
                        raster_2d[y, x] = frac
            end_time = time.time()

            logging.info(f"Generated raster mask for row region id: {region_id} (took {end_time - start_time:.2f} seconds)")

            return raster_2d


def configure_worker_logging():
    import logging
    # Use force=True to overwrite Dask's default worker logging config
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True
    )
    # Silence Dask logs on the worker side too
    logging.getLogger("dask").setLevel(logging.WARNING)
    logging.getLogger("distributed").setLevel(logging.WARNING)


def normalize_fractions(raster_3d, normalize_mask=True):
    if normalize_mask:
        logging.info("Normalizing mask...")
        # the first dimension corresponds to the regions
        sums = raster_3d.sum(axis=0, keepdims=True)
        # Normalize
        raster_3d_normalized = raster_3d / sums
        logging.info("Done normalizing mask.")
    else:
        raster_3d_normalized = raster_3d
    return raster_3d_normalized


@dataclass
class MaskResult:
    """Final and pre-normalization arrays, shifted shapes, and exported paths."""

    mask: xr.DataArray
    raw_mask: xr.DataArray
    regions: gpd.GeoDataFrame
    netcdf_path: Path
    table_path: Path


def generate_mask(mask_shape_file_path, *, bounds=(-0.25, -89.75, 359.75, 90.25),
                  resolution=0.5, normalize_mask=True, num_workers=4,
                  memory_limit="2GB", diagnostics_dir=None):
    """Generate and export a mask and ID table using the original calculation.

    Exports next to the shapefile's parent directory, as in the original notebook.
    Calling this function overwrites those outputs. Optional raw diagnostics use
    the regression adapter's original NetCDF encoding and metadata convention.
    Workers are started only on invocation and always closed before returning.
    From a Python script, call under an ``if __name__ == '__main__'`` guard.
    """
    mask_shape_file_path = Path(mask_shape_file_path)
    min_lon, min_lat, max_lon, max_lat = (float(value) for value in bounds)
    bounds = (min_lon, min_lat, max_lon, max_lat)
    resolution = float(resolution)
    mask_file_path = mask_shape_file_path.parent.parent / (
        "mask_" + mask_shape_file_path.name.replace(".shp", "")
        + f"_lat{max_lat}_lon{min_lon}_res{resolution}.nc"
    )
    csv_file_path = mask_shape_file_path.parent.parent / (
        "ids_" + mask_shape_file_path.name.replace(".shp", "") + ".csv"
    )
    shape_file_geometry_field = "geometry"
    shape_file_region_id_field = "ID"
    with LocalCluster(n_workers=num_workers, memory_limit=memory_limit,
                      threads_per_worker=1) as cluster, Client(cluster) as client:
        logging.info(f"Dask dashboard URL: {client.dashboard_link}")
        client.run(configure_worker_logging)
        logging.info(f"Reading shapefile from {mask_shape_file_path}...")
        gdf = gpd.read_file(mask_shape_file_path)
        logging.info("Shape file loaded")
        shape_file_original_bounds = gdf.total_bounds
        # Check current bounds
        logging.info(f"Original shape bounds: {gdf.total_bounds}")


        logging.info(f"Splitting and shifting geometries along the {min_lon} meridian...")

        # Apply the transformation
        gdf.geometry = gdf.geometry.apply(lambda geom: shift_longitude(geom, shape_file_original_bounds, split_lon=min_lon))

        shape_file_bounds = gdf.total_bounds

        # Check the new bounds
        logging.info(f"New shape bounds: {[float(round(val, 2)) for val in shape_file_bounds]}")


        # Calculate the transform and dimensions
        width = int((bounds[2] - bounds[0]) / resolution)
        height = int((bounds[3] - bounds[1]) / resolution)
        transform = rasterio.transform.from_bounds(*bounds, width, height)

        # Create a base raster (all 1s)
        base_raster = np.ones((height, width), dtype=np.float32)

        # Create a dataset object in memory
        profile = {
            'driver': 'GTiff',
            'height': height,
            'width': width,
            'count': 1,
            'dtype': base_raster.dtype,
            'crs': gdf.crs,
            'transform': transform,
            'nodata': np.nan,
        }

        logging.info(f"Raster profile: height={profile['height']}, width={profile['width']}")
        logging.info(f"Raster profile CRS: {profile['crs'].to_json()}")

        # Create a polygon representing the entire raster bounds
        raster_polygon = Polygon([
            (bounds[0], bounds[1]),
            (bounds[0], bounds[3]),
            (bounds[2], bounds[3]),
            (bounds[2], bounds[1]),
            (bounds[0], bounds[1])
        ])



        logging.info("Starting generating mask...")

        # # Initialize the 3D raster (one band per region)
        tasks = []
        for i, (idx, row) in enumerate(gdf.iterrows()):
            shape = row[shape_file_geometry_field]
            region_id = row[shape_file_region_id_field]
            # Create a list of delayed tasks
            task = rasterize_region(shape, region_id, profile, height, width, i, len(gdf), base_raster, transform, raster_polygon)
            tasks.append(task)

        # Compute all tasks in parallel
        results = dask.compute(*tasks)

        # Stack results into a 3D raster
        raster_3d = np.stack(results, axis=0)

        logging.info("Done generating mask.")

        raster_3d_normalized = normalize_fractions(raster_3d, normalize_mask)

        logging.info(f"Saving raster mask to {mask_file_path}...")

        # Generate 1D coordinates separately
        # Longitude (X): Pass a scalar 0 for row, and array for columns.
        # rasterio broadcasts the scalar 0 against the columns array.
        x_coords, _ = rasterio.transform.xy(transform, 0, np.arange(width).tolist(), offset='center')
        # Latitude (Y): Pass array for rows, and scalar 0 for columns.
        _, y_coords = rasterio.transform.xy(transform, np.arange(height).tolist(), 0, offset='center')
        # Convert to numpy arrays for xarray
        x_coords = np.array(x_coords)
        y_coords = np.array(y_coords)

        region_ids = gdf[shape_file_region_id_field].values

        # Extract metadata to store in the netcdf file
        metadata = gdf.drop(shape_file_geometry_field, axis=1).to_json(orient='records')

        # Create the DataArray
        da = xr.DataArray(
            raster_3d_normalized,
            dims=('region', 'lat', 'lon'),
            coords={
                'region': region_ids,
                'lat': y_coords,
                'lon': x_coords
            },
            name="mask",
            attrs={
                'transform': tuple(transform),
                'crs': str(gdf.crs),
                'resolution': resolution,
                'description': 'Fractional coverage of regions (0.0 to 1.0)',
                'metadata': metadata
            }
        )

        # 4. Save with Compression (Crucial for mask files)
        encoding = {
            da.name: {
                'zlib': True,
                'complevel': 5,
                'dtype': 'float32',
                '_FillValue': np.nan
            }
        }

        da.to_netcdf(mask_file_path, engine='netcdf4', encoding=encoding)
        logging.info(f"Raster mask saved successfully to {mask_file_path}")

        # Saves the IDs to a CSV
        gdf.drop(shape_file_geometry_field, axis=1).to_csv(csv_file_path)
    raw = da.copy(data=raster_3d)
    raw.attrs = dict(da.attrs, regression_stage="before_normalization")
    if diagnostics_dir is not None:
        diagnostics_dir = Path(diagnostics_dir)
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        raw.to_netcdf(diagnostics_dir / ("raw_" + mask_file_path.name),
                      engine="netcdf4", encoding=encoding)
    return MaskResult(da, raw, gdf, mask_file_path, csv_file_path)
