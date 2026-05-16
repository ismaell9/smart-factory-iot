# Smart Factory IoT Digital Twin

A real-time digital twin of a smart factory with 50 IoT sensors, an autonomous robot, and AI-driven anomaly detection. The simulation runs as a native **C++ binary** that publishes MQTT telemetry to a public broker, consumed by a **Python Streamlit dashboard** for visualization and interactive control. An **ESP32 firmware** variant mirrors the same logic for physical or Wokwi-emulated hardware.

```
┌──────────────────────┐     MQTT      ┌─────────────────────┐     Streamlit     ┌──────────────┐
│  C++ Simulator       │ ────────────▶ │  Python Subscriber  │ ────────────────▶ │  Dashboard   │
│  (simulator.cpp)     │  broker.emqx  │  (mqtt_receiver.py) │   localhost:8501  │  (app.py)     │
│  50 virtual sensors  │   .io:1883    │  caches last batch  │                   │  Altair map   │
│                      │               │                     │                   │  AI alerts    │
│  ESP32 Firmware ◀────┘               └─────────────────────┘                   │  CSV export   │
│  (sketch.ino)*       │                                                        └──────────────┘
└──────────────────────┘
```

The dashboard has two data source modes (toggle via top bar button):
- **Random** — local Python simulation (no MQTT needed, works offline)
- **MQTT** — live sensor data from the C++ simulator or a physical ESP32

---

## Project Description

### What This Project Does

This project simulates a smart factory floor with **50 IoT sensors** distributed across **3 operational zones** (Assembly, Logistics, Safety). Each sensor generates realistic telemetry — temperature, vibration, humidity, pressure, smoke, fire, light, current, ultrasonic, and IR readings — and reports anomalies when values exceed safe thresholds.

An **autonomous robot** (visualized as a yellow diamond on the factory map) patrols the floor and navigates toward sensors in fault/override states at double speed.

The system supports **fault injection** (random 3 sensors or all 50 at once) and **sensor override** (set any sensor to a custom value for a custom duration), both of which trigger the robot's response and the anomaly detection engine.

### Architecture Overview

The project has three main components that work together:

| Component | Language | Role |
|-----------|----------|------|
| **C++ Simulator** | C++ (g++) | Generates 50 virtual sensor readings every second, publishes via MQTT |
| **ESP32 Firmware** | C++ (Arduino) | Same logic, runs on physical ESP32 or Wokwi emulator |
| **Streamlit Dashboard** | Python | Visualizes data, detects anomalies, provides controls |

**Data flow**: Simulator → MQTT broker (`broker.emqx.io:1883`) → Python subscriber → Streamlit dashboard. All components publish identical JSON format, so the dashboard works with any source without modification.

### Data Format

Every sensor reading is a JSON object:

```json
{"id":"T1","type":"Temp","zone":"A","value":45.2,"base":45,"status":"NORMAL"}
```

| Field   | Description                        | Example          |
|---------|------------------------------------|------------------|
| id      | Sensor ID                          | T1, V3, P5       |
| type    | Sensor type                        | Temp, Vibration, Smoke |
| zone    | Factory zone (A, B, or C)          | A                |
| value   | Current reading                    | 45.2             |
| base    | Baseline / expected value          | 45.0             |
| status  | Current status                     | NORMAL, ANOMALY, OVERRIDE, UNKNOWN |

The C++ simulator publishes all 50 sensors as a JSON array to `factory/sensors/all` every 1 second. Alert events are published individually to `factory/sensors/alerts`. Command messages are received on `factory/sensors/cmd` (STOP, FAULT_RANDOM_3, FAULT_ALL, OVERRIDE:id:val:sec, CLEAR).

### Dashboard Features

