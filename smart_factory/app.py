import streamlit as st
import pandas as pd
import numpy as np
import time
import random
from datetime import datetime, timedelta
import config

# Alert sound (Windows only)
try:
    import winsound
    HAS_SOUND = True
except ImportError:
    HAS_SOUND = False

# Altair is shipped with Streamlit — used for interactive hover tooltips
try:
    import altair as alt
    HAS_ALTAIR = True
except ImportError:
    HAS_ALTAIR = False

# MQTT integration
try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

# --- Page Setup ---
st.set_page_config(page_title="Smart Factory Digital Twin", layout="wide", page_icon="🏭")

# ==========================================
# 1. INITIALIZATION
# ==========================================
if 'sensors' not in st.session_state:
    SENSOR_TYPES = ['Temp', 'Vibration', 'Current', 'Humidity', 'Pressure', 'Ultrasonic', 'Light', 'Smoke', 'Fire', 'IR']
    sensors = {}
    for s_type in SENSOR_TYPES:
        for i in range(1, 6):
            sid = f"{s_type[0]}{i}"
            zone_map = {
                'Temp':'A', 'Vibration':'A', 'Current':'A', 'Light':'A',
                'Humidity':'B', 'Ultrasonic':'B', 'IR':'B',
                'Pressure':'C', 'Smoke':'C', 'Fire':'C'
            }
            base_map = {
                'Temp':45, 'Vibration':2.5, 'Current':12, 'Humidity':45,
                'Pressure':101.3, 'Ultrasonic':2.0, 'Light':500, 'Smoke':10,
                'Fire':5, 'IR':1.0
            }
            zone = zone_map[s_type]
            base = base_map[s_type]
            sensors[sid] = {
                'id': sid, 'type': s_type, 'zone': zone, 'base_val': base,
                'current_val': float(base), 'override_val': None, 'override_until': None, 'status': 'NORMAL',
                'x': float(random.randint(60, 740)), 'y': float(random.randint(60, 440)),
                'history': []  # For AI trend analysis
            }
    st.session_state.sensors = sensors

if 'robot' not in st.session_state:
    st.session_state.robot = {'x': 400.0, 'y': 250.0, 'target_x': 400.0, 'target_y': 250.0, 'status': 'IDLE', 'speed': 4.0, 'target_sensor': None}
if 'running' not in st.session_state: st.session_state.running = False
if 'ai_on' not in st.session_state: st.session_state.ai_on = False
if 'alerts' not in st.session_state: st.session_state.alerts = []
if 'override_input' not in st.session_state: st.session_state.override_input = 0.0
if 'override_values' not in st.session_state: st.session_state.override_values = {}
if 'last_selected_sensor' not in st.session_state: st.session_state.last_selected_sensor = None
if 'ai_insights' not in st.session_state: st.session_state.ai_insights = []
if 'alert_count' not in st.session_state: st.session_state.alert_count = 0
if 'use_mqtt' not in st.session_state: st.session_state.use_mqtt = False

# ==========================================
# 1b. MQTT RECEIVER (persists across reruns)
# ==========================================
@st.cache_resource
def get_mqtt_receiver():
    if not HAS_MQTT:
        return None
    print("[MQTT] Starting receiver...", flush=True)
    from mqtt_receiver import MQTTReceiver
    r = MQTTReceiver()
    r.start()
    return r

