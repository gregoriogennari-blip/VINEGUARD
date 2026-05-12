import json
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .services.influx_service import get_latest_measurements, get_latest_as_dict

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

from .services.ml_labels import save_malattia_label, get_all_labels
from .services.ml_predict import predict_rischio, predict_tutti
from .services.ml_train import train_and_save, model_exists

import os
import joblib
import numpy as np
from functools import lru_cache

def get_write_api():
    """
    Crea il client InfluxDB al momento dell'uso,
    così le variabili ambiente sono già caricate da Render.
    """
    client = InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )
    return client.write_api(write_options=SYNCHRONOUS)
@lru_cache(maxsize=1)
def _load_ml_model():
    path = os.path.join(os.path.dirname(__file__), "model_rischio.pkl")
    if not os.path.exists(path):
        return None
    return joblib.load(path)


def _calcola_rischio_ml(misure):
    artefact = _load_ml_model()
    if artefact is None or not misure:
        return 0

    model = artefact["model"]
    primo_nodo = list(misure.values())[0]

    row = [[
        float(primo_nodo.get("temparia", 0)),
        float(primo_nodo.get("umidaria", 0)),
        float(primo_nodo.get("umidsuolo", 0)),
        float(primo_nodo.get("rainmm", 0)),
    ]]

    row_arr = np.array(row, dtype=float)
    proba = model.predict_proba(row_arr)[0][1]
    return round(float(proba) * 100)

# ===== VIEW HTML =====

def dashboard_home(request):
    misure   = get_latest_measurements()
    rischi   = predict_tutti()
    rischi_map = {r["node_id"]: r for r in rischi}
    context  = {"titolo": "Vineguard – Dashboard vigneto",
                 "misure": misure, "rischi_map": rischi_map,
                 "model_ready": model_exists()}
    return render(request, "dashboard/index.html", context)


# ===== API JSON per frontend (grafici / refresh) =====

def latest_data_json(request):
    """
    Restituisce le ultime misure in JSON.
    """
    data = get_latest_as_dict()
    return JsonResponse({"nodes": data})


# ===== API per ricevere dati dal gateway (JSON) =====
def _calcola_rischio_ml(misure):
    """
    Calcola il rischio come percentuale 0‑100 usando il modello ML.
    Sostituisci il corpo con la chiamata reale al tuo modello.
    'misure' è il dict che già passi al template (ultimi dati per nodo).
    """

    if not misure:
        return 0

    # Esempio: prendo il primo nodo
    primo_nodo = list(misure.values())[0]

    # Qui dovresti estrarre le feature reali:
    # temparia = primo_nodo.get("temparia")
    # umidaria = primo_nodo.get("umidaria")
    # umidsuolo = primo_nodo.get("umidsuolo")
    # rainmm = primo_nodo.get("rainmm")
    #
    # E poi chiamare il tuo modello, per esempio:
    # prob = modello.predict_proba([[temparia, umidaria, umidsuolo, rainmm]])[0][1]

    # Placeholder: per ora restituisco un valore fisso per non rompere nulla
    prob = 0.42  # float tra 0 e 1

    return round(prob * 100)


def dashboard_home(request):
    """
    Pagina principale: ultimi dati + rischio ML.
    """
    misure = getlatestmeasurements()
    rischio_percento = _calcola_rischio_ml(misure)

    context = {
        "titolo": "Vineguard Dashboard vigneto",
        "misure": misure,
        "rischio_percento": rischio_percento,
    }
    return render(request, "dashboard/index.html", context)
