
    """train_ml_from_influx.py

    Script di esempio per:
    - leggere dati storici da InfluxDB
    - creare un dataset tabellare
    - definire una colonna di rischio sintetica
    - allenare un modello RandomForest
    - salvare il modello in model_rischio.pkl

    Usa le stesse variabili di ambiente del progetto Django:
    - INFLUX_HOST, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
    """

    import os
    from datetime import datetime, timedelta

    import joblib
    import numpy as np
    import pandas as pd
    from influxdb_client import InfluxDBClient
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split


    def fetch_data_from_influx(days: int = 30) -> pd.DataFrame:
        host = os.environ.get("INFLUX_HOST") or os.environ.get("INFLUXHOST")
        token = os.environ.get("INFLUX_TOKEN") or os.environ.get("INFLUXTOKEN")
        org = os.environ.get("INFLUX_ORG") or os.environ.get("INFLUXORG")
        bucket = os.environ.get("INFLUX_BUCKET") or os.environ.get("INFLUXBUCKET")

        if not all([host, token, org, bucket]):
            raise RuntimeError("Manca una delle variabili INFLUX_HOST/TOKEN/ORG/BUCKET")

        client = InfluxDBClient(url=host, token=token, org=org)
        query_api = client.query_api()

        start = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

        query = f"""
from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r["_measurement"] == "sensordata")
  |> filter(fn: (r) => r["_field"] =~ /temparia|umidaria|umidsuolo|rainmm/)
"""

        tables = query_api.query_data_frame(query)
        if isinstance(tables, list):
            df = pd.concat(tables, ignore_index=True)
        else:
            df = tables

        if df.empty:
            raise RuntimeError("Nessun dato trovato in InfluxDB per il periodo richiesto")

        df = df[["_time", "_field", "_value"]]
        df = df.pivot(index="_time", columns="_field", values="_value").reset_index()
        df = df.sort_values("_time")
        return df


    def add_synthetic_target(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        cond = (df.get("temparia", 0) > 25) & (df.get("umidaria", 0) > 80)
        df["rischio_target"] = np.where(cond, 1, 0)
        return df


    def train_model(df: pd.DataFrame):
        feature_cols = [c for c in df.columns if c in ["temparia", "umidaria", "umidsuolo", "rainmm"]]
        target_col = "rischio_target"

        df = df.dropna(subset=feature_cols + [target_col])
        X = df[feature_cols]
        y = df[target_col]

        if len(df) < 50:
            print("Warning: pochissimi campioni, il modello sarà debole")

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        clf = RandomForestClassifier(n_estimators=200, random_state=42, class_weight="balanced")
        clf.fit(X_train, y_train)

        score = clf.score(X_test, y_test)
        print(f"Accuracy di base sul test: {score:.3f}")

        return clf, feature_cols


    def main():
        print("Lettura dati da InfluxDB...")
        df = fetch_data_from_influx(days=30)
        print(f"Record letti: {len(df)}")

        df = add_synthetic_target(df)
        clf, feature_cols = train_model(df)

        artefact = {
            "model": clf,
            "features": feature_cols,
        }
        joblib.dump(artefact, "model_rischio.pkl")
        print("Modello salvato in model_rischio.pkl")


    if __name__ == "__main__":
        main()
