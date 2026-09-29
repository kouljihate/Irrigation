# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0]

Complete rewrite of the application from Streamlit to Flask. This is a
breaking change: the directory layout, entry point and UI framework all
changed. No data format migration is required — saved project JSON files are
read as-is.

### Added

- Flask 3 application factory (`app_factory.py`) with server-rendered
  Jinja2 templates and a JSON API.
- Optional password login, enabled by setting `KML_PASSWORD`.
- Filesystem-backed sessions with a 7-day lifetime, `HttpOnly` and
  `SameSite=Lax` cookies, and opt-in `Secure` via `KML_HTTPS_ONLY`.
- `/health` endpoint reporting app version, debug state, auth state and the
  Python version.
- Ten selectable UI themes, listed and downloadable over
  `/api/theme/list` and `/api/theme/download/<index>`.
- Environment-driven configuration: `FLASK_SECRET_KEY`, `KML_PASSWORD`,
  `KML_HOST`, `KML_PORT`, `FLASK_DEBUG`, `KML_DATA_DIR`,
  `KML_ALLOW_MUTATION`, `KML_HTTPS_ONLY`.
- A `KML_ALLOW_MUTATION=0` kill switch that disables the `PUT /api/project`
  state-replacement endpoint.
- Unified `POST /api/action/<action_name>` dispatcher covering the full design
  pipeline: KML import, land/water/basin setup, sectors, zones, elevation
  analysis, rows, trees, principal routes, sector pipes, driplines, control
  assemblies, flow recalculation and source flow.
- Project storage service with list, save, load and delete.
- Error pages for 404, 413 and 500, with JSON responses on `/api/` paths.
- 50 MB upload cap with a friendly 413 handler.

### Changed

- Project code moved from top-level `core/`, `services/`, `exporters/` and
  `ui/` into the `app/` package.
- Entry point is now `main.py`, which validates the bind address and warns
  when the app is exposed to the network without authentication.
- DXF export grew to full support via `ezdxf`; EPANET export added.
- `gunicorn` added for production serving; `pytest` added for testing.

### Removed

- Streamlit entry point (`app.py`), the `pages/` multipage UI and the
  Streamlit sidebar/layout helpers. This codebase is retained on the
  repository's `main` branch as the 1.x line.

### Security

- The Flask debugger is off unless `FLASK_DEBUG` is set, and the reloader
  follows the same flag.
- `FLASK_ENV=production` now raises if `FLASK_SECRET_KEY` is unset instead of
  falling back to the development key.
