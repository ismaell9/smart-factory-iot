import json
import queue
import threading

import paho.mqtt.client as mqtt
import config

TOPIC_SENSORS = "factory/sensors/all"
TOPIC_ALERTS  = "factory/sensors/alerts"


class MQTTReceiver:
    def __init__(self):
        self.sensor_queue = queue.Queue()
        self.alert_queue = queue.Queue()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._running = False

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"[MQTT] Connected (rc={reason_code})")
        client.subscribe(TOPIC_SENSORS)
        client.subscribe(TOPIC_ALERTS)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if msg.topic == TOPIC_SENSORS:
                self.sensor_queue.put(payload)
            elif msg.topic == TOPIC_ALERTS:
                self.alert_queue.put(payload)
        except Exception as e:
            print(f"[MQTT] Parse error: {e}")

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self.client.connect(
                config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE
            )
            t = threading.Thread(target=self._run, daemon=True)
            t.start()
        except Exception as e:
            print(f"[MQTT] Connection error: {e}")

    def _run(self):
        self.client.loop_forever()

    def get_latest_sensors(self):
        latest = None
        while not self.sensor_queue.empty():
            try:
                latest = self.sensor_queue.get_nowait()
            except queue.Empty:
                break
        if latest is not None:
            self._last_sensors = latest
        return self._last_sensors if hasattr(self, '_last_sensors') else None

    def get_pending_alerts(self):
        alerts = []
        while not self.alert_queue.empty():
            try:
                alerts.append(self.alert_queue.get_nowait())
            except queue.Empty:
                break
        return alerts

    def stop(self):
        self._running = False
        self.client.disconnect()
