import json
import os
import platform
import sys
from datetime import datetime, timezone
from functools import wraps
from math import isfinite


project_root = os.path.dirname(os.path.abspath(__file__))
app_root = os.path.join(project_root, "app")

if app_root not in sys.path:
    sys.path.insert(0, app_root)

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_session import Session

from core.project import (
    create_empty_project,
    ensure_project_shape,
    initialize_project_state,
    read_state,
    save_history_snapshot,
    validate_project_payload,
    write_state,
)


def _resolve_secret_key():
    secret = os.environ.get("FLASK_SECRET_KEY")

    if secret:
        return secret

    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError(
            "FLASK_SECRET_KEY must be set in production."
        )

    return "farm-irrigation-designer-local-dev-key"


app = Flask(
    __name__,
    template_folder=os.path.join(project_root, "templates"),
    static_folder=os.path.join(project_root, "static"),
)
app.config["SECRET_KEY"] = _resolve_secret_key()
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(
    project_root,
    "data",
    "sessions",
)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7
app.config["SESSION_CLEANUP_INTERVAL"] = 3600
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["JSON_SORT_KEYS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(
    os.environ.get("KML_HTTPS_ONLY")
)

@app.after_request
def prevent_html_caching(response):
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store"
    return response

app.config["KML_PASSWORD"] = os.environ.get("KML_PASSWORD")
app.config["KML_ALLOW_MUTATION"] = os.environ.get(
    "KML_ALLOW_MUTATION",
    "1",
) not in ("0", "false", "False", "")

PROTECTED_ENDPOINTS = {
    "write",
    "delete",
    "export",
}

APP_VERSION = "2.2.2"

THEME_NAMES = [
    "cyber-dark",
    "neon-nights",
    "midnight-blue",
    "purple-dream",
    "emerald-green",
    "sunset-orange",
    "arctic-white",
    "dark-matrix",
    "rose-gold",
    "ocean-deep",
]


Session(app)


def auth_enabled():
    return bool(app.config.get("KML_PASSWORD"))


def is_authenticated():
    if not auth_enabled():
        return True

    return bool(read_state(session, "authenticated"))


def login_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            if request.path.startswith("/api/"):
                return jsonify({
                    "ok": False,
                    "message": "Authentication required.",
                }), 401

            return redirect(url_for("page_login"))

        return view_function(*args, **kwargs)

    return wrapper


def get_project():
    initialize_project_state(session)

    project = read_state(session, "farm_project")

    if not isinstance(project, dict):
        project = create_empty_project()
        write_state(session, "farm_project", project)

    return project


def save_project_to_session(project):
    ensure_project_shape(project)

    project["project"]["updated_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    write_state(session, "farm_project", project)


def get_saved_project_file():
    """Name of the project file this session already saved, if any."""

    return read_state(session, "saved_project_file")


def remember_saved_project(file_name):
    write_state(session, "saved_project_file", file_name)


def forget_saved_project():
    write_state(session, "saved_project_file", None)


def sync_saved_project(project):
    """Update the on-disk project after it was imported into a saved project.

    Returns the file name that was updated, or None when the project has
    never been saved. A project that is named and already on disk is
    refreshed in place instead of being saved a second time.
    """

    file_name = get_saved_project_file()

    if not file_name:
        return None

    if not str(
        project.get("project", {}).get("name") or ""
    ).strip():
        return None

    from services.project_storage_service import (
        save_project,
    )

    result = save_project(project, file_name=file_name)

    if not result["ok"]:
        app.logger.warning(
            "Could not update the saved project: %s",
            result["message"],
        )

        return None

    return result["file_name"]


def error_response(message, status_code=400):
    return jsonify({
        "ok": False,
        "message": message,
    }), status_code


def get_json_body():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None

    return data


def download_response(text, download_name, mimetype):
    return Response(
        text,
        mimetype=mimetype,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name}"'
            )
        },
    )


@app.context_processor
def inject_template_globals():
    return {
        "auth_enabled": auth_enabled(),
        "is_authenticated": is_authenticated(),
    }


@app.route("/login", methods=["GET", "POST"])
def page_login():
    if not auth_enabled():
        return redirect(url_for("index"))

    error = None

    if request.method == "POST":
        supplied = request.form.get("password", "")

        if supplied == app.config["KML_PASSWORD"]:
            write_state(session, "authenticated", True)
            return redirect(url_for("index"))

        error = "Incorrect password."

    return render_template(
        "page_login.html",
        page_title="LOGIN",
        error=error,
    )


