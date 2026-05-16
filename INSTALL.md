# Installation Guide

Step-by-step instructions to set up, run, and customize the Smart Factory IoT Digital Twin on a fresh Linux/macOS/Windows system.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Python Environment Setup](#3-python-environment-setup)
4. [C++ Simulator](#4-c-simulator)
5. [Running the Project](#5-running-the-project)
6. [Wokwi / ESP32 Setup (Optional)](#6-wokwi--esp32-setup-optional)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Prerequisites

### System-wide Requirements

| Tool       | Version | Purpose                         | Install Command (Linux)                   | Install Command (macOS)                    | Install Command (Windows)                     |
|------------|---------|---------------------------------|-------------------------------------------|--------------------------------------------|------------------------------------------------|
| Git        | 2.x     | Clone the repository            | `sudo apt install git`                    | `brew install git` or Xcode CLT            | [git-scm.com](https://git-scm.com)            |
| Python     | 3.10+   | Run the Streamlit dashboard     | `sudo apt install python3 python3-pip`    | `brew install python@3.11`                 | [python.org](https://python.org)              |
| g++        | 8+      | Compile the C++ simulator       | `sudo apt install g++`                    | `xcode-select --install`                   | [MinGW-w64](https://www.mingw-w64.org) or WSL |
| make       | —       | Build tools (g++ may need it)   | `sudo apt install build-essential`        | `xcode-select --install`                   | Included with MinGW or WSL                    |

### Verify Installation

```bash
git --version
python3 --version      # should be 3.10+
g++ --version          # should be 8+
pip3 --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/ismaell9/smart-factory-iot.git
cd smart-factory-iot
```

---

## 3. Python Environment Setup

### 3.1 Create a Virtual Environment

```bash
python3 -m venv .venv
```

Activate it:

| Platform | Command                  |
|----------|--------------------------|
| Linux/macOS | `source .venv/bin/activate` |
| Windows  | `.venv\Scripts\activate` |

You should see `(.venv)` at the start of your terminal prompt.

### 3.2 Install Python Dependencies

The file `smart_factory/requirements.txt` contains all needed Python packages:

| Package           | Version | Purpose                          |
|-------------------|---------|----------------------------------|
| `paho-mqtt`       | ≥2.0.0  | MQTT client for receiving sensor data |
| `streamlit`       | ≥1.25.0 | Web dashboard framework          |
| `numpy`           | ≥1.24.0 | Numerical operations for sensor math |

These are **transitive dependencies** pulled in automatically by streamlit:

| Package  | Purpose                          |
|----------|----------------------------------|
| pandas   | Data manipulation for sensor tables |
| altair   | Vega-Lite charts for factory map |

Install with:

```bash
pip install -r smart_factory/requirements.txt
```

> **Note on Windows**: streamlit includes `winsound` support for alert beeps (built into Windows Python, no extra install needed). On Linux/macOS, alerts display as toast notifications but do not beep.

---

## 4. C++ Simulator

### What It Needs

The C++ simulator (`simulation/simulator.cpp`) uses **only the C++ standard library and POSIX sockets** — no external libraries required.

### Compilation

The `run.sh` script compiles it automatically, but you can also compile manually:

```bash
g++ -std=c++11 -o simulation/simulator simulation/simulator.cpp
```

This produces a binary at `simulation/simulator`.

> **Windows users**: The simulator uses POSIX sockets (`sys/socket.h`, `netdb.h`, `unistd.h`, `poll.h`). It does **not** compile natively on Windows. Options:
> - **WSL (recommended)**: Install WSL2 with Ubuntu, clone the repo inside WSL, and follow Linux instructions
> - **Cygwin**: Install Cygwin with g++ and POSIX socket libraries
> - **Skip it**: The dashboard works in **Random** mode without the C++ simulator (no MQTT needed)

---

## 5. Running the Project

### 5.1 Quick Start (Everything)

From the project root, with the virtual environment activated:

```bash
./run.sh
```

What this does:
1. Compiles `simulation/simulator.cpp` if the binary doesn't exist
2. Kills any previously running instances
3. Starts the C++ simulator (connects to `broker.emqx.io:1883`, publishes 50 sensors every 1s)
4. Starts the Streamlit dashboard on `http://localhost:8501`
5. Prints the dashboard URL

Open the URL in your browser, then click the **📡 MQTT: OFF** button in the top bar to switch it to **ON** — the dashboard will begin displaying live MQTT sensor data.

To stop everything:

```bash
./run.sh stop
```

This sends a STOP command via MQTT to the C++ simulator, then force-kills any remaining processes.

### 5.2 Run Dashboard Only (Random / Offline Mode)

If you don't want MQTT (or are on Windows without WSL):

```bash
source .venv/bin/activate
streamlit run smart_factory/app.py
```

Open `http://localhost:8501`, click **Start**, and the dashboard runs a local Python simulation. No MQTT broker needed.

### 5.3 Run C++ Simulator + Dashboard Separately

Terminal 1:

```bash
source .venv/bin/activate
./run.sh
```

Or manually:

```bash
# Terminal 1: C++ simulator
g++ -std=c++11 -o simulation/simulator simulation/simulator.cpp
./simulation/simulator

# Terminal 2: Dashboard
source .venv/bin/activate
streamlit run smart_factory/app.py
```

### 5.4 Logs

| Log File          | Contents                        | View Command                      |
|-------------------|---------------------------------|-----------------------------------|
| `log/sim.log`     | C++ simulator debug output      | `tail -f log/sim.log`             |
| `log/dash.log`    | Streamlit server output         | `tail -f log/dash.log`            |

---

## 6. Wokwi / ESP32 Setup (Optional)

> **Wokwi runs entirely independently** — it does not affect the C++ simulation or the dashboard. The dashboard receives data from whichever source publishes to MQTT.

### 6.1 Project Structure

```
simulation/wokwi/
├── platformio.ini         # PlatformIO project config
├── wokwi.toml             # Wokwi emulator config
├── diagram.json           # Wiring diagram
├── src/sketch.ino         # ESP32 firmware (synced with simulation/sketch.ino)
└── libraries.txt          # Library list for Wokwi online
```

### 6.2 ESP32 Firmware Dependencies

The ESP32 firmware (`sketch.ino`) uses these libraries:

| Library                    | Source          | Purpose                       |
|----------------------------|-----------------|-------------------------------|
| `WiFi.h`                   | Built-in (ESP32 core) | WiFi connectivity        |
| `PubSubClient`             | knolleary/PubSubClient | MQTT publish/subscribe |
| `ArduinoJson`              | bblanchon/ArduinoJson | JSON serialization      |
| `DHT sensor library`       | adafruit/DHT sensor library | DHT22 temperature/humidity sensor |
| `Adafruit Unified Sensor`  | adafruit/Adafruit Unified Sensor | Sensor abstraction layer |

### 6.3 Option A: Wokwi Online (MQTT Works)

1. Go to [wokwi.com](https://wokwi.com) and sign in
2. Click **New Project → ESP32**
3. Replace the auto-generated files with the contents of `simulation/wokwi/`:
   - `sketch.ino` → the code
   - `diagram.json` → the wiring
   - `libraries.txt` → library dependencies
4. Click **Start Simulation**
5. The ESP32 connects to `broker.emqx.io:1883` and publishes to `factory/sensors/all`
6. Run the dashboard locally with MQTT mode ON to see live Wokwi data

### 6.4 Option B: Wokwi VS Code Extension (Free Tier, MQTT Does NOT Work)

The free Wokwi VS Code Gateway does **not** forward internet traffic — MQTT connections will fail.

**Setup:**

1. Install [VS Code](https://code.visualstudio.com)
2. Install the **Wokwi Simulator** extension from the marketplace
3. Open the `simulation/wokwi/` folder in VS Code:
   ```bash
   code simulation/wokwi/
   ```
4. Press **F1 → Wokwi: Start Simulator**

**What works locally**: Serial output, LED blink, button input, sensor readings on the serial monitor.

**What does NOT work**: MQTT (cannot reach `broker.emqx.io`).

To test MQTT from VS Code, you would need the [Wokwi Private Gateway](https://docs.wokwi.com/guides/private-gateway) (paid).

### 6.5 Option C: Physical ESP32 Hardware

1. Install [PlatformIO](https://platformio.org) (VS Code extension or CLI)
2. Open the `simulation/wokwi/` folder
3. Modify WiFi credentials in `sketch.ino`:
   ```cpp
   const char* WIFI_SSID = "Your WiFi Name";
   const char* WIFI_PASS = "Your WiFi Password";
   ```
4. Upload to your ESP32:
   ```bash
   pio run --target upload
   ```
5. Open serial monitor to verify MQTT connection:
   ```bash
   pio device monitor -b 115200
   ```

### 6.6 Physical Sensor Wiring (ESP32)

| Sensor          | ESP32 Pin | Purpose            |
|-----------------|-----------|---------------------|
| DHT22           | GPIO4     | Temp (T1) + Humidity (H1) |
| Potentiometer   | GPIO34    | Vibration proxy (V1) |
| Photoresistor (LDR) | GPIO35 | Light (L1)        |
| HC-SR04 Trig    | GPIO5     | Ultrasonic (U1)    |
| HC-SR04 Echo    | GPIO18    | Ultrasonic (U1)    |
| Pushbutton      | GPIO19    | Fault injection     |
| LED             | GPIO2     | Status indicator    |

---

## 7. Troubleshooting

### "Failed to connect MQTT" from C++ simulator

- Ensure you have internet access (port 1883 outbound)
- The broker `broker.emqx.io` may be temporarily down — try again later
- Check `log/sim.log` for detailed error messages

### Dashboard shows "UNKNOWN" status for all sensors in MQTT mode

- The C++ simulator may not be running (start it with `./run.sh`)
- Wait up to 5 seconds after starting the simulator for the first MQTT message
- Check `log/sim.log` for "MQTT connected" message

### `g++: command not found`

Install g++:
- **Ubuntu/Debian**: `sudo apt install g++ build-essential`
- **macOS**: `xcode-select --install`
- **Windows**: Install WSL and follow Ubuntu instructions

### `pip install` fails

- Upgrade pip: `pip install --upgrade pip`
- Ensure Python 3.10+ is installed: `python3 --version`
- On some systems you may need `python3.11 -m venv .venv` instead of `python3`

### Port 8501 already in use

Kill existing streamlit processes:

```bash
pkill -f streamlit
```

Or use a different port:

```bash
streamlit run smart_factory/app.py --server.port 8502
```

### No Altair chart displayed

Altair ships with streamlit. Ensure your streamlit version is ≥1.25.0:

```bash
pip install --upgrade streamlit
```

### Wokwi VS Code shows "WiFi connection failed"

This is expected on the free tier — the Wokwi Gateway does not forward internet traffic. Use Wokwi Online or physical hardware for MQTT.
