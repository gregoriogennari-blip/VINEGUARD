from django.urls import path
from .views import (
    dashboard_home, latest_data_json, receive_sensors,
    emergency_alert, telegram_webhook,
    ml_risk_json, ml_label_json, ml_labels_list, ml_train_json,
)

urlpatterns = [
    path("",                    dashboard_home,   name="dashboard_home"),
    path("api/latest/",         latest_data_json, name="latest_data_json"),
    path("api/sensors/",        receive_sensors,  name="receive_sensors"),
    path("api/emergency/",      emergency_alert,  name="emergency_alert"),
    path("telegram/webhook/",   telegram_webhook, name="telegram_webhook"),
    path("api/ml-risk/",        ml_risk_json,     name="ml_risk_json"),
    path("api/ml-label/",       ml_label_json,    name="ml_label_json"),
    path("api/ml-labels/",      ml_labels_list,   name="ml_labels_list"),
    path("api/ml-train/",       ml_train_json,    name="ml_train_json"),
]
