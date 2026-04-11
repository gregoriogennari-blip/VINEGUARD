# dashboard/services/influx_service.py
from dataclasses import dataclass
from typing import List

@dataclass
class NodeMeasurement:
    node_id: str
    temp_aria: float
    umid_aria: float
    umid_suolo: float
    rain_mm: float

def get_latest_measurements() -> List[NodeMeasurement]:
    # Dati di esempio: poi li sostituiremo con la query a InfluxDB
    return [
        NodeMeasurement("node1", 22.5, 85.2, 71.4, 2.1),
        NodeMeasurement("node2", 21.8, 80.0, 65.0, 0.0),
        NodeMeasurement("node3", 23.1, 78.5, 69.0, 5.0),
    ]