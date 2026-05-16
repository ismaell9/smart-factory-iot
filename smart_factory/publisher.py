import json
import time
import random
import paho.mqtt.client as mqtt

import config

TOPIC_SENSORS = "factory/sensors/all"
TOPIC_ALERTS  = "factory/sensors/alerts"
TOPIC_CMD     = "factory/sensors/cmd"

SENSOR_TYPES = [
    ("Temp", 45.0, "A"),
    ("Vibration", 2.5, "A"),
    ("Current", 12.0, "A"),
    ("Light", 500.0, "A"),
    ("Humidity", 45.0, "B"),
    ("Ultrasonic", 2.0, "B"),
    ("IR", 1.0, "B"),
    ("Pressure", 101.3, "C"),
    ("Smoke", 10.0, "C"),
    ("Fire", 5.0, "C"),
]
PREFIXES = [t[0][0] for t in SENSOR_TYPES]
ANOMALY_RATIO = 1.3


class SensorSim:
    def __init__(self):
        self.sensors = []
        for t_idx, (t_name, t_base, t_zone) in enumerate(SENSOR_TYPES):
            for i in range(1, 6):
                sid = f"{PREFIXES[t_idx]}{i}"
                self.sensors.append({
                    "id": sid,
                    "type": t_name,
                    "zone": t_zone,
                    "base": t_base,
                    "cur": t_base,
                    "override_val": None,
                    "override_until": 0,
                    "status": "NORMAL",
                    "alerted": False,
                })
        print(f"Init {len(self.sensors)} sensors")

    def gauss(self):
        s = sum(random.uniform(-1, 1) for _ in range(12))
        return s / 12.0

    def update(self):
        now = time.monotonic()
        for s in self.sensors:
            if s["override_until"] > 0 and now < s["override_until"]:
                s["cur"] = s["override_val"]
                s["status"] = "OVERRIDE"
                continue
            s["override_until"] = 0
            s["status"] = "NORMAL"
            s["alerted"] = False
            noise = self.gauss() * (s["base"] * 0.02)
            s["cur"] = round(max(0, s["base"] + noise), 2)
            if s["base"] > 0 and (s["cur"] / s["base"]) > ANOMALY_RATIO:
                s["status"] = "ANOMALY"

    def get_all(self):
        return [{"id": s["id"], "type": s["type"], "zone": s["zone"],
                 "value": s["cur"], "base": s["base"], "status": s["status"]}
                for s in self.sensors]

    def get_alerts(self):
        alerts = []
        for s in self.sensors:
            if s["status"] == "ANOMALY" and not s["alerted"]:
                s["alerted"] = True
                alerts.append({
                    "id": s["id"], "type": s["type"], "zone": s["zone"],
                    "value": s["cur"], "base": s["base"],
                    "ratio": round(s["cur"] / s["base"], 2),
                    "severity": "HIGH", "ts": int(time.time() * 1000),
                })
        return alerts

    def handle_cmd(self, msg):
        print(f"CMD: {msg}")
        now = time.monotonic()
        if msg == "FAULT_RANDOM_3":
            chosen = random.sample(self.sensors, 3)
            for s in chosen:
                s["override_val"] = s["base"] * 1.6
                s["override_until"] = now + 15
                s["cur"] = s["override_val"]
                s["status"] = "OVERRIDE"
            print(f"  Fault {[s['id'] for s in chosen]}")
        elif msg == "FAULT_ALL":
            for s in self.sensors:
                s["override_val"] = s["base"] * 2.0
                s["override_until"] = now + 15
                s["cur"] = s["override_val"]
                s["status"] = "OVERRIDE"
            print("  Fault ALL")
        elif msg.startswith("OVERRIDE:"):
            parts = msg[9:].split(":")
            if len(parts) == 3:
                sid, val, dur = parts[0], float(parts[1]), float(parts[2])
                for s in self.sensors:
                    if s["id"] == sid:
                        s["override_val"] = val
                        s["override_until"] = now + dur
                        s["cur"] = val
                        s["status"] = "OVERRIDE"
                        print(f"  Override {sid} = {val} for {dur}s")
                        break
        elif msg == "CLEAR":
            for s in self.sensors:
                s["override_until"] = 0
                s["status"] = "NORMAL"
                s["alerted"] = False
            print("  Clear all")


def on_connect(client, userdata, flags, rc, prop):
    print(f"MQTT connected (rc={rc})")
    client.subscribe(TOPIC_CMD)


def on_message(client, userdata, msg):
    sim = userdata["sim"]
    sim.handle_cmd(msg.payload.decode())


def main():
    sim = SensorSim()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.user_data_set({"sim": sim})
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
    client.loop_start()

    print(f"Publishing to {config.MQTT_BROKER}:{config.MQTT_PORT}")
    print(f"  Sensors -> {TOPIC_SENSORS}")
    print(f"  Alerts  -> {TOPIC_ALERTS}")
    print(f"  Cmds    -> {TOPIC_CMD}")

    try:
        while True:
            sim.update()
            all_data = sim.get_all()
            client.publish(TOPIC_SENSORS, json.dumps(all_data))
            for alert in sim.get_alerts():
                client.publish(TOPIC_ALERTS, json.dumps(alert))
                print(f"Alert: {alert['id']} ({alert['value']}/{alert['base']})")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
