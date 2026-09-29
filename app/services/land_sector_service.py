import copy
import re


def get_imported_features(project):
    return project.get("kml_features", [])


def get_imported_polygons(project):
    return [
        feature
        for feature in get_imported_features(project)
        if feature.get("geometry", {}).get("type") == "Polygon"
    ]


def get_imported_points(project):
    return [
        feature
        for feature in get_imported_features(project)
        if feature.get("geometry", {}).get("type") == "Point"
    ]


def get_feature_by_id(project, feature_id):
    for feature in get_imported_features(project):
        if feature.get("id") == feature_id:
            return copy.deepcopy(feature)

    return None


def set_land_boundary(project, feature_id):
    feature = get_feature_by_id(project, feature_id)

    if feature is None:
        return {
            "ok": False,
            "message": "Selected land polygon was not found.",
        }

    if feature.get("geometry", {}).get("type") != "Polygon":
        return {
            "ok": False,
            "message": "The land boundary must be a polygon.",
        }

    feature["id"] = "LAND-001"
    feature["name"] = "Land Boundary"
    feature["entity_type"] = "land"

    project["land"] = feature

    return {
        "ok": True,
        "message": "Land boundary saved successfully.",
        "feature": feature,
    }


def set_water_point(project, feature_id):
    feature = get_feature_by_id(project, feature_id)

    if feature is None:
        return {
            "ok": False,
            "message": "Selected water point was not found.",
        }

    if feature.get("geometry", {}).get("type") != "Point":
        return {
            "ok": False,
            "message": "The water point must be a point marker.",
        }

    feature["id"] = "WELL-001"
    feature["name"] = "Water Point / Well"
    feature["entity_type"] = "water_point"

    project["water_points"] = [feature]

    return {
        "ok": True,
        "message": "Water point saved successfully.",
        "feature": feature,
    }


def set_basin(project, feature_id):
    feature = get_feature_by_id(project, feature_id)

    if feature is None:
        return {
            "ok": False,
            "message": "Selected basin polygon was not found.",
        }

    if feature.get("geometry", {}).get("type") != "Polygon":
        return {
            "ok": False,
            "message": "The basin must be a polygon.",
        }

    feature["id"] = "BASIN-001"
    feature["name"] = "Basin"
    feature["entity_type"] = "basin"

    project["basins"] = [feature]

    return {
        "ok": True,
        "message": "Basin saved successfully.",
        "feature": feature,
    }


def get_sector_number_from_name(name):
    match = re.search(
        r"(\d+)",
        str(name),
    )

    if match:
        return int(match.group(1))

    return None


def add_sector(project, feature_id, sector_number):
    feature = get_feature_by_id(project, feature_id)

    if feature is None:
        return {
            "ok": False,
            "message": "Selected sector polygon was not found.",
        }

    if feature.get("geometry", {}).get("type") != "Polygon":
        return {
            "ok": False,
            "message": "A sector must be a polygon.",
        }

    sector_id = f"S{sector_number}"

    existing_sectors = project.get("sectors", [])

    for sector in existing_sectors:
        if sector.get("id") == sector_id:
            return {
                "ok": False,
                "message": f"{sector_id} already exists.",
            }

    feature["kml_feature_id"] = feature.get("kml_feature_id") or feature.get("id")
    feature["id"] = sector_id
    feature["name"] = sector_id
    feature["entity_type"] = "sector"
    feature["sector_number"] = sector_number

    from core.geometry import measure_area_m2

    area_m2 = measure_area_m2(feature.get("geometry"))

    feature["area_m2"] = round(area_m2, 2)
    feature["area_ha"] = round(area_m2 / 10000, 4)

    land = project.get("land")

    if land and land.get("geometry"):
        from core.geometry import is_inside_polygon

        if not is_inside_polygon(
            feature["geometry"],
            land["geometry"],
        ):
            return {
                "ok": False,
                "message": (
                    f"{sector_id} lies outside the assigned "
                    "land boundary."
                ),
            }

    project["sectors"].append(feature)

    project["sectors"] = sorted(
        project["sectors"],
        key=lambda item: item.get("sector_number", 999),
    )

    return {
        "ok": True,
        "message": f"{sector_id} saved successfully.",
        "feature": feature,
    }


def remove_sector(project, sector_id):
    sectors_before = len(project.get("sectors", []))

    project["sectors"] = [
        sector
        for sector in project.get("sectors", [])
        if sector.get("id") != sector_id
    ]

    sectors_after = len(project["sectors"])

    if sectors_before == sectors_after:
        return {
            "ok": False,
            "message": f"{sector_id} was not found.",
        }

    return {
        "ok": True,
        "message": f"{sector_id} removed.",
    }


def clear_land_and_sector_setup(project):
    project["land"] = None
    project["water_points"] = []
    project["basins"] = []
    project["sectors"] = []

    return {
        "ok": True,
        "message": "Land, water point, basin, and sectors were cleared.",
    }