# Farm Irrigation Designer

A web application for designing agricultural irrigation networks from KML land
survey data. Import a KML, define land, water source, basin and sectors, then
generate zones, planting rows, trees, pipe networks and control assemblies —
and export the result to KML, DXF, GeoJSON, CSV and EPANET.

**Version: 2.2.5** · Flask 3 + Bootstrap 5

> **Note on branches.** `main` holds the current Flask application (v2).
> The original Streamlit prototype (v1) is preserved on the
> **`flask-2.0.0`** branch.

---

## Design workflow

1. **Project storage** — create, save, load, delete and download projects.
   Naming a project is optional: an empty name falls back to the project's
   own name. A project that is already saved is refreshed in place whenever
   a new KML is uploaded.
2. **Project map** — Leaflet/MapLibre map with the imported KML features.
   Every element read from the file is drawn: land, sectors, basins, water
   points, remaining plots, paths and canals.
3. **Land & sectors** — set the land boundary, water point and basin, then
   add and number sectors.
4. **Zones** — create zones per sector, or auto-generate three per sector.
5. **Elevation analysis** — sample terrain and compute per-zone elevation
   statistics.
6. **Planting rows** — generate planting rows with row spacing and headland.
7. **Trees** — place trees with spacing, end offset, crop type and emitter
   flow.
8. **Zone control assemblies** — build valve/manifold assemblies per zone.
9. **Principal 90 mm routes** — draw the mainline routes.
10. **Sector 63 mm pipes** — generate lateral mains per sector.
11. **Hydraulic checks** — validate flows and pressure.
12. **Quantities** — bill of materials by pipe class.
13. **Export** — download the network in any supported format.

## Pipe classes

| Key | Description | Diameter | Role |
| --- | --- | --- | --- |
| `principal_90` | Principal Pipe | 90 mm | principal |
| `major_63` | Major Pipe | 63 mm | major |
| `minor_32` | Minor Pipe | 32 mm | minor |
| `dripline_16` | Dripline | 16 mm | dripline |

Hierarchy: 90 → 63 → 32 → 16.

## Requirements

- Python 3.11 or newer (developed against 3.14)
- The dependencies in `requirements.txt` (Flask, shapely, pyproj, geopandas,
  ezdxf, fastkml, folium, pandas, openpyxl)

## Install and run

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The app is served at <http://127.0.0.1:5000>. It binds to loopback only by
default.

For a production-style run:

```powershell
gunicorn --bind 127.0.0.1:5000 "app_factory:app"
```

## Configuration

All configuration is via environment variables.

| Variable | Default | Purpose |
| --- | --- | --- |
| `FLASK_SECRET_KEY` | dev fallback | Session signing key. **Required** when `FLASK_ENV=production`. |
| `KML_PASSWORD` | unset | Enables the login screen when set. |
| `KML_HOST` | `127.0.0.1` | Bind address. Anything else exposes the app to the network. |
| `KML_PORT` | `5000` | Bind port. |
| `FLASK_DEBUG` | unset | Enables the debugger and reloader. Never on a shared network. |
| `KML_DATA_DIR` | `./data` | Overrides the data directory location. |
| `KML_ALLOW_MUTATION` | `1` | Set to `0` to disable `PUT /api/project`. |
| `KML_HTTPS_ONLY` | unset | Set to `1` to mark session cookies `Secure`. |

`main.py` prints a warning if you bind to a non-loopback address without
setting `KML_PASSWORD`.

## HTTP API

### Pages

| Route | Description |
| --- | --- |
| `/` | Project map (home) |
| `/login`, `/logout` | Authentication, when `KML_PASSWORD` is set |
| `/health` | Liveness probe — reports app version and Python version |

### Project state

| Route | Method | Description |
| --- | --- | --- |
| `/api/project` | `GET` | Read project state |
| `/api/project` | `PUT` | Replace project state (disable via `KML_ALLOW_MUTATION=0`) |
| `/api/project/new` | `POST` | Create an empty project |
| `/api/project/save` | `POST` | Persist the project. `name` may be empty. |
| `/api/project/load/<file_name>` | `POST` | Load a saved project |
| `/api/project/delete/<file_name>` | `POST` | Delete a saved project |
| `/api/project/list` | `GET` | List saved projects |

### Analysis

| Route | Method | Description |
| --- | --- | --- |
| `/api/action/<action_name>` | `POST` | Run a design action (see below) |
| `/api/leaflet-map` | `GET` | Map fragment for the current project |
| `/api/project/elevation` | `GET` | Per-zone elevation data |
| `/api/project/summary` | `GET` | Project summary counts |
| `/api/project/hydraulic` | `GET` | Hydraulic check results |
| `/api/project/settings` | `POST` | Update project settings |

### Downloads

`/api/project/download/{json,geojson,kml,dxf,csv,epanet}`

### Themes

| Route | Method | Description |
| --- | --- | --- |
| `/api/theme/list` | `GET` | List available themes |
| `/api/theme/download/<index>` | `GET` | Download a theme stylesheet |

### Design actions

Accepted by `POST /api/action/<action_name>`:

`import_kml`, `set_land_boundary`, `set_water_point`, `set_basin`,
`add_sector`, `remove_sector`, `clear_land_and_sector`, `create_zone`,
`create_3_zones_all`, `remove_zone`, `remove_all_zones`, `analyze_elevation`,
`create_rows_all`, `remove_all_rows`, `create_trees_all`, `remove_all_trees`,
`create_principal_route`, `remove_principal_route`, `create_sector_pipes_all`,
`remove_all_sector_pipes`, `create_driplines_all`, `remove_all_driplines`,
`create_control_assemblies_all`, `recalculate_pipe_flows`, `set_source_flow`.

`import_kml` reads the file, classifies it and draws it on the map. If the
session already has a saved, named project, the saved file is updated in
place and the response carries `saved_project_file`.

## Architecture

```
main.py                  Entry point; env config and startup warnings
app_factory.py           Flask application factory, all routes and actions
app/core/                Geometry, coordinates, IDs, models, project state
app/services/            Domain logic for the design pipeline
app/exporters/           GeoJSON, KML, DXF, CSV and EPANET writers
app/ui/                  Presentation helpers
templates/               Jinja2 templates (one per workflow step)
static/css/              Layout and base styles
static/themes/           10 selectable themes
static/fonts/            Icon and display fonts
data/                    Saved projects, sessions and logs (git-ignored)
```

`app/core/project.py` owns the canonical project state: creating, reading and
writing state, schema validation, and history snapshots. The design services
are pure functions over that state, so each step is independently testable.

## Project layout on disk

Runtime state is written under `data/`:

- `data/projects/` — saved project JSON files
- `data/sessions/` — Flask filesystem session store
- `data/logs/` — application logs

This directory is git-ignored, so farm survey data and project files stay on
your machine and are never pushed.

## Security notes

- Uploads are capped at 50 MB (`MAX_CONTENT_LENGTH`); larger requests return
  HTTP 413.
- Session cookies are `HttpOnly` and `SameSite=Lax`; set `KML_HTTPS_ONLY=1`
  behind TLS to add `Secure`.
- The login screen only appears when `KML_PASSWORD` is set. If you bind to a
  non-loopback address, set it.
- Set a real `FLASK_SECRET_KEY` and `FLASK_ENV=production` for any deployment.
- Do not run with `FLASK_DEBUG` enabled on a shared network.

## License

Add your license here.