# ==========================================
# 2. SIMULATION LOGIC
# ==========================================
def run_simulation():
    if not st.session_state.running:
        return
        
    ts = datetime.now().strftime("%H:%M:%S")
    
    # 1. Pull MQTT data (if enabled and available)
    mqtt_map = {}
    if st.session_state.use_mqtt:
        recv = get_mqtt_receiver()
        if recv:
            data = recv.get_latest_sensors()
            print(f"[MQTT DEBUG] got {len(data) if data else 0} sensors", flush=True)
        if data:
            for entry in data:
                mqtt_map[entry['id']] = entry
            for alert in recv.get_pending_alerts():
                st.session_state.alerts.append({
                    "ts": datetime.now().strftime("%H:%M:%S"),
                    "msg": f"ESP32: {alert.get('id','?')} {alert.get('type','?')} ({alert.get('value','?')})",
                    "sev": "HIGH",
                    "type": "ESP_ALERT"
                })

    # 2. Update Sensors
    for sid, s in st.session_state.sensors.items():
        now = datetime.now()
        if s['override_until'] and now < s['override_until']:
            s['current_val'] = s['override_val']
            s['status'] = 'OVERRIDE'
        elif sid in mqtt_map:
            s['current_val'] = mqtt_map[sid]['value']
            s['status'] = mqtt_map[sid]['status']
        elif st.session_state.use_mqtt:
            s['status'] = 'UNKNOWN'
        else:
            s['override_until'] = None
            noise = random.gauss(0, s['base_val'] * 0.02) if s['base_val'] != 0 else 0
            s['current_val'] = round(max(0, s['base_val'] + noise), 2)
            if s['base_val'] > 0 and (s['current_val'] / s['base_val']) > 1.3:
                s['status'] = 'ANOMALY'
            else:
                s['status'] = 'NORMAL'
        
        s['history'].append({'ts': datetime.now().strftime("%H:%M:%S"), 'val': s['current_val'], 'status': s['status']})
        if len(s['history']) > 30: s['history'].pop(0)

    # 2. Robot Navigation - Prioritize Fault Sensors
    r = st.session_state.robot
    
    # Find all sensors in fault/override state
    fault_sensors = [s for s in st.session_state.sensors.values() if s['status'] in ('OVERRIDE', 'ANOMALY')]
    
    if fault_sensors:
        # Speed boost when responding to faults
        r['speed'] = 8.0
        # Find nearest fault sensor
        nearest = min(fault_sensors, key=lambda s: np.sqrt((s['x']-r['x'])**2 + (s['y']-r['y'])**2))
        dist_to_target = np.sqrt((nearest['x']-r['x'])**2 + (nearest['y']-r['y'])**2)
        
        if dist_to_target > 10:
            r['target_x'], r['target_y'] = nearest['x'], nearest['y']
            r['target_sensor'] = nearest['id']
            r['status'] = 'INSPECTING'
        else:
            r['status'] = 'ON_SITE'
    else:
        # Normal patrol speed
        r['speed'] = 4.0
        # No faults - navigate randomly with waypoints
        wp = [(150.0, 150.0), (400.0, 100.0), (650.0, 200.0), (650.0, 400.0), (400.0, 400.0), (200.0, 300.0)]
        r['target_sensor'] = None
        dx, dy = r['target_x']-r['x'], r['target_y']-r['y']
        dist = np.sqrt(dx**2+dy**2)
        if dist <= r['speed']:
            wp_idx = random.randint(0, len(wp)-1)
            r['target_x'], r['target_y'] = wp[wp_idx]
    
    # Move robot
    dx, dy = r['target_x']-r['x'], r['target_y']-r['y']
    dist = np.sqrt(dx**2+dy**2)
    if dist > r['speed']:
        r['x'] += (dx/dist)*r['speed']
        r['y'] += (dy/dist)*r['speed']
        if r['status'] not in ['INSPECTING', 'ON_SITE']:
            r['status'] = 'MOVING'

    # 3. AI Detection & Advanced Analytics
    if st.session_state.ai_on:
        for sid, s in st.session_state.sensors.items():
            # Basic threshold anomaly
            if s['base_val'] > 0 and (s['current_val'] / s['base_val']) > 1.3:
                al = {"ts": ts, "msg": f"AI: {sid} High ({s['current_val']})", "sev": "HIGH", "type": "THRESHOLD"}
                if al not in st.session_state.alerts:
                    st.session_state.alerts.append(al)
            
            # Advanced: Trend analysis (rising temperature)
            if len(s['history']) >= 10:
                recent_vals = [h['val'] for h in s['history'][-10:]]
                if all(recent_vals[i] <= recent_vals[i+1] for i in range(len(recent_vals)-1)):
                    if s['base_val'] > 0 and s['current_val'] / s['base_val'] > 1.1:
                        trend_al = {"ts": ts, "msg": f"AI: {sid} RISING TREND ({s['current_val']:.1f})", "sev": "MEDIUM", "type": "TREND"}
                        if trend_al not in st.session_state.alerts:
                            st.session_state.alerts.append(trend_al)

        # Generate AI Insight summaries
        insights = []
        temp_sensors = [s for sid, s in st.session_state.sensors.items() if s['type'] == 'Temp']
        if temp_sensors:
            avg_temp = np.mean([s['current_val'] for s in temp_sensors])
            max_temp = max([s['current_val'] for s in temp_sensors])
            insights.append(f"🌡 Avg Temp: {avg_temp:.1f}°C | Max: {max_temp:.1f}°C")
        
        fault_count = sum(1 for s in st.session_state.sensors.values() if s['status'] in ('OVERRIDE', 'ANOMALY'))
        if fault_count > 0:
            insights.append(f"⚠ {fault_count} sensor(s) in override state")
        
        if len(st.session_state.alerts) > 0:
            insights.append(f"📊 Total Alerts Today: {len(st.session_state.alerts)}")
        
        st.session_state.ai_insights = insights

