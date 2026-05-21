import csv
import json
from datetime import datetime

import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .services.influx_service import (
    format_timestamp,
    get_historical_data,
    get_latest_as_dict,
    get_node_ids,
    risk_level,
)
from .services.ml_labels import get_all_labels, save_malattia_label
from .services.ml_predict import predict_rischio, predict_tutti
from .services.ml_train import model_exists, train_and_save


def _format_time(value):
    return format_timestamp(value)


MINI_CHART_WIDTH = 420
MINI_CHART_HEIGHT = 120
MINI_CHART_LEFT = 42
MINI_CHART_RIGHT = 12
MINI_CHART_TOP = 12
MINI_CHART_BOTTOM = 24


def _mini_svg_points(values, min_value, max_value):
    clean = [None if value is None else float(value) for value in values]
    if not clean:
        return ""
    plot_w = MINI_CHART_WIDTH - MINI_CHART_LEFT - MINI_CHART_RIGHT
    plot_h = MINI_CHART_HEIGHT - MINI_CHART_TOP - MINI_CHART_BOTTOM
    value_range = max(max_value - min_value, 1)
    denom = max(len(clean) - 1, 1)
    points = []
    for index, value in enumerate(clean):
        if value is None:
            continue
        clipped = max(min_value, min(value, max_value))
        x = MINI_CHART_LEFT + (index / denom) * plot_w
        y = MINI_CHART_TOP + plot_h - ((clipped - min_value) / value_range) * plot_h
        points.append(f"{round(x, 1)},{round(y, 1)}")
    return " ".join(points)


def _latest_value(values):
    for value in reversed(values or []):
        if value is not None:
            return round(float(value), 1)
    return None


def _build_chart_context(history):
    labels = history.get("time_labels", [])
    first_label = labels[0][8:10] + "/" + labels[0][5:7] + " " + labels[0][11:13] + "h" if labels else ""
    last_label = labels[-1][8:10] + "/" + labels[-1][5:7] + " " + labels[-1][11:13] + "h" if labels else ""

    return {
        "node_id": history.get("node_id"),
        "point_count": len(labels),
        "first_label": first_label,
        "last_label": last_label,
        "chart_left": MINI_CHART_LEFT,
        "chart_right_x": MINI_CHART_WIDTH - MINI_CHART_RIGHT,
        "chart_top": MINI_CHART_TOP,
        "chart_mid_y": MINI_CHART_TOP + ((MINI_CHART_HEIGHT - MINI_CHART_TOP - MINI_CHART_BOTTOM) / 2),
        "chart_bottom_y": MINI_CHART_HEIGHT - MINI_CHART_BOTTOM,
        "series": [
            {
                "name": "Temperatura aria",
                "unit": "C",
                "class": "line-temp",
                "min": 0,
                "max": 40,
                "mid": 20,
                "range_label": "0-40 C",
                "latest": _latest_value(history.get("temperatures", [])),
                "points": _mini_svg_points(history.get("temperatures", []), 0, 40),
            },
            {
                "name": "Umidita aria",
                "unit": "%",
                "class": "line-air",
                "min": 0,
                "max": 100,
                "mid": 50,
                "range_label": "0-100%",
                "latest": _latest_value(history.get("humidity_air", [])),
                "points": _mini_svg_points(history.get("humidity_air", []), 0, 100),
            },
            {
                "name": "Umidita suolo",
                "unit": "%",
                "class": "line-soil",
                "min": 0,
                "max": 100,
                "mid": 50,
                "range_label": "0-100%",
                "latest": _latest_value(history.get("humidity_soil", [])),
                "points": _mini_svg_points(history.get("humidity_soil", []), 0, 100),
            },
            {
                "name": "Pioggia",
                "unit": "mm",
                "class": "line-rain",
                "min": 0,
                "max": 5,
                "mid": 2.5,
                "range_label": "0-5 mm",
                "latest": _latest_value(history.get("rainfall", [])),
                "points": _mini_svg_points(history.get("rainfall", []), 0, 5),
            },
        ],
    }


