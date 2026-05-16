#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ====== Physical Sensor Pin Assignments ======
#define DHTPIN 4
#define DHTTYPE DHT22
#define POT_PIN 34
#define LDR_PIN 35
#define TRIG_PIN 5
#define ECHO_PIN 18
#define BTN_PIN 19
#define LED_PIN 2

DHT dht(DHTPIN, DHTTYPE);

// ====== MQTT ======
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";

const char* MQTT_HOSTS[] = {"broker.emqx.io", "test.mosquitto.org", "broker.hivemq.com"};
const int   MQTT_PORT = 1883;

const char* TOPIC_SENSORS = "factory/sensors/all";
const char* TOPIC_ALERTS  = "factory/sensors/alerts";
const char* TOPIC_CMD     = "factory/sensors/cmd";

const unsigned long PUBLISH_MS = 1000;
const float ANOMALY_RATIO = 1.3;

#define SENSORS_PER_TYPE 5
#define NUM_TYPES        10
#define TOTAL_SENSORS    50

struct Sensor {
  char  id[4];
  const char* type;
  const char* zone;
  float base;
  float cur;
  float overrideVal;
  unsigned long overrideUntil;
  const char* status;
  bool alerted;
};

const char* TYPES[NUM_TYPES]    = {"Temp","Vibration","Current","Light","Humidity","Ultrasonic","IR","Pressure","Smoke","Fire"};
const char* ZONES[NUM_TYPES]    = {"A","A","A","A","B","B","B","C","C","C"};
const float BASES[NUM_TYPES]    = {45, 2.5, 12, 500, 45, 2.0, 1.0, 101.3, 10, 5};
const char  PREFIXES[NUM_TYPES] = {'T','V','C','L','H','U','I','P','S','F'};

Sensor sensors[TOTAL_SENSORS];
unsigned long lastPub = 0;
int currentBroker = 0;
unsigned long lastConnAttempt = 0;
bool mqttEverConnected = false;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

JsonDocument jsonDoc;
char jsonBuf[6144];

unsigned long lastBtnRead = 0;
bool lastBtnState = HIGH;

void connectWiFi() {
  Serial.print("WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500); Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf(" OK (%s)\n", WiFi.localIP().toString().c_str());
    Serial.flush();
  } else {
    Serial.printf(" FAIL (%d)\n", WiFi.status());
    Serial.flush();
  }
}

void connectMQTT() {
  if (WiFi.status() != WL_CONNECTED) return;
  unsigned long now = millis();
  if (now - lastConnAttempt < 3000) return;
  lastConnAttempt = now;

  for (int i = 0; i < 3; i++) {
    int idx = (currentBroker + i) % 3;
    IPAddress ip;
    Serial.printf("MQTT[%d] %s...", idx, MQTT_HOSTS[idx]);
    Serial.flush();
    if (!WiFi.hostByName(MQTT_HOSTS[idx], ip)) {
      Serial.println("DNS FAIL");
      Serial.flush();
      continue;
    }
    mqtt.setServer(ip, MQTT_PORT);
    String cid = "FactoryWokwi-";
    cid += String(random(0xFFFF), HEX);
    if (mqtt.connect(cid.c_str())) {
      Serial.println("OK");
      Serial.flush();
      mqtt.subscribe(TOPIC_CMD);
      currentBroker = idx;
      mqttEverConnected = true;
      digitalWrite(LED_PIN, HIGH);
      return;
    }
    Serial.printf("rc=%d\n", mqtt.state());
    Serial.flush();
  }
}

float gauss() {
  float s = 0;
  for (int i = 0; i < 12; i++) s += random(-10000, 10001) / 10000.0;
  return s / 12.0;
}

void initSensors() {
  int idx = 0;
  for (int t = 0; t < NUM_TYPES; t++) {
    for (int i = 1; i <= SENSORS_PER_TYPE; i++) {
      Sensor& sn = sensors[idx];
      snprintf(sn.id, sizeof(sn.id), "%c%d", PREFIXES[t], i);
      sn.type   = TYPES[t];
      sn.zone   = ZONES[t];
      sn.base   = BASES[t];
      sn.cur    = sn.base;
      sn.overrideVal   = 0;
      sn.overrideUntil = 0;
      sn.status = "NORMAL";
      sn.alerted = false;
      idx++;
    }
  }
  Serial.printf("Init %d sensors\n", TOTAL_SENSORS);
  Serial.flush();
}

void readPhysicalSensors() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  if (!isnan(h) && !isnan(t)) {
    sensors[0].cur = roundf(t * 100.0) / 100.0;
    sensors[15].cur = roundf(h * 100.0) / 100.0;
  }
  int potRaw = analogRead(POT_PIN);
  sensors[5].cur = roundf((potRaw / 4095.0) * 5.0 * 100.0) / 100.0;
  int ldrRaw = analogRead(LDR_PIN);
  sensors[30].cur = roundf((ldrRaw / 4095.0) * 1000.0 * 100.0) / 100.0;
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  float dist = duration * 0.034 / 2.0 / 100.0;
  if (dist > 0 && dist < 4.0) {
    sensors[25].cur = roundf(dist * 100.0) / 100.0;
  }
  bool btn = digitalRead(BTN_PIN);
  if (btn == LOW && lastBtnState == HIGH && millis() - lastBtnRead > 300) {
    lastBtnRead = millis();
    Serial.println("BTN fault");
    bool picked[TOTAL_SENSORS] = {false};
    for (int n = 0; n < 3; n++) {
      int idx;
      do { idx = random(TOTAL_SENSORS); } while (picked[idx]);
      picked[idx] = true;
      Sensor& s = sensors[idx];
      s.overrideVal = s.base * 1.6;
      s.overrideUntil = millis() + 15000UL;
      s.cur = s.overrideVal;
      s.status = "OVERRIDE";
    }
  }
  lastBtnState = btn;
}