# ==========================================
# 3. UI & RENDERING
# ==========================================
st.title("🏭 Smart Factory Digital Twin")

# --- Top Control Bar (compact horizontal row) ---
ctrl_top = st.columns([1.5, 1.5, 1, 1, 1, 1, 1])
with ctrl_top[1]:
    st.button("🚀 Start", type="primary", disabled=st.session_state.running, on_click=lambda: setattr(st.session_state, 'running', True), width='stretch')
with ctrl_top[2]:
    st.button("⏹ Stop", disabled=not st.session_state.running, on_click=lambda: setattr(st.session_state, 'running', False), width='stretch')
with ctrl_top[3]:
    ai_label = "🤖 AI: ON" if st.session_state.ai_on else "🤖 AI: OFF"
    st.button(ai_label, type="secondary" if not st.session_state.ai_on else "primary", on_click=lambda: setattr(st.session_state, 'ai_on', not st.session_state.ai_on), width='stretch')
with ctrl_top[4]:
    st.button("🎲 Random", type="primary" if not st.session_state.use_mqtt else "secondary",
              on_click=lambda: setattr(st.session_state, 'use_mqtt', False), width='stretch')
with ctrl_top[5]:
    mqtt_disabled = not HAS_MQTT
    st.button("📡 MQTT", type="primary" if st.session_state.use_mqtt else "secondary",
              disabled=mqtt_disabled,
              on_click=lambda: setattr(st.session_state, 'use_mqtt', True), width='stretch')
with ctrl_top[6]:
    src = "📡 MQTT" if st.session_state.use_mqtt else "🎲 Random"
    st.write(f"**Source: {src}**")

# --- Sidebar: Only Fault Injection ---
with st.sidebar:
    st.header("🎲 Fault Injection")
    if st.button("🎲 Random Fault (3 sensors)", width='stretch'):
        keys = list(st.session_state.sensors.keys())
        for t in random.sample(keys, 3):
            s = st.session_state.sensors[t]
            s['override_val'] = s['base_val'] * 1.6
            s['current_val'] = s['override_val']
            s['override_until'] = datetime.now() + timedelta(seconds=15)
            s['status'] = 'OVERRIDE'
    if st.button("🔥 ALL Sensors Fault", width='stretch'):
        for s in st.session_state.sensors.values():
            s['override_val'] = s['base_val'] * 2.0
            s['current_val'] = s['override_val']
            s['override_until'] = datetime.now() + timedelta(seconds=15)
            s['status'] = 'OVERRIDE'

    st.divider()
    st.markdown("**📡 Sensor Override**")
    sel = st.selectbox("Select Sensor", [s['id'] for s in st.session_state.sensors.values()], key="sensor_sel")
    if sel:
        s = st.session_state.sensors[sel]
        st.write(f"Type: {s['type']} | Base: {s['base_val']} | Current: {s['current_val']}")

        if st.session_state.last_selected_sensor != sel:
            st.session_state.override_values[sel] = float(s['current_val'])
            st.session_state.last_selected_sensor = sel

        if sel not in st.session_state.override_values:
            st.session_state.override_values[sel] = float(s['current_val'])

        nv = st.number_input("Override Value", value=float(st.session_state.override_values[sel]), step=0.5, key="ov_" + sel)
        st.session_state.override_values[sel] = nv

        dur = st.slider("Duration (sec)", 5, 60, 10, key="override_dur")
        if st.button("✅ Apply Override", width="stretch"):
            s['override_val'] = nv
            s['override_until'] = datetime.now() + timedelta(seconds=dur)
            st.success(f"Applied {nv} for {dur}s")

