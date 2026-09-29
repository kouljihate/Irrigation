import base64
import copy
import re
from lxml import etree


KML_NS = "http://www.opengis.net/kml/2.2"
NS = {"kml": KML_NS}


def parse_kml(kml_bytes):
    return etree.fromstring(kml_bytes)


def serialize_kml(root):
    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )


def parse_coordinates(coordinates_text):
    if not coordinates_text:
        return []

    coordinates = []

    for item in coordinates_text.strip().split():
        values = item.split(",")

        if len(values) < 2:
            continue

        longitude = float(values[0])
        latitude = float(values[1])
        altitude = float(values[2]) if len(values) >= 3 else 0.0

        coordinates.append([
            longitude,
            latitude,
            altitude,
        ])

    return coordinates


def get_placemark_name(placemark):
    name_node = placemark.find("kml:name", namespaces=NS)

    if name_node is not None and name_node.text:
        return name_node.text.strip()

    return "Unnamed Item"


def get_placemark_description(placemark):
    description_node = placemark.find(
        "kml:description",
        namespaces=NS,
    )

    if description_node is not None and description_node.text:
        return description_node.text.strip()

    return ""


def get_parent_folder_name(placemark):
    parent = placemark.getparent()

    while parent is not None:
        if parent.tag == f"{{{KML_NS}}}Folder":
            name_node = parent.find("kml:name", namespaces=NS)

            if name_node is not None and name_node.text:
                return name_node.text.strip()

        parent = parent.getparent()

    return "Imported KML"


def extract_kml_features(kml_bytes):
    root = parse_kml(kml_bytes)

    features = []

    placemarks = root.findall(
        ".//kml:Placemark",
        namespaces=NS,
    )

    for index, placemark in enumerate(placemarks, start=1):
        name = get_placemark_name(placemark)
        description = get_placemark_description(placemark)
        folder_name = get_parent_folder_name(placemark)

        point_nodes = placemark.findall(
            ".//kml:Point/kml:coordinates",
            namespaces=NS,
        )

        for geometry_index, point_node in enumerate(point_nodes, start=1):
            coordinates = parse_coordinates(point_node.text)

            if not coordinates:
                continue

            longitude, latitude, altitude = coordinates[0]

            features.append({
                "id": f"KML-POINT-{index}-{geometry_index}",
                "name": name,
                "description": description,
                "folder": folder_name,
                "entity_type": "imported_point",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        longitude,
                        latitude,
                        altitude,
                    ],
                },
            })

        line_nodes = placemark.findall(
            ".//kml:LineString/kml:coordinates",
            namespaces=NS,
        )

        for geometry_index, line_node in enumerate(line_nodes, start=1):
            coordinates = parse_coordinates(line_node.text)

            if len(coordinates) < 2:
                continue

            features.append({
                "id": f"KML-LINE-{index}-{geometry_index}",
                "name": name,
                "description": description,
                "folder": folder_name,
                "entity_type": "imported_line",
                "length_m": round(
                    line_length_m({
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coordinates,
                        },
                    }),
                    2,
                ),
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
            })

        polygon_nodes = placemark.findall(
            ".//kml:Polygon/kml:outerBoundaryIs/"
            "kml:LinearRing/kml:coordinates",
            namespaces=NS,
        )

        for geometry_index, polygon_node in enumerate(polygon_nodes, start=1):
            coordinates = parse_coordinates(polygon_node.text)

            if len(coordinates) < 3:
                continue

            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])

            features.append({
                "id": f"KML-POLYGON-{index}-{geometry_index}",
                "name": name,
                "description": description,
                "folder": folder_name,
                "entity_type": "imported_polygon",
                "area_m2": round(
                    polygon_area_m2({
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [coordinates],
                        },
                    }),
                    2,
                ),
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coordinates],
                },
            })

    return features


def polygon_area_m2(feature):
    from core.geometry import measure_area_m2

    geometry = feature.get("geometry")

    if not geometry or geometry.get("type") != "Polygon":
        return 0.0

    try:
        return measure_area_m2(geometry)
    except Exception:
        return 0.0


def line_length_m(feature):
    from core.geometry import measure_length_m

    geometry = feature.get("geometry")

    if not geometry or geometry.get("type") != "LineString":
        return 0.0

    try:
        return measure_length_m(geometry)
    except Exception:
        return 0.0


SECTOR_NAME_PATTERNS = [
    re.compile(r"^s\s*[-_]?\s*(\d+)$"),
    re.compile(r"^sector\s*[-_]?\s*(\d+)$"),
    re.compile(r"^block\s*[-_]?\s*(\d+)$"),
    re.compile(r"^plot\s*[-_]?\s*(\d+)$"),
]


def normalize_name(value):
    return value.strip().lower()


def get_sector_number(name):
    normalized = normalize_name(name)

    for pattern in SECTOR_NAME_PATTERNS:
        match = pattern.fullmatch(normalized)

        if match:
            return int(match.group(1))

    return None


def is_sector_name(name):
    return get_sector_number(name) is not None


def is_basin_name(name):
    normalized = normalize_name(name)

    basin_keywords = [
        "basin",
        "bassin",
        "reservoir",
        "tank",
        "water tank",
        "water storage",
    ]

    return any(
        keyword in normalized
        for keyword in basin_keywords
    )


