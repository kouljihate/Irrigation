from shapely.geometry import box, mapping, shape

from core.geometry import measure_area_m2
from core.validators import validate_zone_inside_sector


def get_zones_for_sector(project, sector_id):
    return [
        zone
        for zone in project.get("zones", [])
        if zone.get("sector_id") == sector_id
    ]


def get_sector_by_id(project, sector_id):
    for sector in project.get("sectors", []):
        if sector.get("id") == sector_id:
            return sector

    return None


def get_sector_number(sector):
    value = sector.get("sector_number")

    if value is not None:
        return int(value)

    sector_id = str(sector.get("id", ""))

    if sector_id.startswith("S"):
        try:
            return int(sector_id[1:])
        except ValueError:
            return 0

    return 0


def get_polygon_from_geometry(geometry):
    polygon = shape(geometry)

    if polygon.geom_type != "Polygon":
        raise ValueError(
            "Expected a Polygon geometry."
        )

    if not polygon.is_valid:
        raise ValueError(
            "Sector polygon is invalid."
        )

    if polygon.area <= 0:
        raise ValueError(
            "Sector polygon area must be greater than zero."
        )

    return polygon


def find_cut_coordinate(
    polygon,
    axis,
    target_fraction,
):
    min_x, min_y, max_x, max_y = polygon.bounds

    margin = max(
        max_x - min_x,
        max_y - min_y,
    ) * 2

    total_area = polygon.area
    target_area = total_area * target_fraction

    if axis == "x":
        low = min_x
        high = max_x

        for _ in range(60):
            middle = (low + high) / 2

            left_side = box(
                min_x - margin,
                min_y - margin,
                middle,
                max_y + margin,
            )

            current_area = polygon.intersection(
                left_side
            ).area

            if current_area < target_area:
                low = middle
            else:
                high = middle

        return (low + high) / 2

    low = min_y
    high = max_y

    for _ in range(60):
        middle = (low + high) / 2

        bottom_side = box(
            min_x - margin,
            min_y - margin,
            max_x + margin,
            middle,
        )

        current_area = polygon.intersection(
            bottom_side
        ).area

        if current_area < target_area:
            low = middle
        else:
            high = middle

    return (low + high) / 2


def make_three_equal_parts(polygon):
    min_x, min_y, max_x, max_y = polygon.bounds

    width = max_x - min_x
    height = max_y - min_y

    axis = "x" if width >= height else "y"

    first_cut = find_cut_coordinate(
        polygon=polygon,
        axis=axis,
        target_fraction=1 / 3,
    )

    second_cut = find_cut_coordinate(
        polygon=polygon,
        axis=axis,
        target_fraction=2 / 3,
    )

    margin = max(width, height) * 2

    if axis == "x":
        first_area_box = box(
            min_x - margin,
            min_y - margin,
            first_cut,
            max_y + margin,
        )

        second_area_box = box(
            first_cut,
            min_y - margin,
            second_cut,
            max_y + margin,
        )

        third_area_box = box(
            second_cut,
            min_y - margin,
            max_x + margin,
            max_y + margin,
        )

    else:
        first_area_box = box(
            min_x - margin,
            min_y - margin,
            max_x + margin,
            first_cut,
        )

        second_area_box = box(
            min_x - margin,
            first_cut,
            max_x + margin,
            second_cut,
        )

        third_area_box = box(
            min_x - margin,
            second_cut,
            max_x + margin,
            max_y + margin,
        )

    part_1 = polygon.intersection(first_area_box)
    part_2 = polygon.intersection(second_area_box)
    part_3 = polygon.intersection(third_area_box)

    parts = [
        part_1,
        part_2,
        part_3,
    ]

    for index, part in enumerate(parts, start=1):
        if part.is_empty:
            raise ValueError(
                f"Zone part {index} is empty."
            )

        if part.geom_type != "Polygon":
            raise ValueError(
                f"Zone part {index} is not a simple polygon."
            )

        if part.area <= 0:
            raise ValueError(
                f"Zone part {index} has no area."
            )

    return parts


