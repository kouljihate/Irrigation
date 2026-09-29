from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class BaseEntity:
    id: str
    name: str
    geometry: Dict[str, Any]
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Land(BaseEntity):
    area_m2: float = 0.0
    area_ha: float = 0.0


@dataclass
class WaterPoint(BaseEntity):
    flow_m3h: float = 0.0
    static_water_level_m: Optional[float] = None
    pump_depth_m: Optional[float] = None


@dataclass
class Basin(BaseEntity):
    capacity_m3: float = 0.0
    bottom_elevation_m: Optional[float] = None
    overflow_elevation_m: Optional[float] = None


@dataclass
class Sector(BaseEntity):
    sector_number: int = 0
    area_m2: float = 0.0
    parent_land_id: Optional[str] = None


@dataclass
class Zone(BaseEntity):
    sector_id: str = ""
    zone_number: int = 0
    area_m2: float = 0.0
    target_flow_m3h: float = 0.0
    valve_id: Optional[str] = None
    min_elevation_m: Optional[float] = None
    max_elevation_m: Optional[float] = None


@dataclass
class Row(BaseEntity):
    sector_id: str = ""
    zone_id: str = ""
    row_number: int = 0
    length_m: float = 0.0
    spacing_m: float = 4.0
    direction_degrees: float = 0.0


@dataclass
class Tree(BaseEntity):
    sector_id: str = ""
    zone_id: str = ""
    row_id: str = ""
    tree_number: int = 0
    crop_type: str = "Orchard"
    emitters_per_tree: int = 2
    emitter_flow_lph: float = 4.0


@dataclass
class Pipe(BaseEntity):
    pipe_type: str = "main"
    diameter_mm: int = 90
    material: str = "HDPE"
    length_m: float = 0.0
    from_node_id: Optional[str] = None
    to_node_id: Optional[str] = None
    sector_id: Optional[str] = None
    zone_id: Optional[str] = None
    flow_m3h: float = 0.0
    pressure_bar: Optional[float] = None


@dataclass
class Valve(BaseEntity):
    valve_type: str = "zone"
    sector_id: Optional[str] = None
    zone_id: Optional[str] = None
    diameter_mm: int = 32
    is_automatic: bool = False
    pressure_regulated: bool = False


@dataclass
class Fitting(BaseEntity):
    fitting_type: str = "tee"
    inlet_diameter_mm: int = 90
    outlet_diameter_mm: Optional[int] = 63
    connected_pipe_ids: List[str] = field(default_factory=list)