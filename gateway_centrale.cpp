#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <LoRa.h>

// ===== WIFI =====
const char* WIFI_SSID = "TUO_WIFI";
const char* WIFI_PASS = "TUA_PASSWORD";

// ===== INFLUX =====
const char* INFLUX_HOST = "https://eu-central-1-1.aws.cloud2.influxdata.com";
const char* INFLUX_ORG = "VINEGUARD SSH";
const char* INFLUX_BUCKET = "nodo_vineguard_1";
const char* INFLUX_TOKEN = "TUO_TOKEN";

// ===== LORA PINS =====
// Esempio tipico ESP32 + SX127x/RFM95
#define LORA_SS   5
#define LORA_RST  14
#define LORA_DIO0 2

// ===== LORA SETTINGS =====
const long LORA_FREQ = 868E6;   // Europa
const int  LORA_SYNC = 0xF3;

// ===== FUNZIONI =====
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Connessione WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connesso!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi NON connesso.");
  }
}

bool sendToInflux(String lineProtocol) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  WiFiClientSecure client;
  client.setInsecure(); // per semplicità nei test

  HTTPClient https;
  String url = String(INFLUX_HOST) +
               "/api/v2/write?org=" + INFLUX_ORG +
               "&bucket=" + INFLUX_BUCKET +
               "&precision=s";

  https.begin(client, url);
  https.addHeader("Authorization", "Token " + String(INFLUX_TOKEN));
  https.addHeader("Content-Type", "text/plain; charset=utf-8");
  https.addHeader("Accept", "application/json");

  int httpCode = https.POST(lineProtocol);

  Serial.print("HTTP code: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    String response = https.getString();
    if (response.length() > 0) {
      Serial.print("Response: ");
      Serial.println(response);
    }
  }

  https.end();
  return (httpCode == 204);
}

bool parsePayload(String payload,
                  String &nodeId,
                  float &tempAria,
                  float &umidAria,
                  float &umidSuolo,
                  float &rainMm,
                  int &batteryPct) {
  // formato atteso:
  // node1;22.5;85.2;72.0;2.1;95

  int p1 = payload.indexOf(';');
  int p2 = payload.indexOf(';', p1 + 1);
  int p3 = payload.indexOf(';', p2 + 1);
  int p4 = payload.indexOf(';', p3 + 1);
  int p5 = payload.indexOf(';', p4 + 1);

  if (p1 == -1 || p2 == -1 || p3 == -1 || p4 == -1 || p5 == -1) {
    return false;
  }

  nodeId     = payload.substring(0, p1);
  tempAria   = payload.substring(p1 + 1, p2).toFloat();
  umidAria   = payload.substring(p2 + 1, p3).toFloat();
  umidSuolo  = payload.substring(p3 + 1, p4).toFloat();
  rainMm     = payload.substring(p4 + 1, p5).toFloat();
  batteryPct = payload.substring(p5 + 1).toInt();

  return true;
}

String buildLineProtocol(String nodeId,
                         float tempAria,
                         float umidAria,
                         float umidSuolo,
                         float rainMm,
                         int batteryPct) {
  String line = "sensor_data,node_id=" + nodeId +
                " temp_aria=" + String(tempAria, 1) +
                ",umid_aria=" + String(umidAria, 1) +
                ",umid_suolo=" + String(umidSuolo, 1) +
                ",rain_mm=" + String(rainMm, 1) +
                ",battery_pct=" + String(batteryPct);
  return line;
}

void setupLoRa() {
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  while (!LoRa.begin(LORA_FREQ)) {
    Serial.println("Errore init LoRa, ritento...");
    delay(1000);
  }

  LoRa.setSyncWord(LORA_SYNC);
  Serial.println("LoRa inizializzato.");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectWiFi();
  setupLoRa();

  Serial.println("Gateway centrale pronto.");
}

void loop() {
  int packetSize = LoRa.parsePacket();

  if (packetSize) {
    String payload = "";

    while (LoRa.available()) {
      payload += (char)LoRa.read();
    }

    int rssi = LoRa.packetRssi();
    Serial.println("\n--- Pacchetto ricevuto ---");
    Serial.print("Payload: ");
    Serial.println(payload);
    Serial.print("RSSI: ");
    Serial.println(rssi);

    String nodeId;
    float tempAria, umidAria, umidSuolo, rainMm;
    int batteryPct;

    bool ok = parsePayload(payload, nodeId, tempAria, umidAria, umidSuolo, rainMm, batteryPct);

    if (!ok) {
      Serial.println("Payload non valido.");
      return;
    }

    String lineProtocol = buildLineProtocol(nodeId, tempAria, umidAria, umidSuolo, rainMm, batteryPct);

    Serial.print("Line protocol: ");
    Serial.println(lineProtocol);

    bool sent = sendToInflux(lineProtocol);

    if (sent) {
      Serial.println("Dati inviati corretamente a InfluxDB");
    } else {
      Serial.println("Errore invio dei dati a InfluxDB");
    }
  }
}
#define LORA_DIO0 2