def build_zone(
    sector_id,
    zone_number,
    polygon,
    name="",
):
    zone_id = f"{sector_id}-Z{zone_number}"

    area_m2 = measure_area_m2(mapping(polygon))

    return {
        "id": zone_id,
        "name": name or zone_id,
        "entity_type": "zone",
        "sector_id": sector_id,
        "zone_number": zone_number,
        "geometry": mapping(polygon),
        "area_m2": round(area_m2, 2),
        "area_ha": round(area_m2 / 10000.0, 4),
        "target_flow_m3h": 0.0,
        "valve_id": None,
        "row_ids": [],
        "tree_ids": [],
        "pipe_ids": [],
        "properties": {
            "creation_method": "automatic_equal_split",
        },
        "description": (
            f"Automatically generated approximately equal zone "
            f"{zone_number} inside {sector_id}."
        ),
    }


def get_zone_by_id(project, zone_id):
    for zone in project.get("zones", []):
        if zone.get("id") == zone_id:
            return zone

    return None


def create_zone(
    project,
    sector_id,
    zone_number=1,
    geojson_geometry=None,
    name="",
):
    sector = get_sector_by_id(
        project,
        sector_id,
    )

    if sector is None:
        return {
            "ok": False,
            "message": f"Sector {sector_id} was not found.",
            "created_zone": None,
        }

    try:
        zone_number = int(zone_number)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "message": "Zone number must be a whole number.",
            "created_zone": None,
        }

    if zone_number < 1:
        return {
            "ok": False,
            "message": "Zone number must be 1 or greater.",
            "created_zone": None,
        }

    zone_id = f"{sector_id}-Z{zone_number}"

    if get_zone_by_id(project, zone_id) is not None:
        return {
            "ok": False,
            "message": f"{zone_id} already exists.",
            "created_zone": None,
        }

    if not geojson_geometry:
        return {
            "ok": False,
            "message": (
                "No zone geometry was provided. "
                "Draw a polygon on the map first."
            ),
            "created_zone": None,
        }

    try:
        polygon = get_polygon_from_geometry(
            geojson_geometry
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": f"Invalid zone geometry: {exc}",
            "created_zone": None,
        }

    sector_geometry = sector.get("geometry")

    if sector_geometry:
        validation = validate_zone_inside_sector(
            geojson_geometry,
            sector_geometry,
        )

        if not validation["ok"]:
            return {
                "ok": False,
                "message": validation["message"],
                "created_zone": None,
            }

    zone = build_zone(
        sector_id=sector_id,
        zone_number=zone_number,
        polygon=polygon,
        name=name,
    )

    zone["properties"]["creation_method"] = "manual_digitised"

    project["zones"].append(zone)

    return {
        "ok": True,
        "message": f"Created {zone_id} ({zone['area_m2']} m2).",
        "created_zone": zone,
    }


def create_three_zones_for_sector(
    project,
    sector_id,
):
    sector = get_sector_by_id(
        project,
        sector_id,
    )

    if sector is None:
        return {
            "ok": False,
            "message": f"{sector_id} was not found.",
            "created_zones": [],
        }

    existing_zones = get_zones_for_sector(
        project,
        sector_id,
    )

    if existing_zones:
        return {
            "ok": False,
            "message": (
                f"{sector_id} already has "
                f"{len(existing_zones)} zone(s). "
                "It was skipped to prevent duplicates."
            ),
            "created_zones": [],
        }

    try:
        sector_polygon = get_polygon_from_geometry(
            sector["geometry"]
        )

        parts = make_three_equal_parts(
            sector_polygon
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Unable to split {sector_id}: {exc}"
            ),
            "created_zones": [],
        }

    new_zones = []

    for zone_number, part in enumerate(parts, start=1):
        zone = build_zone(
            sector_id=sector_id,
            zone_number=zone_number,
            polygon=part,
        )

        new_zones.append(zone)

    project["zones"].extend(new_zones)

    return {
        "ok": True,
        "message": (
            f"Created three approximately equal zones "
            f"for {sector_id}."
        ),
        "created_zones": new_zones,
    }


