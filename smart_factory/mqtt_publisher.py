import paho.mqtt.client as mqtt
import config
import json
import time

class SmartFactoryPublisher:
    def __init__(self, simulator):
        self.simulator = simulator
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"Connected to MQTT Broker with result code: {reason_code}")

    def publish_sensors(self):
        try:
            data = self.simulator.get_all_data()
            self.client.publish(config.TOPIC_TEMP, payload=json.dumps({"value": data['temperature'], "ts": data['timestamp']}))
            self.client.publish(config.TOPIC_VIBRATION, payload=json.dumps({"value": data['vibration'], "ts": data['timestamp']}))
            self.client.publish(config.TOPIC_CURRENT, payload=json.dumps({"value": data['current'], "ts": data['timestamp']}))

            print(f"Published: {data}")
            
            if data['temperature'] > 55.0 or data['vibration'] > 6.0:
                alert = {"type": "CRITICAL", "reason": "Threshold Exceeded", "data": data}
                self.client.publish(config.TOPIC_ALERT, payload=json.dumps(alert))
                print(">> ALERT SENT <<")

        except Exception as e:
            print(f"Publish Error: {e}")

    def run_loop(self):
        try:
            while True:
                self.publish_sensors()
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping simulation...")
            self.client.loop_stop()
            self.client.disconnect()
