import streamlit as st
import paho.mqtt.client as mqtt
import config
import json
import pandas as pd
import time
from datetime import datetime
import threading

st.set_page_config(page_title="Smart Factory IoT", layout="wide")

if 'df' not in st.session_state:
    st.session_state['df'] = pd.DataFrame(columns=['Timestamp', 'Temperature', 'Vibration', 'Current'])
if 'alerts' not in st.session_state:
    st.session_state['alerts'] = []

def mqtt_callback(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        ts = datetime.fromtimestamp(payload.get('ts', time.time())).strftime('%H:%M:%S')
        
        if 'temperature' in msg.topic:
            new_row = {'Timestamp': ts, 'Temperature': payload['value'], 'Vibration': None, 'Current': None}
        elif 'vibration' in msg.topic:
            new_row = {'Timestamp': ts, 'Temperature': None, 'Vibration': payload['value'], 'Current': None}
        elif 'current' in msg.topic:
            new_row = {'Timestamp': ts, 'Temperature': None, 'Vibration': None, 'Current': payload['value']}
        elif 'alerts' in msg.topic:
            alert_msg = f"[{ts}] {payload.get('type', 'ALERT')}: {payload.get('reason', 'Anomaly detected')}"
            st.session_state['alerts'].append(alert_msg)
            if len(st.session_state['alerts']) > 20:
                st.session_state['alerts'].pop(0)
            return
        else:
            return

        df = st.session_state['df']
        df.loc[len(df)] = new_row
        if len(df) > 100:
            st.session_state['df'] = df.iloc[-100:]
            
    except Exception:
        pass

@st.cache_resource
def start_mqtt():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = mqtt_callback
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
    client.subscribe("factory/zone1/#")
    client.loop_start()
    return client

st.title("🏭 Smart Factory Real-Time Dashboard")
client = start_mqtt()
col1, col2, col3 = st.columns(3)
df = st.session_state['df']

latest_temp = df['Temperature'].dropna().iloc[-1] if not df['Temperature'].dropna().empty else 0
latest_vib = df['Vibration'].dropna().iloc[-1] if not df['Vibration'].dropna().empty else 0
latest_curr = df['Current'].dropna().iloc[-1] if not df['Current'].dropna().empty else 0

col1.metric("🌡️ Temperature (°C)", f"{latest_temp:.1f}", delta=None)
col2.metric("📳 Vibration (mm/s)", f"{latest_vib:.2f}", delta=None)
col3.metric("⚡ Current (A)", f"{latest_curr:.1f}", delta=None)

st.subheader("📈 Telemetry Trends")
chart_col1, chart_col2 = st.columns(2)
temp_df = df.dropna(subset=['Temperature'])
vib_df = df.dropna(subset=['Vibration'])

if not temp_df.empty:
    chart_col1.line_chart(temp_df.set_index('Timestamp')[['Temperature']], color="#FF4B4B")
if not vib_df.empty:
    chart_col2.line_chart(vib_df.set_index('Timestamp')[['Vibration']], color="#00D4FF")

st.subheader("🤖 AI Anomaly Alerts")
if st.session_state['alerts']:
    for alert in reversed(st.session_state['alerts'][-10:]):
        if "CRITICAL" in alert or "HIGH" in alert:
            st.error(alert)
        elif "AI_PREDICTIVE" in alert:
            st.warning(alert)
        else:
            st.info(alert)
else:
    st.success("✅ System Operating Normally - No Anomalies Detected")

time.sleep(0.5)
st.rerun()
