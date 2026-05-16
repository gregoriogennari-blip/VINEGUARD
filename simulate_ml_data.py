#!/usr/bin/env python3
"""Simula dati sensore e etichette ML in InfluxDB per VINEGUARD."""
import os
from datetime import datetime, timedelta, timezone
from random import uniform

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vineguard.settings")

from django.conf import settings
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dashboard.services.ml_train import train_and_save


def generate_point(node_id: str, ts: datetime, temp: float, umid: float,
                   soil: float, rain: float) -> Point:
    return (
        Point("sensor_data")
        .tag("node_id", node_id)
        .field("temp_aria", round(temp, 2))
        .field("umid_aria", round(umid, 2))
        .field("umid_suolo", round(soil, 2))
        .field("rain_mm", round(rain, 2))
        .time(ts)
    )


def main():
    print("Simulazione dati ML InfluxDB")

    nodes = {
        "node1": {
            "label": 0,
            "temp": (16.0, 20.0),
            "umid": (45.0, 60.0),
            "soil": (30.0, 45.0),
            "rain": (0.0, 2.0),
        },
        "node2": {
            "label": 1,
            "temp": (27.0, 30.0),
            "umid": (85.0, 92.0),
            "soil": (60.0, 75.0),
            "rain": (0.0, 3.0),
        },
        "node3": {
            "label": 0,
            "temp": (18.0, 23.0),
            "umid": (55.0, 70.0),
            "soil": (35.0, 55.0),
            "rain": (0.0, 4.0),
        },
        "node4": {
            "label": 1,
            "temp": (26.0, 29.0),
            "umid": (88.0, 95.0),
            "soil": (65.0, 82.0),
            "rain": (0.0, 2.5),
        },
    }

    client = InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    start = datetime.now(timezone.utc) - timedelta(days=5)
    for day in range(6):
        ts = start + timedelta(days=day)
        for node_id, defs in nodes.items():
            temp = uniform(*defs["temp"])
            umid = uniform(*defs["umid"])
            soil = uniform(*defs["soil"])
            rain = uniform(*defs["rain"])
            point = generate_point(node_id, ts, temp, umid, soil, rain)
            write_api.write(bucket=settings.INFLUX_BUCKET, record=point)
    print("Dati sensore inviati per", len(nodes), "nodi su 6 giorni.")

    label_time = datetime.now(timezone.utc) - timedelta(days=1)
    for node_id, defs in nodes.items():
        label_point = (
            Point("ml_labels")
            .tag("node_id", node_id)
            .field("label", defs["label"])
            .field("window_days", 7)
            .time(label_time)
        )
        write_api.write(bucket=settings.INFLUX_BUCKET, record=label_point)
    print("Etichette ML inviate (label 0/1).")

    write_api.close()
    client.close()

    print("Avvio training del modello...")
    result = train_and_save()
    print(result)


if __name__ == "__main__":
    main()
