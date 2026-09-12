/*
 * CropWatch Lite - ESP32 Smart Irrigation Node Firmware
 * -------------------------------------------------------
 * Board:   ESP32 DevKit v1 (or ESP32-S3)
 * IDE:     Arduino IDE 2.x / PlatformIO
 * Libs:    PubSubClient (MQTT), ArduinoJson, WiFiClientSecure
 *
 * Hardware wiring:
 *   - Capacitive soil moisture sensor  → ADC1 CH6 (GPIO 34, input-only)
 *   - DS18B20 soil temperature sensor  → GPIO 4 (OneWire)
 *   - EC sensor (analog)               → ADC1 CH7 (GPIO 35)
 *   - 24V solenoid relay               → GPIO 26 (active HIGH)
 *   - Status LED                       → GPIO 2
 *
 * MQTT topics:
 *   Publish:  cropwatch/telemetry/{NODE_ID}
 *   Subscribe: cropwatch/commands/{NODE_ID}
 *
 * Edge fallback: if WiFi drops, run local VWC threshold loop.
 */

#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---- Configuration (change per node) ----
const char* NODE_ID         = "field_corn_01_zone_sw_n5";
const char* ZONE_ID         = "zone_sw";
const char* WIFI_SSID       = "YourFarmSSID";
const char* WIFI_PASSWORD   = "YourWiFiPassword";
const char* MQTT_BROKER     = "your-iot-endpoint.iot.us-east-1.amazonaws.com";
const int   MQTT_PORT       = 8883;

// AWS IoT certificates (paste PEM strings or load from SPIFFS)
const char* CA_CERT         = "-----BEGIN CERTIFICATE-----\n...AmazonRootCA1...\n-----END CERTIFICATE-----\n";
const char* DEVICE_CERT     = "-----BEGIN CERTIFICATE-----\n...device cert...\n-----END CERTIFICATE-----\n";
const char* PRIVATE_KEY     = "-----BEGIN RSA PRIVATE KEY-----\n...private key...\n-----END RSA PRIVATE KEY-----\n";

// ---- Pin definitions ----
const int PIN_MOISTURE      = 34;   // Capacitive moisture sensor (ADC)
const int PIN_EC            = 35;   // EC sensor (ADC)
const int PIN_RELAY         = 26;   // Solenoid valve relay (active HIGH)
const int PIN_LED           = 2;    // Onboard LED

// ---- Thresholds (edge fallback) ----
const float CRITICAL_VWC_PCT = 28.0;
const int   VALVE_OPEN_MS    = 1200000;  // 20 minutes in ms

// ---- Globals ----
WiFiClientSecure wifiClient;
PubSubClient mqttClient(wifiClient);
bool valveOpen = false;
unsigned long valveOpenedAt = 0;
unsigned long lastTelemetryMs = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 300000;  // 5 minutes

// ---- Sensor readings ----
float readVWC() {
  // Calibrate: map raw ADC to VWC% (0-100)
  // Raw 4095 = air (0% VWC), Raw 1500 = saturated (field capacity)
  int raw = analogRead(PIN_MOISTURE);
  float vwc = map(raw, 4095, 1500, 0, 100);
  return constrain(vwc, 0.0, 100.0);
}

float readEC() {
  int raw = analogRead(PIN_EC);
  // Approximate EC in dS/m from ADC voltage
  float voltage = raw * (3.3 / 4095.0);
  return voltage * 1.5;  // Calibration factor (adjust per sensor model)
}

float readSoilTemp() {
  // Stub: implement DS18B20 OneWire read here
  // Real: DallasTemperature sensors.getTempCByIndex(0);
  return 22.5;
}

// ---- MQTT callback: handles incoming valve commands ----
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) return;

  const char* action = doc["action"] | "skip";
  if (strcmp(action, "irrigate") == 0) {
    float durationMin = doc["duration_min"] | 20.0;
    openValve((unsigned long)(durationMin * 60000));
  } else if (strcmp(action, "close") == 0) {
    closeValve();
  }
}

