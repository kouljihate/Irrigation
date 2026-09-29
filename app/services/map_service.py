import html
import json

import folium
from branca.element import MacroElement, Template


MAP_STYLES = {
    "land": {
        "color": "#ffffff",
        "weight": 4,
        "fill_color": "#ffffff",
        "fill_opacity": 0.03,
    },
    "water_point": {
        "color": "#00bfff",
        "radius": 9,
    },
    "basin": {
        "color": "#0066cc",
        "weight": 3,
        "fill_color": "#0066cc",
        "fill_opacity": 0.30,
    },
    "sector": {
        "color": "#f39c12",
        "weight": 3,
        "fill_color": "#f39c12",
        "fill_opacity": 0.05,
    },
    "zone": {
        "color": "#9b59b6",
        "weight": 3,
        "fill_color": "#9b59b6",
        "fill_opacity": 0.18,
    },
    "pipe_90": {
        "color": "#ff0000",
        "weight": 7,
    },
    "pipe_63": {
        "color": "#0066ff",
        "weight": 6,
    },
    "pipe_32": {
        "color": "#00aa00",
        "weight": 5,
    },
    "pipe_16": {
        "color": "#808080",
        "weight": 2,
    },
    "valve": {
        "color": "#ffd000",
        "radius": 7,
    },
    "tree": {
        "color": "#2ecc71",
        "radius": 3,
    },
    "row": {
        "color": "#6b8e23",
        "weight": 2,
    },
    "imported_point": {
        "color": "#e67e22",
        "radius": 7,
    },
    "imported_line": {
        "color": "#3388ff",
        "weight": 4,
    },
    "imported_polygon": {
        "color": "#888888",
        "weight": 2,
        "fill_color": "#888888",
        "fill_opacity": 0.06,
    },
}


def get_feature_name(feature):
    return feature.get(
        "name",
        feature.get(
            "id",
            "Unnamed item",
        ),
    )


def get_feature_description(feature):
    return feature.get(
        "description",
        "",
    )


def get_feature_style_key(feature):
    diameter = feature.get(
        "diameter_mm"
    )

    if diameter == 90:
        return "pipe_90"

    if diameter == 63:
        return "pipe_63"

    if diameter == 32:
        return "pipe_32"

    if diameter == 16:
        return "pipe_16"

    entity_type = feature.get(
        "entity_type",
        "",
    )

    if entity_type:
        return entity_type

    geometry_type = feature.get(
        "geometry",
        {},
    ).get(
        "type",
        "",
    )

    if geometry_type == "Point":
        return "imported_point"

    if geometry_type == "LineString":
        return "imported_line"

    if geometry_type == "Polygon":
        return "imported_polygon"

    return "imported_polygon"

def get_feature_style(feature):
    style_key = get_feature_style_key(feature)

    return MAP_STYLES.get(
        style_key,
        MAP_STYLES["imported_polygon"],
    )


def create_popup(feature):
    name = html.escape(
        str(get_feature_name(feature))
    )

    description = html.escape(
        str(get_feature_description(feature))
    )

    entity_type = html.escape(
        str(feature.get("entity_type", ""))
    )

    feature_id = html.escape(
        str(feature.get("id", ""))
    )

    folder = html.escape(
        str(feature.get("folder", ""))
    )

    popup_html = f"<b>{name}</b><br>"

    if feature_id:
        popup_html += f"<small>ID: {feature_id}</small><br>"

    if entity_type:
        popup_html += (
            f"<small>Type: {entity_type}</small><br>"
        )

    if folder:
        popup_html += (
            f"<small>Folder: {folder}</small><br>"
        )

    if feature.get("sector_id"):
        popup_html += (
            f"<small>Sector: "
            f"{html.escape(str(feature['sector_id']))}"
            f"</small><br>"
        )

    if feature.get("zone_id"):
        popup_html += (
            f"<small>Zone: "
            f"{html.escape(str(feature['zone_id']))}"
            f"</small><br>"
        )

    if feature.get("diameter_mm"):
        popup_html += (
            f"<small>Pipe: "
            f"{html.escape(str(feature['diameter_mm']))}"
            f" mm</small><br>"
        )

    if description:
        popup_html += (
            f"<hr><div>{description}</div>"
        )

    return folium.Popup(
        popup_html,
        max_width=350,
    )


