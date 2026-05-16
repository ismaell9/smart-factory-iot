#!/usr/bin/env python3
"""Publish STOP command via MQTT to gracefully shut down the C++ simulator."""
import sys
import paho.mqtt.client as mqtt

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "factory/sensors/cmd"

def main():
    client = mqtt.Client()
    client.connect(BROKER, PORT, 10)
    client.publish(TOPIC, "STOP")
    print(f"Published STOP to {BROKER}{TOPIC}")
    client.disconnect()

if __name__ == "__main__":
    main()
