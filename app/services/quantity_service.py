from datetime import datetime, timezone

import pandas as pd

from core.geometry import measure_area_m2, measure_length_m


def build_pipe_quantity_table(project):
    rows = []

    for pipe in project.get("pipes", []):
        rows.append({
            "Pipe ID": pipe.get("id"),
            "Diameter (mm)": pipe.get("diameter_mm"),
            "Material": pipe.get("material", "HDPE"),
            "Length (m)": pipe.get("length_m", 0),
            "Sector": pipe.get("sector_id"),
            "Zone": pipe.get("zone_id"),
        })

    return pd.DataFrame(
        rows,
        columns=[
            "Pipe ID",
            "Diameter (mm)",
            "Material",
            "Length (m)",
            "Sector",
            "Zone",
        ],
    )


def get_area_m2(collection):
    total = 0.0

    for item in collection:
        geometry = item.get("geometry")

        if not geometry:
            continue

        try:
            total += measure_area_m2(geometry)
        except Exception:
            continue

    return round(total, 2)


def get_length_m(collection):
    total = 0.0

    for item in collection:
        geometry = item.get("geometry")

        if not geometry:
            continue

        try:
            total += measure_length_m(geometry)
        except Exception:
            continue

    return round(total, 2)


def build_demand_summary(project):
    total_flow = 0.0
    total_trees = 0

    zone_rows = []

    for zone in project.get("zones", []):
        flow = float(zone.get("target_flow_m3h") or 0.0)
        trees = int(zone.get("tree_count") or 0)

        total_flow += flow
        total_trees += trees

        zone_rows.append({
            "Zone": zone.get("id"),
            "Sector": zone.get("sector_id"),
            "Area (m2)": round(
                float(zone.get("area_m2") or 0.0),
                2,
            ),
            "Trees": trees,
            "Flow (m3/h)": round(flow, 3),
        })

    source_flow = float(
        project.get("project", {}).get(
            "source_flow_m3h",
            0.0,
        )
    )

    return {
        "total_trees": total_trees,
        "total_demand_m3h": round(total_flow, 3),
        "source_flow_m3h": source_flow,
        "margin_m3h": round(source_flow - total_flow, 3),
        "sufficient_supply": total_flow <= source_flow,
        "zones": zone_rows,
    }


def build_bill_of_materials(project):
    groups = {}

    for pipe in project.get("pipes", []):
        diameter = pipe.get("diameter_mm")
        key = (diameter, pipe.get("material", "HDPE"))

        if key not in groups:
            groups[key] = {
                "Diameter (mm)": diameter,
                "Material": pipe.get("material", "HDPE"),
                "Count": 0,
                "Total length (m)": 0.0,
            }

        groups[key]["Count"] += 1
        groups[key]["Total length (m)"] += round(
            float(pipe.get("length_m") or 0.0),
            2,
        )

    rows = list(groups.values())

    for row in rows:
        row["Total length (m)"] = round(
            row["Total length (m)"],
            2,
        )

    rows.sort(
        key=lambda row: (
            -(row["Diameter (mm)"] or 0),
            row["Material"],
        )
    )

    return rows


def build_project_summary(project):
    zones = project.get("zones", [])

    return {
        "project": {
            "name": project.get("project", {}).get(
                "name",
                "",
            ),
            "updated_utc": project.get("project", {}).get(
                "updated_utc",
                "",
            ),
        },
        "counts": {
            "sectors": len(project.get("sectors", [])),
            "zones": len(zones),
            "rows": len(project.get("rows", [])),
            "trees": len(project.get("trees", [])),
            "pipes": len(project.get("pipes", [])),
            "valves": len(project.get("valves", [])),
            "fittings": len(project.get("fittings", [])),
        },
        "areas_m2": {
            "land": round(
                measure_area_m2(
                    project["land"]["geometry"]
                ),
                2,
            )
            if project.get("land")
            else 0.0,
            "sectors": get_area_m2(
                project.get("sectors", [])
            ),
            "zones": get_area_m2(zones),
        },
        "lengths_m": {
            "rows": get_length_m(project.get("rows", [])),
            "pipes": get_length_m(
                project.get("pipes", [])
            ),
        },
        "demand": build_demand_summary(project),
        "bill_of_materials": build_bill_of_materials(project),
        "generated_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }
