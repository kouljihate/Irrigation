from math import floor

from shapely.affinity import rotate
from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform

from core.geometry import WGS84, get_transformer


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


def get_transformers(working_crs):
    return (
        get_transformer(WGS84, working_crs),
        get_transformer(working_crs, WGS84),
    )


def transform_to_projected(
    geometry,
    transformer,
):
    return transform(
        transformer.transform,
        geometry,
    )


def transform_to_wgs84(
    geometry,
    transformer,
):
    return transform(
        transformer.transform,
        geometry,
    )


def get_line_parts(geometry):
    if geometry.is_empty:
        return []

    if geometry.geom_type == "LineString":
        return [geometry]

    if geometry.geom_type == "MultiLineString":
        return list(geometry.geoms)

    if geometry.geom_type == "GeometryCollection":
        lines = []

        for item in geometry.geoms:
            lines.extend(
                get_line_parts(item)
            )

        return lines

    return []


def generate_row_lines(
    zone_geometry,
    row_spacing_m,
    row_angle_degrees=0,
    headland_m=2.0,
):
    zone_polygon_wgs84 = shape(zone_geometry)

    if zone_polygon_wgs84.geom_type != "Polygon":
        raise ValueError(
            "Zone geometry must be a Polygon."
        )

    if not zone_polygon_wgs84.is_valid:
        raise ValueError(
            "Zone polygon is invalid."
        )

    working_crs = get_utm_epsg_from_geometry(
        zone_geometry
    )

    to_projected, to_wgs84 = get_transformers(
        working_crs
    )

    zone_polygon = transform_to_projected(
        zone_polygon_wgs84,
        to_projected,
    )

    usable_polygon = zone_polygon.buffer(
        -headland_m
    )

    if usable_polygon.is_empty:
        raise ValueError(
            "Headland is too large for this zone."
        )

    if usable_polygon.geom_type != "Polygon":
        raise ValueError(
            "Zone became invalid after applying headland."
        )

    rotated_polygon = rotate(
        usable_polygon,
        -row_angle_degrees,
        origin="centroid",
        use_radians=False,
    )

    min_x, min_y, max_x, max_y = rotated_polygon.bounds

    start_y = min_y + (
        row_spacing_m / 2
    )

    extended_length = (
        max_x - min_x
    ) + 1000

    generated_rows = []
    current_y = start_y
    row_number = 1

    while current_y <= max_y:
        candidate_line = LineString([
            [min_x - extended_length, current_y],
            [max_x + extended_length, current_y],
        ])

        clipped_geometry = rotated_polygon.intersection(
            candidate_line
        )

        line_parts = get_line_parts(
            clipped_geometry
        )

        for line_part in line_parts:
            if line_part.length < 1:
                continue

            restored_line = rotate(
                line_part,
                row_angle_degrees,
                origin=usable_polygon.centroid,
                use_radians=False,
            )

            restored_line_wgs84 = transform_to_wgs84(
                restored_line,
                to_wgs84,
            )

            generated_rows.append({
                "row_number": row_number,
                "geometry": mapping(
                    restored_line_wgs84
                ),
                "length_m": round(
                    restored_line.length,
                    2,
                ),
                "working_crs": working_crs,
            })

            row_number += 1

        current_y += row_spacing_m

    return generated_rows


def create_rows_for_zone(
    project,
    zone_id,
    row_spacing_m,
    row_angle_degrees=0,
    headland_m=2.0,
):
    zone = get_zone_by_id(
        project,
        zone_id,
    )

    if zone is None:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
            "created_rows": [],
        }

    existing_rows = get_rows_for_zone(
        project,
        zone_id,
    )

    if existing_rows:
        return {
            "ok": False,
            "message": (
                f"{zone_id} already has "
                f"{len(existing_rows)} row(s). "
                "It was skipped to avoid duplicates."
            ),
            "created_rows": [],
        }

    try:
        generated_rows = generate_row_lines(
            zone_geometry=zone["geometry"],
            row_spacing_m=row_spacing_m,
            row_angle_degrees=row_angle_degrees,
            headland_m=headland_m,
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Unable to generate rows for "
                f"{zone_id}: {exc}"
            ),
            "created_rows": [],
        }

    saved_rows = []

    for generated_row in generated_rows:
        row_number = generated_row["row_number"]

        row = {
            "id": (
                f"ROW-{zone_id}-{row_number:03d}"
            ),
            "name": (
                f"Row {row_number} - {zone_id}"
            ),
            "entity_type": "row",
            "sector_id": zone.get("sector_id"),
            "zone_id": zone_id,
            "row_number": row_number,
            "length_m": generated_row["length_m"],
            "spacing_m": row_spacing_m,
            "direction_degrees": row_angle_degrees,
            "headland_m": headland_m,
            "geometry": generated_row["geometry"],
            "properties": {
                "working_crs": (
                    generated_row["working_crs"]
                ),
                "creation_method": (
                    "automatic_row_generation"
                ),
            },
            "description": (
                f"Automatic planting row inside "
                f"{zone_id}."
            ),
        }

        saved_rows.append(row)

    project["rows"].extend(saved_rows)

    zone["row_ids"] = [
        row["id"]
        for row in saved_rows
    ]

    return {
        "ok": True,
        "message": (
            f"Created {len(saved_rows)} rows "
            f"inside {zone_id}."
        ),
        "created_rows": saved_rows,
    }


def create_rows_for_all_zones(
    project,
    row_spacing_m,
    headland_m=2.0,
):
    zones = project.get("zones", [])

    if not zones:
        return {
            "ok": False,
            "message": "No zones are available.",
            "created_zone_ids": [],
            "skipped_zone_ids": [],
            "errors": [],
            "total_rows": 0,
        }

    created_zone_ids = []
    skipped_zone_ids = []
    errors = []
    total_rows = 0

    ordered_zones = sorted(
        zones,
        key=lambda zone: (
            zone.get("sector_id", ""),
            zone.get("zone_number", 0),
        ),
    )

    for zone in ordered_zones:
        zone_id = zone.get("id")

        zone_angle = zone.get(
            "recommended_row_angle_degrees"
        )

        if zone_angle is None:
            errors.append(
                f"{zone_id} has no elevation-based row angle. "
                "Run elevation analysis before generating rows."
            )
            continue

        result = create_rows_for_zone(
            project=project,
            zone_id=zone_id,
            row_spacing_m=row_spacing_m,
            row_angle_degrees=zone_angle,
            headland_m=headland_m,
        )

        if result["ok"]:
            created_zone_ids.append(
                zone_id
            )

            total_rows += len(
                result["created_rows"]
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
            f"Created {total_rows} planting rows "
            f"in {len(created_zone_ids)} zone(s)."
        ),
        "created_zone_ids": created_zone_ids,
        "skipped_zone_ids": skipped_zone_ids,
        "errors": errors,
        "total_rows": total_rows,
    }

def remove_all_rows(project):
    removed_count = len(
        project.get("rows", [])
    )

    project["rows"] = []

    for zone in project.get("zones", []):
        zone["row_ids"] = []

    return {
        "ok": True,
        "message": (
            f"Removed {removed_count} row(s)."
        ),
    }