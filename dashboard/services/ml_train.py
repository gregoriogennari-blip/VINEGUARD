"""
Addestra RandomForestClassifier e salva il modello come .pkl.
Avvia da shell:
  python manage.py shell -c
    "from dashboard.services.ml_train import train_and_save; train_and_save()"
Oppure via POST /api/ml-train/
"""
from pathlib import Path
from django.conf import settings
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from .ml_dataset import build_dataset, FEATURE_COLUMNS

MODEL_PATH  = Path(settings.BASE_DIR) / "dashboard" / "services" / "risk_model.pkl"
MIN_SAMPLES = 4


def train_and_save() -> dict:
    df = build_dataset()
    if df.empty or len(df) < MIN_SAMPLES:
        return {"status": "no_data",
                "msg": f"Esempi insufficienti: {len(df)}/{MIN_SAMPLES}",
                "n_samples": len(df)}
    if df["label"].nunique() < 2:
        return {"status": "single_class",
                "msg": "Servono esempi di entrambe le classi (malata e sana).",
                "n_samples": len(df)}

    X = df[FEATURE_COLUMNS].fillna(0)
    y = df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42,
        stratify=y if len(df) >= 8 else None)

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=100, max_depth=6,
            class_weight="balanced", random_state=42)),
    ])
    pipeline.fit(X_train, y_train)
    joblib.dump(pipeline, MODEL_PATH)

    report = classification_report(
        y_test, pipeline.predict(X_test), output_dict=True)
    return {"status": "trained", "n_samples": len(df),
            "n_train": len(X_train), "n_test": len(X_test),
            "model_path": str(MODEL_PATH), "report": report}


def model_exists() -> bool:
    return MODEL_PATH.exists()