TREE_CANVAS_THRESHOLD = 2000


class TreeCanvasLayer(MacroElement):
    """Draws every tree on one canvas instead of one Leaflet marker each."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function () {
            var points = {{ this.points }};
            var owner = {{ this._parent.get_name() }};

            if (!points.length) { return; }

            var TreeCanvas = L.Layer.extend({
                onAdd: function (target) {
                    this._map = target;
                    this._canvas = L.DomUtil.create('canvas', 'leaflet-tree-canvas');
                    this._ctx = this._canvas.getContext('2d');
                    target.getPanes().overlayPane.appendChild(this._canvas);
                    this._onViewChange = this._redraw.bind(this);
                    target.on('moveend zoomend resize', this._onViewChange);
                    this._redraw();
                },
                onRemove: function (target) {
                    target.off('moveend zoomend resize', this._onViewChange);
                    this._canvas.remove();
                },
                _redraw: function () {
                    var target = this._map;
                    if (!target) { return; }

                    var size = target.getSize();
                    var ratio = window.devicePixelRatio || 1;
                    var canvas = this._canvas;

                    canvas.width = size.x * ratio;
                    canvas.height = size.y * ratio;
                    canvas.style.width = size.x + 'px';
                    canvas.style.height = size.y + 'px';
                    L.DomUtil.setPosition(
                        canvas,
                        target.containerPointToLayerPoint([0, 0])
                    );

                    var context = this._ctx;
                    context.setTransform(ratio, 0, 0, ratio, 0, 0);
                    context.clearRect(0, 0, size.x, size.y);
                    context.fillStyle = {{ this.color }};
                    context.beginPath();

                    for (var i = 0; i < points.length; i++) {
                        var point = target.latLngToContainerPoint(points[i]);
                        if (point.x < -4 || point.y < -4 ||
                            point.x > size.x + 4 || point.y > size.y + 4) {
                            continue;
                        }
                        context.moveTo(point.x + {{ this.radius }}, point.y);
                        context.arc(point.x, point.y, {{ this.radius }}, 0, Math.PI * 2);
                    }

                    context.fill();
                }
            });

            var layer = new TreeCanvas();
            owner.addLayer(layer);
            owner.tree_canvas_layer = layer;
        })();
        {% endmacro %}
        """
    )

    def __init__(
        self,
        points,
        color="#00c853",
        radius=3,
    ):
        super().__init__()
        self.points = json.dumps(points, separators=(",", ":"))
        self.color = json.dumps(color)
        self.radius = radius


def tree_points(trees):
    coordinates = []

    for tree in trees:
        geometry = tree.get(
            "geometry",
            {},
        )

        if geometry.get("type") != "Point":
            continue

        point = geometry.get("coordinates") or []

        if len(point) < 2:
            continue

        coordinates.append(
            [point[1], point[0]]
        )

    return coordinates


def draw_feature(
    feature_group,
    feature,
    bounds,
):
    geometry = feature.get(
        "geometry",
        {},
    )

    geometry_type = geometry.get(
        "type",
        "",
    )

    coordinates = geometry.get(
        "coordinates",
        [],
    )

    if not coordinates:
        return

    style = get_feature_style(feature)
    name = get_feature_name(feature)
    popup = create_popup(feature)

    if geometry_type == "Point":
        longitude = coordinates[0]
        latitude = coordinates[1]

        folium.CircleMarker(
            location=[latitude, longitude],
            radius=style.get("radius", 7),
            color=style["color"],
            fill=True,
            fill_color=style["color"],
            fill_opacity=1,
            weight=2,
            popup=popup,
            tooltip=name,
        ).add_to(feature_group)

        bounds.append(
            [latitude, longitude]
        )

    elif geometry_type == "LineString":
        line_coordinates = []

        for coordinate in coordinates:
            longitude = coordinate[0]
            latitude = coordinate[1]

            line_coordinates.append(
                [latitude, longitude]
            )

        folium.PolyLine(
            locations=line_coordinates,
            color=style["color"],
            weight=style.get("weight", 3),
            opacity=0.95,
            popup=popup,
            tooltip=name,
        ).add_to(feature_group)

        bounds.extend(line_coordinates)

    elif geometry_type == "Polygon":
        outer_ring = coordinates[0]

        polygon_coordinates = []

        for coordinate in outer_ring:
            longitude = coordinate[0]
            latitude = coordinate[1]

            polygon_coordinates.append(
                [latitude, longitude]
            )

        folium.Polygon(
            locations=polygon_coordinates,
            color=style["color"],
            weight=style.get("weight", 3),
            fill=True,
            fill_color=style.get(
                "fill_color",
                style["color"],
            ),
            fill_opacity=style.get(
                "fill_opacity",
                0.12,
            ),
            popup=popup,
            tooltip=name,
        ).add_to(feature_group)

        bounds.extend(polygon_coordinates)


