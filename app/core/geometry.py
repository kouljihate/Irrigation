from functools import lru_cache
from math import floor

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform


WGS84 = "EPSG:4326"


@lru_cache(maxsize=32)
def get_transformer(source_crs, target_crs):
    """Return a cached pyproj transformer.

    Building a Transformer is expensive, and the export paths call this
    once per geometry. Projects routinely contain tens of thousands of
    trees, rows and driplines, so the cache keeps large exports tractable.
    """
    return Transformer.from_crs(
        source_crs,
        target_crs,
        always_xy=True,
    )


def geojson_to_shape(geometry):
    return shape(geometry)


def is_inside_polygon(candidate_geometry, boundary_geometry):
    candidate = geojson_to_shape(candidate_geometry)
    boundary = geojson_to_shape(boundary_geometry)
    return boundary.covers(candidate)


def get_utm_epsg_from_geometry(geometry):
    centroid = shape(geometry).centroid
    return get_utm_epsg_from_coordinates(centroid.x, centroid.y)


def get_utm_epsg_from_coordinates(longitude, latitude):
    longitude = min(180.0, max(-180.0, float(longitude)))
    latitude = min(90.0, max(-90.0, float(latitude)))

    zone_number = int(floor((longitude + 180.0) / 6.0)) + 1
    zone_number = min(60, max(1, zone_number))

    if latitude >= 0:
        return f"EPSG:{32600 + zone_number}"

    return f"EPSG:{32700 + zone_number}"


def get_transformers(working_crs):
    return (
        get_transformer(WGS84, working_crs),
        get_transformer(working_crs, WGS84),
    )


def to_projected(geometry, working_crs):
    return transform(
        get_transformer(WGS84, working_crs).transform,
        geometry,
    )


def to_wgs84(geometry, working_crs):
    return transform(
        get_transformer(working_crs, WGS84).transform,
        geometry,
    )


def measure_area_m2(geometry):
    if geometry is None:
        return 0.0

    polygon = shape(geometry)
    working_crs = get_utm_epsg_from_geometry(geometry)
    projected_polygon = to_projected(polygon, working_crs)
    return projected_polygon.area


def measure_length_m(geometry):
    if geometry is None:
        return 0.0

    line = shape(geometry)
    working_crs = get_utm_epsg_from_geometry(geometry)
    projected_line = to_projected(line, working_crs)
    return projected_line.length
