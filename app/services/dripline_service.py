def get_zone_by_id(project, zone_id):
    for zone in project.get("zones", []):
        if zone.get("id") == zone_id:
            return zone

    return None


def get_rows_for_zone(project, zone_id):
    return [
        row
        for row in project.get("rows", [])
        if row.get("zone_id") == zone_id
    ]


def get_trees_for_row(project, row_id):
    return [
        tree
        for tree in project.get("trees", [])
        if tree.get("row_id") == row_id
    ]


def get_driplines_for_zone(project, zone_id):
    return [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") == "dripline"
        and pipe.get("zone_id") == zone_id
    ]


def build_dripline_id(zone_id, row_number):
    return (
        f"D16-{zone_id}-"
        f"R{row_number:03d}"
    )


def create_driplines_for_zone(
    project,
    zone_id,
    diameter_mm=16,
    material="LDPE",
):
    zone = get_zone_by_id(
        project,
        zone_id,
    )

    if zone is None:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
            "created_driplines": [],
        }

    existing_driplines = get_driplines_for_zone(
        project,
        zone_id,
    )

    if existing_driplines:
        return {
            "ok": False,
            "message": (
                f"{zone_id} already has "
                f"{len(existing_driplines)} dripline(s). "
                "It was skipped to avoid duplicates."
            ),
            "created_driplines": [],
        }

    rows = get_rows_for_zone(
        project,
        zone_id,
    )

    if not rows:
        return {
            "ok": False,
            "message": (
                f"{zone_id} has no planting rows. "
                "Generate rows before driplines."
            ),
            "created_driplines": [],
        }

    created_driplines = []

    for row in rows:
        row_number = row.get(
            "row_number",
            0,
        )

        dripline_id = build_dripline_id(
            zone_id,
            row_number,
        )

        trees_on_row = get_trees_for_row(
            project,
            row.get("id"),
        )

        emitters_per_tree = 2
        emitter_flow_lph = 4.0

        if trees_on_row:
            emitters_per_tree = trees_on_row[0].get(
                "emitters_per_tree",
                2,
            )

            emitter_flow_lph = trees_on_row[0].get(
                "emitter_flow_lph",
                4.0,
            )

        tree_count = len(trees_on_row)

        lateral_flow_lph = (
            tree_count
            * emitters_per_tree
            * emitter_flow_lph
        )

        dripline = {
            "id": dripline_id,
            "name": dripline_id,
            "entity_type": "pipe",
            "pipe_type": "dripline",
            "diameter_mm": diameter_mm,
            "material": material,
            "sector_id": zone.get("sector_id"),
            "zone_id": zone_id,
            "row_id": row.get("id"),
            "row_number": row_number,
            "length_m": row.get(
                "length_m",
                0.0,
            ),
            "flow_m3h": round(
                lateral_flow_lph / 1000,
                4,
            ),
            "tree_count": tree_count,
            "emitters_per_tree": emitters_per_tree,
            "emitter_flow_lph": emitter_flow_lph,
            "from_node_id": None,
            "to_node_id": None,
            "geometry": row.get("geometry"),
            "properties": {
                "creation_method": (
                    "automatic_from_planting_row"
                ),
                "requires_start_connector": True,
                "requires_end_flush": True,
            },
            "description": (
                f"16 mm dripline serving "
                f"{tree_count} tree(s) on {row['id']}."
            ),
        }

        created_driplines.append(
            dripline
        )

    project["pipes"].extend(
        created_driplines
    )

    zone["dripline_ids"] = [
        dripline["id"]
        for dripline in created_driplines
    ]

    zone["dripline_count"] = len(
        created_driplines
    )

    zone["dripline_length_m"] = round(
        sum(
            dripline["length_m"]
            for dripline in created_driplines
        ),
        2,
    )

    return {
        "ok": True,
        "message": (
            f"Created {len(created_driplines)} "
            f"16 mm driplines in {zone_id}."
        ),
        "created_driplines": created_driplines,
    }


def create_driplines_for_all_zones(
    project,
    diameter_mm=16,
    material="LDPE",
):
    zones = project.get("zones", [])

    if not zones:
        return {
            "ok": False,
            "message": "No zones are available.",
            "created_zone_ids": [],
            "skipped_zone_ids": [],
            "errors": [],
            "total_driplines": 0,
            "total_length_m": 0.0,
        }

    created_zone_ids = []
    skipped_zone_ids = []
    errors = []
    total_driplines = 0
    total_length_m = 0.0

    ordered_zones = sorted(
        zones,
        key=lambda zone: (
            zone.get("sector_id", ""),
            zone.get("zone_number", 0),
        ),
    )

    for zone in ordered_zones:
        zone_id = zone.get("id")

        result = create_driplines_for_zone(
            project=project,
            zone_id=zone_id,
            diameter_mm=diameter_mm,
            material=material,
        )

        if result["ok"]:
            created_zone_ids.append(
                zone_id
            )

            created_driplines = result.get(
                "created_driplines",
                [],
            )

            total_driplines += len(
                created_driplines
            )

            total_length_m += sum(
                dripline.get(
                    "length_m",
                    0.0,
                )
                for dripline in created_driplines
            )

        else:
            message = result.get(
                "message",
                "",
            )

            if "already has" in message:
                skipped_zone_ids.append(
                    zone_id
                )
            else:
                errors.append(message)

    return {
        "ok": len(created_zone_ids) > 0,
        "message": (
            f"Created {total_driplines} "
            f"16 mm dripline(s) in "
            f"{len(created_zone_ids)} zone(s)."
        ),
        "created_zone_ids": created_zone_ids,
        "skipped_zone_ids": skipped_zone_ids,
        "errors": errors,
        "total_driplines": total_driplines,
        "total_length_m": round(
            total_length_m,
            2,
        ),
    }


def remove_all_driplines(project):
    before_count = len(
        project.get("pipes", [])
    )

    project["pipes"] = [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("pipe_type") != "dripline"
    ]

    removed_count = before_count - len(
        project["pipes"]
    )

    for zone in project.get("zones", []):
        zone["dripline_ids"] = []
        zone["dripline_count"] = 0
        zone["dripline_length_m"] = 0.0

    return {
        "ok": True,
        "message": (
            f"Removed {removed_count} "
            f"16 mm dripline(s)."
        ),
    }