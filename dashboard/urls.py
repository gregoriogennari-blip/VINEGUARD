from django.urls import path
from .views import dashboard_home, receive_sensors, emergency_alert

urlpatterns = [
    path("", dashboard_home, name="dashboard_home"),
    path("api/sensors/", receive_sensors, name="receive_sensors"),
    path("api/emergency/", emergency_alert, name="emergency_alert"),
]