def get_write_api():
    """
    Crea il client InfluxDB al momento dell'uso, quando le variabili ambiente
    sono gia' caricate.
    """
    client = InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )
    return client.write_api(write_options=SYNCHRONOUS)


def dashboard_home(request):
    selected_node = request.GET.get("node_id")
    misure = get_latest_as_dict(node_id=selected_node)
    all_node_ids = get_node_ids()
    chart_node_id = selected_node or (all_node_ids[0] if all_node_ids else None)
    history = get_historical_data(chart_node_id, days=7) if chart_node_id else {
        "node_id": None,
        "time_labels": [],
        "temperatures": [],
        "humidity_air": [],
        "humidity_soil": [],
        "rainfall": [],
    }

    risks = [m["rischio_db"] for m in misure if m.get("rischio_db") is not None]
    rischio_percento = round(sum(risks) / len(risks), 1) if risks else 0
    overall_level = risk_level(rischio_percento)

    context = {
        "titolo": "Vineguard - Dashboard vigneto",
        "misure": misure,
        "all_node_ids": all_node_ids,
        "model_ready": model_exists(),
        "rischio_percento": rischio_percento,
        "overall_risk_label": overall_level["label"],
        "overall_risk_class": overall_level["class"],
        "selected_node": selected_node,
        "chart": _build_chart_context(history),
        "latest_label": _format_time(misure[0]["time"]) if misure else "N/D",
    }
    return render(request, "dashboard/index.html", context)


def latest_data_json(request):
    """
    Restituisce le ultime misure in JSON. Se node_id e' presente, filtra il
    risultato anche nei refresh automatici del frontend.
    """
    node_id = request.GET.get("node_id")
    data = get_latest_as_dict(node_id=node_id)
    return JsonResponse({"nodes": data})


def historical_data_json(request):
    """
    Restituisce serie storiche sensore dal database InfluxDB per i grafici.
    """
    node_id = request.GET.get("node_id")
    if not node_id:
        node_ids = get_node_ids()
        node_id = node_ids[0] if node_ids else None

    if not node_id:
        return JsonResponse({
            "history": {
                "node_id": None,
                "time_labels": [],
                "temperatures": [],
                "humidity_air": [],
                "humidity_soil": [],
                "rainfall": [],
            }
        })

    try:
        days = int(request.GET.get("days", 7))
    except (TypeError, ValueError):
        days = 7
    days = max(1, min(days, 30))

    return JsonResponse({"history": get_historical_data(node_id=node_id, days=days)})


def export_csv(request):
    node_id = request.GET.get("node_id")
    days = 7

    response = HttpResponse(content_type="text/csv")
    filename = f"vineguard_{node_id}_{days}d.csv" if node_id else f"vineguard_last_{days}d.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "Nodo",
        "Timestamp",
        "Temp aria (C)",
        "Umid aria (%)",
        "Umid suolo (%)",
        "Pioggia (mm)",
    ])

    node_ids = [node_id] if node_id else get_node_ids(days=days)
    for current_node in node_ids:
        history = get_historical_data(current_node, days=days)
        for index, timestamp in enumerate(history.get("time_labels", [])):
            writer.writerow([
                current_node,
                timestamp,
                history.get("temperatures", [])[index] if index < len(history.get("temperatures", [])) else "",
                history.get("humidity_air", [])[index] if index < len(history.get("humidity_air", [])) else "",
                history.get("humidity_soil", [])[index] if index < len(history.get("humidity_soil", [])) else "",
                history.get("rainfall", [])[index] if index < len(history.get("rainfall", [])) else "",
            ])

    return response


