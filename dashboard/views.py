from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import requests, os
from datetime import datetime

# InfluxDB client
client = InfluxDBClient(
    url=os.getenv('INFLUX_HOST', 'https://eu-central-1-1.aws.cloud2.influxdata.com'),
    token=os.getenv('INFLUX_TOKEN'),
    org=os.getenv('INFLUX_ORG', 'VINEGUARD SSH')
)
write_api = client.write_api(write_options=SYNCHRONOUS)
from django.shortcuts import render
from .services.influx_service import get_latest_measurements

def dashboard_home(request):
    misure = get_latest_measurements()
    context = {
        "titolo": "Vineguard – Dashboard vigneto",
        "misure": misure,
    }
    return render(request, "dashboard/index.html", context)
@csrf_exempt
def receive_sensors(request):
    if request.method == 'POST':
        data = request.body.decode('utf-8')  # Line Protocol
        write_api.write(bucket="_monitoring", record=data)
        return JsonResponse({"status": "saved", "points": 1}, status=204)
    return JsonResponse({"error": "POST only"}, status=405)

@csrf_exempt
def emergency_alert(request):
    point = Point("emergency_alert") \
        .tag("manual", "true") \
        .tag("org", "VINEGUARD SSH") \
        .field("triggered", 1) \
        .time(datetime.utcnow())
    
    write_api.write(bucket="_monitoring", record=point)
    
    # Telegram
    telegram_url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}/sendMessage"
    requests.post(telegram_url, json={
        "chat_id": os.getenv('TELEGRAM_CHAT_ID'),
        "text": "🚨 VINEGUARD EMERGENZA MANUALE - Controlla vigneto!"
    })
    
    return JsonResponse({"status": "alert_sent"})
