from math import atan2, degrees, floor

import numpy as np
from shapely.geometry import Point, shape
from shapely.ops import transform

from core.geometry import WGS84, get_transformer


def get_utm_epsg_from_geometry(geometry):
    polygon = shape(geometry)
    centroid = polygon.centroid

    longitude = centroid.x
    latitude = centroid.y

    utm_zone = int(
        floor((longitude + 180) / 6) + 1
    )

    if latitude >= 0:
        return f"EPSG:{32600 + utm_zone}"

    return f"EPSG:{32700 + utm_zone}"


def get_projected_transformer(working_crs):
    return get_transformer(WGS84, working_crs)


def add_elevation_point(
    points,
    longitude,
    latitude,
    elevation,
    source_id,
):
    if elevation is None:
        return

    try:
        elevation_value = float(elevation)
    except (TypeError, ValueError):
        return

    points.append({
        "longitude": float(longitude),
        "latitude": float(latitude),
        "elevation_m": elevation_value,
        "source_id": source_id,
    })


def extract_elevation_points_from_kml(project):
    """Collect one elevation sample per distinct map position.

    KML frequently repeats a vertex across overlapping placemarks and
    sometimes with different altitudes. Keying on longitude/latitude only
    and averaging the reported altitudes keeps one sample per physical
    location, so the least-squares plane is not fitted to duplicate
    positions.
    """
    grouped = {}

    for feature in project.get(
        "kml_features",
        [],
    ):
        geometry = feature.get("geometry", {})
        geometry_type = geometry.get("type", "")
        coordinates = geometry.get("coordinates", [])
        source_id = feature.get("id", "KML")

        raw_coordinates = []

        if geometry_type == "Point":
            raw_coordinates = [coordinates]

        elif geometry_type == "LineString":
            raw_coordinates = coordinates

        elif geometry_type == "Polygon":
            if coordinates:
                raw_coordinates = coordinates[0]

        for coordinate in raw_coordinates:
            if len(coordinate) < 3:
                continue

            longitude = coordinate[0]
            latitude = coordinate[1]
            elevation = coordinate[2]

            key = (
                round(float(longitude), 8),
                round(float(latitude), 8),
            )

            entry = grouped.setdefault(
                key,
                {
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                    "z_sum": 0.0,
                    "sample_count": 0,
                    "source_ids": [],
                },
            )

            try:
                entry["z_sum"] += float(elevation)
            except (TypeError, ValueError):
                continue

            entry["sample_count"] += 1

            if source_id not in entry["source_ids"]:
                entry["source_ids"].append(source_id)

    points = []

    for entry in grouped.values():
        if entry["sample_count"] == 0:
            continue

        add_elevation_point(
            points=points,
            longitude=entry["longitude"],
            latitude=entry["latitude"],
            elevation=entry["z_sum"] / entry["sample_count"],
            source_id=", ".join(entry["source_ids"]),
        )

    return points


def get_zone_by_id(project, zone_id):
    for zone in project.get("zones", []):
        if zone.get("id") == zone_id:
            return zone

    return None


