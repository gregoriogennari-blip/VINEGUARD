from django.urls import path
from .views import (
    dashboard_home,
    latest_data_json,
    receive_sensors,
    emergency_alert,
)

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),
    path("api/latest/", latest_data_json, name="latest_data_json"),
    path("api/sensors/", receive_sensors, name="receive_sensors"),
    path("api/emergency/", emergency_alert, name="emergency_alert"),
]