def build_project_map(project):
    farm_map = folium.Map(
        location=[33.845, -4.585],
        zoom_start=15,
        tiles=None,
        control_scale=True,
    )

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Street map",
        attr="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(farm_map)

    folium.TileLayer(
        tiles="Esri.WorldImagery",
        name="Satellite",
        attr="Esri",
        overlay=False,
        control=True,
    ).add_to(farm_map)

    imported_layer = folium.FeatureGroup(
        name="Original imported KML",
        show=False,
    )

    land_layer = folium.FeatureGroup(
        name="Land boundary",
        show=True,
    )

    water_basin_layer = folium.FeatureGroup(
        name="Water point and basin",
        show=True,
    )

    sector_layer = folium.FeatureGroup(
        name="Sectors",
        show=True,
    )

    zone_layer = folium.FeatureGroup(
        name="Irrigation zones",
        show=True,
    )

    pipe_layer = folium.FeatureGroup(
        name="Pipes",
        show=True,
    )

    valve_layer = folium.FeatureGroup(
        name="Valves",
        show=True,
    )

    row_layer = folium.FeatureGroup(
        name="Rows and trees",
        show=False,
    )

    bounds = []

    for feature in project.get(
        "kml_features",
        [],
    ):
        draw_feature(
            imported_layer,
            feature,
            bounds,
        )

    land = project.get("land")

    if land:
        draw_feature(
            land_layer,
            land,
            bounds,
        )

    for water_point in project.get(
        "water_points",
        [],
    ):
        draw_feature(
            water_basin_layer,
            water_point,
            bounds,
        )

    for basin in project.get(
        "basins",
        [],
    ):
        draw_feature(
            water_basin_layer,
            basin,
            bounds,
        )

    for sector in project.get(
        "sectors",
        [],
    ):
        draw_feature(
            sector_layer,
            sector,
            bounds,
        )

    for zone in project.get(
        "zones",
        [],
    ):
        draw_feature(
            zone_layer,
            zone,
            bounds,
        )

    for pipe in project.get(
        "pipes",
        [],
    ):
        draw_feature(
            pipe_layer,
            pipe,
            bounds,
        )

    for valve in project.get(
        "valves",
        [],
    ):
        draw_feature(
            valve_layer,
            valve,
            bounds,
        )

    for row in project.get(
        "rows",
        [],
    ):
        draw_feature(
            row_layer,
            row,
            bounds,
        )

    trees = project.get(
        "trees",
        [],
    )

    tree_coordinates = tree_points(trees)

    if len(tree_coordinates) > TREE_CANVAS_THRESHOLD:
        latitudes = [point[0] for point in tree_coordinates]
        longitudes = [point[1] for point in tree_coordinates]

        bounds.extend(
            [
                [min(latitudes), min(longitudes)],
                [max(latitudes), max(longitudes)],
            ]
        )

        row_layer.add_child(
            TreeCanvasLayer(
                tree_coordinates,
                color=MAP_STYLES.get("tree", {}).get("color", "#00c853"),
                radius=MAP_STYLES.get("tree", {}).get("radius", 7) / 2.4,
            )
        )
    else:
        for tree in trees:
            draw_feature(
                row_layer,
                tree,
                bounds,
            )

    imported_layer.add_to(farm_map)
    land_layer.add_to(farm_map)
    water_basin_layer.add_to(farm_map)
    sector_layer.add_to(farm_map)
    zone_layer.add_to(farm_map)
    pipe_layer.add_to(farm_map)
    valve_layer.add_to(farm_map)
    row_layer.add_to(farm_map)

    if bounds:
        farm_map.fit_bounds(
            bounds,
            padding=(20, 20),
        )

    folium.LayerControl(
        collapsed=False,
    ).add_to(farm_map)

    return farm_map