@app.route("/logout", methods=["POST"])
def page_logout():
    if auth_enabled():
        write_state(session, "authenticated", False)

    return redirect(url_for("page_login"))


@app.route("/")
@login_required
def index():
    return render_template(
        "index.html",
        project=get_project(),
        page_title="HOME",
    )


@app.route("/api/project", methods=["GET"])
@login_required
def api_get_project():
    return jsonify(get_project())


@app.route("/api/project", methods=["PUT"])
@login_required
def api_save_project():
    if not app.config["KML_ALLOW_MUTATION"]:
        return error_response(
            "Direct project writes are disabled. "
            "Use the action endpoints instead.",
            403,
        )

    data = get_json_body()

    if data is None:
        return error_response(
            "A JSON object body is required.",
            415,
        )

    validation = validate_project_payload(data)

    if not validation["ok"]:
        return error_response(
            validation["message"],
            400,
        )

    project = ensure_project_shape(data)
    save_project_to_session(project)
    save_history_snapshot(session, "Project replaced via API")

    return jsonify({
        "ok": True,
        "message": "Project saved.",
    })


@app.route("/api/project/new", methods=["POST"])
@login_required
def api_new_project():
    write_state(session, "farm_project", create_empty_project())
    write_state(session, "project_history", [])
    forget_saved_project()

    return jsonify({
        "ok": True,
        "message": "New project created.",
    })


@app.route("/api/project/save", methods=["POST"])
@login_required
def api_save_to_file():
    data = request.get_json(silent=True) or {}
    project_name = str(data.get("name") or "").strip()

    project = get_project()

    if project_name:
        project["project"]["name"] = project_name

    from services.project_storage_service import (
        save_project,
    )

    result = save_project(project, project_name or None)

    if not result["ok"]:
        return error_response(result["message"])

    project["project"]["saved_file"] = result["file_name"]
    save_project_to_session(project)
    remember_saved_project(result["file_name"])

    return jsonify(result)


@app.route("/api/project/load/<file_name>", methods=["POST"])
@login_required
def api_load_project(file_name):
    from services.project_storage_service import (
        load_project,
    )

    result = load_project(file_name)

    if result["ok"]:
        project = ensure_project_shape(result["project"])
        project["project"]["saved_file"] = file_name
        save_project_to_session(project)
        write_state(session, "project_history", [])
        remember_saved_project(file_name)

        return jsonify({
            "ok": True,
            "message": result["message"],
        })

    return error_response(result["message"])


@app.route("/api/project/delete/<file_name>", methods=["POST"])
@login_required
def api_delete_project(file_name):
    from services.project_storage_service import (
        delete_project as delete_saved_project,
    )

    result = delete_saved_project(file_name)

    if result["ok"]:
        if get_saved_project_file() == file_name:
            forget_saved_project()

            project = get_project()
            project.get("project", {}).pop("saved_file", None)
            save_project_to_session(project)

        return jsonify(result)

    return error_response(result["message"])


@app.route("/api/project/list", methods=["GET"])
@login_required
def api_list_projects():
    from services.project_storage_service import (
        ensure_projects_directory,
        list_saved_projects,
    )

    ensure_projects_directory()

    return jsonify(list_saved_projects())


