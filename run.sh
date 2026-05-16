#!/usr/bin/env bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
SIM_BIN="$ROOT/simulation/simulator"
LOG="$ROOT/log"
DASH_CMD="$ROOT/.venv/bin/python -m streamlit run $ROOT/smart_factory/app.py --server.headless true"
mkdir -p "$LOG"

cleanup() {
    echo ""
    echo "=== Stopping ==="
    kill $SIM_PID $DASH_PID 2>/dev/null
    wait $SIM_PID $DASH_PID 2>/dev/null
    echo "Stopped"
    exit 0
}

stop_mqtt() {
    echo "[STOP] Sending STOP via MQTT..."
    python3 "$ROOT/simulation/stop_sim.py" 2>/dev/null
    sleep 2
}

kill_old() {
    ps aux | grep -E "[s]treamlit.*app\.py|[s]imulator" | awk '{print $2}' | xargs -r kill -9 2>/dev/null
    sleep 1
}

if [ "${1:-}" = "stop" ]; then stop_mqtt; kill_old; echo "Stopped"; exit 0; fi
trap cleanup INT TERM

echo "=== Smart Factory IoT - Launcher ==="
echo ""

# 1. Compile C++ simulator if needed
if [ ! -f "$SIM_BIN" ]; then
    echo "[BUILD] Compiling C++ simulator..."
    g++ -std=c++11 -o "$SIM_BIN" "$ROOT/simulation/simulator.cpp"
    echo "[BUILD] Done"
fi

# 2. Stop old instances
kill_old

# 3. Start C++ simulator
echo "[SIM] Starting C++ sensor simulator..."
stdbuf -oL "$SIM_BIN" > $LOG/sim.log 2>&1 &
SIM_PID=$!
echo "[SIM] PID $SIM_PID"

sleep 3
if grep -q "MQTT connected" $LOG/sim.log 2>/dev/null; then
    echo "[SIM] Connected to MQTT"
else
    echo "[SIM] Waiting for MQTT..."
fi

# 4. Start dashboard
echo "[DASH] Starting Streamlit dashboard..."
$DASH_CMD > $LOG/dash.log 2>&1 &
DASH_PID=$!
echo "[DASH] PID $DASH_PID"

sleep 4
echo ""

echo "=== READY ==="
grep -o "http://[^ ]*:[0-9]*" $LOG/dash.log 2>/dev/null | while read url; do
    echo "  $url"
done
echo ""
echo "Open the dashboard and click '📡 MQTT: OFF' -> ON"
echo ""
echo "  Live sim: tail -f $LOG/sim.log"
echo "  Stop:     $0 stop"
