"""
Salva e legge le etichette di malattia su InfluxDB.
Quando il contadino segnala MALATTIA, viene salvato un record
nella measurement 'ml_labels'.
"""
from datetime import datetime, timezone
from django.conf import settings
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


def _build_client():
    return InfluxDBClient(url=settings.INFLUX_HOST,
                          token=settings.INFLUX_TOKEN,
                          org=settings.INFLUX_ORG)


def save_malattia_label(node_id: str, window_days: int = 7,
                        event_time: datetime = None):
    """Salva un'etichetta positiva (malattia confermata)."""
    if event_time is None:
        event_time = datetime.now(timezone.utc)
    client = _build_client()
    write_api = client.write_api(write_options=SYNCHRONOUS)
    point = (Point("ml_labels")
             .tag("node_id", node_id)
             .field("label", 1)
             .field("window_days", window_days)
             .time(event_time))
    write_api.write(bucket=settings.INFLUX_BUCKET, record=point)
    client.close()


def get_all_labels() -> list:
    """Restituisce tutte le etichette salvate come lista di dict."""
    client = _build_client()
    query_api = client.query_api()
    flux = f'''
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -1000d)
  |> filter(fn: (r) => r["_measurement"] == "ml_labels")
'''
    try:
        tables = query_api.query(query=flux)
    except Exception:
        client.close()
        return []
    client.close()

    labels = {}
    for table in tables:
        for record in table.records:
            t = record.get_time().isoformat()
            node = record.values.get("node_id", "unknown")
            key = f"{node}_{t}"
            if key not in labels:
                labels[key] = {"node_id": node, "event_time": t,
                               "label": None, "window_days": 7}
            field = record.get_field()
            if field == "label":
                labels[key]["label"] = int(record.get_value())
            elif field == "window_days":
                labels[key]["window_days"] = int(record.get_value())
    return list(labels.values())
