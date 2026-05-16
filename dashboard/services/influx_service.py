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


def calculate_database_risk(measurement: NodeMeasurement | dict) -> float:
    """
    Calcola un rischio malattia 0-100 dai dati sensore reali, senza ML.
    Il punteggio cresce con umidita alta, temperatura favorevole, suolo umido
    e pioggia recente.
    """
    get_value = (
        measurement.get
        if isinstance(measurement, dict)
        else lambda field, default=None: getattr(measurement, field, default)
    )
    temp = get_value("temp_aria", None)
    hum_air = get_value("umid_aria", None)
    hum_soil = get_value("umid_suolo", None)
    rain = get_value("rain_mm", None)

    score = 0.0
    weight = 0.0

    if temp is not None:
        weight += 30
        temp_distance = min(abs(float(temp) - 22.0) / 12.0, 1.0)
        score += 30 * (1.0 - temp_distance)

    if hum_air is not None:
        weight += 35
        score += 35 * max(0.0, min((float(hum_air) - 55.0) / 40.0, 1.0))

    if hum_soil is not None:
        weight += 20
        score += 20 * max(0.0, min((float(hum_soil) - 35.0) / 45.0, 1.0))

    if rain is not None:
        weight += 15
        score += 15 * max(0.0, min(float(rain) / 5.0, 1.0))

    if not weight:
        return 0.0
    return round((score / weight) * 100, 1)


def risk_level(risk: float) -> dict:
    if risk >= 70:
        return {"label": "Alto", "class": "risk-high"}
    if risk >= 35:
        return {"label": "Medio", "class": "risk-medium"}
    return {"label": "Basso", "class": "risk-low"}


def format_timestamp(value: str | None) -> str:
    if not value:
        return "N/D"
    return value.replace("T", " ").split(".")[0]


def _build_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )


def get_node_ids(days: int = 30) -> List[str]:
    """
    Restituisce i node_id presenti nel bucket negli ultimi N giorni.
    """
    client = _build_client()
    query_api = client.query_api()

    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> keep(columns: ["node_id"])
  |> distinct(column: "node_id")
"""

    try:
        tables = query_api.query(query=flux)
    except Exception:
        client.close()
        return []
    client.close()

    node_ids = [record.get_value() for table in tables for record in table.records]
    return sorted(node_id for node_id in node_ids if node_id)


def get_latest_measurements(days: int = 30) -> List[NodeMeasurement]:
    """
    Restituisce l'ultima misura per ogni nodo (node_id) dal bucket InfluxDB.
    """
    client = _build_client()
    query_api = client.query_api()

    # Query: ultimo valore disponibile per ogni nodo negli ultimi N giorni.
    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["_field"] == "temp_aria" or r["_field"] == "umid_aria" or r["_field"] == "umid_suolo" or r["_field"] == "rain_mm")
  |> group(columns: ["node_id", "_field"])
  |> last()
  |> pivot(rowKey:["_time", "node_id"], columnKey: ["_field"], valueColumn: "_value")
"""

    try:
        tables = query_api.query(query=flux)
    except Exception:
        client.close()
        return []
    client.close()

    # Aggrego per node_id
    by_node: Dict[str, Dict[str, object]] = {}

    for table in tables:
        for record in table.records:
            values = record.values
            node_id = values.get("node_id", "unknown")
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

            for field in ("temp_aria", "umid_aria", "umid_suolo", "rain_mm"):
                value = values.get(field)
                if value is not None:
                    node[field] = value
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


def get_latest_as_dict(node_id: str = None) -> List[dict]:
    """
    Helper per API JSON. Se node_id è fornito, filtra per quel nodo.
    """
    measurements = get_latest_measurements()
    if node_id:
        measurements = [m for m in measurements if m.node_id == node_id]
    
    rows = []
    for m in measurements:
        risk = calculate_database_risk(m)
        level = risk_level(risk)
        rows.append({
            "node_id": m.node_id,
            "temp_aria": m.temp_aria,
            "umid_aria": m.umid_aria,
            "umid_suolo": m.umid_suolo,
            "rain_mm": m.rain_mm,
            "rischio_db": risk,
            "risk_label": level["label"],
            "risk_class": level["class"],
            "time": m.time,
            "time_label": format_timestamp(m.time),
        })
    return rows


def get_historical_data(node_id: str, days: int = 7) -> Dict:
    """
    Ritorna i dati storici aggregati per ora per un nodo specifico negli ultimi N giorni.
    Utile per grafici storici con linee temporali.
    
    Returns:
    {
        "node_id": "node1",
        "time_labels": ["2026-05-09 00:00", "2026-05-09 01:00", ...],
        "temperatures": [15.2, 16.1, ...],
        "humidity_air": [45.3, 47.2, ...],
        "humidity_soil": [65.1, 68.2, ...],
        "rainfall": [0, 0, 2.3, ...]
    }
    """
    client = _build_client()
    query_api = client.query_api()

    safe_node_id = node_id.replace('"', '\\"')

    # Aggregazione oraria (1h) degli ultimi N giorni per un nodo specifico
    flux = f"""
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["node_id"] == "{safe_node_id}")
  |> filter(fn: (r) => r["_field"] == "temp_aria" or r["_field"] == "umid_aria" or r["_field"] == "umid_suolo" or r["_field"] == "rain_mm")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> group(columns: ["_field"])
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
"""

    try:
        tables = query_api.query(query=flux)
    except Exception as e:
        client.close()
        print(f"Error querying historical data: {e}")
        return {
            "node_id": node_id,
            "time_labels": [],
            "temperatures": [],
            "humidity_air": [],
            "humidity_soil": [],
            "rainfall": [],
        }
    
    client.close()

    # Raccolgo i dati ordinati per timestamp
    by_time: Dict[str, Dict] = {}

    for table in tables:
        for record in table.records:
            time = record.get_time()
            if not time:
                continue
            time_str = time.strftime("%Y-%m-%d %H:%M")

            if time_str not in by_time:
                by_time[time_str] = {
                    "temp_aria": None,
                    "umid_aria": None,
                    "umid_suolo": None,
                    "rain_mm": None,
                }

            values = record.values
            for field in ("temp_aria", "umid_aria", "umid_suolo", "rain_mm"):
                value = values.get(field)
                if value is not None:
                    by_time[time_str][field] = value

    # Ordina per tempo e estrai i dati
    sorted_times = sorted(by_time.keys())
    
    result = {
        "node_id": node_id,
        "time_labels": sorted_times,
        "temperatures": [by_time[t].get("temp_aria") for t in sorted_times],
        "humidity_air": [by_time[t].get("umid_aria") for t in sorted_times],
        "humidity_soil": [by_time[t].get("umid_suolo") for t in sorted_times],
        "rainfall": [by_time[t].get("rain_mm") for t in sorted_times],
    }

    return result