def _matches_token(normalized, keyword):
    if keyword.isalnum():
        pattern = rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])"
        return re.search(pattern, normalized) is not None

    return keyword in normalized


def is_water_point_name(name):
    normalized = normalize_name(name)

    water_keywords = [
        "well",
        "water",
        "source",
        "pump",
        "forage",
        "puits",
        "t1",
    ]

    return any(
        _matches_token(normalized, keyword)
        for keyword in water_keywords
    )


def _original_id(feature):
    kml_feature_id = feature.get("kml_feature_id")

    if kml_feature_id:
        return kml_feature_id

    return feature.get("id")


def import_kml_to_project(project, kml_bytes):
    if isinstance(kml_bytes, str):
        kml_bytes = base64.b64decode(kml_bytes)
    features = extract_kml_features(kml_bytes)

    project["kml_features"] = features
    project["land_features"] = []
    project["sector_features"] = []
    project["water_point_features"] = []
    project["basin_features"] = []

    project["land"] = None
    project["water_points"] = []
    project["basins"] = []
    project["sectors"] = []

    point_features = [
        feature
        for feature in features
        if feature["geometry"]["type"] == "Point"
    ]

    line_features = [
        feature
        for feature in features
        if feature["geometry"]["type"] == "LineString"
    ]

    polygon_features = [
        feature
        for feature in features
        if feature["geometry"]["type"] == "Polygon"
    ]

    for point in point_features:
        point = copy.deepcopy(point)
        source_id = _original_id(point)
        point_name = point.get("name", "")

        if is_water_point_name(point_name):
            point["entity_type"] = "water_point"
        else:
            point["entity_type"] = "imported_point"

        point["kml_feature_id"] = source_id
        project["water_points"].append(point)
        project["water_point_features"].append(point)

    basin_polygons = []

    for polygon in polygon_features:
        polygon = copy.deepcopy(polygon)
        polygon_name = polygon.get("name", "")
        sector_number = get_sector_number(polygon_name)

        if sector_number is not None:
            polygon["entity_type"] = "sector"
            polygon["sector_number"] = sector_number
            polygon["kml_feature_id"] = _original_id(polygon)
            polygon["id"] = f"S{sector_number}"

            project["sectors"].append(polygon)
            project["sector_features"].append(polygon)

        elif is_basin_name(polygon_name):
            polygon["entity_type"] = "basin"
            polygon["kml_feature_id"] = _original_id(polygon)
            polygon["id"] = "BASIN-001"

            basin_polygons.append(polygon)
            project["basin_features"].append(polygon)

    project["basins"] = basin_polygons

    classified_ids = set()

    for sector in project["sectors"]:
        classified_ids.add(sector.get("kml_feature_id"))

    for basin in project["basins"]:
        classified_ids.add(basin.get("kml_feature_id"))

    unclassified_polygons = [
        polygon
        for polygon in polygon_features
        if polygon.get("id") not in classified_ids
    ]

    if unclassified_polygons:
        land_polygon = max(
            unclassified_polygons,
            key=polygon_area_m2,
        )
    else:
        land_polygon = None

    available_polygons = [
        polygon
        for polygon in unclassified_polygons
        if land_polygon is None
        or polygon.get("id") != land_polygon.get("id")
    ]

    project["unclassified_polygons"] = [
        dict(
            copy.deepcopy(polygon),
            kml_feature_id=polygon.get("id"),
            area_m2=round(polygon_area_m2(polygon), 2),
        )
        for polygon in available_polygons
    ]

    if land_polygon is not None:
        land_feature = copy.deepcopy(land_polygon)
        land_feature["entity_type"] = "land"
        land_feature["kml_feature_id"] = land_polygon.get("id")
        land_feature["id"] = "LAND-001"
        land_feature["name"] = "Land Boundary"
        land_feature["area_m2"] = round(
            polygon_area_m2(land_polygon),
            2,
        )

        project["land"] = land_feature
        project["land_features"].append(land_feature)

    project["sectors"] = sorted(
        project["sectors"],
        key=lambda sector: sector.get(
            "sector_number",
            999,
        ),
    )

    return {
        "ok": True,
        "feature_count": len(features),
        "point_count": len(point_features),
        "line_count": len(line_features),
        "polygon_count": len(polygon_features),
        "land_count": 1 if project["land"] else 0,
        "water_point_count": len(project["water_points"]),
        "basin_count": len(project["basins"]),
        "sector_count": len(project["sectors"]),
        "unclassified_polygon_count": len(available_polygons),
        "unclassified_polygons": [
            {
                "kml_feature_id": polygon.get("kml_feature_id"),
                "name": polygon.get("name"),
                "area_m2": polygon.get("area_m2"),
            }
            for polygon in project["unclassified_polygons"]
        ],
        "message": (
            "KML imported and classified successfully. "
            f"{len(project['sectors'])} sector(s) and "
            f"{len(project['basins'])} basin(s) were detected "
            "automatically; assign the remaining polygons from "
            "the Land and Sectors page."
        ),
    }


def export_project_to_kml(project):
    from exporters.kml_exporter import (
        export_kml_text,
    )

    return export_kml_text(project)
