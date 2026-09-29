PIPE_TYPES = {
    "principal_90": {
        "name": "90 mm Principal Pipe",
        "diameter_mm": 90,
        "role": "principal",
        "color": "#ff0000",
        "line_weight": 6,
    },
    "major_63": {
        "name": "63 mm Major Pipe",
        "diameter_mm": 63,
        "role": "major",
        "color": "#0066ff",
        "line_weight": 5,
    },
    "minor_32": {
        "name": "32 mm Minor Pipe",
        "diameter_mm": 32,
        "role": "minor",
        "color": "#00aa00",
        "line_weight": 4,
    },
    "dripline_16": {
        "name": "16 mm Dripline",
        "diameter_mm": 16,
        "role": "dripline",
        "color": "#808080",
        "line_weight": 2,
    },
}

PIPE_HIERARCHY = {
    90: [90, 63],
    63: [63, 32],
    32: [32, 16],
    16: [],
}

DEFAULT_PROJECT_SETTINGS = {
    "project_name": "New Farm Irrigation Project",
    "country": "Morocco",
    "source_flow_m3h": 10.0,
    "tree_spacing_m": 4.0,
    "row_spacing_m": 4.0,
    "emitters_per_tree": 2,
    "emitter_flow_lph": 4.0,
    "pipe_material": "HDPE",
    "coordinate_system": "EPSG:4326",
    "working_crs": None,
}
