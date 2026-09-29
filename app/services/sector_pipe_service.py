from shapely.geometry import LineString, mapping, shape
from shapely.ops import nearest_points, transform

from core.geometry import (
    WGS84,
    get_transformer,
    get_utm_epsg_from_coordinates,
    measure_length_m,
)


def get_sector_by_id(project, sector_id):
    for sector in project.get("sectors", []):
        if sector.get("id") == sector_id:
            return sector

    return None


def get_sector_pipes(project, sector_id=None):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "major_63"
        and (
            sector_id is None
            or pipe.get("sector_id") == sector_id
        )
    ]


def get_sector_zones(project, sector_id):
    return [
        zone
        for zone in project.get("zones", [])
        if zone.get("sector_id") == sector_id
    ]


def get_zone_control_point(project, zone_id):
    for valve in project.get("valves", []):
        if valve.get("zone_id") == zone_id:
            return valve.get("geometry")

    return None


def get_utm_crs_from_geometry(geometry):
    polygon = shape(geometry)
    centroid = polygon.centroid

    longitude = centroid.x
    latitude = centroid.y

    zone_number = int(
        (longitude + 180) / 6
    ) + 1

    if latitude >= 0:
        return f"EPSG:{32600 + zone_number}"

    return f"EPSG:{32700 + zone_number}"


def calculate_geometry_length_m(geometry):
    working_crs = get_utm_crs_from_geometry(
        geometry
    )

    to_projected = get_transformer(
        WGS84,
        working_crs,
    )

    line = shape(geometry)

    projected_line = transform(
        to_projected.transform,
        line,
    )

    return working_crs, projected_line.length


def create_sector_pipe(
    project,
    sector_id,
    coordinates,
    pipe_number,
    parent_pipe_id=None,
    supply_side="automatic_high_elevation",
):
    sector = get_sector_by_id(
        project,
        sector_id,
    )

    if sector is None:
        return {
            "ok": False,
            "message": f"Sector {sector_id} was not found.",
        }

    if len(coordinates) < 2:
        return {
            "ok": False,
            "message": "A sector pipe needs at least two points.",
        }

    geometry = {
        "type": "LineString",
        "coordinates": coordinates,
    }

    sector_polygon = shape(
        sector["geometry"]
    )

    if not sector_polygon.is_valid:
        sector_polygon = sector_polygon.buffer(0)

    pipe_line = shape(geometry)

    inside_geometry = pipe_line.intersection(sector_polygon)

    total_length_m = measure_length_m(geometry)

    inside_length_m = 0.0

    if not inside_geometry.is_empty and inside_geometry.length > 0:
        inside_length_m = measure_length_m(
            mapping(inside_geometry)
        )

    if inside_length_m <= 0:
        return {
            "ok": False,
            "message": (
                f"The 63 mm pipe does not run inside {sector_id}."
            ),
        }

    if (
        total_length_m > 0
        and inside_length_m / total_length_m < 0.10
    ):
        return {
            "ok": False,
            "message": (
                f"Only {inside_length_m:.1f} m of the 63 mm pipe "
                f"lies inside {sector_id}; it is almost entirely "
                "outside the sector."
            ),
        }

    existing_pipes = get_sector_pipes(
        project,
        sector_id,
    )

    pipe_id = (
        f"P63-{sector_id}-"
        f"{pipe_number:03d}"
    )

    if any(
        pipe.get("id") == pipe_id
        for pipe in existing_pipes
    ):
        return {
            "ok": False,
            "message": f"{pipe_id} already exists.",
        }

    try:
        working_crs, length_m = (
            calculate_geometry_length_m(
                geometry
            )
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Unable to calculate pipe length: {exc}"
            ),
        }

    pipe = {
        "id": pipe_id,
        "name": pipe_id,
        "entity_type": "pipe",
        "pipe_type": "major_63",
        "diameter_mm": 63,
        "material": "HDPE",
        "sector_id": sector_id,
        "zone_id": None,
        "length_m": round(length_m, 2),
        "flow_m3h": 0.0,
        "parent_pipe_id": parent_pipe_id,
        "supply_side": supply_side,
        "geometry": mapping(pipe_line),
        "properties": {
            "working_crs": working_crs,
            "role": "sector_major_distribution",
        },
        "description": (
            f"63 mm sector distribution pipe "
            f"for {sector_id}."
        ),
    }

    project["pipes"].append(pipe)

    return {
        "ok": True,
        "message": f"{pipe_id} created successfully.",
        "pipe": pipe,
    }


