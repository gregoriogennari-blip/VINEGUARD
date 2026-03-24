import requests
from settings import INFLUX_HOST, INFLUX_TOKEN, INFLUX_BUCKET, INFLUX_ORG
import os, time
from influxdb_client_3 import InfluxDBClient3, Point
client = InfluxDBClient3(host=INFLUX_HOST, token=INFLUX_TOKEN, org=INFLUX_ORG)
database="nodo_vineguard_1"

data = {
  "point1": {
    "location": "Klamath",
    "species": "bees",
    "count": 23,
  },
  "point2": {
    "location": "Portland",
    "species": "ants",
    "count": 30,
  },
  "point3": {
    "location": "Klamath",
    "species": "bees",
    "count": 28,
  },
  "point4": {
    "location": "Portland",
    "species": "ants",
    "count": 32,
  },
  "point5": {
    "location": "Klamath",
    "species": "bees",
    "count": 29,
  },
  "point6": {
    "location": "Portland",
    "species": "ants",
    "count": 40,
  },
}

for key in data:
  point = (
    Point("census")
    .tag("location", data[key]["location"])
    .field(data[key]["species"], data[key]["count"])
  )
  client.write(database=INFLUX_BUCKET, record=point)
  time.sleep(1) # separate points by 1 second

print("Complete. Return to the InfluxDB UI.")