def _run_action(action_name, data):
    project = get_project()

    save_history_snapshot(
        session,
        f"Before {action_name}",
    )

    from services import kml_service
    from services.dripline_service import (
        create_driplines_for_all_zones,
        remove_all_driplines,
    )
    from services.land_sector_service import (
        add_sector,
        clear_land_and_sector_setup,
        set_basin,
        set_land_boundary,
        set_water_point,
    )
    from services.manifold_service import (
        create_control_assemblies_for_all_zones,
    )
    from services.principal_pipe_service import (
        create_principal_route,
        remove_principal_route,
    )
    from services.elevation_service import (
        calculate_elevation_for_all_zones,
    )
    from services.row_service import (
        create_rows_for_all_zones,
        remove_all_rows,
    )
    from services.sector_pipe_service import (
        create_sector_pipes_for_all_sectors,
        remove_all_sector_pipes,
        update_sector_pipe_flows,
    )
    from services.tree_service import (
        create_trees_for_all_zones,
        remove_all_trees,
    )
    from services.zone_service import (
        create_three_zones_for_all_sectors,
        create_zone,
        remove_all_zones,
        remove_zone,
    )

    actions = {
        "import_kml": lambda: kml_service.import_kml_to_project(
            project=project,
            kml_bytes=data.get("kml_bytes"),
        ),
        "set_land_boundary": lambda: set_land_boundary(
            project,
            data.get("feature_id"),
        ),
        "set_water_point": lambda: set_water_point(
            project,
            data.get("feature_id"),
        ),
        "set_basin": lambda: set_basin(
            project,
            data.get("feature_id"),
        ),
        "add_sector": lambda: add_sector(
            project,
            data.get("feature_id"),
            data.get("sector_number", 1),
        ),
        "remove_sector": lambda: _remove_sector(
            project,
            data.get("sector_id"),
        ),
        "clear_land_and_sector": lambda: (
            clear_land_and_sector_setup(project)
        ),
        "create_3_zones_all": lambda: (
            create_three_zones_for_all_sectors(project)
        ),
        "create_zone": lambda: create_zone(
            project=project,
            sector_id=data.get("sector_id"),
            zone_number=data.get("zone_number", 1),
            geojson_geometry=data.get("geometry"),
            name=data.get("name", ""),
        ),
        "remove_all_zones": lambda: remove_all_zones(project),
        "remove_zone": lambda: remove_zone(
            project,
            data.get("zone_id"),
        ),
        "analyze_elevation": lambda: (
            calculate_elevation_for_all_zones(project)
        ),
        "create_rows_all": lambda: create_rows_for_all_zones(
            project,
            row_spacing_m=data.get("row_spacing_m", 4.0),
            headland_m=data.get("headland_m", 2.0),
        ),
        "remove_all_rows": lambda: remove_all_rows(project),
        "create_trees_all": lambda: create_trees_for_all_zones(
            project,
            tree_spacing_m=data.get("tree_spacing_m", 4.0),
            end_offset_m=data.get("end_offset_m", 2.0),
            crop_type=data.get("crop_type", "Orchard"),
            emitters_per_tree=data.get(
                "emitters_per_tree",
                2,
            ),
            emitter_flow_lph=data.get(
                "emitter_flow_lph",
                4.0,
            ),
        ),
        "remove_all_trees": lambda: remove_all_trees(project),
        "create_principal_route": lambda: create_principal_route(
            project=project,
            route_id=data.get("route_id", ""),
            coordinates=data.get("coordinates") or [],
            route_description=data.get("description", ""),
        ),
        "remove_principal_route": lambda: (
            remove_principal_route(
                project,
                data.get("route_id", ""),
            )
        ),
        "create_sector_pipes_all": lambda: (
            create_sector_pipes_for_all_sectors(project)
        ),
        "remove_all_sector_pipes": lambda: (
            remove_all_sector_pipes(project)
        ),
        "create_driplines_all": lambda: (
            create_driplines_for_all_zones(project)
        ),
        "remove_all_driplines": lambda: (
            remove_all_driplines(project)
        ),
        "create_control_assemblies_all": lambda: (
            create_control_assemblies_for_all_zones(project)
        ),
        "recalculate_pipe_flows": lambda: {
            "ok": True,
            "message": "Pipe flows recalculated.",
            "pipes": len(
                update_sector_pipe_flows(project).get(
                    "pipes",
                    [],
                )
            ),
        },
        "set_source_flow": lambda: _set_source_flow(
            project,
            data.get("source_flow_m3h"),
        ),
    }

    handler = actions.get(action_name)

    if handler is None:
        return error_response(
            f"Unknown action: {action_name}",
            404,
        )

    try:
        result = handler()
    except Exception as exc:
        app.logger.exception(
            "Action %s failed",
            action_name,
        )

        return error_response(
            f"Action '{action_name}' failed: {exc}",
            500,
        )

    if isinstance(result, tuple):
        # A handler rejected the request; leave the session untouched.
        return result

    save_project_to_session(project)

    updated_file = None

    if action_name == "import_kml":
        # A project that was already saved is refreshed in place, so the
        # KML data never has to be uploaded a second time.
        updated_file = sync_saved_project(project)

    if isinstance(result, Response):
        return result

    if isinstance(result, dict):
        if updated_file:
            result["saved_project_file"] = updated_file

        return jsonify(result)

    return jsonify({
        "ok": True,
        "message": f"Action '{action_name}' completed.",
    })


def _remove_sector(project, sector_id):
    from services.land_sector_service import (
        remove_sector,
    )

    return remove_sector(project, sector_id)


