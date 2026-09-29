def get_zone_by_id(project, zone_id):
    for zone in project.get("zones", []):
        if zone.get("id") == zone_id:
            return zone

    return None


def get_zone_driplines(project, zone_id):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "dripline"
        and pipe.get("zone_id") == zone_id
    ]


def get_zone_manifolds(project, zone_id):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "manifold_32"
        and pipe.get("zone_id") == zone_id
    ]


def get_zone_valves(project, zone_id):
    return [
        valve
        for valve in project.get("valves", [])
        if valve.get("zone_id") == zone_id
    ]


def get_zone_centroid(zone):
    geometry = zone.get("geometry", {})
    coordinates = geometry.get("coordinates", [])

    if not coordinates:
        return None

    ring = coordinates[0]

    longitude_values = [
        coordinate[0]
        for coordinate in ring
    ]

    latitude_values = [
        coordinate[1]
        for coordinate in ring
    ]

    return {
        "type": "Point",
        "coordinates": [
            sum(longitude_values) / len(longitude_values),
            sum(latitude_values) / len(latitude_values),
            0.0,
        ],
    }


def create_zone_valve(project, zone):
    zone_id = zone["id"]

    existing_valves = get_zone_valves(
        project,
        zone_id,
    )

    existing_zone_valves = [
        valve
        for valve in existing_valves
        if valve.get("valve_type") == "zone"
    ]

    if existing_zone_valves:
        return existing_zone_valves[0]

    
    sector_id = zone.get(
        "sector_id"
    )

    zone_number = zone.get(
        "zone_number"
    )

    valve_id = f"{sector_id}-ZV{zone_number}"
    
    
    valve = {
        "id": valve_id,
        "name": valve_id,
        "entity_type": "valve",
        "valve_type": "zone",
        "sector_id": zone.get("sector_id"),
        "zone_id": zone_id,
        "diameter_mm": 32,
        "is_automatic": False,
        "pressure_regulated": True,
        "geometry": get_zone_centroid(zone),
        "properties": {
            "installation_order": [
                "isolation_valve",
                "filter",
                "pressure_regulator",
                "32_mm_manifold",
            ],
        },
        "description": (
            f"Zone control valve for {zone_id}."
        ),
    }

    project["valves"].append(valve)

    zone["valve_id"] = valve_id

    return valve


def create_zone_manifold(project, zone):
    zone_id = zone["id"]

    existing_manifolds = get_zone_manifolds(
        project,
        zone_id,
    )

    if existing_manifolds:
        return existing_manifolds[0]

    manifold_id = f"M32-{zone_id}"

    dripline_ids = [
        dripline.get("id")
        for dripline in get_zone_driplines(
            project,
            zone_id,
        )
    ]

    manifold = {
        "id": manifold_id,
        "name": manifold_id,
        "entity_type": "pipe",
        "pipe_type": "manifold_32",
        "diameter_mm": 32,
        "material": "HDPE",
        "sector_id": zone.get("sector_id"),
        "zone_id": zone_id,
        "length_m": 0.0,
        "flow_m3h": zone.get(
            "target_flow_m3h",
            0.0,
        ),
        "from_node_id": zone.get(
            "valve_id"
        ),
        "to_node_id": None,
        "dripline_ids": dripline_ids,
        "geometry": {
            "type": "LineString",
            "coordinates": [],
        },
        "properties": {
            "outlet_count": len(dripline_ids),
            "role": "zone_manifold",
        },
        "description": (
            f"32 mm manifold serving "
            f"{len(dripline_ids)} dripline(s) "
            f"in {zone_id}."
        ),
    }

    project["pipes"].append(manifold)

    zone["manifold_id"] = manifold_id

    return manifold


