from lxml import etree


KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"

NSMAP = {None: KML_NS, "gx": GX_NS}


LAYER_STYLES = {
    "land": ("ffffffff", 3, 1),
    "sector": ("ff12f39c", 2, 1),
    "zone": ("ffb659b6", 2, 1),
    "row": ("ff236b8e", 1, 0),
    "tree": ("ff712ecc", 0, 1),
    "pipe_90": ("ff0000ff", 4, 0),
    "pipe_63": ("ffff6600", 3, 0),
    "pipe_32": ("ff00aa00", 2, 0),
    "pipe_16": ("ff808080", 1, 0),
    "valve": ("ff00d0ff", 0, 1),
    "water_point": ("ffffbf00", 0, 1),
    "basin": ("ffcc0066", 2, 1),
    "fitting": ("ffffcc00", 0, 1),
}


def kml_tag(tag):
    return f"{{{KML_NS}}}{tag}"


def get_style(entity_type, diameter_mm=None):
    if diameter_mm is not None:
        key = f"pipe_{diameter_mm}"

        if key in LAYER_STYLES:
            return LAYER_STYLES[key]

    return LAYER_STYLES.get(
        entity_type,
        ("ff888888", 2, 0),
    )


def add_text(parent, tag, value):
    if value is None:
        return None

    node = etree.SubElement(parent, kml_tag(tag))
    node.text = str(value)

    return node


def format_coordinate(point):
    longitude = float(point[0])
    latitude = float(point[1])
    altitude = float(point[2]) if len(point) > 2 else 0.0

    return f"{longitude},{latitude},{altitude}"


def format_ring(ring):
    return " ".join(
        format_coordinate(point)
        for point in ring
    )


def add_style(parent, feature):
    color, width, is_fill = get_style(
        feature.get("entity_type", ""),
        feature.get("diameter_mm"),
    )

    style = etree.SubElement(parent, kml_tag("Style"))

    line_style = etree.SubElement(style, kml_tag("LineStyle"))
    add_text(line_style, "color", color)
    add_text(line_style, "width", width)

    if is_fill:
        poly_style = etree.SubElement(
            style,
            kml_tag("PolyStyle"),
        )
        add_text(poly_style, "color", f"{color[:-2]}44")

    return style


def add_geometry(parent, feature):
    geometry = feature.get("geometry") or {}
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates") or []

    if geometry_type == "Point":
        if not coordinates:
            return False

        node = etree.SubElement(parent, kml_tag("Point"))
        add_text(
            node,
            "coordinates",
            format_coordinate(coordinates),
        )
        return True

    if geometry_type == "LineString":
        if len(coordinates) < 2:
            return False

        node = etree.SubElement(parent, kml_tag("LineString"))
        add_text(node, "tessellate", 1)
        add_text(
            node,
            "coordinates",
            format_ring(coordinates),
        )
        return True

    if geometry_type == "Polygon":
        if not coordinates:
            return False

        node = etree.SubElement(parent, kml_tag("Polygon"))
        written = 0

        for index, ring in enumerate(coordinates):
            if len(ring) < 4:
                continue

            if index == 0:
                boundary = etree.SubElement(
                    node,
                    kml_tag("outerBoundaryIs"),
                )
            else:
                boundary = etree.SubElement(
                    node,
                    kml_tag("innerBoundaryIs"),
                )

            linear_ring = etree.SubElement(
                boundary,
                kml_tag("LinearRing"),
            )
            add_text(
                linear_ring,
                "coordinates",
                format_ring(ring),
            )
            written += 1

        return written > 0

    return False


def add_placemark(parent, feature):
    if feature.get("geometry") is None:
        return False

    placemark = etree.SubElement(
        parent,
        kml_tag("Placemark"),
    )

    add_text(placemark, "name", feature.get("name"))
    add_text(
        placemark,
        "description",
        feature.get("description"),
    )

    add_style(placemark, feature)

    if not add_geometry(placemark, feature):
        parent.remove(placemark)
        return False

    return True


def build_collections(project):
    collections = []

    land = project.get("land")

    if land:
        collections.append({
            "name": "Land boundary",
            "features": [land],
        })

    for name, key in [
        ("Basins", "basins"),
        ("Water points", "water_points"),
        ("Sectors", "sectors"),
        ("Zones", "zones"),
        ("Pipes", "pipes"),
        ("Valves", "valves"),
        ("Fittings", "fittings"),
        ("Rows", "rows"),
        ("Trees", "trees"),
    ]:
        features = project.get(key) or []

        if features:
            collections.append({
                "name": name,
                "features": features,
            })

    return collections


def export_kml_text(project):
    root = etree.Element(kml_tag("kml"), nsmap=NSMAP)

    document = etree.SubElement(
        root,
        kml_tag("Document"),
    )

    add_text(
        document,
        "name",
        project.get("project", {}).get(
            "name",
            "Farm Project",
        ),
    )

    add_text(
        document,
        "description",
        "Exported by Farm Irrigation Designer.",
    )

    for collection in build_collections(project):
        folder = etree.SubElement(
            document,
            kml_tag("Folder"),
        )
        add_text(folder, "name", collection["name"])

        for feature in collection["features"]:
            add_placemark(folder, feature)

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    ).decode("utf-8")


def export_kml_bytes(project):
    return export_kml_text(project).encode("utf-8")
