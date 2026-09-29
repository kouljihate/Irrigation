from math import floor

from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform

from core.geometry import WGS84, get_transformer


ALLOWED_PRINCIPAL_ROUTE_IDS = [
    "P90-R1",
    "P90-R2",
    "P90-R3",
]


def get_principal_pipes(project):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "principal_90"
    ]


def get_principal_pipe_by_id(
    project,
    route_id,
):
    for pipe in get_principal_pipes(project):
        if pipe.get("id") == route_id:
            return pipe

    return None


def get_utm_crs_from_geometry(geometry):
    line = shape(geometry)
    centroid = line.centroid

    longitude = centroid.x
    latitude = centroid.y

    utm_zone = int(
        floor((longitude + 180) / 6) + 1
    )

    if latitude >= 0:
        return f"EPSG:{32600 + utm_zone}"

    return f"EPSG:{32700 + utm_zone}"


def calculate_line_length_m(geometry):
    working_crs = get_utm_crs_from_geometry(
        geometry
    )

    transformer = get_transformer(
        WGS84,
        working_crs,
    )

    line = shape(geometry)

    projected_line = transform(
        transformer.transform,
        line,
    )

    return working_crs, projected_line.length


def validate_route_inside_land(
    project,
    geometry,
):
    land = project.get("land")

    if not land:
        return {
            "ok": False,
            "message": (
                "No land boundary has been assigned yet."
            ),
        }

    land_polygon = shape(
        land["geometry"]
    )

    principal_line = shape(geometry)

    if not land_polygon.covers(principal_line):
        return {
            "ok": False,
            "message": (
                "The principal route extends outside "
                "the land boundary."
            ),
        }

    return {
        "ok": True,
        "message": (
            "Principal route stays inside the land boundary."
        ),
    }


def create_principal_route(
    project,
    route_id,
    coordinates,
    route_description="",
):
    if route_id not in ALLOWED_PRINCIPAL_ROUTE_IDS:
        return {
            "ok": False,
            "message": (
                "Invalid principal route ID. "
                "Only P90-R1, P90-R2, and P90-R3 are allowed."
            ),
        }

    if len(coordinates) < 2:
        return {
            "ok": False,
            "message": (
                "A principal route needs at least two points."
            ),
        }

    existing_route = get_principal_pipe_by_id(
        project,
        route_id,
    )

    if existing_route:
        return {
            "ok": False,
            "message": (
                f"{route_id} already exists. "
                "Remove it first if you want to redraw it."
            ),
        }

    existing_routes = get_principal_pipes(
        project
    )

    if len(existing_routes) >= 3:
        return {
            "ok": False,
            "message": (
                "Only three 90 mm principal routes "
                "are allowed."
            ),
        }

    geometry = {
        "type": "LineString",
        "coordinates": coordinates,
    }

    land_validation = validate_route_inside_land(
        project,
        geometry,
    )

    if not land_validation["ok"]:
        return land_validation

    try:
        working_crs, length_m = calculate_line_length_m(
            geometry
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Could not calculate route length: {exc}"
            ),
        }

    principal_route = {
        "id": route_id,
        "name": route_id,
        "entity_type": "pipe",
        "pipe_type": "principal_90",
        "diameter_mm": 90,
        "material": "HDPE",
        "sector_id": None,
        "zone_id": None,
        "length_m": round(length_m, 2),
        "flow_m3h": 0.0,
        "parent_pipe_id": None,
        "from_node_id": "BASIN-001",
        "to_node_id": None,
        "geometry": mapping(
            LineString(coordinates)
        ),
        "properties": {
            "route_role": (
                "high_elevation_principal_route"
            ),
            "requires_high_elevation_review": True,
            "working_crs": working_crs,
            "maximum_principal_routes": 3,
        },
        "description": (
            route_description
            or (
                "90 mm principal supply route. "
                "Must remain on the approved "
                "high-elevation boundary corridor."
            )
        ),
    }

    project["pipes"].append(
        principal_route
    )

    return {
        "ok": True,
        "message": (
            f"{route_id} created successfully. "
            "Review that it follows the high-elevation boundary."
        ),
        "pipe": principal_route,
    }


def remove_principal_route(
    project,
    route_id,
):
    before_count = len(
        project.get("pipes", [])
    )

    project["pipes"] = [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("id") != route_id
    ]

    after_count = len(
        project["pipes"]
    )

    if before_count == after_count:
        return {
            "ok": False,
            "message": (
                f"{route_id} was not found."
            ),
        }

    return {
        "ok": True,
        "message": (
            f"{route_id} removed successfully."
        ),
    }


def get_available_principal_route_ids(
    project,
):
    existing_ids = [
        pipe.get("id")
        for pipe in get_principal_pipes(project)
    ]

    return [
        route_id
        for route_id in ALLOWED_PRINCIPAL_ROUTE_IDS
        if route_id not in existing_ids
    ]