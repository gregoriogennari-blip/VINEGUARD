"""
Costruisce il dataset di training a partire dalle etichette salvate
e dai dati storici dei sensori in InfluxDB.
Feature calcolate su ogni finestra giornaliera:
  temp_aria_mean/max/min, umid_aria_mean/max, umid_suolo_mean,
  rain_mm_sum, giorni_umid_aria_alta, giorni_temp_favorevole, giorni_pioggia
"""
from datetime import datetime, timezone, timedelta
from django.conf import settings
from influxdb_client import InfluxDBClient
import pandas as pd
from .ml_labels import get_all_labels


def _build_client():
    return InfluxDBClient(url=settings.INFLUX_HOST,
                          token=settings.INFLUX_TOKEN,
                          org=settings.INFLUX_ORG)


def _fetch_window(node_id, start, stop):
    client = _build_client()
    query_api = client.query_api()
    s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    e = stop.strftime("%Y-%m-%dT%H:%M:%SZ")
    flux = f'''
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: {s}, stop: {e})
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["node_id"] == "{node_id}")
  |> filter(fn: (r) => r["_field"] == "temp_aria" or r["_field"] == "umid_aria"
            or r["_field"] == "umid_suolo" or r["_field"] == "rain_mm")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
'''
    try:
        tables = query_api.query(query=flux)
    except Exception:
        client.close()
        return pd.DataFrame()
    client.close()

    rows = []
    for table in tables:
        for record in table.records:
            rows.append({"date": record.get_time().date(),
                         "field": record.get_field(),
                         "value": record.get_value()})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    pivot = df.pivot_table(index="date", columns="field",
                           values="value", aggfunc="mean")
    pivot.columns.name = None
    return pivot.reset_index()


def _compute_features(df):
    if df is None or df.empty:
        return None
    f = {}
    if "temp_aria" in df.columns:
        f["temp_aria_mean"] = round(df["temp_aria"].mean(), 2)
        f["temp_aria_max"]  = round(df["temp_aria"].max(), 2)
        f["temp_aria_min"]  = round(df["temp_aria"].min(), 2)
        f["giorni_temp_favorevole"] = int(
            ((df["temp_aria"] >= 15) & (df["temp_aria"] <= 25)).sum())
    else:
        f.update(temp_aria_mean=0, temp_aria_max=0,
                 temp_aria_min=0, giorni_temp_favorevole=0)

    if "umid_aria" in df.columns:
        f["umid_aria_mean"] = round(df["umid_aria"].mean(), 2)
        f["umid_aria_max"]  = round(df["umid_aria"].max(), 2)
        f["giorni_umid_aria_alta"] = int((df["umid_aria"] > 80).sum())
    else:
        f.update(umid_aria_mean=0, umid_aria_max=0, giorni_umid_aria_alta=0)

    if "umid_suolo" in df.columns:
        f["umid_suolo_mean"] = round(df["umid_suolo"].mean(), 2)
    else:
        f["umid_suolo_mean"] = 0

    if "rain_mm" in df.columns:
        f["rain_mm_sum"]   = round(df["rain_mm"].sum(), 2)
        f["giorni_pioggia"] = int((df["rain_mm"] > 0).sum())
    else:
        f.update(rain_mm_sum=0, giorni_pioggia=0)
    return f


FEATURE_COLUMNS = [
    "temp_aria_mean", "temp_aria_max", "temp_aria_min",
    "umid_aria_mean", "umid_aria_max", "umid_suolo_mean",
    "rain_mm_sum", "giorni_umid_aria_alta",
    "giorni_temp_favorevole", "giorni_pioggia",
]


def build_dataset():
    labels = get_all_labels()
    if not labels:
        return pd.DataFrame()
    rows = []
    for entry in labels:
        node_id     = entry["node_id"]
        label       = entry.get("label", 1)
        window_days = entry.get("window_days", 7)
        event_time  = datetime.fromisoformat(
            entry["event_time"]).replace(tzinfo=timezone.utc)
        df_w = _fetch_window(node_id,
                             event_time - timedelta(days=window_days),
                             event_time)
        feat = _compute_features(df_w)
        if feat is None:
            continue
        feat["label"]   = label
        feat["node_id"] = node_id
        rows.append(feat)
    return pd.DataFrame(rows) if rows else pd.DataFrame()