**Factory Floor Map (Altair scatter chart)**
- 3 zones displayed with distinct background colors
- 50 sensor dots color-coded by status (green = NORMAL, yellow = OVERRIDE, red = ANOMALY, gray = UNKNOWN)
- Each dot labeled with sensor ID + current value
- Hover tooltip shows ID, type, zone, value, base, status
- Autonomous robot (yellow diamond) patrols or targets faults

**Controls (top bar)**
- Start / Stop simulation
- AI toggle (enable/disable anomaly detection)
- MQTT data source toggle (Random ↔ MQTT)

**Sidebar**
- Fault injection: Random 3 sensors or ALL sensors (1.6× or 2.0× baseline for 15 seconds)
- Sensor Override: select any sensor, set custom value and duration (seconds)
- Mode selector (MQTT source)

**AI Analytics (right panel)**
- Real-time summaries: average temperature, max temperature, fault count, total alerts
- Trending chart, anomaly breakdown pie chart

**AI Alerts**
- Last 6 alerts with severity color coding:
  - **HIGH** (red) — value exceeds 130% of baseline
  - **MEDIUM** (yellow) — monotonically rising values over 10 consecutive samples
- Toast notifications and beep sound (Windows) on new HIGH alerts

**Robot Teleport (right panel)**
- X/Y sliders to reposition the robot instantly

**Sensor Data Table (below map)**
- Live snapshot of all 50 sensors: Timestamp, ID, Type, Zone, Value, Base, Deviation %, Status
- Interactive Altair hover chart below the table
- Sensor details popup: select a sensor → popover with full details + history line chart
- **Download CSV** (appears when stopped) — exports complete session history

### Sensor Inventory

| Type       | Base Value | Zone | Count | Function |
|------------|-----------|------|-------|----------|
| Temp       | 45        | A    | 5     | Temperature in °C |
| Vibration  | 2.5       | A    | 5     | Vibration amplitude (mm/s) |
| Current    | 12        | A    | 5     | Electrical current (A) |
| Light      | 500       | A    | 5     | Ambient light (lux) |
| Humidity   | 45        | B    | 5     | Relative humidity (%) |
| Ultrasonic | 2.0       | B    | 5     | Distance measurement (m) |
| IR         | 1.0       | B    | 5     | Infrared reading |
| Pressure   | 101.3     | C    | 5     | Atmospheric pressure (kPa) |
| Smoke      | 10        | C    | 5     | Smoke density (ppm) |
| Fire       | 5         | C    | 5     | Fire risk index |

### Simulation Engine Details

**C++ Native Simulator** (`simulation/simulator.cpp`)
- No external libraries — uses POSIX sockets with a hand-written minimal MQTT v3.1.1 client
- Each sensor fluctuates with ±2% Gaussian noise around its baseline every second
- Anomaly auto-detection when value exceeds 1.3× baseline
- Fault injection sets override values at 1.6× (random 3) or 2.0× (all) baseline for 15 seconds
- Sensor override allows setting any sensor to any value for any duration
- Subscribes to `factory/sensors/cmd` for real-time control commands
- Pings MQTT broker every 30 seconds to keep connection alive

**ESP32 Firmware** (`simulation/sketch.ino`)
- Same sensor logic but runs on physical hardware with real sensors:
  - DHT22 (temperature, humidity) on GPIO4
  - Potentiometer (vibration proxy) on GPIO34
  - Photoresistor (light) on GPIO35
  - HC-SR04 ultrasonic rangefinder on GPIO5/18
  - Pushbutton for fault injection on GPIO19
  - LED indicator on GPIO2
- Falls back to internal simulation when physical sensor reads fail
- Connects to WiFi (Wokwi-GUEST for emulator, configurable for real hardware)

**Python Local Simulator** (Random mode in dashboard)
- Pure Python fallback that works entirely offline
- No MQTT broker needed — runs entirely within the Streamlit process
- Same 50-sensor model with noise, anomalies, and fault injection

### Robot Behavior

