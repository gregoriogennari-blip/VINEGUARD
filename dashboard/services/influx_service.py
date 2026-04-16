from dataclasses import dataclass
from typing import List, Dict

from django.conf import settings

from influxdb_client import InfluxDBClient


@dataclass
class NodeMeasurement:
    node_id: str
    temp_aria: float | None
    umid_aria: float | None
    umid_suolo: float | None
    rain_mm: float | None
    time: str | None = None  # ISO timestamp


def _build_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )


def get_latest_measurements() -> List[NodeMeasurement]:
    """
    Restituisce l'ultima misura per ogni nodo (node_id) dal bucket InfluxDB.
    """
    client = _build_client()
    query_api = client.query_api()

    # Query: ultime 2 ore, measurement "sensor_data"
    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -2h)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> group(columns: ["node_id"])
  |> last()
"""

    tables = query_api.query(query=flux)
    client.close()

    # Aggrego per node_id
    by_node: Dict[str, Dict[str, object]] = {}

    for table in tables:
        for record in table.records:
            node_id = record.values.get("node_id", "unknown")
            field = record.get_field()
            value = record.get_value()
            time = record.get_time().isoformat() if record.get_time() else None

            node = by_node.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "temp_aria": None,
                    "umid_aria": None,
                    "umid_suolo": None,
                    "rain_mm": None,
                    "time": time,
                },
            )

            if field in node:
                node[field] = value
            # aggiorno comunque il timestamp all'ultimo
            node["time"] = time or node["time"]

    measurements: List[NodeMeasurement] = []
    for node in by_node.values():
        measurements.append(
            NodeMeasurement(
                node_id=node["node_id"],
                temp_aria=node["temp_aria"],
                umid_aria=node["umid_aria"],
                umid_suolo=node["umid_suolo"],
                rain_mm=node["rain_mm"],
                time=node["time"],
            )
        )

    return measurements


def get_latest_as_dict() -> List[dict]:
    """
    Helper per API JSON.
    """
    return [
        {
            "node_id": m.node_id,
            "temp_aria": m.temp_aria,
            "umid_aria": m.umid_aria,
            "umid_suolo": m.umid_suolo,
            "rain_mm": m.rain_mm,
            "time": m.time,
        }
        for m in get_latest_measurements()
    ]