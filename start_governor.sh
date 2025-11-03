chmod +x ~/.termux/boot/start_governor.sh
pkg install lsof curl -y
~/.termux/boot/start_governor.shchmod +x ~/.termux/boot/start_governor.sh
pkg install lsof -y                     # make sure lsof is available#!/data/data/com.termux/files/usr/bin/bash
# ───────────────────────────────────────────────
#  Governor AI Auto-Start Script (Termux Boot)
#  Author: The Governor AI System
#  Purpose: Ensure clean startup, port-free Flask server, and logging
# ───────────────────────────────────────────────

LOG_DIR="$HOME/governor_ai/logs"
APP_DIR="$HOME/governor_ai"
PYTHON_BIN="$(which python)"
PORT=5050

mkdir -p "$LOG_DIR"

echo "[$(date)] Starting Governor AI..." >> "$LOG_DIR/startup.log"

# Kill any old Governor AI processes
pkill -f "python.*governor.py" 2>/dev/null
sleep 1

# Verify port 5050 is free using lsof (Termux compatible)
if command -v lsof >/dev/null 2>&1; then
  PID=$(lsof -ti tcp:$PORT)
  if [ -n "$PID" ]; then
    echo "[$(date)] Port $PORT still in use by PID $PID — killing..." >> "$LOG_DIR/startup.log"
    kill -9 "$PID" 2>/dev/null
    echo "[$(date)] Port $PORT freed successfully." >> "$LOG_DIR/startup.log"
  fi
else
  echo "[$(date)] WARNING: lsof not installed, skipping port check." >> "$LOG_DIR/startup.log"
fi

# Activate virtual environment if exists
if [ -f "$APP_DIR/venv/bin/activate" ]; then
  source "$APP_DIR/venv/bin/activate"
fi

# Launch Governor AI Core
cd "$APP_DIR"
nohup "$PYTHON_BIN" governor.py >> "$LOG_DIR/governor.out.log" 2>> "$LOG_DIR/governor.err.log" &

# Launch Watchdog if available
if [ -f "$HOME/.governor_watchdog.sh" ]; then
  nohup bash "$HOME/.governor_watchdog.sh" >> "$LOG_DIR/watchdog.log" 2>&1 &
fi

# Launch auto-update if available
if [ -f "$HOME/.auto_update_governor.sh" ]; then
  echo "[$(date)] Triggering update check..." >> "$LOG_DIR/startup.log"
  bash "$HOME/.auto_update_governor.sh" >> "$LOG_DIR/update.log" 2>&1 &
fi

echo "[$(date)] Governor AI started successfully on port $PORT" >> "$LOG_DIR/startup.log"
