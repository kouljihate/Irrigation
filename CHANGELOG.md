# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0]

Interface fixes for the header, storage actions and the map.

### Fixed

- The loading overlay no longer sticks. Three `showLoading()` calls (a
  capture-phase click listener, a `window.fetch` monkey-patch and
  `apiFetch`) were balanced by only two `hideLoading()` calls, so every
  button click leaked a pending request. Because `body.loading` sets
  `pointer-events: none` across the whole page, the overlay never
  cleared and the interface became unresponsive. `apiFetch` is now the
  only caller, and it hides in a `finally` block, so a failed request
  cannot leave the overlay stuck. A 30-second watchdog force-clears it
  as a failsafe.
- Importing a KML file ran twice: selecting a file fired the `change`
  handler and the Import button fired a second time. Only the button
  triggers an import now.
- `/api/leaflet-map` is no longer unusable on large projects. Every tree
  was drawn as its own `folium.CircleMarker` with a popup and tooltip,
  roughly 1.5 KB of inline JavaScript each. 38,820 trees produced 58.8 MB
  of HTML and took 60s to generate, and 288,243 trees exceeded a 300s
  timeout. Above 2,000 trees the map now draws them on a single canvas
  that redraws on `moveend`, `zoomend` and `resize`. 38,820 trees render
  as 841 KB in 0.27s, and 288,243 trees in 7.6s. Per-tree popups are
  unchanged at or below the threshold.

### Changed

- The brand title and the Home button moved from the header into the
  body title, which is now the Home link. The header keeps the Arabic
  brand, settings and log out. The per-page name is shown on its own
  line under the body title.
- The storage actions sit on a single row. The New project button was
  removed from the interface for now; `POST /api/project/new` is
  unchanged and still available.

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
