from sensor_sim import SensorSimulator
from mqtt_publisher import SmartFactoryPublisher

if __name__ == "__main__":
    print("Initializing Smart Factory IoT Node...")
    simulator = SensorSimulator()
    publisher = SmartFactoryPublisher(simulator)
    print("Publishing sensor data to broker.hivemq.com...")
    publisher.run_loop()
