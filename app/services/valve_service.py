def add_valve(project, valve):
    project["valves"].append(valve)


def get_valves_for_zone(project, zone_id):
    return [
        valve
        for valve in project.get("valves", [])
        if valve.get("zone_id") == zone_id
    ]
