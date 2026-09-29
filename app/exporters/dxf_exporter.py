from functools import lru_cache

import ezdxf
from ezdxf import colors
from shapely.geometry import shape
from shapely.ops import nearest_points, transform

from core.geometry import (
    WGS84,
    get_transformer,
    get_utm_epsg_from_coordinates,
)



LAYERS = {
    "LAND_BOUNDARY": {
        "color": colors.WHITE,
        "description": "Farm land boundary",
    },
    "SECTORS": {
        "color": colors.YELLOW,
        "description": "Irrigation sectors",
    },
    "ZONES": {
        "color": colors.MAGENTA,
        "description": "Irrigation zones",
    },
    "PIPE_90": {
        "color": colors.RED,
        "description": "90 mm principal pipe",
    },
    "PIPE_63": {
        "color": colors.BLUE,
        "description": "63 mm sector main",
    },
    "PIPE_32": {
        "color": colors.GREEN,
        "description": "32 mm manifold pipe",
    },
    "DRIP_16": {
        "color": colors.GRAY,
        "description": "16 mm dripline",
    },
    "VALVES": {
        "color": colors.YELLOW,
        "description": "Control valves",
    },
    "TREES": {
        "color": 50,
        "description": "Planted trees",
    },
    "ROWS": {
        "color": colors.GREEN,
        "description": "Planting rows",
    },
    "WATER_POINTS": {
        "color": colors.CYAN,
        "description": "Water sources",
    },
    "BASINS": {
        "color": colors.BLUE,
        "description": "Storage basins",
    },
}


@lru_cache(maxsize=64)
def get_pipe_layer(diameter_mm):
    try:
        diameter_mm = int(diameter_mm)
    except (TypeError, ValueError):
        return "PIPE_32"

    return {
        90: "PIPE_90",
        63: "PIPE_63",
        32: "PIPE_32",
        16: "DRIP_16",
    }.get(diameter_mm, "PIPE_32")


def _get_working_crs(project, geometry=None):
    settings = project.get("project") or {}
    configured = settings.get("working_crs")

    if configured:
        return configured

    coordinates = _first_coordinate(geometry)

    if coordinates:
        return get_utm_epsg_from_coordinates(
            coordinates[0],
            coordinates[1],
        )

    return "EPSG:3857"


def _first_coordinate(geometry):
    if not geometry:
        return None

    coordinates = geometry.get("coordinates")

    if not coordinates:
        return None

    candidate = coordinates

    while isinstance(candidate, (list, tuple)) and candidate:
        if isinstance(candidate[0], (int, float)):
            return candidate
        candidate = candidate[0]

    return None


def to_dxf_coordinates(geometry, project):
    if not geometry:
        return None

    working_crs = _get_working_crs(project, geometry)

    projected = transform(
        get_transformer(WGS84, working_crs).transform,
        shape(geometry),
    )

    if projected.is_empty:
        return None

    return projected


def add_point(msp, geometry, project, layer):
    projected = to_dxf_coordinates(geometry, project)

    if projected is None or projected.is_empty:
        return False

    centroid = projected.centroid

    msp.add_point(
        (centroid.x, centroid.y),
        dxfattribs={"layer": layer},
    )

    return True


def add_polyline(msp, geometry, project, layer, close=False):
    projected = to_dxf_coordinates(geometry, project)

    if projected is None or projected.is_empty:
        return False

    if projected.geom_type == "Polygon":
        rings = [projected.exterior] + list(projected.interiors)
    elif projected.geom_type == "MultiLineString":
        rings = list(projected.geoms)
    else:
        rings = [projected]

    for ring in rings:
        if ring.geom_type != "LinearRing":
            ring = type(ring)(list(ring.coords))

        coordinates = [
            (float(x), float(y))
            for x, y, *_ in ring.coords
        ]

        if len(coordinates) < 2:
            continue

        if close and coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        msp.add_lwpolyline(
            coordinates,
            dxfattribs={"layer": layer},
        )

    return True


def add_geometry(msp, geometry, project, layer):
    if not geometry:
        return 0

    geometry_type = geometry.get("type")

    if geometry_type == "Point":
        return 1 if add_point(
            msp,
            geometry,
            project,
            layer,
        ) else 0

    if geometry_type in ("LineString", "MultiLineString"):
        return 1 if add_polyline(
            msp,
            geometry,
            project,
            layer,
        ) else 0

    if geometry_type in ("Polygon", "MultiPolygon"):
        return 1 if add_polyline(
            msp,
            geometry,
            project,
            layer,
            close=True,
        ) else 0

    return 0


def _iter_entities(project):
    for basin in project.get("basins", []):
        yield basin.get("geometry"), "BASINS"

    for water_point in project.get("water_points", []):
        yield water_point.get("geometry"), "WATER_POINTS"

    for sector in project.get("sectors", []):
        yield sector.get("geometry"), "SECTORS"

    for zone in project.get("zones", []):
        yield zone.get("geometry"), "ZONES"

    for row in project.get("rows", []):
        yield row.get("geometry"), "ROWS"

    for tree in project.get("trees", []):
        yield tree.get("geometry"), "TREES"

    for valve in project.get("valves", []):
        yield valve.get("geometry"), "VALVES"

    for pipe in project.get("pipes", []):
        yield (
            pipe.get("geometry"),
            get_pipe_layer(pipe.get("diameter_mm")),
        )


def build_dxf_document(project):
    document = ezdxf.new("R2010")

    document.header["$INSUNITS"] = 6

    for name, settings in LAYERS.items():
        if name in document.layers:
            layer = document.layers.get(name)
            layer.dxf.color = settings["color"]
            layer.description = settings["description"]
        else:
            layer = document.layers.new(
                name,
                dxfattribs={"color": settings["color"]},
            )
            layer.description = settings["description"]

    modelspace = document.modelspace()

    land = project.get("land")

    if land:
        add_geometry(
            modelspace,
            land.get("geometry"),
            project,
            "LAND_BOUNDARY",
        )

    for geometry, layer in _iter_entities(project):
        add_geometry(
            modelspace,
            geometry,
            project,
            layer,
        )

    return document


def export_dxf_text(project):
    from io import StringIO

    document = build_dxf_document(project)
    stream = StringIO()
    document.write(stream)

    return stream.getvalue()


def export_dxf_bytes(project):
    return export_dxf_text(project).encode("utf-8")


def export_project_to_dxf(project, output_path):
    build_dxf_document(project).saveas(output_path)

    return output_path
