import json


def export_geojson(project):
    features = []

    collections = [
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

    for collection_name in collections:
        for item in project.get(collection_name, []):
            features.append({
                "type": "Feature",
                "geometry": item.get("geometry"),
                "properties": {
                    key: value
                    for key, value in item.items()
                    if key != "geometry"
                },
            })

    return json.dumps({
        "type": "FeatureCollection",
        "features": features,
    }, ensure_ascii=False, indent=2)