@csrf_exempt
def receive_sensors(request):
    """
    Endpoint da chiamare dal gateway. Accetta JSON e scrive i dati nel bucket
    InfluxDB.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

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
    """
    Ritorna il rischio ML per un nodo (se node_id) o per tutti i nodi.
    L'endpoint resta disponibile, ma la dashboard principale usa grafici DB.
    """
    node_id = request.GET.get("node_id")
    window = int(request.GET.get("window", 7))

    data = predict_rischio(node_id, window) if node_id else predict_tutti(window)
    return JsonResponse({"ml_risk": data})


@csrf_exempt
def ml_label_json(request):
    """
    Salva un'etichetta di malattia per un nodo, usando gli ultimi N giorni.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    payload = json.loads(request.body.decode("utf-8"))
    node_id = payload.get("node_id")
    if not node_id:
        return JsonResponse({"error": "node_id obbligatorio"}, status=400)

    window_days = int(payload.get("window_days", 7))
    label = payload.get("label", 1)
    try:
        label = int(label)
    except (TypeError, ValueError):
        return JsonResponse({"error": "label deve essere 0 o 1"}, status=400)
    if label not in (0, 1):
        return JsonResponse({"error": "label deve essere 0 o 1"}, status=400)

    save_malattia_label(node_id, window_days=window_days, label=label)

    return JsonResponse({"status": "label_saved", "node_id": node_id, "label": label}, status=201)


def ml_labels_list(request):
    """
    Lista tutte le etichette di malattia registrate.
    """
    return JsonResponse({"labels": get_all_labels()})


@csrf_exempt
def ml_train_json(request):
    """
    Lancia il training del modello RandomForest e salva il .pkl.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    result = train_and_save()
    return JsonResponse(result)


@csrf_exempt
def emergency_alert(request):
    """
    Scatta un evento di emergenza: scrive un record in InfluxDB e manda un
    messaggio Telegram, se configurato. Se node_id e' presente, salva anche
    l'etichetta malattia per la finestra temporale del nodo.
    """
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
    except Exception:
        payload = {}

    node_id = payload.get("node_id") or request.POST.get("node_id") or request.GET.get("node_id")
    if not node_id:
        return JsonResponse({"error": "Seleziona un nodo prima di segnare una malattia."}, status=400)

    try:
        window_days = int(payload.get("window_days", 7))
    except (TypeError, ValueError):
        window_days = 7
    window_days = max(1, min(window_days, 30))

    save_malattia_label(node_id, window_days=window_days, label=1)

    point = (
        Point("emergency_alert")
        .tag("manual", "true")
        .tag("node_id", node_id)
        .tag("org", settings.INFLUX_ORG)
        .field("triggered", 1)
        .field("label_saved", 1)
        .field("window_days", window_days)
        .time(datetime.utcnow())
    )
    write_api = get_write_api()
    write_api.write(bucket=settings.INFLUX_BUCKET, record=point)

    if settings.TELEGRAM_TOKEN and settings.TELEGRAM_CHAT_ID:
        telegram_url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(
                telegram_url,
                json={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": f"VINEGUARD - MALATTIA segnata per {node_id}. Controlla il vigneto.",
                },
                timeout=10,
            )
        except requests.RequestException:
            pass

    return JsonResponse({
        "status": "alert_sent",
        "label_saved": True,
        "node_id": node_id,
        "window_days": window_days,
    })


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
    """
    Webhook Telegram per comandi: MALATTIA, AIUTO, STATO, ADDESTRA.
    """
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
        send_telegram_message(
            chat_id,
            "Segnalazione MALATTIA registrata correttamente.",
        )
        return JsonResponse({"ok": True, "action": "malattia_registered"})

    if text == "AIUTO":
        send_telegram_message(
            chat_id,
            "Comandi disponibili: MALATTIA, AIUTO, STATO, ADDESTRA",
        )
        return JsonResponse({"ok": True, "action": "help_sent"})

    if text == "STATO":
        send_telegram_message(chat_id, "Vineguard online. Dashboard attiva.")
        return JsonResponse({"ok": True, "action": "status_sent"})

    if text == "ADDESTRA":
        result = train_and_save()
        if result["status"] == "trained":
            msg = f"Modello aggiornato. {result['n_samples']} campioni usati."
        else:
            msg = result.get("msg", "Errore training.")

        send_telegram_message(chat_id, msg)
        return JsonResponse({"ok": True, "action": "training_done"})

    send_telegram_message(chat_id, "Comando non riconosciuto. Scrivi AIUTO.")
    return JsonResponse({"ok": True, "action": "unknown_command"})
