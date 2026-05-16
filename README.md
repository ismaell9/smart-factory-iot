# Smart Factory IoT Digital Twin

A real-time digital twin of a smart factory with 50 IoT sensors. The simulation runs as a native **C++ binary** publishing MQTT telemetry to a public broker, consumed by a **Streamlit dashboard** for visualization, anomaly detection, and interactive control.

## Architecture

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
- **Random** — local Python simulation (no MQTT needed)
- **MQTT** — live sensor data from the C++ simulator (or physical ESP32)

## Features

### Factory Floor Map
- **3 zones**: Assembly (A), Logistics (B), Safety (C)
- **50 sensors** (10 types × 5 each) plotted as color-coded dots with ID + value labels
- **Autonomous robot** (yellow diamond) navigates toward fault/override sensors, patrols otherwise
- **Hover tooltips** showing ID, type, zone, value, base, status

### Simulation Engine (C++ native)
- Each sensor fluctuates with Gaussian noise around its baseline
- **Fault injection**: Random 3 sensors or ALL — overrides at 1.6×/2.0× baseline for 15 s
- Sensors auto-detect **ANOMALY** when value exceeds 1.3× baseline
- Publishes JSON to `factory/sensors/all` every 1 second

### Controls
- **Start / Stop** simulation
- **AI toggle** for anomaly detection
- **Sidebar**: Fault injection, Sensor Override, MQTT data source selection

### AI Anomaly Detection
- **Threshold alert**: value > 130% baseline → HIGH alert + toast
- **Trend alert**: 10 consecutive rising samples → MEDIUM alert
- Real-time summaries: avg/max temperature, fault count, total alerts

### Data Export
- **Download CSV** (when stopped) — full session history across all sensors
- Status logging: NORMAL, ANOMALY, OVERRIDE, UNKNOWN

## Data Format

All sources (C++ simulator, ESP32 firmware, Python) publish identical JSON:

```json
{"id":"T1","type":"Temp","zone":"A","value":45.2,"base":45,"status":"NORMAL"}
```

| Field   | Description                        |
|---------|------------------------------------|
| id      | Sensor ID (e.g. T1, V3, P5)       |
| type    | Sensor type (Temp, Vibration, ...) |
| zone    | Zone A, B, or C                    |
| value   | Current reading                    |
| base    | Baseline value                     |
| status  | NORMAL / ANOMALY / OVERRIDE        |

## Sensors

| Type       | Base   | Zone | Count |
|------------|--------|------|-------|
| Temp       | 45     | A    | 5     |
| Vibration  | 2.5    | A    | 5     |
| Current    | 12     | A    | 5     |
| Light      | 500    | A    | 5     |
| Humidity   | 45     | B    | 5     |
| Ultrasonic | 2.0    | B    | 5     |
| IR         | 1.0    | B    | 5     |
| Pressure   | 101.3  | C    | 5     |
| Smoke      | 10     | C    | 5     |
| Fire       | 5      | C    | 5     |

## Tech Stack

| Component          | Technology                      |
|--------------------|---------------------------------|
| Simulation engine  | C++ (native binary, g++)        |
| Dashboard          | Streamlit                       |
| Map + chart        | Altair                          |
| Data processing    | Pandas, NumPy                   |
| MQTT broker        | broker.emqx.io (public)         |
| MQTT (C++)         | POSIX sockets (minimal client)  |
| MQTT (Python)      | paho-mqtt                       |
| ESP32 firmware     | Arduino framework, PubSubClient |

## Installation

### Prerequisites
- Python 3.10+
- g++ (for C++ simulator)
- pip

### Setup

```bash
git clone https://github.com/ismaell9/smart-factory-iot.git
cd smart-factory-iot

python3 -m venv .venv
source .venv/bin/activate

pip install -r smart_factory/requirements.txt
```

## Usage

### Quick start (simulator + dashboard)

```bash
./run.sh
```

The script:
1. Compiles `simulation/simulator.cpp` if needed
2. Kills any old instances
3. Starts the C++ simulator (publishes to broker.emqx.io)
4. Starts the Streamlit dashboard

Open the URL shown in the terminal, then click **📡 MQTT: OFF → ON** in the top bar.

### Stop

```bash
./run.sh stop
```

Sends an MQTT STOP command, then force-kills remaining processes.

### Run dashboard only (local simulation, no MQTT)

```bash
source .venv/bin/activate
streamlit run smart_factory/app.py
```

Dashboard works in **Random** mode without any MQTT broker — click Start to begin.

## Project Structure

```
.
├── run.sh                          # Launcher (compiles, starts sim + dashboard)
├── simulation/
│   ├── simulator.cpp               # C++ native simulator (50 sensors, MQTT publisher)
│   ├── sketch.ino                  # Canonical ESP32 firmware source
│   ├── stop_sim.py                 # Publishes STOP command via MQTT
│   ├── diagram.json                # Wokwi wiring diagram
│   ├── libraries.txt               # Wokwi library list
│   └── wokwi/                      # Wokwi VS Code project (standalone)
│       ├── platformio.ini
│       ├── wokwi.toml
│       ├── diagram.json
│       ├── src/sketch.ino
│       └── ...
├── smart_factory/
│   ├── app.py                      # Streamlit dashboard (main entry point)
│   ├── config.py                   # MQTT broker configuration
│   ├── mqtt_receiver.py            # MQTT subscriber thread (caches last data)
│   ├── mqtt_publisher.py           # Python MQTT publisher (legacy)
│   ├── sensor_sim.py               # Local Python sensor simulation (Random mode)
│   ├── fault_injector.py           # Fault injection logic
│   ├── ai_anomaly_detector.py      # AI threshold + trend detection
│   ├── dashboard.py, main.py, run_all.py, publisher.py  # Legacy entries
│   └── requirements.txt            # Python dependencies
├── log/                            # Runtime logs (gitignored)
└── .gitignore
```

## Wokwi (ESP32 Firmware)

> **Wokwi runs entirely separately** and does **not** affect the C++ simulation or the dashboard in any way.

The `simulation/wokwi/` directory contains a complete PlatformIO project for the ESP32 firmware, identical in logic to the C++ simulator but designed for physical or emulated hardware:

### Sensors (Wokwi/ESP32 only)

| Sensor          | Pin  | ID      |
|-----------------|------|---------|
| DHT22 (Temp/Hum)| GPIO4| T1, H1  |
| Potentiometer   | GPIO34| V1     |
| Photoresistor   | GPIO35| L1     |
| HC-SR04 (Ultr.) | GPIO5/18 | U1  |
| Pushbutton      | GPIO19| Fault   |
| LED             | GPIO2 | —       |

### Running on Wokwi VS Code Extension (free tier)

1. Open `simulation/wokwi/` in VS Code
2. Install **Wokwi Simulator** extension
3. Press **F1 → Wokwi: Start Simulator**
4. Firmware runs locally — **MQTT will NOT work** (free Wokwi Gateway doesn't forward internet traffic)
5. Test locally: serial output, LED blink, button input

### Running on Wokwi.com (online, MQTT works)

1. Go to [wokwi.com](https://wokwi.com)
2. Create a new project, upload the files from `simulation/wokwi/`
3. Start the simulation — the ESP32 connects to `broker.emqx.io:1883` and publishes to `factory/sensors/all`
4. Dashboard picks up the data when MQTT mode is enabled

The `simulation/sketch.ino` is the **canonical firmware source** — `simulation/wokwi/src/sketch.ino` is kept in sync.