- Yellow diamond icon on the factory floor map
- **Default state**: patrols by moving toward random waypoints
- **Fault response**: when sensors are in OVERRIDE or ANOMALY state, the robot navigates toward the affected sensor at 2× normal speed
- **Teleport**: X/Y sliders in the right panel reposition the robot instantly

### Anomaly Detection

Two detection modes run simultaneously when AI is enabled:

1. **Threshold detection**: any sensor exceeding 130% of its baseline → HIGH severity alert with toast notification and beep sound
2. **Trend detection**: any sensor with monotonically rising values over 10 consecutive samples → MEDIUM severity alert

Alerts appear in the right panel with severity badges and are published to `factory/sensors/alerts` via MQTT.

### Data Logging and Export

- **CSV export**: when the simulation is stopped, a Download CSV button appears with complete session history
- **Real-time logging**: dashboard CSV file tracks every sensor reading with timestamp and status
- **Log files**: `log/sim.log` (C++ simulator output), `log/dash.log` (Streamlit output)

### Wokwi (ESP32 Emulation)

The `simulation/wokwi/` directory contains a complete PlatformIO project for emulating the ESP32 firmware in Wokwi. This runs **independently** and does not affect the C++ simulation or dashboard. See [INSTALL.md](INSTALL.md) for setup instructions.

---

## Project Structure

```
.
├── run.sh                          # Launcher: compiles sim, starts both processes
├── INSTALL.md                      # Step-by-step installation guide
├── README.md                       # This file
│
├── simulation/
│   ├── simulator.cpp               # C++ native simulator (50 sensors, MQTT)
│   ├── sketch.ino                  # Canonical ESP32 firmware source
│   ├── stop_sim.py                 # Publishes MQTT STOP command
│   ├── diagram.json                # Wokwi wiring diagram reference
│   ├── libraries.txt               # Wokwi library list reference
│   └── wokwi/                      # Standalone Wokwi PlatformIO project
│       ├── platformio.ini
│       ├── wokwi.toml
│       ├── diagram.json
│       ├── src/sketch.ino          # (kept in sync with ../sketch.ino)
│       └── ...
│
├── smart_factory/
│   ├── app.py                      # Streamlit dashboard (main entry)
│   ├── config.py                   # MQTT broker settings
│   ├── mqtt_receiver.py            # MQTT subscriber thread (caches last data)
│   ├── mqtt_publisher.py           # Python MQTT publisher (legacy)
│   ├── sensor_sim.py               # Local Python simulation (Random mode)
│   ├── fault_injector.py           # Fault injection logic
│   ├── ai_anomaly_detector.py      # AI threshold + trend detection
│   ├── dashboard.py, main.py, run_all.py, publisher.py  # Legacy scripts
│   └── requirements.txt            # Python dependencies
│
├── log/                            # Runtime logs (gitignored)
└── .gitignore
```

---

## Quick Start

```bash
git clone https://github.com/ismaell9/smart-factory-iot.git
cd smart-factory-iot
python3 -m venv .venv
source .venv/bin/activate
pip install -r smart_factory/requirements.txt
./run.sh
```

See **[INSTALL.md](INSTALL.md)** for detailed setup including prerequisites, Wokwi, and troubleshooting.

## Tech Stack

| Component          | Technology                                    |
|--------------------|-----------------------------------------------|
| Simulation engine  | C++11 (g++, POSIX sockets)                    |
| Dashboard          | Streamlit                                     |
| Map + chart        | Altair (native Vega-Lite, ships with Streamlit)|
| Data processing    | Pandas, NumPy                                 |
| MQTT broker        | broker.emqx.io:1883 (public, free)            |
| MQTT (C++)         | Hand-written minimal MQTT v3.1.1 client       |
| MQTT (Python)      | paho-mqtt                                     |
| ESP32 firmware     | Arduino framework, PubSubClient, ArduinoJson  |
| ESP32 emulation    | Wokwi (online or VS Code extension)           |