void updateSensors() {
  unsigned long now = millis();
  for (int i = 0; i < TOTAL_SENSORS; i++) {
    Sensor& s = sensors[i];
    if (s.overrideUntil > 0 && now < s.overrideUntil) {
      s.cur = s.overrideVal;
      s.status = "OVERRIDE";
      continue;
    }
    s.overrideUntil = 0;
    s.status = "NORMAL";
    s.alerted = false;
    float noise = gauss() * (s.base * 0.02);
    s.cur = s.base + noise;
    if (s.cur < 0) s.cur = 0;
    s.cur = roundf(s.cur * 100.0) / 100.0;
    if (s.base > 0 && (s.cur / s.base) > ANOMALY_RATIO) {
      s.status = "ANOMALY";
    }
  }
  readPhysicalSensors();
}

void publishSensors() {
  jsonDoc.clear();
  JsonArray arr = jsonDoc.to<JsonArray>();
  for (int i = 0; i < TOTAL_SENSORS; i++) {
    Sensor& s = sensors[i];
    JsonObject o = arr.add<JsonObject>();
    o["id"]     = s.id;
    o["type"]   = s.type;
    o["zone"]   = s.zone;
    o["value"]  = s.cur;
    o["base"]   = s.base;
    o["status"] = s.status;
  }
  size_t len = serializeJson(jsonDoc, jsonBuf, sizeof(jsonBuf));
  mqtt.publish(TOPIC_SENSORS, jsonBuf);
  Serial.printf("Pub %d (%uB)\n", TOTAL_SENSORS, len);
  Serial.flush();
}

void publishAlerts() {
  for (int i = 0; i < TOTAL_SENSORS; i++) {
    Sensor& s = sensors[i];
    if (strcmp(s.status, "ANOMALY") == 0 && !s.alerted) {
      s.alerted = true;
      jsonDoc.clear();
      JsonObject o = jsonDoc.to<JsonObject>();
      o["id"]   = s.id;
      o["type"] = s.type;
      o["zone"] = s.zone;
      o["value"] = s.cur;
      o["base"]  = s.base;
      o["ratio"] = roundf((s.cur / s.base) * 100.0) / 100.0;
      o["severity"] = "HIGH";
      o["ts"]   = millis();
      size_t len = serializeJson(jsonDoc, jsonBuf, sizeof(jsonBuf));
      mqtt.publish(TOPIC_ALERTS, jsonBuf);
      Serial.printf("Alert %s\n", s.id);
      Serial.flush();
    }
  }
}

void handleCmd(const char* msg) {
  if (strcmp(msg, "FAULT_RANDOM_3") == 0) {
    bool picked[TOTAL_SENSORS] = {false};
    for (int n = 0; n < 3; n++) {
      int idx;
      do { idx = random(TOTAL_SENSORS); } while (picked[idx]);
      picked[idx] = true;
      Sensor& s = sensors[idx];
      s.overrideVal = s.base * 1.6;
      s.overrideUntil = millis() + 15000UL;
      s.cur = s.overrideVal;
      s.status = "OVERRIDE";
    }
  } else if (strcmp(msg, "FAULT_ALL") == 0) {
    for (int i = 0; i < TOTAL_SENSORS; i++) {
      sensors[i].overrideVal = sensors[i].base * 2.0;
      sensors[i].overrideUntil = millis() + 15000UL;
      sensors[i].cur = sensors[i].overrideVal;
      sensors[i].status = "OVERRIDE";
    }
  } else if (strncmp(msg, "OVERRIDE:", 9) == 0) {
    char sid[4]; float val; unsigned long dur;
    if (sscanf(msg + 9, "%3[^:]:%f:%lu", sid, &val, &dur) == 3) {
      for (int i = 0; i < TOTAL_SENSORS; i++) {
        if (strcmp(sensors[i].id, sid) == 0) {
          sensors[i].overrideVal = val;
          sensors[i].overrideUntil = millis() + dur * 1000UL;
          sensors[i].cur = val;
          sensors[i].status = "OVERRIDE";
          break;
        }
      }
    }
  } else if (strcmp(msg, "CLEAR") == 0) {
    for (int i = 0; i < TOTAL_SENSORS; i++) {
      sensors[i].overrideUntil = 0;
      sensors[i].status = "NORMAL";
      sensors[i].alerted = false;
    }
  } else if (strcmp(msg, "STOP") == 0) {
    esp_deep_sleep_start();
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  char msg[length + 1];
  memcpy(msg, payload, length);
  msg[length] = '\0';
  handleCmd(msg);
}

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println();
  Serial.println("=== Smart Factory IoT - Wokwi ESP32 ===");
  Serial.flush();

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  delay(300);
  digitalWrite(LED_PIN, LOW);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BTN_PIN, INPUT_PULLUP);
  lastBtnState = digitalRead(BTN_PIN);

  dht.begin();
  initSensors();
  connectWiFi();
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(6144);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    delay(2000);
    return;
  }
  if (!mqtt.connected()) {
    if (millis() - lastConnAttempt > 5000) connectMQTT();
    delay(100);
    return;
  }
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastPub >= PUBLISH_MS) {
    updateSensors();
    publishSensors();
    publishAlerts();
    lastPub = now;
  }
}