# Run simulation
run_simulation()

# --- Main Layout ---
col_map, ctrl = st.columns([3, 1])

# --- Factory Map ---
with col_map:
    st.subheader("🗺️ Interactive Factory Floor")

    s_list = list(st.session_state.sensors.values())
    r_pos = st.session_state.robot

    if HAS_ALTAIR:
        sensors_df = pd.DataFrame([{
            'id': s['id'], 'type': s['type'], 'zone': s['zone'],
            'value': s['current_val'], 'base': s['base_val'],
            'status': s['status'], 'x': s['x'], 'y': s['y']
        } for s in s_list])
        robot_df = pd.DataFrame([{'x': r_pos['x'], 'y': r_pos['y'], 'label': f"🤖 {r_pos['status']}"}])

        domain = alt.Scale(domain=['NORMAL','OVERRIDE','ANOMALY','UNKNOWN'], range=['#22c55e','#f59e0b','#ef4444','#64748b'])

        layers = [
            alt.Chart(sensors_df).mark_circle(size=150, stroke='white', strokeWidth=1.5).encode(
                x='x', y='y', color=alt.Color('status', scale=domain, legend=alt.Legend(title="Status")),
                tooltip=['id', 'type', 'zone', 'value', 'base', 'status']),
            alt.Chart(sensors_df).mark_text(align='left', fontSize=8, fontWeight='bold', color='white', dx=8).encode(
                x='x', y='y', text='id'),
            alt.Chart(sensors_df).mark_text(align='left', fontSize=7, color='#94a3b8', dx=8, dy=11).encode(
                x='x', y='y', text='value'),
            alt.Chart(robot_df).mark_point(shape='diamond', size=400, color='#fbbf24', stroke='white', strokeWidth=2.5, filled=True).encode(
                x='x', y='y'),
            alt.Chart(robot_df).mark_text(align='center', fontSize=14, fontWeight='bold', color='#fbbf24', dy=-25).encode(
                x='x', y='y', text='label'),
        ]

        ts = r_pos.get('target_sensor')
        if ts:
            tgt = next((s for s in s_list if s['id'] == ts), None)
            if tgt:
                line_df = pd.DataFrame([{'x': r_pos['x'], 'y': r_pos['y']}, {'x': tgt['x'], 'y': tgt['y']}])
                layers.insert(0, alt.Chart(line_df).mark_line(color='#fbbf24', strokeDash=[4,4], strokeWidth=1, opacity=0.5).encode(x='x', y='y'))

        chart = alt.layer(*layers).properties(height=450).configure_view(fill='#0f172a', stroke=None)
        st.altair_chart(chart, width='stretch')
    else:
        st.warning("Altair not available for interactive map.")
        df_map = pd.DataFrame([{
            'x': s['x'], 'y': s['y'], 'id': s['id'], 'status': s['status']
        } for s in s_list] + [{'x': r_pos['x'], 'y': r_pos['y'], 'id': '🤖 ROBOT', 'status': r_pos['status']}])
        st.scatter_chart(df_map, x='x', y='y', color='status', size=60, width='stretch')

    # --- Sensor Data Table ---
    st.divider()
    st.subheader("📊 Live Sensor Data")
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table_data = []
    for s in s_list:
        dev = round((s['current_val'] / s['base_val'] - 1) * 100, 1) if s['base_val'] > 0 else 0
        table_data.append({
            "Timestamp": ts_now, "ID": s['id'], "Type": s['type'],
            "Zone": s['zone'], "Value": s['current_val'], "Base": s['base_val'],
            "Dev %": dev, "Status": s['status']
        })
    df_table = pd.DataFrame(table_data)

    # Click → popup: use selectbox + popover (works in all Streamlit versions)
    sel_for_detail = st.selectbox("🔍 Click a sensor to see full details", [""] + [s['id'] for s in s_list], key="detail_sel")
    if sel_for_detail:
        ds = st.session_state.sensors[sel_for_detail]
        with st.popover(f"📡 {ds['id']} — Full Details", width='stretch'):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**ID:** {ds['id']}")
                st.markdown(f"**Type:** {ds['type']}")
                st.markdown(f"**Zone:** {ds['zone']}")
                st.markdown(f"**Base:** {ds['base_val']}")
                st.markdown(f"**Current:** {ds['current_val']}")
            with c2:
                st.markdown(f"**Status:** {ds['status']}")
                st.markdown(f"**Deviation:** {round((ds['current_val']/ds['base_val']-1)*100,1) if ds['base_val']>0 else 0}%")
                st.markdown(f"**Override:** {'Active' if ds['override_until'] and datetime.now() < ds['override_until'] else 'None'}")
                st.markdown(f"**History:** {len(ds['history'])} samples")
            if ds['history']:
                hist_df = pd.DataFrame(ds['history'])
                st.line_chart(hist_df, x='ts', y='val', height=150)

    st.dataframe(df_table, hide_index=True, width='stretch', height=280)

    # Download button (visible when stopped) — full session history
    if not st.session_state.running:
        all_rows = []
        for s in s_list:
            h = s.get('history', [])
            if h:
                for entry in h:
                    all_rows.append({
                        "Timestamp": entry['ts'],
                        "Sensor_ID": s['id'],
                        "Type": s['type'],
                        "Zone": s['zone'],
                        "Value": entry['val'],
                        "Base": s['base_val'],
                        "Status": entry['status']
                    })
            else:
                all_rows.append({
                    "Timestamp": ts_now,
                    "Sensor_ID": s['id'],
                    "Type": s['type'],
                    "Zone": s['zone'],
                    "Value": s['current_val'],
                    "Base": s['base_val'],
                    "Status": s['status']
                })
        df_all = pd.DataFrame(all_rows)
        csv = df_all.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Download Full Session CSV", data=csv,
                          file_name=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                          mime="text/csv")

