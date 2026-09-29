from math import isfinite

from core.constants import PIPE_HIERARCHY
from core.geometry import is_inside_polygon


MAX_RECOMMENDED_VELOCITY_MPS = 1.5


def coerce_number(value, field_name, allow_zero=False):
    """Coerce user input to a float and reject anything unusable.

    Guards the geometric generators against non-positive spacings, which
    would otherwise never advance their scan loops, and against NaN and
    infinity, which propagate silently through area and flow maths.

    Returns {"ok": True, "value": number} on success, or
    {"ok": False, "message": "..."} on failure, matching the result
    shape used across the service layer.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "message": f"{field_name} must be a number.",
        }

    if isinstance(value, bool):
        return {
            "ok": False,
            "message": f"{field_name} must be a number.",
        }

    if not isfinite(number):
        return {
            "ok": False,
            "message": f"{field_name} must be a finite number.",
        }

    if number < 0 or (number == 0 and not allow_zero):
        requirement = (
            "zero or greater" if allow_zero else "greater than zero"
        )

        return {
            "ok": False,
            "message": f"{field_name} must be {requirement}.",
        }

    return {"ok": True, "value": number}


def coerce_non_negative_int(value, field_name):
    """Coerce user input to a non-negative whole number.

    Returns the same result shape as coerce_number.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return {
            "ok": False,
            "message": f"{field_name} must be a whole number.",
        }

    if isinstance(value, bool):
        return {
            "ok": False,
            "message": f"{field_name} must be a whole number.",
        }

    if number < 0:
        return {
            "ok": False,
            "message": f"{field_name} cannot be negative.",
        }

    return {"ok": True, "value": number}


def validate_pipe_hierarchy(parent_diameter_mm, child_diameter_mm):
    allowed = PIPE_HIERARCHY.get(parent_diameter_mm, [])

    if child_diameter_mm not in allowed:
        return {
            "ok": False,
            "message": (
                f"Invalid connection: {parent_diameter_mm} mm pipe cannot "
                f"directly supply {child_diameter_mm} mm pipe."
            ),
        }

    return {
        "ok": True,
        "message": "Pipe hierarchy is valid.",
    }


def validate_zone_inside_sector(zone_geometry, sector_geometry):
    valid = is_inside_polygon(zone_geometry, sector_geometry)

    return {
        "ok": valid,
        "message": (
            "Zone is inside the selected sector."
            if valid
            else "Zone extends outside the selected sector."
        ),
    }


def calculate_velocity_mps(flow_m3h, diameter_mm):
    if not diameter_mm or diameter_mm <= 0:
        return 0.0

    internal_radius_m = (float(diameter_mm) / 1000.0) / 2.0
    flow_m3s = max(float(flow_m3h), 0.0) / 3600.0
    area_m2 = 3.141592653589793 * internal_radius_m**2

    if area_m2 <= 0:
        return 0.0

    return flow_m3s / area_m2


def validate_flow_velocity(
    flow_m3h,
    diameter_mm,
    max_velocity_mps=MAX_RECOMMENDED_VELOCITY_MPS,
):
    velocity = calculate_velocity_mps(flow_m3h, diameter_mm)

    if velocity > max_velocity_mps:
        return {
            "ok": False,
            "velocity_mps": round(velocity, 3),
            "message": (
                f"Flow {flow_m3h:.3f} m3/h exceeds the recommended "
                f"{max_velocity_mps} m/s limit in a {diameter_mm} mm pipe "
                f"({velocity:.2f} m/s)."
            ),
        }

    return {
        "ok": True,
        "velocity_mps": round(velocity, 3),
        "message": f"Velocity is {velocity:.2f} m/s.",
    }
