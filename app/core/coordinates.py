from core.geometry import WGS84, get_transformer


def lonlat_to_projected(longitude, latitude, working_crs):
    return get_transformer(
        WGS84,
        working_crs,
    ).transform(longitude, latitude)


def projected_to_lonlat(x, y, working_crs):
    return get_transformer(
        working_crs,
        WGS84,
    ).transform(x, y)
