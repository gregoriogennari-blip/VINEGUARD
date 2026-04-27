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
# ===== Client InfluxDB usato per SCRIVERE (API sensori + emergenza) =====

influx_write_client = InfluxDBClient(
    url=settings.INFLUX_HOST,
    token=settings.INFLUX_TOKEN,
    org=settings.INFLUX_ORG,
)
write_api = influx_write_client.write_api(write_options=SYNCHRONOUS)


# ===== VIEW HTML =====

def dashboard_home(request):
    """
    Pagina principale: mostra ultimi dati per ogni nodo.
    """
    misure = get_latest_measurements()
    context = {
        "titolo": "Vineguard – Dashboard vigneto",
        "misure": misure,
    }
    return render(request, "dashboard/index.html", context)


# ===== API JSON per frontend (grafici / refresh) =====

def latest_data_json(request):
    """
    Restituisce le ultime misure in JSON.
    """
    data = get_latest_as_dict()
    return JsonResponse({"nodes": data})


# ===== API per ricevere dati dal gateway (JSON) =====

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

    write_api.write(bucket=settings.INFLUX_BUCKET, record=point)

    return JsonResponse({"status": "saved"}, status=201)


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
            "Comandi disponibili: MALATTIA, AIUTO, STATO"
        )
        return JsonResponse({"ok": True, "action": "help_sent"})

    if text == "STATO":
        send_telegram_message(
            chat_id,
            "Vineguard online. Dashboard attiva."
        )
        return JsonResponse({"ok": True, "action": "status_sent"})

    send_telegram_message(
        chat_id,
        "Comando non riconosciuto. Scrivi AIUTO."
    )
    return JsonResponse({"ok": True, "action": "unknown_command"})
