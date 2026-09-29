import copy
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIRECTORY = Path(
    os.environ.get(
        "KML_DATA_DIR",
        str(APP_ROOT / "data"),
    )
) / "projects"


def ensure_projects_directory():
    PROJECTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_file_name(value):
    cleaned = str(value).strip().lower()

    cleaned = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        cleaned,
    )

    cleaned = cleaned.strip("_")

    if not cleaned:
        cleaned = "farm_irrigation_project"

    return cleaned


def get_project_file_path(project_name):
    safe_name = safe_file_name(project_name)

    return PROJECTS_DIRECTORY / f"{safe_name}.json"


def resolve_project_path(file_name):
    requested = str(file_name or "").strip()

    if not requested:
        return None, {
            "ok": False,
            "message": "No project file name was provided.",
        }

    if requested != os.path.basename(requested):
        return None, {
            "ok": False,
            "message": "Invalid project file path.",
        }

    if not requested.lower().endswith(".json"):
        return None, {
            "ok": False,
            "message": "Invalid project file path.",
        }

    requested_path = (
        PROJECTS_DIRECTORY / requested
    ).resolve()

    projects_root = PROJECTS_DIRECTORY.resolve()

    if projects_root != requested_path.parent:
        return None, {
            "ok": False,
            "message": "Invalid project file path.",
        }

    return requested_path, None


def prepare_project_for_save(project):
    import copy

    project_copy = copy.deepcopy(project)

    project_copy["project"] = dict(
        project.get("project", {})
    )

    project_copy["project"]["saved_utc"] = utc_now()

    return project_copy


def save_project(project, project_name=None):
    ensure_projects_directory()

    if project_name is None:
        project_name = project.get(
            "project",
            {},
        ).get(
            "name",
            "farm_irrigation_project",
        )

    file_path = get_project_file_path(project_name)

    project_to_save = prepare_project_for_save(
        project
    )

    temporary_path = file_path.with_suffix(
        ".tmp"
    )

    temporary_path.write_text(
        json.dumps(
            project_to_save,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(file_path)

    return {
        "ok": True,
        "message": "Project saved successfully.",
        "file_name": file_path.name,
        "file_path": str(file_path),
    }


def list_saved_projects():
    ensure_projects_directory()

    project_files = sorted(
        PROJECTS_DIRECTORY.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    projects = []

    for project_file in project_files:
        try:
            data = json.loads(
                project_file.read_text(
                    encoding="utf-8"
                )
            )

            project_info = data.get(
                "project",
                {},
            )

            projects.append({
                "file_name": project_file.name,
                "project_name": project_info.get(
                    "name",
                    project_file.stem,
                ),
                "saved_utc": project_info.get(
                    "saved_utc",
                    "",
                ),
                "modified_timestamp": (
                    project_file.stat().st_mtime
                ),
            })

        except Exception:
            projects.append({
                "file_name": project_file.name,
                "project_name": project_file.stem,
                "saved_utc": "Unreadable JSON file",
                "modified_timestamp": (
                    project_file.stat().st_mtime
                ),
            })

    return projects


def load_project(file_name):
    ensure_projects_directory()

    requested_path, error = resolve_project_path(
        file_name
    )

    if error:
        return {
            "ok": False,
            "message": error["message"],
            "project": None,
        }

    if not requested_path.exists():
        return {
            "ok": False,
            "message": (
                f"Project file {file_name} does not exist."
            ),
            "project": None,
        }

    try:
        project = json.loads(
            requested_path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        return {
            "ok": False,
            "message": (
                f"Unable to read project JSON: {exc}"
            ),
            "project": None,
        }

    if not isinstance(project, dict):
        return {
            "ok": False,
            "message": "Project file is not a JSON object.",
            "project": None,
        }

    required_keys = [
        "project",
        "water_points",
        "basins",
        "sectors",
        "zones",
        "rows",
        "trees",
        "pipes",
        "valves",
    ]

    for key in required_keys:
        if key not in project:
            return {
                "ok": False,
                "message": (
                    f"Invalid project file: missing key '{key}'."
                ),
                "project": None,
            }

    return {
        "ok": True,
        "message": "Project loaded successfully.",
        "project": project,
    }


def delete_project(file_name):
    ensure_projects_directory()

    requested_path, error = resolve_project_path(
        file_name
    )

    if error:
        return {
            "ok": False,
            "message": error["message"],
        }

    if not requested_path.exists():
        return {
            "ok": False,
            "message": "Project file does not exist.",
        }

    requested_path.unlink()

    return {
        "ok": True,
        "message": f"Deleted {file_name}.",
    }