// ===== LORA SETTINGS =====
const long LORA_FREQ = 868E6;   // Europa
const int  LORA_SYNC = 0xF3;

// ===== FUNZIONI =====
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.print("Connessione WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500);
    Serial.print(".");
    tries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connesso!");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi NON connesso.");
  }
}

bool sendToInflux(String lineProtocol) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  WiFiClientSecure client;
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  WiFiClientSecure client;
  client.setInsecure(); // per semplicità nei test

  HTTPCl
    connectWiFi();
    if (WiFi.status() != WL_CONN
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;

  WiFiClientSecure client;
  client.setInsecure(); // per semplicità nei test

  HTTPCl  String url = String(INFLUX_HOST) +
               "/api/v2/write?org=" + INFLUX_ORG +
               "&bucket=" + INFLUX_BUCKET +
               "&precision=s";

  https.begin(client, url);
  https.addHeader("Authorization", "Token " + String(INFLUX_TOKEN));
  https.addHeader("Content-Type", "text/plain; charset=utf-8");
  https.addHeader("Accept", "application/json");

  int httpCode = https.POST(lineProtocol);

  Serial.print("HTTP code: ");
  Serial.println(httpCode);

  if (httpCode > 0) {
    String response = https.getString();
    if (response.length() > 0) {
      Serial.print("Response: ");
      Serial.println(response);
    }
  }

  https.end();
  return (httpCode == 204);
}

bool parsePayload(String payload,
                  String &nodeId,
                  float &tempAria,
                  float &umidAria,
                  float &umidSuolo,
                  float &rainMm,
                  int &batteryPct) {
  // formato atteso:
  // node1;22.5;85.2;72.0;2.1;95

  int p1 = payload.indexOf(';');
  int p2 = payload.indexOf(';', p1 + 1);
  int p3 = payload.indexOf(';', p2 + 1);
  int p4 = payload.indexOf(';', p3 + 1);
  int p5 = payload.indexOf(';', p4 + 1);

  if (p1 == -1 || p2 == -1 || p3 == -1 || p4 == -1 || p5 == -1) {
    return false;
  }

  nodeId     = payload.substring(0, p1);
  tempAria   = payload.substring(p1 + 1, p2).toFloat();
  umidAria   = payload.substring(p2 + 1, p3).toFloat();
  umidSuolo  = payload.substring(p3 + 1, p4).toFloat();
  rainMm     = payload.substring(p4 + 1, p5).toFloat();
  batteryPct = payload.substring(p5 + 1).toInt();

  return true;
}

String buildLineProtocol(String nodeId,
                         float tempAria,
                         float umidAria,
                         float umidSuolo,
                         float rainMm,
                         int batteryPct) {
  String line = "sensor_data,node_id=" + nodeId +
                " temp_aria=" + String(tempAria, 1) +
                ",umid_aria=" + String(umidAria, 1) +
                ",umid_suolo=" + String(umidSuolo, 1) +
                ",rain_mm=" + String(rainMm, 1) +
                ",battery_pct=" + String(batteryPct);
  return line;
}

void setupLoRa() {
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

  while (!LoRa.begin(LORA_FREQ)) {
    Serial.println("Errore init LoRa, ritento...");
    delay(1000);
  }

  LoRa.setSyncWord(LORA_SYNC);
  Serial.println("LoRa inizializzato.");
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectWiFi();
  setupLoRa();

  Serial.println("Gateway centrale pronto.");
}

void loop() {
  int packetSize = LoRa.parsePacket();

  if (packetSize) {
    String payload = "";

    while (LoRa.available()) {
      payload += (char)LoRa.read();
    }

    int rssi = LoRa.packetRssi();
    Serial.println("\n--- Pacchetto ricevuto ---");
    Serial.print("Payload: ");
    Serial.println(payload);
    Serial.print("RSSI: ");
    Serial.println(rssi);

    String nodeId;
    float tempAria, umidAria, umidSuolo, rainMm;
    int batteryPct;

    bool ok = parsePayload(payload, nodeId, tempAria, umidAria, umidSuolo, rainMm, batteryPct);

    if (!ok) {
      Serial.println("Payload non valido.");
      return;
    }

    String lineProtocol = buildLineProtocol(nodeId, tempAria, umidAria, umidSuolo, rainMm, batteryPct);

    Serial.print("Line protocol: ");
    Serial.println(lineProtocol);

    bool sent = sendToInflux(lineProtocol);

    if (sent) {
      Serial.println("I InfluxDB");
    } else {
      Serial.println("Errore invio dati a InfluxDB");
    }
  }
}