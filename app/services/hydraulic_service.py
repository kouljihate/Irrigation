from core.validators import (
    MAX_RECOMMENDED_VELOCITY_MPS,
    calculate_velocity_mps,
)


FALLBACK_PRESSURE_BAR = 2.0


def calculate_zone_flow_m3h(
    tree_count,
    emitters_per_tree,
    emitter_flow_lph,
):
    total_lph = tree_count * emitters_per_tree * emitter_flow_lph
    return total_lph / 1000


def calculate_static_pressure_bar(elevation_difference_m):
    return elevation_difference_m / 10.2


def get_project_flow_m3h(project):
    total = 0.0

    for zone in project.get("zones", []):
        total += float(zone.get("target_flow_m3h") or 0.0)

    return round(total, 3)


def get_source_flow_m3h(project):
    settings = project.get("project", {})
    return float(settings.get("source_flow_m3h") or 0.0)


def build_zone_checks(project):
    checks = []
    total_demand = 0.0

    for zone in project.get("zones", []):
        flow = float(zone.get("target_flow_m3h") or 0.0)
        total_demand += flow

        analysis = zone.get("elevation_analysis") or {}
        min_elevation = analysis.get("minimum_elevation_m")
        max_elevation = analysis.get("maximum_elevation_m")

        entry = {
            "zone_id": zone.get("id"),
            "tree_count": int(zone.get("tree_count") or 0),
            "flow_m3h": round(flow, 3),
            "minimum_elevation_m": min_elevation,
            "maximum_elevation_m": max_elevation,
            "elevation_range_m": analysis.get("elevation_range_m"),
            "warnings": [],
        }

        if analysis:
            entry["static_pressure_bar"] = round(
                calculate_static_pressure_bar(
                    float(max_elevation or 0.0)
                    - float(min_elevation or 0.0)
                ),
                3,
            )
        else:
            entry["static_pressure_bar"] = FALLBACK_PRESSURE_BAR
            entry["warnings"].append(
                "No elevation analysis. Run elevation analysis "
                "to size the pressure regime."
            )

        if zone.get("tree_count") is None:
            entry["warnings"].append(
                "No trees defined, so the flow is zero."
            )

        checks.append(entry)

    return checks, round(total_demand, 3)


def build_pipe_checks(project):
    checks = []

    for pipe in project.get("pipes", []):
        flow = float(pipe.get("flow_m3h") or 0.0)
        diameter = pipe.get("diameter_mm")
        velocity = calculate_velocity_mps(flow, diameter)
        warnings = []

        if velocity > MAX_RECOMMENDED_VELOCITY_MPS:
            warnings.append(
                f"Velocity {velocity:.2f} m/s exceeds the "
                f"{MAX_RECOMMENDED_VELOCITY_MPS} m/s recommendation."
            )

        if float(pipe.get("length_m") or 0.0) <= 0:
            warnings.append("Pipe length has not been calculated.")

        checks.append({
            "pipe_id": pipe.get("id"),
            "pipe_type": pipe.get("pipe_type"),
            "diameter_mm": diameter,
            "length_m": pipe.get("length_m"),
            "flow_m3h": round(flow, 3),
            "velocity_mps": round(velocity, 3),
            "velocity_ok": velocity <= MAX_RECOMMENDED_VELOCITY_MPS,
            "warnings": warnings,
        })

    return checks


def run_hydraulic_checks(project):
    if not project.get("zones"):
        source_flow = get_source_flow_m3h(project)

        return {
            "ok": False,
            "message": "No zones are available. Create zones first.",
            "source_flow_m3h": source_flow,
            "total_demand_m3h": 0.0,
            "margin_m3h": round(source_flow, 3),
            "simultaneous_operation_possible": False,
            "zones": [],
            "pipes": [],
            "errors": [
                "No zones are available. Create zones first.",
            ],
            "warnings": [],
        }

    zone_checks, total_demand = build_zone_checks(project)
    pipe_checks = build_pipe_checks(project)
    source_flow = get_source_flow_m3h(project)

    global_warnings = []
    global_errors = []

    if source_flow <= 0:
        global_errors.append(
            "Source flow is not set. Define it in project settings."
        )
    elif total_demand > source_flow:
        global_errors.append(
            f"Total demand {total_demand:.3f} m3/h exceeds the available "
            f"source flow {source_flow:.3f} m3/h."
        )

    oversized = [
        check
        for check in pipe_checks
        if not check["velocity_ok"]
    ]

    if oversized:
        global_warnings.append(
            f"{len(oversized)} pipe(s) exceed the recommended velocity."
        )

    return {
        "ok": not global_errors,
        "message": (
            f"Hydraulic check completed. Demand {total_demand:.3f} m3/h "
            f"against {source_flow:.3f} m3/h available."
        ),
        "source_flow_m3h": source_flow,
        "total_demand_m3h": total_demand,
        "margin_m3h": round(source_flow - total_demand, 3),
        "simultaneous_operation_possible": total_demand <= source_flow,
        "zones": zone_checks,
        "pipes": pipe_checks,
        "errors": global_errors,
        "warnings": global_warnings,
    }