def calculate_sector_flow(project, sector_id):
    total_flow = 0.0

    for zone in get_sector_zones(
        project,
        sector_id,
    ):
        total_flow += zone.get(
            "target_flow_m3h",
            0.0,
        )

    return round(total_flow, 3)


def update_sector_pipe_flows(project):
    sector_flows = {}

    for pipe in project.get("pipes", []):
        if pipe.get("pipe_type") != "major_63":
            continue

        sector_id = pipe.get("sector_id")

        if sector_id not in sector_flows:
            sector_flows[sector_id] = calculate_sector_flow(
                project,
                sector_id,
            )

        pipe["flow_m3h"] = sector_flows[sector_id]

    for pipe in project.get("pipes", []):
        if pipe.get("pipe_type") != "principal_90":
            continue

        supplied_sectors = {
            child.get("sector_id")
            for child in project.get("pipes", [])
            if child.get("parent_pipe_id") == pipe.get("id")
        }

        pipe["flow_m3h"] = round(
            sum(
                sector_flows.get(sector_id, 0.0)
                for sector_id in supplied_sectors
            ),
            3,
        )

    for valve in project.get("valves", []):
        if valve.get("valve_type") != "zone":
            continue

        zone = get_zone_by_id(project, valve.get("zone_id"))

        if zone:
            valve["flow_m3h"] = round(
                float(zone.get("target_flow_m3h") or 0.0),
                3,
            )

    for pipe in project.get("pipes", []):
        if pipe.get("pipe_type") != "manifold_32":
            continue

        zone = get_zone_by_id(project, pipe.get("zone_id"))

        if zone:
            pipe["flow_m3h"] = round(
                float(zone.get("target_flow_m3h") or 0.0),
                3,
            )

    for pipe in project.get("pipes", []):
        if pipe.get("pipe_type") != "dripline":
            continue

        trees = [
            tree
            for tree in project.get("trees", [])
            if tree.get("row_id") == pipe.get("row_id")
        ]

        if not trees:
            continue

        emitters = float(
            trees[0].get("emitters_per_tree") or 2
        )
        flow_lph = float(
            trees[0].get("emitter_flow_lph") or 4.0
        )

        pipe["flow_m3h"] = round(
            len(trees) * emitters * flow_lph / 1000.0,
            4,
        )

    return project


def get_zone_by_id(project, zone_id):
    for zone in project.get("zones", []):
        if zone.get("id") == zone_id:
            return zone

    return None


def get_principal_routes(project):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "principal_90"
    ]


def _route_working_crs(principal_route):
    properties = principal_route.get("properties") or {}

    if properties.get("working_crs"):
        return properties["working_crs"]

    coordinates = (
        principal_route.get("geometry", {}).get("coordinates") or []
    )

    if coordinates:
        return get_utm_epsg_from_coordinates(
            coordinates[0][0],
            coordinates[0][1],
        )

    return "EPSG:3857"