# --- Right Panel: AI Analytics (top) → Controls → Sensor Override (bottom) ---
with ctrl:
    # 1. AI Analytics (most important, at top)
    st.subheader("🤖 AI Analytics")
    if st.session_state.ai_on:
        if st.session_state.ai_insights:
            for insight in st.session_state.ai_insights:
                st.info(insight)
        else:
            st.info("AI Online - Analyzing...")
    else:
        st.warning("AI Detection Disabled")

    st.divider()
    
    # 2. AI Alerts
    st.subheader("📋 AI Alerts")
    if st.session_state.alerts:
        for a in reversed(st.session_state.alerts[-6:]):
            if a['sev'] == "HIGH": st.error(f"[{a['ts']}] {a['msg']}")
            elif a['sev'] == "MEDIUM": st.warning(f"[{a['ts']}] {a['msg']}")
            else: st.info(f"[{a['ts']}] {a['msg']}")
    else:
        st.info("No alerts")

    st.divider()
    
    # 3. Controls
    st.subheader("🎛️ Robot Teleport")
    rx = st.slider("X", 20, 780, int(r_pos['x']), key="rx")
    ry = st.slider("Y", 20, 480, int(r_pos['y']), key="ry")
    if st.button("📍 Move Robot Here", width="stretch"):
        st.session_state.robot.update({'x': float(rx), 'y': float(ry), 'target_x': float(rx), 'target_y': float(ry), 'target_sensor': None})

    # Toast notification + sound for new HIGH alerts
    if st.session_state.alert_count < len(st.session_state.alerts):
        new_alerts = st.session_state.alerts[st.session_state.alert_count:]
        for a in new_alerts:
            if a['sev'] == 'HIGH':
                st.toast(f"🚨 {a['msg']}", icon='🚨')
                if HAS_SOUND:
                    winsound.Beep(880, 300)
        st.session_state.alert_count = len(st.session_state.alerts)

    if st.session_state.running:
        time.sleep(0.4)
        st.rerun()
