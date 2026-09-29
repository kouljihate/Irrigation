NODE_TYPE_BY_PIPE_TYPE = {
    "principal_90": "RESERVOIR",
    "major_63": "JUNCTION",
    "manifold_32": "JUNCTION",
    "dripline": "JUNCTION",
    "minor_32": "JUNCTION",
}


def sanitize_id(value):
    cleaned = "".join(
        character
        if character.isalnum() or character == "_"
        else "_"
        for character in str(value)
    )

    if not cleaned:
        cleaned = "NODE"

    if cleaned[0].isdigit():
        cleaned = f"N_{cleaned}"

    return cleaned


def get_node_name(pipe):
    return sanitize_id(pipe.get("id"))


def collect_nodes(project):
    nodes = []
    seen = set()

    for pipe in project.get("pipes", []):
        node_id = get_node_name(pipe)

        if node_id in seen:
            continue

        seen.add(node_id)

        nodes.append({
            "id": node_id,
            "type": NODE_TYPE_BY_PIPE_TYPE.get(
                pipe.get("pipe_type"),
                "JUNCTION",
            ),
            "elevation_m": round(
                float(
                    (pipe.get("elevation_m") or 0.0)
                ),
                3,
            ),
            "pattern": None,
        })

    return nodes


def collect_pipes(project):
    links = []

    for pipe in project.get("pipes", []):
        parent = sanitize_id(pipe.get("parent_pipe_id")) if pipe.get(
            "parent_pipe_id"
        ) else None
        node = get_node_name(pipe)

        if not parent:
            continue

        links.append({
            "id": f"{parent}->{node}",
            "from": parent,
            "to": node,
            "diameter_mm": int(pipe.get("diameter_mm") or 63),
            "length_m": round(
                float(pipe.get("length_m") or 0.0),
                2,
            ),
            "flow_m3h": round(
                float(pipe.get("flow_m3h") or 0.0),
                3,
            ),
        })

    return links


def export_epanet_inp(project):
    name = project.get("project", {}).get(
        "name",
        "Farm Irrigation",
    )

    nodes = collect_nodes(project)
    pipes = collect_pipes(project)

    lines = [
        "[TITLE]",
        f"; {name}",
        "",
        "[JUNCTIONS]",
    ]

    junction_count = 0

    for node in nodes:
        if node["type"] != "JUNCTION":
            continue

        lines.append(
            f"{node['id']} {node['elevation_m']}"
        )
        junction_count += 1

    lines.append("")
    lines.append("[RESERVOIRS]")

    for node in nodes:
        if node["type"] != "RESERVOIR":
            continue

        lines.append(
            f"{node['id']} {node['elevation_m']}"
        )

    lines.append("")
    lines.append("[PIPES]")

    for pipe in pipes:
        lines.append(
            f"{pipe['id']} {pipe['from']} {pipe['to']} "
            f"{pipe['diameter_mm']} {pipe['length_m']} 100 0"
        )

    lines.append("")
    lines.append("[DEMANDS]")
    lines.append("; Demand is applied at zone control valves.")
    lines.append("")
    lines.append("[STATUS]")
    lines.append("; All links active.")
    lines.append("")
    lines.append("[END]")

    if junction_count == 0 and not pipes:
        lines.insert(2, "; No pipes have been defined yet.")

    return "\n".join(lines)


def export_epanet_bytes(project):
    return export_epanet_inp(project).encode("utf-8")