def create_reducer_fitting(project, zone):
    zone_id = zone["id"]

    existing = [
        fitting
        for fitting in project.get("fittings", [])
        if fitting.get("zone_id") == zone_id
        and fitting.get("fitting_type")
        == "reducer_63_32"
    ]

    if existing:
        return existing[0]

    fitting = {
        "id": f"TEE-63-32-{zone_id}",
        "name": f"TEE-63-32-{zone_id}",
        "entity_type": "fitting",
        "fitting_type": "reducer_63_32",
        "sector_id": zone.get("sector_id"),
        "zone_id": zone_id,
        "inlet_diameter_mm": 63,
        "outlet_diameter_mm": 32,
        "connected_pipe_ids": [],
        "geometry": get_zone_centroid(zone),
        "description": (
            f"63 mm to 32 mm reducer tee "
            f"for {zone_id}."
        ),
    }

    project["fittings"].append(fitting)

    return fitting


def create_zone_control_assembly(project, zone):
    valve = create_zone_valve(
        project,
        zone,
    )

    manifold = create_zone_manifold(
        project,
        zone,
    )

    reducer = create_reducer_fitting(
        project,
        zone,
    )

    return {
        "valve": valve,
        "manifold": manifold,
        "reducer": reducer,
    }


def create_control_assemblies_for_all_zones(project):
    zones = project.get("zones", [])

    if not zones:
        return {
            "ok": False,
            "message": "No zones are available.",
            "created_zone_ids": [],
            "errors": [],
        }

    created_zone_ids = []
    errors = []

    ordered_zones = sorted(
        zones,
        key=lambda zone: (
            zone.get("sector_id", ""),
            zone.get("zone_number", 0),
        ),
    )

    for zone in ordered_zones:
        try:
            create_zone_control_assembly(
                project,
                zone,
            )

            created_zone_ids.append(
                zone["id"]
            )

        except Exception as exc:
            errors.append(
                f"{zone['id']}: {exc}"
            )

    return {
        "ok": len(created_zone_ids) > 0,
        "message": (
            f"Created or confirmed control "
            f"assemblies for "
            f"{len(created_zone_ids)} zone(s)."
        ),
        "created_zone_ids": created_zone_ids,
        "errors": errors,
    }
    
def migrate_zone_valve_ids(project):
    renamed_valves = []
    id_mapping = {}

    for valve in project.get("valves", []):
        if valve.get("valve_type") != "zone":
            continue

        sector_id = valve.get(
            "sector_id"
        )

        zone_id = valve.get(
            "zone_id"
        )

        if not sector_id or not zone_id:
            continue

        zone_number = None

        for zone in project.get("zones", []):
            if zone.get("id") == zone_id:
                zone_number = zone.get(
                    "zone_number"
                )
                break

        if zone_number is None:
            continue

        old_valve_id = valve.get("id")

        new_valve_id = (
            f"{sector_id}-ZV{zone_number}"
        )

        if old_valve_id == new_valve_id:
            continue

        id_mapping[old_valve_id] = new_valve_id

        valve["id"] = new_valve_id
        valve["name"] = new_valve_id

        valve["description"] = (
            f"Zone valve {new_valve_id} "
            f"serving {zone_id}."
        )

        renamed_valves.append({
            "old_id": old_valve_id,
            "new_id": new_valve_id,
        })

    for zone in project.get("zones", []):
        current_valve_id = zone.get(
            "valve_id"
        )

        if current_valve_id in id_mapping:
            zone["valve_id"] = id_mapping[
                current_valve_id
            ]

    for pipe in project.get("pipes", []):
        current_from_node = pipe.get(
            "from_node_id"
        )

        if current_from_node in id_mapping:
            pipe["from_node_id"] = id_mapping[
                current_from_node
            ]

        current_to_node = pipe.get(
            "to_node_id"
        )

        if current_to_node in id_mapping:
            pipe["to_node_id"] = id_mapping[
                current_to_node
            ]

    for fitting in project.get("fittings", []):
        connected_pipe_ids = fitting.get(
            "connected_pipe_ids",
            []
        )

        fitting["connected_pipe_ids"] = [
            id_mapping.get(
                item_id,
                item_id,
            )
            for item_id in connected_pipe_ids
        ]

    return {
        "ok": True,
        "message": (
            f"Renamed {len(renamed_valves)} "
            f"zone valve(s)."
        ),
        "renamed_valves": renamed_valves,
    }