def _set_source_flow(project, value):
    try:
        flow = float(value)
    except (TypeError, ValueError):
        return error_response(
            "A numeric source flow in m3/h is required.",
            400,
        )

    if not isfinite(flow) or flow < 0:
        return error_response(
            "Source flow must be a finite, non-negative number.",
            400,
        )

    project.setdefault("project", {})["source_flow_m3h"] = flow

    return {
        "ok": True,
        "message": f"Source flow set to {flow:.3f} m3/h.",
        "source_flow_m3h": flow,
    }


@app.route("/api/action/<action_name>", methods=["POST"])
@login_required
def api_action(action_name):
    return _run_action(
        action_name,
        request.get_json(silent=True) or {},
    )


@app.route("/api/leaflet-map")
@login_required
def leaflet_map():
    from services.map_service import build_project_map

    folium_map = build_project_map(get_project())
    map_html = folium_map.get_root().render()

    return render_template(
        "map_embed.html",
        map_html=map_html,
    )


@app.route("/api/project/download/json")
@login_required
def api_download_json():
    return download_response(
        json.dumps(
            get_project(),
            ensure_ascii=False,
            indent=2,
        ),
        "farm_project.json",
        "application/json",
    )


@app.route("/api/project/download/geojson")
@login_required
def api_download_geojson():
    from exporters.geojson_exporter import export_geojson

    return download_response(
        export_geojson(get_project()),
        "farm_project.geojson",
        "application/geo+json",
    )


@app.route("/api/project/download/kml")
@login_required
def api_download_kml():
    from exporters.kml_exporter import export_kml_text

    return download_response(
        export_kml_text(get_project()),
        "farm_project.kml",
        "application/vnd.google-earth.kml+xml",
    )


@app.route("/api/project/download/dxf")
@login_required
def api_download_dxf():
    from exporters.dxf_exporter import export_dxf_text

    return download_response(
        export_dxf_text(get_project()),
        "farm_project.dxf",
        "application/dxf",
    )


@app.route("/api/project/download/csv")
@login_required
def api_download_csv():
    from exporters.csv_exporter import (
        export_pipe_quantities_csv,
    )

    return Response(
        export_pipe_quantities_csv(get_project()),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="pipe_quantities.csv"'
            )
        },
    )


@app.route("/api/project/download/epanet")
@login_required
def api_download_epanet():
    from exporters.epanet_exporter import (
        export_epanet_inp,
    )

    return download_response(
        export_epanet_inp(get_project()),
        "farm_project.inp",
        "text/plain",
    )


@app.route("/api/project/elevation")
@login_required
def api_elevation():
    from services.elevation_service import (
        extract_elevation_points_from_kml,
    )

    project = get_project()
    points = extract_elevation_points_from_kml(project)

    zones = project.get("zones", [])
    analysed = [
        zone
        for zone in zones
        if zone.get("elevation_analysis")
    ]

    return jsonify({
        "ok": True,
        "kml_feature_count": len(
            project.get("kml_features", [])
        ),
        "elevation_point_count": len(points),
        "elevation_points": points[:500],
        "elevation_point_total": len(points),
        "elevation_points_truncated": len(points) > 500,
        "zone_count": len(zones),
        "analysed_zone_count": len(analysed),
        "failed_zone_ids": [
            zone.get("id")
            for zone in zones
            if not zone.get("elevation_analysis")
        ],
    })


@app.route("/api/project/summary")
@login_required
def api_summary():
    from services.quantity_service import (
        build_project_summary,
    )

    return jsonify(build_project_summary(get_project()))


@app.route("/api/project/hydraulic")
@login_required
def api_hydraulic():
    from services.hydraulic_service import run_hydraulic_checks

    project = get_project()
    result = run_hydraulic_checks(project)

    project["hydraulic_results"] = {
        "ok": result["ok"],
        "message": result["message"],
        "source_flow_m3h": result["source_flow_m3h"],
        "total_demand_m3h": result["total_demand_m3h"],
        "margin_m3h": result["margin_m3h"],
        "simultaneous_operation_possible": result[
            "simultaneous_operation_possible"
        ],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "checked_utc": datetime.now(timezone.utc).isoformat(),
    }

    save_project_to_session(project)

    return jsonify(result)


