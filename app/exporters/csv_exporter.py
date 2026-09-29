import csv
import io

from services.quantity_service import build_pipe_quantity_table


PIPE_TABLE_COLUMNS = [
    "Pipe ID",
    "Pipe type",
    "Diameter (mm)",
    "Material",
    "Length (m)",
    "Sector",
    "Zone",
    "Flow (m3/h)",
]


def build_pipe_rows(project):
    rows = []

    for pipe in project.get("pipes", []):
        rows.append({
            "Pipe ID": pipe.get("id"),
            "Pipe type": pipe.get("pipe_type"),
            "Diameter (mm)": pipe.get("diameter_mm"),
            "Material": pipe.get("material", "HDPE"),
            "Length (m)": pipe.get("length_m", 0),
            "Sector": pipe.get("sector_id"),
            "Zone": pipe.get("zone_id"),
            "Flow (m3/h)": pipe.get("flow_m3h", 0),
        })

    return rows


def export_pipe_quantities_csv(project):
    buffer = io.StringIO()

    writer = csv.DictWriter(
        buffer,
        fieldnames=PIPE_TABLE_COLUMNS,
        extrasaction="ignore",
    )

    writer.writeheader()

    for row in build_pipe_rows(project):
        writer.writerow(row)

    return buffer.getvalue().encode("utf-8")


def export_project_summary_csv(project):
    summary = build_pipe_quantity_table(project)

    buffer = io.StringIO()

    summary.to_csv(buffer, index=False)

    return buffer.getvalue().encode("utf-8")
