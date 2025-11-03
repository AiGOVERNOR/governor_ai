# ~/governor_ai/agents/agent_hub.py
"""
Agent Hub — a tiny control plane API for Governor sub-agents.
Endpoints:
  GET  /status
  POST /start/arbitrage
  POST /stop/arbitrage
  POST /start/monitor
  POST /stop/monitor
  POST /restart/all
"""

import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from process_utils import start_process, stop_process, is_running, read_pid

# Load .env from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

app = Flask(__name__)

# Agent names and commands
AGENTS = {
    "arbitrage": ["python", os.path.join(PROJECT_ROOT, "agents", "arbitrage_agent.py")],
    "monitor":   ["python", os.path.join(PROJECT_ROOT, "agents", "arbitrage_monitor.py")],
}

def agent_status(name: str):
    return {
        "running": is_running(name),
        "pid": read_pid(name),
    }

@app.get("/status")
def status():
    return jsonify({
        "arbitrage": agent_status("arbitrage"),
        "monitor": agent_status("monitor"),
    })

@app.post("/start/arbitrage")
def start_arbitrage():
    pid = start_process("arbitrage", AGENTS["arbitrage"])
    return jsonify({"started": True, "pid": pid})

@app.post("/stop/arbitrage")
def stop_arbitrage():
    ok = stop_process("arbitrage")
    return jsonify({"stopped": ok})

@app.post("/start/monitor")
def start_monitor():
    pid = start_process("monitor", AGENTS["monitor"])
    return jsonify({"started": True, "pid": pid})

@app.post("/stop/monitor")
def stop_monitor():
    ok = stop_process("monitor")
    return jsonify({"stopped": ok})

@app.post("/restart/all")
def restart_all():
    stop_process("arbitrage")
    stop_process("monitor")
    pid_a = start_process("arbitrage", AGENTS["arbitrage"])
    pid_m = start_process("monitor", AGENTS["monitor"])
    return jsonify({"restarted": True, "arbitrage_pid": pid_a, "monitor_pid": pid_m})

if __name__ == "__main__":
    # Default to 5060 so it doesn't conflict with Governor (5050)
    port = int(os.getenv("HUB_PORT", "5060"))
    app.run(host="0.0.0.0", port=port)
