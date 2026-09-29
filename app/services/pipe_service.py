from core.validators import validate_pipe_hierarchy


def add_pipe(project, pipe, parent_pipe=None):
    if parent_pipe is not None:
        validation = validate_pipe_hierarchy(
            parent_pipe["diameter_mm"],
            pipe["diameter_mm"],
        )

        if not validation["ok"]:
            return validation

    project["pipes"].append(pipe)

    return {
        "ok": True,
        "message": "Pipe added successfully.",
        "pipe": pipe,
    }
