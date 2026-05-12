# Smart Factory IoT Digital Twin

A real-time Streamlit dashboard simulating a smart factory with 50 IoT sensors, an autonomous robot, AI-driven anomaly detection, and interactive controls.

## Features

### Factory Floor Map
- **3 operational zones**: Assembly (A), Logistics (B), Safety (C)
- **50 sensors** (10 types × 5 each) plotted as color-coded nodes:
  - Zone A: Temp, Vibration, Current, Light
  - Zone B: Humidity, Ultrasonic, IR
  - Zone C: Pressure, Smoke, Fire
- **Autonomous robot** (yellow diamond) navigates toward fault/override sensors at double speed, otherwise patrols random waypoints
- **Hover tooltips** on sensor nodes (via Altair interactive chart below the map) showing ID, type, value, and status

### Simulation Engine
- Each sensor fluctuates with ±2% Gaussian noise around its baseline
- **Fault injection**: Random (3 sensors) or ALL — sets override values at 1.6× or 2.0× baseline for 15 seconds
- Sensors auto-detect **ANOMALY** status when value exceeds 1.3× baseline
- Status color code: 🟢 NORMAL, 🟡 OVERRIDE, 🔴 ANOMALY

### Controls (top bar)
- **Start/Stop** simulation
- **AI toggle** to enable/disable anomaly detection
- **Sidebar**: Fault injection buttons (Random 3 / ALL)

### Right Panel
1. **AI Analytics** — real-time summaries: avg/max temperature, fault count, total alerts
2. **AI Alerts** — last 6 alerts with severity color (HIGH = red, MEDIUM = yellow)
3. **Robot Teleport** — X/Y sliders to reposition the robot instantly
4. **Sensor Override** — select any sensor, set a custom value and duration

### Sensor Data Table (below map)
- Live snapshot of all 50 sensors: Timestamp, ID, Type, Zone, Value, Base, Dev %, Status
- **Interactive hover chart** (Altair) — hover to see ID, type, value, status
- **Sensor details popup** — select a sensor → popover with full details + history line chart
- **Download CSV** (appears when stopped) — exports complete session history (all readings across all sensors)

### AI Anomaly Detection
- **Threshold alert**: value exceeds 130% of baseline → HIGH alert + toast notification + beep sound
- **Trend alert**: monotonically rising values over 10 consecutive samples → MEDIUM alert
- **Sound** (Windows): `winsound.Beep(880Hz, 300ms)` on HIGH alerts

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Dashboard | Streamlit |
| Map rendering | Matplotlib |
| Interactive chart | Altair (shipped with Streamlit) |
| Data processing | Pandas, NumPy |
| Sound alerts | winsound (Windows) |
| MQTT bridge | paho-mqtt (optional, configured in config.py) |

## Sensors

| Type | Base Value | Zone | Count |
|------|-----------|------|-------|
| Temp | 45 | A | 5 |
| Vibration | 2.5 | A | 5 |
| Current | 12 | A | 5 |
| Light | 500 | A | 5 |
| Humidity | 45 | B | 5 |
| Ultrasonic | 2.0 | B | 5 |
| IR | 1.0 | B | 5 |
| Pressure | 101.3 | C | 5 |
| Smoke | 10 | C | 5 |
| Fire | 5 | C | 5 |

## Getting Started

```bash
cd smart_factory
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

### Optional Dependencies
- `matplotlib` — factory floor map with zone rectangles
- `winsound` — alert beeps (Windows only, included in standard library)

## Project Structure

```
.
├── smart_factory/
│   ├── app.py                 # Main Streamlit dashboard
│   ├── config.py              # MQTT broker settings
│   ├── sensor_sim.py          # Sensor simulation logic
│   ├── mqtt_publisher.py      # MQTT telemetry publisher
│   ├── ai_anomaly_detector.py # AI detection engine
│   ├── fault_injector.py      # Fault injection module
│   ├── dashboard.py           # Alternative dashboard
│   ├── main.py                # Entry point
│   ├── run_all.py             # Launch all components
│   └── requirements.txt       # Python dependencies
├── README.md
└── .gitignore
```

## Usage Tips

1. Click **Start** to begin simulation
2. Inject faults via sidebar to see robot react
3. Enable **AI Detection** for automated alerts
4. Hover over the interactive scatter chart below the map to inspect sensors
5. Use the **details selector** to view full sensor history
6. Stop simulation and click **Download CSV** to export all session data