@app.route("/api/project/settings", methods=["POST"])
@login_required
def api_update_settings():
    data = get_json_body()

    if data is None:
        return error_response(
            "A JSON object body is required.",
            415,
        )

    project = get_project()
    settings = project.setdefault("project", {})

    if "name" in data:
        settings["name"] = str(data["name"])[:200]

    if "source_flow_m3h" in data:
        try:
            source_flow = float(data["source_flow_m3h"])
        except (TypeError, ValueError):
            return error_response(
                "source_flow_m3h must be a number."
            )

        if not isfinite(source_flow):
            return error_response(
                "source_flow_m3h must be a finite number."
            )

        if source_flow < 0:
            return error_response(
                "source_flow_m3h cannot be negative."
            )

        settings["source_flow_m3h"] = source_flow

    if "working_crs" in data:
        working_crs = data["working_crs"]

        settings["working_crs"] = (
            str(working_crs).strip() or None
            if working_crs is not None
            else None
        )

    save_project_to_session(project)
    save_history_snapshot(session, "Project settings updated")

    return jsonify({
        "ok": True,
        "message": "Project settings updated.",
        "project": project["project"],
    })


def _page(template, title):
    @login_required
    def view():
        return render_template(
            template,
            page_title=title,
            project=get_project(),
        )

    view.__name__ = f"page_{title.lower()}"

    return view()


def register_page(route, template, title):
    def view():
        return render_template(
            template,
            page_title=title,
            project=get_project(),
        )

    view.__name__ = route.replace("/", "_").strip("_")

    app.add_url_rule(
        route,
        endpoint=view.__name__,
        view_func=login_required(view),
    )


for route, template, title in [
    ("/page/storage", "page_storage.html", "STORAGE"),
    ("/page/map", "page_map.html", "MAP"),
    ("/page/land_sectors", "page_land_sectors.html", "LAND & SECTORS"),
    ("/page/zones", "page_zones.html", "ZONES"),
    ("/page/elevation", "page_elevation.html", "ELEVATION"),
    ("/page/rows", "page_rows.html", "ROWS"),
    ("/page/trees", "page_trees.html", "TREES"),
    ("/page/pipes", "page_pipes.html", "PIPES"),
    ("/page/hydraulic", "page_hydraulic.html", "HYDRAULIC"),
    ("/page/quantities", "page_quantities.html", "QUANTITIES"),
    ("/page/export", "page_export.html", "EXPORT"),
    ("/page/settings", "page_settings.html", "SETTINGS"),
]:
    register_page(route, template, title)


@app.route("/api/theme/download/<int:index>")
@login_required
def download_theme(index):
    if 0 <= index < len(THEME_NAMES):
        theme_name = THEME_NAMES[index]
        theme_path = os.path.join(
            project_root,
            "static",
            "themes",
            f"{theme_name}.css",
        )

        if os.path.exists(theme_path):
            return send_file(
                theme_path,
                as_attachment=True,
                download_name=f"{theme_name}.css",
            )

    return error_response("Theme not found.", 404)


@app.route("/api/theme/list")
@login_required
def list_themes():
    themes = []

    for index, name in enumerate(THEME_NAMES):
        theme_path = os.path.join(
            project_root,
            "static",
            "themes",
            f"{name}.css",
        )

        themes.append({
            "index": index,
            "slug": name,
            "name": name.replace("-", " ").title(),
            "available": os.path.exists(theme_path),
            "url": f"/static/themes/{name}.css",
        })

    return jsonify(themes)


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "Farm Irrigation Designer",
        "version": APP_VERSION,
        "debug": bool(app.debug),
        "auth_enabled": auth_enabled(),
        "python": platform.python_version(),
    })


@app.errorhandler(413)
def handle_too_large(_error):
    return error_response(
        "The uploaded file is too large. The limit is 50 MB.",
        413,
    )


@app.errorhandler(404)
def handle_not_found(_error):
    if request.path.startswith("/api/"):
        return error_response("Not found.", 404)

    return render_template(
        "page_error.html",
        page_title="NOT FOUND",
        status_code=404,
        message="That page does not exist.",
    ), 404


@app.errorhandler(500)
def handle_server_error(_error):
    if request.path.startswith("/api/"):
        return error_response(
            "An internal error occurred. Check the server log.",
            500,
        )

    return render_template(
        "page_error.html",
        page_title="ERROR",
        status_code=500,
        message="Something went wrong on the server.",
    ), 500


if __name__ == "__main__":
    for directory in ("projects", "sessions"):
        os.makedirs(
            os.path.join(project_root, "data", directory),
            exist_ok=True,
        )

    app.run(
        debug=bool(os.environ.get("FLASK_DEBUG")),
        host=os.environ.get("KML_HOST", "127.0.0.1"),
        port=int(os.environ.get("KML_PORT", 5000)),
    )