def create_three_zones_for_all_sectors(project):
    sectors = project.get("sectors", [])

    if not sectors:
        return {
            "ok": False,
            "message": "No sectors are available.",
            "created_sector_ids": [],
            "skipped_sector_ids": [],
            "errors": [],
        }

    created_sector_ids = []
    skipped_sector_ids = []
    errors = []

    ordered_sectors = sorted(
        sectors,
        key=get_sector_number,
    )

    for sector in ordered_sectors:
        sector_id = sector.get("id")

        result = create_three_zones_for_sector(
            project=project,
            sector_id=sector_id,
        )

        if result["ok"]:
            created_sector_ids.append(
                sector_id
            )
        else:
            message = result.get("message", "")

            if "already has" in message:
                skipped_sector_ids.append(
                    sector_id
                )
            else:
                errors.append(message)

    total_created_zones = len(
        created_sector_ids
    ) * 3

    message = (
        f"Created {total_created_zones} zones in "
        f"{len(created_sector_ids)} sector(s)."
    )

    return {
        "ok": len(created_sector_ids) > 0,
        "message": message,
        "created_sector_ids": created_sector_ids,
        "skipped_sector_ids": skipped_sector_ids,
        "errors": errors,
        "total_created_zones": total_created_zones,
    }


def _purge_zone_dependents(project, zone_ids):
    """Remove the pipes, valves, rows and trees owned by the given zones.

    Deleting zones without clearing their dependents leaves orphan
    manifolds and valves behind, which then show up in the quantity and
    hydraulic reports as if they were still connected.
    """
    if not zone_ids:
        return {
            "pipes": 0,
            "valves": 0,
            "rows": 0,
            "trees": 0,
        }

    surviving_rows = {
        row.get("id")
        for row in project.get("rows", [])
        if row.get("zone_id") not in zone_ids
    }

    removed = {
        "pipes": sum(
            1
            for pipe in project.get("pipes", [])
            if pipe.get("zone_id") in zone_ids
        ),
        "valves": sum(
            1
            for valve in project.get("valves", [])
            if valve.get("zone_id") in zone_ids
        ),
        "rows": sum(
            1
            for row in project.get("rows", [])
            if row.get("zone_id") in zone_ids
        ),
        "trees": sum(
            1
            for tree in project.get("trees", [])
            if tree.get("zone_id") in zone_ids
        ),
    }

    project["pipes"] = [
        pipe
        for pipe in project.get("pipes", [])
        if pipe.get("zone_id") not in zone_ids
    ]

    project["valves"] = [
        valve
        for valve in project.get("valves", [])
        if valve.get("zone_id") not in zone_ids
    ]

    project["rows"] = [
        row
        for row in project.get("rows", [])
        if row.get("zone_id") not in zone_ids
    ]

    project["trees"] = [
        tree
        for tree in project.get("trees", [])
        if tree.get("zone_id") not in zone_ids
    ]

    project["pipes"] = [
        pipe
        for pipe in project["pipes"]
        if pipe.get("row_id") in surviving_rows
        or pipe.get("row_id") is None
    ]

    return removed


def remove_zone(project, zone_id):
    before_count = len(project.get("zones", []))

    zone = next(
        (
            item
            for item in project.get("zones", [])
            if item.get("id") == zone_id
        ),
        None,
    )

    if zone is None:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
        }

    project["zones"] = [
        item
        for item in project.get("zones", [])
        if item.get("id") != zone_id
    ]

    after_count = len(project["zones"])

    if before_count == after_count:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
        }

    removed = _purge_zone_dependents(project, {zone_id})

    return {
        "ok": True,
        "message": (
            f"Zone {zone_id} removed together with "
            f"{removed['pipes']} pipe(s), {removed['valves']} valve(s), "
            f"{removed['rows']} row(s) and {removed['trees']} tree(s)."
        ),
    }


def remove_all_zones(project):
    removed_count = len(project.get("zones", []))

    zone_ids = {
        zone.get("id")
        for zone in project.get("zones", [])
    }

    project["zones"] = []

    removed = _purge_zone_dependents(project, zone_ids)

    return {
        "ok": True,
        "message": (
            f"Removed {removed_count} zone(s) together with "
            f"{removed['pipes']} pipe(s), {removed['valves']} valve(s), "
            f"{removed['rows']} row(s) and {removed['trees']} tree(s)."
        ),
    }
