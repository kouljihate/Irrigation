from math import floor

from shapely.geometry import Point, mapping, shape
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


def get_trees_for_zone(project, zone_id):
    return [
        tree
        for tree in project.get("trees", [])
        if tree.get("zone_id") == zone_id
    ]


def get_working_crs_from_row(row):
    properties = row.get("properties", {})

    working_crs = properties.get(
        "working_crs"
    )

    if working_crs:
        return working_crs

    return "EPSG:32630"


def get_transformers(working_crs):
    return (
        get_transformer(WGS84, working_crs),
        get_transformer(working_crs, WGS84),
    )


def generate_trees_on_row(
    row_geometry,
    working_crs,
    tree_spacing_m=4.0,
    end_offset_m=2.0,
):
    row_line_wgs84 = shape(row_geometry)

    if row_line_wgs84.geom_type != "LineString":
        raise ValueError(
            "Row geometry must be a LineString."
        )

    to_projected, to_wgs84 = get_transformers(
        working_crs
    )

    row_line = transform(
        to_projected.transform,
        row_line_wgs84,
    )

    usable_length = (
        row_line.length
        - (2 * end_offset_m)
    )

    if usable_length < 0:
        return []

    tree_count = int(
        floor(
            usable_length / tree_spacing_m
        )
    ) + 1

    trees = []

    for tree_number in range(
        1,
        tree_count + 1,
    ):
        distance_m = end_offset_m + (
            (tree_number - 1) * tree_spacing_m
        )

        if distance_m > (
            row_line.length - end_offset_m
        ):
            break

        tree_point_projected = row_line.interpolate(
            distance_m
        )

        tree_point_wgs84 = transform(
            to_wgs84.transform,
            tree_point_projected,
        )

        trees.append({
            "tree_number": tree_number,
            "geometry": mapping(
                tree_point_wgs84
            ),
        })

    return trees


def create_trees_for_zone(
    project,
    zone_id,
    tree_spacing_m=4.0,
    end_offset_m=2.0,
    crop_type="Orchard",
    emitters_per_tree=2,
    emitter_flow_lph=4.0,
):
    zone = get_zone_by_id(
        project,
        zone_id,
    )

    if zone is None:
        return {
            "ok": False,
            "message": f"Zone {zone_id} was not found.",
            "created_trees": [],
        }

    existing_trees = get_trees_for_zone(
        project,
        zone_id,
    )

    if existing_trees:
        return {
            "ok": False,
            "message": (
                f"{zone_id} already has "
                f"{len(existing_trees)} tree(s). "
                "It was skipped to avoid duplicates."
            ),
            "created_trees": [],
        }

    rows = get_rows_for_zone(
        project,
        zone_id,
    )

    if not rows:
        return {
            "ok": False,
            "message": (
                f"{zone_id} has no rows. "
                "Generate rows before generating trees."
            ),
            "created_trees": [],
        }

    saved_trees = []

    for row in rows:
        working_crs = get_working_crs_from_row(
            row
        )

        try:
            generated_trees = generate_trees_on_row(
                row_geometry=row["geometry"],
                working_crs=working_crs,
                tree_spacing_m=tree_spacing_m,
                end_offset_m=end_offset_m,
            )

        except Exception as exc:
            return {
                "ok": False,
                "message": (
                    f"Unable to generate trees on "
                    f"{row['id']}: {exc}"
                ),
                "created_trees": [],
            }

        for generated_tree in generated_trees:
            tree_number = generated_tree[
                "tree_number"
            ]

            tree_id = (
                f"TREE-{zone_id}-"
                f"R{row['row_number']:03d}-"
                f"T{tree_number:03d}"
            )

            tree = {
                "id": tree_id,
                "name": tree_id,
                "entity_type": "tree",
                "sector_id": zone.get(
                    "sector_id"
                ),
                "zone_id": zone_id,
                "row_id": row["id"],
                "row_number": row["row_number"],
                "tree_number": tree_number,
                "crop_type": crop_type,
                "tree_spacing_m": tree_spacing_m,
                "emitters_per_tree": (
                    emitters_per_tree
                ),
                "emitter_flow_lph": (
                    emitter_flow_lph
                ),
                "tree_flow_lph": (
                    emitters_per_tree
                    * emitter_flow_lph
                ),
                "geometry": generated_tree[
                    "geometry"
                ],
                "properties": {
                    "creation_method": (
                        "automatic_tree_generation"
                    ),
                },
                "description": (
                    f"{crop_type} tree in {zone_id}, "
                    f"on {row['id']}."
                ),
            }

            saved_trees.append(tree)

    project["trees"].extend(saved_trees)

    zone["tree_ids"] = [
        tree["id"]
        for tree in saved_trees
    ]

    zone["tree_count"] = len(saved_trees)

    zone["target_flow_m3h"] = round(
        (
            len(saved_trees)
            * emitters_per_tree
            * emitter_flow_lph
        ) / 1000,
        3,
    )

    return {
        "ok": True,
        "message": (
            f"Created {len(saved_trees)} trees "
            f"in {zone_id}."
        ),
        "created_trees": saved_trees,
        "zone_flow_m3h": zone[
            "target_flow_m3h"
        ],
    }


def create_trees_for_all_zones(
    project,
    tree_spacing_m=4.0,
    end_offset_m=2.0,
    crop_type="Orchard",
    emitters_per_tree=2,
    emitter_flow_lph=4.0,
):
    zones = project.get("zones", [])

    if not zones:
        return {
            "ok": False,
            "message": "No zones are available.",
            "created_zone_ids": [],
            "skipped_zone_ids": [],
            "errors": [],
            "total_trees": 0,
        }

    created_zone_ids = []
    skipped_zone_ids = []
    errors = []
    total_trees = 0

    ordered_zones = sorted(
        zones,
        key=lambda zone: (
            zone.get("sector_id", ""),
            zone.get("zone_number", 0),
        ),
    )

    for zone in ordered_zones:
        zone_id = zone.get("id")

        result = create_trees_for_zone(
            project=project,
            zone_id=zone_id,
            tree_spacing_m=tree_spacing_m,
            end_offset_m=end_offset_m,
            crop_type=crop_type,
            emitters_per_tree=emitters_per_tree,
            emitter_flow_lph=emitter_flow_lph,
        )

        if result["ok"]:
            created_zone_ids.append(
                zone_id
            )

            total_trees += len(
                result["created_trees"]
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
            f"Created {total_trees} tree(s) in "
            f"{len(created_zone_ids)} zone(s)."
        ),
        "created_zone_ids": created_zone_ids,
        "skipped_zone_ids": skipped_zone_ids,
        "errors": errors,
        "total_trees": total_trees,
    }


def remove_all_trees(project):
    removed_count = len(
        project.get("trees", [])
    )

    project["trees"] = []

    for zone in project.get("zones", []):
        zone["tree_ids"] = []
        zone["tree_count"] = 0
        zone["target_flow_m3h"] = 0.0

    return {
        "ok": True,
        "message": (
            f"Removed {removed_count} tree(s)."
        ),
    }