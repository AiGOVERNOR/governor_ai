#!/data/data/com.termux/files/usr/bin/bash
# ───────────────────────────────────────────────
#  Governor AI — Health Daemon (Persistent Monitor)
#  Keeps Flask and AI core alive even across Termux sessions
# ───────────────────────────────────────────────

APP_DIR="$HOME/governor_ai"
LOG_DIR="$APP_DIR/logs"
PYTHON_BIN="$(which python)"
PORT=5050

mkdir -p "$LOG_DIR"
echo "[$(date)] Governor Health Daemon started." >> "$LOG_DIR/healthd.log"

restart_governor() {
  echo "[$(date)] Restarting Governor AI..." >> "$LOG_DIR/healthd.log"
  pkill -f "python.*governor.py" 2>/dev/null
  sleep 2
  cd "$APP_DIR"
  nohup "$PYTHON_BIN" governor.py >> "$LOG_DIR/governor.out.log" 2>> "$LOG_DIR/governor.err.log" &
  echo "[$(date)] Relaunch complete." >> "$LOG_DIR/healthd.log"
}

while true; do
  sleep 60
  PID=$(pgrep -f "python.*governor.py")

  if [ -z "$PID" ]; then
    echo "[$(date)] Process missing — trigger restart." >> "$LOG_DIR/healthd.log"
    restart_governor
    continue
  fi

  if command -v curl >/dev/null 2>&1; then
    curl -s http://127.0.0.1:$PORT/health >/dev/null 2>&1
    if [ $? -ne 0 ]; then
      echo "[$(date)] Healthcheck failed — restarting Governor AI." >> "$LOG_DIR/healthd.log"
      restart_governor
    else
      echo "[$(date)] Healthcheck OK (PID $PID)" >> "$LOG_DIR/healthd.log"
    fi
  else
    echo "[$(date)] WARNING: curl not installed — skipping healthcheck." >> "$LOG_DIR/healthd.log"
  fi
done
