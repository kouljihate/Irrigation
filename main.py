"""
Farm Irrigation Designer - Flask + Bootstrap Web Application
=============================================================

Usage:
    python main.py

The application runs on http://127.0.0.1:5000

## Setup
    python -m venv venv
    venv\\Scripts\\activate
    pip install -r requirements.txt
    python main.py

## Environment variables
    FLASK_SECRET_KEY   Session signing key. Required in production.
    KML_PASSWORD       Enables the login screen when set.
    KML_HOST           Bind address. Defaults to 127.0.0.1 (local only).
    KML_PORT           Bind port. Defaults to 5000.
    FLASK_DEBUG        Set to 1 to enable the debugger. Off by default.
    KML_DATA_DIR       Overrides the data/ directory location.
    KML_ALLOW_MUTATION Set to 0 to disable the PUT /api/project endpoint.
    KML_HTTPS_ONLY     Set to 1 to mark session cookies Secure.

## Architecture
    - app_factory.py - Flask application factory and all routes
    - app/core/      - Geometry, CRS, validation and project state
    - app/services/  - Domain logic for the irrigation design pipeline
    - app/exporters/ - JSON, GeoJSON, KML, DXF, CSV and EPANET writers
    - templates/     - Jinja2 HTML templates
    - static/        - CSS, JavaScript and theme files
    - data/          - Saved projects, sessions and logs
"""

import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app_factory import app, project_root as app_project_root


def ensure_data_directories():
    for directory in ("projects", "sessions", "logs"):
        os.makedirs(
            os.path.join(project_root, "data", directory),
            exist_ok=True,
        )


def main():
    ensure_data_directories()

    host = os.environ.get("KML_HOST", "127.0.0.1")
    port = int(os.environ.get("KML_PORT", 5000))
    debug = bool(os.environ.get("FLASK_DEBUG"))

    if debug:
        print("WARNING: the Flask debugger is enabled. Do not use it on a shared network.")

    if host not in ("127.0.0.1", "localhost", "::1") and not debug:
        print(
            f"WARNING: binding to {host} exposes the app to the network. "
            "Set KML_PASSWORD to require a login."
        )

    print("=" * 60)
    print("  Farm Irrigation Designer")
    print("  Flask + Bootstrap 5 Web Application")
    print("=" * 60)
    print(f"  Server running on: http://{host}:{port}")
    print(f"  Project root:      {app_project_root}")
    print(f"  Authentication:    {'enabled' if app.config.get('KML_PASSWORD') else 'disabled'}")
    print("=" * 60)

    app.run(
        debug=debug,
        host=host,
        port=port,
        use_reloader=debug,
    )


if __name__ == "__main__":
    main()