def collect_nearest_elevation_points(
    zone_geometry,
    elevation_points,
    maximum_points=20,
    search_radius_m=None,
    radius_factor=None,
):
    if len(elevation_points) < 3:
        return []

    working_crs = get_utm_epsg_from_geometry(
        zone_geometry
    )

    transformer = get_projected_transformer(
        working_crs
    )

    zone_polygon_wgs84 = shape(zone_geometry)

    zone_polygon = transform(
        transformer.transform,
        zone_polygon_wgs84,
    )

    if not zone_polygon.is_valid:
        zone_polygon = zone_polygon.buffer(0)

    centroid = zone_polygon.centroid

    min_x, min_y, max_x, max_y = zone_polygon.bounds

    if search_radius_m is None:
        width = max(max_x - min_x, max_y - min_y, 1.0)
        search_radius_m = width * (
            1.5 if radius_factor is None else radius_factor
        )

    search_polygon = zone_polygon.buffer(search_radius_m)

    inside = []
    outside = []

    for item in elevation_points:
        x, y = transformer.transform(
            item["longitude"],
            item["latitude"],
        )

        point = Point(x, y)

        if not search_polygon.covers(point):
            continue

        distance_m = centroid.distance(point)

        candidate = {
            "x": x,
            "y": y,
            "z": item["elevation_m"],
            "distance_m": distance_m,
            "source_id": item["source_id"],
            "inside_zone": zone_polygon.covers(point),
        }

        if candidate["inside_zone"]:
            inside.append(candidate)
        else:
            outside.append(candidate)

    inside.sort(key=lambda item: item["distance_m"])
    outside.sort(key=lambda item: item["distance_m"])

    return (inside + outside)[:maximum_points]


FIT_ATTEMPTS = [
    {"maximum_points": 20, "radius_factor": 1.5},
    {"maximum_points": 30, "radius_factor": 4.0},
    {"maximum_points": 50, "radius_factor": 10.0},
    {"maximum_points": 80, "radius_factor": 25.0},
]


def fit_zone_terrain_plane(zone_geometry, elevation_points):
    """Fit a terrain plane, widening the search until the points are
    well conditioned.

    Small or badly shaped zones can end up with only three nearly
    collinear neighbours, which makes the least-squares problem singular.
    Rather than returning a meaningless plane, the search is widened and
    retried so that each zone gets its own well-conditioned fit.
    """
    last_error = None
    last_count = 0

    for attempt in FIT_ATTEMPTS:
        candidates = collect_nearest_elevation_points(
            zone_geometry=zone_geometry,
            elevation_points=elevation_points,
            maximum_points=attempt["maximum_points"],
            radius_factor=attempt["radius_factor"],
        )

        last_count = len(candidates)

        if len(candidates) < 3:
            last_error = (
                f"only {len(candidates)} usable elevation "
                "point(s) are available nearby"
            )
            continue

        try:
            slope_x, slope_y, intercept = fit_terrain_plane(
                candidates
            )
        except ValueError as exc:
            last_error = str(exc)
            continue

        return (
            slope_x,
            slope_y,
            intercept,
            candidates,
            attempt["maximum_points"],
        )

    raise ValueError(
        f"{last_error or 'the nearby elevation points are unusable'} "
        f"(widest search found {last_count} point(s))"
    )


def fit_terrain_plane(projected_points):
    if len(projected_points) < 3:
        raise ValueError(
            "At least three elevation points are required."
        )

    matrix = []
    elevations = []

    for point in projected_points:
        matrix.append([
            point["x"],
            point["y"],
            1.0,
        ])

        elevations.append(
            point["z"]
        )

    x_values = [point["x"] for point in projected_points]
    y_values = [point["y"] for point in projected_points]

    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)

    centred = [
        [point["x"] - mean_x, point["y"] - mean_y, 1.0]
        for point in projected_points
    ]

    normal_matrix = np.array(centred)
    target = np.array(elevations)

    try:
        coefficients, _, rank, _ = np.linalg.lstsq(
            normal_matrix,
            target,
            rcond=None,
        )
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"Terrain plane fit failed: {exc}"
        ) from exc

    if rank < 3:
        raise ValueError(
            "Elevation points are collinear, so the "
            "terrain plane cannot be determined."
        )

    slope_x = float(coefficients[0])
    slope_y = float(coefficients[1])
    intercept = float(
        coefficients[2] - (slope_x * mean_x) - (slope_y * mean_y)
    )

    return slope_x, slope_y, intercept


