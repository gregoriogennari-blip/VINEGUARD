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
        "node5": {
            "label": 0,
            "temp": (15.0, 19.0),
            "umid": (50.0, 65.0),
            "soil": (28.0, 42.0),
            "rain": (0.0, 3.5),
        },
        "node6": {
            "label": 1,
            "temp": (28.0, 32.0),
            "umid": (82.0, 96.0),
            "soil": (58.0, 78.0),
            "rain": (0.0, 3.0),
        },
        "node7": {
            "label": 0,
            "temp": (17.0, 22.0),
            "umid": (52.0, 68.0),
            "soil": (33.0, 50.0),
            "rain": (0.0, 4.5),
        },
        "node8": {
            "label": 1,
            "temp": (25.0, 30.0),
            "umid": (87.0, 94.0),
            "soil": (64.0, 80.0),
            "rain": (0.0, 2.8),
        },
    }

    client = InfluxDBClient(
        url=settings.INFLUX_HOST,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG,
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    num_days = 7
    points_per_day = 4
    start = datetime.now(timezone.utc) - timedelta(days=num_days)
    times = [timedelta(hours=6), timedelta(hours=12), timedelta(hours=18), timedelta(hours=23)]

    total_points = 0
    for day in range(num_days):
        for point_idx in range(points_per_day):
            ts = start + timedelta(days=day) + times[point_idx]
            for node_id, defs in nodes.items():
                temp = uniform(*defs["temp"])
                umid = uniform(*defs["umid"])
                soil = uniform(*defs["soil"])
                rain = uniform(*defs["rain"])
                point = generate_point(node_id, ts, temp, umid, soil, rain)
                write_api.write(bucket=settings.INFLUX_BUCKET, record=point)
                total_points += 1

    print("Dati sensore inviati:", total_points, "punti per", len(nodes), "nodi su", num_days, "giorni.")

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