void openValve(unsigned long durationMs) {
  digitalWrite(PIN_RELAY, HIGH);
  digitalWrite(PIN_LED, HIGH);
  valveOpen = true;
  valveOpenedAt = millis();
  Serial.printf("[VALVE] OPEN for %.1f min\n", durationMs / 60000.0);
}

void closeValve() {
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_LED, LOW);
  valveOpen = false;
  Serial.println("[VALVE] CLOSED");
}

// ---- Publish telemetry to MQTT ----
void publishTelemetry() {
  float vwc  = readVWC();
  float ec   = readEC();
  float temp = readSoilTemp();
  int   batt = 92;  // Stub: read from fuel gauge IC if available

  StaticJsonDocument<512> doc;
  doc["node_id"]    = NODE_ID;
  doc["zone_id"]    = ZONE_ID;
  doc["vwc_pct"]    = vwc;
  doc["ec_ds_m"]    = ec;
  doc["soil_temp_c"] = temp;
  doc["battery_pct"] = batt;
  doc["valve_open"] = valveOpen;

  char buf[512];
  serializeJson(doc, buf);

  char topic[128];
  snprintf(topic, sizeof(topic), "cropwatch/telemetry/%s", NODE_ID);
  mqttClient.publish(topic, buf);
  Serial.printf("[MQTT] Published → %s\n", topic);
}

// ---- Edge fallback: run locally when cloud is down ----
void edgeFallbackTick() {
  float vwc = readVWC();
  Serial.printf("[EDGE] VWC=%.1f%% (threshold=%.1f%%)\n", vwc, CRITICAL_VWC_PCT);
  if (vwc < CRITICAL_VWC_PCT && !valveOpen) {
    Serial.println("[EDGE] Below threshold → opening valve (fallback mode)");
    openValve(VALVE_OPEN_MS);
  } else if (vwc >= CRITICAL_VWC_PCT && valveOpen) {
    closeValve();
  }
}

// ---- WiFi + MQTT connection ----
bool connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 20; i++) {
    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("[WiFi] Connected: %s\n", WiFi.localIP().toString().c_str());
      return true;
    }
    delay(500);
  }
  Serial.println("[WiFi] FAILED — entering edge fallback mode");
  return false;
}

bool connectMQTT() {
  wifiClient.setCACert(CA_CERT);
  wifiClient.setCertificate(DEVICE_CERT);
  wifiClient.setPrivateKey(PRIVATE_KEY);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);

  if (mqttClient.connect(NODE_ID)) {
    char sub_topic[128];
    snprintf(sub_topic, sizeof(sub_topic), "cropwatch/commands/%s", NODE_ID);
    mqttClient.subscribe(sub_topic);
    Serial.printf("[MQTT] Connected. Subscribed to %s\n", sub_topic);
    return true;
  }
  Serial.printf("[MQTT] Failed, rc=%d\n", mqttClient.state());
  return false;
}

// ---- Arduino setup / loop ----
void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_LED, LOW);

  bool wifiOk = connectWiFi();
  if (wifiOk) connectMQTT();
}

void loop() {
  bool cloudOk = WiFi.status() == WL_CONNECTED && mqttClient.connected();

  if (cloudOk) {
    mqttClient.loop();
    // Publish telemetry every 5 minutes
    if (millis() - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
      publishTelemetry();
      lastTelemetryMs = millis();
    }
  } else {
    // Edge fallback: re-evaluate every 5 minutes locally
    if (millis() - lastTelemetryMs >= TELEMETRY_INTERVAL_MS) {
      edgeFallbackTick();
      lastTelemetryMs = millis();
    }
    // Try to reconnect every 30s
    static unsigned long lastReconnect = 0;
    if (millis() - lastReconnect > 30000) {
      lastReconnect = millis();
      if (WiFi.status() != WL_CONNECTED) connectWiFi();
      else connectMQTT();
    }
  }

  // Auto-close valve after scheduled duration
  if (valveOpen && (millis() - valveOpenedAt >= VALVE_OPEN_MS)) {
    closeValve();
  }
}
