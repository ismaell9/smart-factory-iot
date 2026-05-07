import paho.mqtt.client as mqtt
import config
import json
import numpy as np
from collections import deque
import time

class AIDetector:
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.history = deque(maxlen=window_size)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
        self.threshold = 2.5

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print("AI Detector: Connected. Subscribing to sensors...")
        self.client.subscribe(config.TOPIC_TEMP)
        self.client.subscribe(config.TOPIC_VIBRATION)
        self.client.subscribe(config.TOPIC_CURRENT)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            data = {"topic": msg.topic, "value": payload["value"], "ts": payload["ts"]}
            self.history.append(data)
            self.analyze()
        except Exception:
            pass

    def analyze(self):
        if len(self.history) < self.window_size:
            return
        recent_vibration = [d['value'] for d in list(self.history) if 'vibration' in d['topic']]
        recent_temp = [d['value'] for d in list(self.history) if 'temperature' in d['topic']]

        if len(recent_vibration) > 10:
            self.check_anomaly("Vibration", recent_vibration)
        if len(recent_temp) > 10:
            self.check_anomaly("Temperature", recent_temp)

    def check_anomaly(self, sensor_name, values):
        mean = np.mean(values)
        std = np.std(values)
        if std == 0: return
        
        current_val = values[-1]
        z_score = abs((current_val - mean) / std)
        
        if z_score > self.threshold or current_val > (mean + std * 1.5):
            alert = {
                "type": "AI_PREDICTIVE", "sensor": sensor_name,
                "severity": "HIGH" if z_score > 3 else "MEDIUM",
                "z_score": round(z_score, 2), "value": current_val,
                "expected_mean": round(mean, 2), "timestamp": int(time.time())
            }
            self.client.publish(config.TOPIC_ALERT, json.dumps(alert))
            print(f"AI ALERT: {sensor_name} anomaly detected! Z-Score: {z_score:.2f}")

    def run(self):
        self.client.loop_forever()

if __name__ == "__main__":
    AIDetector().run()
