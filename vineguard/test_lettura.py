import requests
import os, time, pandas
from influxdb_client_3 import InfluxDBClient3, Point
client = InfluxDBClient3(host=INFLUX_HOST, token=INFLUX_TOKEN, org=INFLUX_ORG)
database="nodo_vineguard_1"

query = """SELECT *
FROM 'census'
WHERE time >= now() - interval '24 hours'
AND ('bees' IS NOT NULL OR 'ants' IS NOT NULL)"""

# Execute the query
table = client.query(query=query, database="nodo_vineguard_1", language='sql') 

# Convert to dataframe
df = table.to_pandas().sort_values(by="time")
print(df)
