import paho.mqtt.client as mqtt
import config
import json
import time

class FaultInjector:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
        self.client.loop_start()

    def inject_fault(self, fault_type):
        print(f"\n💥 Injecting Fault: {fault_type}")
        if fault_type == '1':
            print(">> Simulating Motor Overheating...")
            for i in range(10):
                self.client.publish(config.TOPIC_TEMP, json.dumps({"value": 50 + (i * 1.5), "ts": int(time.time())}))
                time.sleep(0.5)
        elif fault_type == '2':
            print(">> Simulating Mechanical Bearing Failure...")
            for _ in range(5):
                self.client.publish(config.TOPIC_VIBRATION, json.dumps({"value": 15.0, "ts": int(time.time())}))
                time.sleep(0.5)
        elif fault_type == '3':
            print(">> Simulating Electrical Surge...")
            self.client.publish(config.TOPIC_CURRENT, json.dumps({"value": 25.0, "ts": int(time.time())}))
        print(">> Fault Injection Complete.")

if __name__ == "__main__":
    injector = FaultInjector()
    print("=== SMART FAULT INJECTOR ===")
    print("1. Equipment Degradation (Temp Rise)")
    print("2. Mechanical Failure (Vibration Spike)")
    print("3. Electrical Surge (Current Spike)")
    choice = input("Select Fault [1-3]: ")
    injector.inject_fault(choice)
