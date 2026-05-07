import subprocess
import sys
import os
import time

def run_script(name, cmd):
    print(f"[START] Starting {name}...")
    return subprocess.Popen([sys.executable, cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)

if __name__ == "__main__":
    print("=== SMART FACTORY IoT ECOSYSTEM ===")
    print("Initializing all subsystems...")
    
    run_script("Sensor Simulator", "main.py")
    run_script("AI Anomaly Detector", "ai_anomaly_detector.py")
    
    print("\n[WAIT] Waiting for sensors to initialize...")
    time.sleep(3)
    
    run_script("Dashboard", "streamlit run dashboard.py --server.headless=true")
    
    print("\n[OK] All systems operational!")
    print("1. Check 'main.py' window for sensor data.")
    print("2. Check 'ai_anomaly_detector.py' window for AI alerts.")
    print("3. Dashboard will open in your browser shortly.")
    print("\n[TEST] To test faults, run: python fault_injector.py")
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