def calculate_zone_elevation_analysis(
    project,
    zone_id,
):
    zone = get_zone_by_id(
        project,
        zone_id,
    )

    if zone is None:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
        }

    elevation_points = extract_elevation_points_from_kml(
        project
    )

    if len(elevation_points) < 3:
        return {
            "ok": False,
            "message": (
                "The KML does not contain at least three usable "
                "elevation coordinates."
            ),
        }

    try:
        (
            slope_x,
            slope_y,
            intercept,
            projected_points,
            search_limit,
        ) = fit_zone_terrain_plane(
            zone["geometry"],
            elevation_points,
        )

    except ValueError as exc:
        return {
            "ok": False,
            "message": (
                f"Unable to calculate terrain plane "
                f"for {zone_id}: {exc}. Add more elevation "
                "detail around this zone in the source KML."
            ),
        }

    downhill_x = -slope_x
    downhill_y = -slope_y

    downhill_bearing = (
        degrees(
            atan2(
                downhill_x,
                downhill_y,
            )
        )
        + 360
    ) % 360

    contour_row_bearing = (
        downhill_bearing + 90
    ) % 180

    row_angle_degrees = (
        90 - contour_row_bearing
    ) % 180

    slope_ratio = (
        slope_x ** 2 + slope_y ** 2
    ) ** 0.5

    slope_percent = slope_ratio * 100

    elevations = [
        point["z"]
        for point in projected_points
    ]

    inside_count = sum(
        1
        for point in projected_points
        if point.get("inside_zone")
    )

    analysis = {
        "elevation_point_count": len(
            projected_points
        ),
        "elevation_search_limit": search_limit,
        "inside_zone_point_count": inside_count,
        "minimum_elevation_m": round(
            min(elevations),
            2,
        ),
        "maximum_elevation_m": round(
            max(elevations),
            2,
        ),
        "average_elevation_m": round(
            sum(elevations) / len(elevations),
            2,
        ),
        "elevation_range_m": round(
            max(elevations) - min(elevations),
            2,
        ),
        "slope_x": round(slope_x, 8),
        "slope_y": round(slope_y, 8),
        "slope_percent": round(
            slope_percent,
            2,
        ),
        "downhill_bearing_degrees": round(
            downhill_bearing,
            2,
        ),
        "contour_row_bearing_degrees": round(
            contour_row_bearing,
            2,
        ),
        "recommended_row_angle_degrees": round(
            row_angle_degrees,
            2,
        ),
        "working_crs": get_utm_epsg_from_geometry(
            zone["geometry"]
        ),
        "method": (
            "KML elevation vertices - "
            "least-squares terrain plane"
        ),
    }

    if inside_count < 3:
        analysis["warning"] = (
            f"Only {inside_count} elevation point(s) fall inside "
            "this zone, so the plane is dominated by nearby "
            "outside points. Survey the zone for accuracy."
        )

    zone["elevation_analysis"] = analysis
    zone["recommended_row_angle_degrees"] = (
        analysis["recommended_row_angle_degrees"]
    )

    return {
        "ok": True,
        "message": (
            f"Elevation analysis complete for {zone_id}."
        ),
        "analysis": analysis,
    }


def calculate_elevation_for_all_zones(project):
    zones = project.get("zones", [])

    if not zones:
        return {
            "ok": False,
            "message": "No zones are available.",
            "analysed_zone_ids": [],
            "errors": [],
        }

    analysed_zone_ids = []
    errors = []

    ordered_zones = sorted(
        zones,
        key=lambda zone: (
            zone.get("sector_id", ""),
            zone.get("zone_number", 0),
        ),
    )

    for zone in ordered_zones:
        result = calculate_zone_elevation_analysis(
            project=project,
            zone_id=zone["id"],
        )

        if result["ok"]:
            analysed_zone_ids.append(
                zone["id"]
            )
        else:
            errors.append(
                result["message"]
            )

    return {
        "ok": len(analysed_zone_ids) > 0,
        "message": (
            f"Elevation analysis completed for "
            f"{len(analysed_zone_ids)} zone(s)."
        ),
        "analysed_zone_ids": analysed_zone_ids,
        "errors": errors,
    }