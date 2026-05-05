"""
Carica il modello .pkl e restituisce la probabilità di rischio
per un nodo usando gli ultimi N giorni di dati sensore.
"""
from datetime import datetime, timezone, timedelta
from django.conf import settings
import joblib
import pandas as pd
from .ml_dataset import _fetch_window, _compute_features, FEATURE_COLUMNS
from .ml_train import MODEL_PATH


def load_model():
    return joblib.load(MODEL_PATH) if MODEL_PATH.exists() else None


def predict_rischio(node_id: str, window_days: int = 7) -> dict:
    model = load_model()
    if model is None:
        return {"node_id": node_id, "rischio_ml": None,
                "classe": None, "stato": "modello_non_disponibile",
                "msg": "Aggiungi almeno 4 etichette e chiama /api/ml-train/"}

    stop  = datetime.now(timezone.utc)
    start = stop - timedelta(days=window_days)
    feat  = _compute_features(_fetch_window(node_id, start, stop))

    if feat is None:
        return {"node_id": node_id, "rischio_ml": None,
                "classe": None, "stato": "dati_insufficienti"}

    X = pd.DataFrame([{col: feat.get(col, 0) for col in FEATURE_COLUMNS}])
    proba    = model.predict_proba(X)[0]
    classes  = list(model.classes_)
    idx      = classes.index(1) if 1 in classes else -1
    rischio  = round(float(proba[idx]) * 100, 1) if idx >= 0 else 0.0
    classe   = "alto_rischio" if rischio >= 50 else "basso_rischio"
    return {"node_id": node_id, "rischio_ml": rischio,
            "classe": classe, "stato": "ok", "feature_usate": feat}


def predict_tutti(window_days: int = 7) -> list:
    from influxdb_client import InfluxDBClient
    client = InfluxDBClient(url=settings.INFLUX_HOST,
                            token=settings.INFLUX_TOKEN,
                            org=settings.INFLUX_ORG)
    try:
        flux = f'''
from(bucket: "{settings.INFLUX_BUCKET}")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> keep(columns: ["node_id"])
  |> distinct(column: "node_id")
'''
        tables = client.query_api().query(query=flux)
        nodi = [r.get_value() for t in tables for r in t.records]
    except Exception:
        nodi = []
    client.close()
    return [predict_rischio(n, window_days) for n in nodi]
