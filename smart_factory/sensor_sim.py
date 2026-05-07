import random
import time

class SensorSimulator:
    def __init__(self):
        self.base_temp = 45.0
        self.base_vibration = 2.5
        self.base_current = 12.0

    def get_temperature(self):
        noise = random.gauss(0, 1.0)
        if random.random() < 0.05:
            noise += random.uniform(5, 10)
        return round(self.base_temp + noise, 2)

    def get_vibration(self):
        noise = random.gauss(0, 0.2)
        if random.random() < 0.03:
            noise += random.uniform(2, 4)
        return round(max(0, self.base_vibration + noise), 2)

    def get_current(self):
        noise = random.gauss(0, 0.5)
        return round(max(0, self.base_current + noise), 2)

    def get_all_data(self):
        return {
            "temperature": self.get_temperature(),
            "vibration": self.get_vibration(),
            "current": self.get_current(),
            "timestamp": int(time.time())
        }
