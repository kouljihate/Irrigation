import copy
import json
from datetime import datetime, timezone


MAX_HISTORY_ENTRIES = 20
MAX_SNAPSHOT_ENTRIES = 3


def create_empty_project():
    return {
        "project": {
            "project_id": "new_farm_project",
            "name": "New Farm Irrigation Project",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "coordinate_system": "EPSG:4326",
            "working_crs": None,
            "source_flow_m3h": 10.0,
        },
        "land": None,
        "water_points": [],
        "basins": [],
        "sectors": [],
        "zones": [],
        "rows": [],
        "trees": [],
        "pipes": [],
        "valves": [],
        "fittings": [],
        "obstacles": [],
        "elevation_points": [],
        "hydraulic_results": {},
        "warnings": [],
    }


def read_state(state, key, default=None):
    getter = getattr(state, "get", None)

    if callable(getter):
        return getter(key, default)

    return getattr(state, key, default)


def write_state(state, key, value):
    if isinstance(state, dict):
        state[key] = value
    else:
        setattr(state, key, value)

    modifier = getattr(state, "modified", None)

    if modifier is not None:
        try:
            state.modified = True
        except (AttributeError, TypeError):
            pass

    return value


def delete_state(state, key):
    if isinstance(state, dict):
        state.pop(key, None)
    else:
        if hasattr(state, key):
            delattr(state, key)


def initialize_project_state(session_state):
    if read_state(session_state, "farm_project") is None:
        write_state(
            session_state,
            "farm_project",
            create_empty_project(),
        )

    if read_state(session_state, "project_history") is None:
        write_state(session_state, "project_history", [])


def save_history_snapshot(session_state, action_name, store_snapshot=False):
    history = read_state(session_state, "project_history")

    if not isinstance(history, list):
        history = []
        write_state(session_state, "project_history", history)

    entry = {
        "action": action_name,
        "at_utc": datetime.now(timezone.utc).isoformat(),
    }

    if store_snapshot:
        project = read_state(session_state, "farm_project")
        entry["project"] = copy.deepcopy(project)

    history.append(entry)

    write_state(session_state, "project_history", history[-MAX_HISTORY_ENTRIES:])


def update_project_timestamp(project):
    project["project"]["updated_utc"] = datetime.now(
        timezone.utc
    ).isoformat()


def ensure_project_shape(project):
    template = create_empty_project()

    for key, default in template.items():
        if key not in project:
            project[key] = copy.deepcopy(default)
        elif isinstance(default, list) and not isinstance(
            project[key], list
        ):
            project[key] = copy.deepcopy(default)

    for key, value in template["project"].items():
        if key not in project["project"]:
            project["project"][key] = copy.deepcopy(value)

    return project


def validate_project_payload(payload):
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "message": "Project payload must be a JSON object.",
        }

    project = payload.get("project")

    if not isinstance(project, dict):
        return {
            "ok": False,
            "message": "Project payload is missing the 'project' object.",
        }

    if not isinstance(project.get("name"), str):
        return {
            "ok": False,
            "message": "Project payload is missing a string 'project.name'.",
        }

    list_keys = [
        "water_points",
        "basins",
        "sectors",
        "zones",
        "rows",
        "trees",
        "pipes",
        "valves",
        "fittings",
        "obstacles",
    ]

    for key in list_keys:
        value = payload.get(key, [])

        if not isinstance(value, list):
            return {
                "ok": False,
                "message": f"Project key '{key}' must be a list.",
            }

    if payload.get("land") is not None and not isinstance(
        payload.get("land"), dict
    ):
        return {
            "ok": False,
            "message": "Project key 'land' must be an object or null.",
        }

    return {"ok": True, "message": "Project payload is valid."}


def project_to_json(project):
    return json.dumps(project, ensure_ascii=False, indent=2)


def project_from_json(json_text):
    return json.loads(json_text)