@csrf_exempt
def receive_sensors(request):
    """
    Endpoint da chiamare dal gateway.
    Accetta JSON e scrive i dati nel bucket InfluxDB.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # JSON atteso:
    # {
    #   "node_id": "node1",
    #   "temp_aria": 22.5,
    #   "umid_aria": 85.2,
    #   "umid_suolo": 71.4,
    #   "pioggia": 2.1,
    #   "timestamp": "2026-04-13T15:30:00Z"
    # }

    node_id = payload.get("node_id", "unknown")

    try:
        temp_aria = float(payload.get("temp_aria", 0))
        umid_aria = float(payload.get("umid_aria", 0))
        umid_suolo = float(payload.get("umid_suolo", 0))
        rain_mm = float(payload.get("pioggia", 0))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid numeric fields"}, status=400)

    timestamp = payload.get("timestamp")
    if timestamp:
        try:
            time_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            time_obj = datetime.utcnow()
    else:
        time_obj = datetime.utcnow()

    point = (
        Point("sensor_data")
        .tag("node_id", node_id)
        .field("temp_aria", temp_aria)
        .field("umid_aria", umid_aria)
        .field("umid_suolo", umid_suolo)
        .field("rain_mm", rain_mm)
        .time(time_obj)
    )

    write_api = get_write_api()
    write_api.write(bucket=settings.INFLUX_BUCKET, record=point)

    return JsonResponse({"status": "saved"}, status=201)

def ml_risk_json(request):
    node_id = request.GET.get("node_id")
    window  = int(request.GET.get("window", 7))
    data = predict_rischio(node_id, window) if node_id else predict_tutti(window)
    return JsonResponse({"ml_risk": data})

@csrf_exempt
def ml_label_json(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    payload  = json.loads(request.body.decode("utf-8"))
    node_id  = payload.get("node_id")
    if not node_id:
        return JsonResponse({"error": "node_id obbligatorio"}, status=400)
    window_days = int(payload.get("window_days", 7))
    save_malattia_label(node_id, window_days=window_days)
    return JsonResponse({"status": "label_saved", "node_id": node_id}, status=201)

def ml_labels_list(request):
    return JsonResponse({"labels": get_all_labels()})

@csrf_exempt
def ml_train_json(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)
    result = train_and_save()
    return JsonResponse(result)
# ===== API emergenza manuale (pulsante dashboard) =====

@csrf_exempt
def emergency_alert(request):
    """
    Scatta un evento di emergenza: scrive un record in InfluxDB
    e manda un messaggio Telegram (se configurato).
    """
    # Scrittura su Influx
    point = (
        Point("emergency_alert")
        .tag("manual", "true")
        .tag("org", settings.INFLUX_ORG)
        .field("triggered", 1)
        .time(datetime.utcnow())
    )
    write_api = get_write_api()
    write_api.write(bucket=settings.INFLUX_BUCKET, record=point)

    # Invio messaggio Telegram, se TOKEN e CHAT_ID ci sono
    if settings.TELEGRAM_TOKEN and settings.TELEGRAM_CHAT_ID:
        telegram_url = (
            f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage"
        )
        try:
            requests.post(
                telegram_url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": "🚨 VINEGUARD – EMERGENZA MANUALE: controlla il vigneto!",
                },
                timeout=10,
            )
        except requests.RequestException:
            # in dev possiamo ignorare l'errore, oppure loggare
            pass

    return JsonResponse({"status": "alert_sent"})

def send_telegram_message(chat_id, text):
    token = settings.TELEGRAM_TOKEN
    if not token:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    try:
        r = requests.post(url, data=payload, timeout=10)
        return r.ok
    except requests.RequestException:
        return False

@csrf_exempt
@require_POST
def telegram_webhook(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    message = data.get("message", {})
    chat = message.get("chat", {})
    text = (message.get("text") or "").strip().upper()
    chat_id = chat.get("id")

    if not chat_id:
        return JsonResponse({"ok": True})

    if text == "MALATTIA":
        # Qui puoi anche salvare l'evento su DB o Influx
        send_telegram_message(
            chat_id,
            "Segnalazione MALATTIA registrata correttamente."
        )
        return JsonResponse({"ok": True, "action": "malattia_registered"})

    if text == "AIUTO":
        send_telegram_message(
            chat_id,
            "Comandi disponibili: MALATTIA, AIUTO, STATO, ADDESTRA"
        )
        return JsonResponse({"ok": True, "action": "help_sent"})

    if text == "STATO":
        send_telegram_message(
            chat_id,
            "Vineguard online. Dashboard attiva."
        )
        return JsonResponse({"ok": True, "action": "status_sent"})
    if text == "ADDESTRA":
        result = train_and_save()
        if result["status"] == "trained":
            msg = f"🤖 Modello aggiornato! {result['n_samples']} campioni usati."
        else:
            msg = f"⚠️ {result.get('msg', 'Errore training.')}"
        send_telegram_message(chat_id, msg)
        return JsonResponse({"ok": True, "action": "training_done"})
    
    send_telegram_message(
        chat_id,
        "Comando non riconosciuto. Scrivi AIUTO."
    )
    return JsonResponse({"ok": True, "action": "unknown_command"})