def build_sector_spine(
    sector,
    principal_route,
    zone_polygons=None,
):
    """Build a 63 mm main from the principal route into the sector.

    The spine is assembled in the projected working CRS so the connection
    point is genuinely the closest point on the route, then converted back
    to WGS84 as a single geometry.
    """
    sector_geometry = sector.get("geometry")

    if not sector_geometry or not principal_route:
        return None

    route_coordinates = (
        principal_route.get("geometry", {}).get("coordinates") or []
    )

    if len(route_coordinates) < 2:
        return None

    working_crs = _route_working_crs(principal_route)

    to_projected = get_transformer(
        WGS84,
        working_crs,
    )

    to_wgs84 = get_transformer(
        working_crs,
        WGS84,
    )

    sector_projected = transform(
        to_projected.transform,
        shape(sector_geometry),
    )

    if not sector_projected.is_valid:
        sector_projected = sector_projected.buffer(0)

    route_projected = transform(
        to_projected.transform,
        shape(principal_route["geometry"]),
    )

    connection = nearest_points(
        route_projected,
        sector_projected,
    )[1]

    min_x, min_y, max_x, max_y = sector_projected.bounds

    centroids = []

    for zone_polygon in zone_polygons or []:
        centroid = zone_polygon.centroid

        if sector_projected.covers(centroid):
            centroids.append(centroid)

    if centroids:
        middle = (
            sum(point.x for point in centroids) / len(centroids),
            sum(point.y for point in centroids) / len(centroids),
        )
    else:
        middle = (
            (min_x + max_x) / 2,
            (min_y + max_y) / 2,
        )

    candidates = [
        (connection.x, connection.y),
        middle,
        (min_x, min_y),
        (min_x, max_y),
    ]

    deduplicated = [candidates[0]]

    for point in candidates[1:]:
        if (
            abs(point[0] - deduplicated[-1][0]) > 1e-6
            or abs(point[1] - deduplicated[-1][1]) > 1e-6
        ):
            deduplicated.append(point)

    if len(deduplicated) < 2:
        return None

    spine = LineString(deduplicated)

    if spine.intersection(sector_projected).length <= 0:
        return None

    spine_wgs84 = transform(to_wgs84.transform, spine)

    return [
        [round(longitude, 9), round(latitude, 9)]
        for longitude, latitude, *_ in spine_wgs84.coords
    ]


def create_sector_pipes_for_all_sectors(project):
    sectors = sorted(
        project.get("sectors", []),
        key=lambda sector: sector.get("sector_number", 999),
    )

    if not sectors:
        return {
            "ok": False,
            "message": "No sectors are available.",
            "created_pipe_ids": [],
            "errors": [],
        }

    principal_routes = get_principal_routes(project)

    if not principal_routes:
        return {
            "ok": False,
            "message": (
                "Create a 90 mm principal route before "
                "building the 63 mm sector mains."
            ),
            "created_pipe_ids": [],
            "errors": [],
        }

    created_pipe_ids = []
    errors = []

    principal_route = principal_routes[0]

    for sector in sectors:
        sector_id = sector.get("id")

        zone_polygons = [
            shape(zone["geometry"])
            for zone in project.get("zones", [])
            if zone.get("sector_id") == sector_id
            and zone.get("geometry")
        ]

        coordinates = build_sector_spine(
            sector,
            principal_route,
            zone_polygons,
        )

        if not coordinates:
            errors.append(
                f"{sector_id}: unable to build a supply spine "
                "that reaches into the sector."
            )
            continue

        pipe_number = len(
            get_sector_pipes(project, sector_id)
        ) + 1

        result = create_sector_pipe(
            project=project,
            sector_id=sector_id,
            coordinates=coordinates,
            pipe_number=pipe_number,
            parent_pipe_id=principal_route.get("id"),
        )

        if result["ok"]:
            created_pipe_ids.append(result["pipe"]["id"])
        else:
            errors.append(f"{sector_id}: {result['message']}")

    update_sector_pipe_flows(project)

    return {
        "ok": bool(created_pipe_ids),
        "message": (
            f"Created {len(created_pipe_ids)} 63 mm sector main(s)."
        ),
        "created_pipe_ids": created_pipe_ids,
        "errors": errors,
    }


def remove_all_sector_pipes(project):
    before = len(project.get("pipes", []))

    project["pipes"] = [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") != "major_63"
    ]

    removed = before - len(project["pipes"])

    for zone in project.get("zones", []):
        zone["pipe_ids"] = []

    return {
        "ok": True,
        "message": f"Removed {removed} 63 mm sector main(s).",
    }