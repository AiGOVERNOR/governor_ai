# ~/governor_ai/modules/intel.py
import json
import os
from datetime import datetime, timezone

class AIStrategy:
    """
    Governor AI intelligence core (placeholder).
    Persists state and logs a heartbeat each cycle.
    """

    def __init__(self, state_path="./.state"):
        self.state_path = state_path
        self.state = self._load_state()

    def _load_state(self):
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path, "r") as f:
                raw = f.read().strip()
                return json.loads(raw) if raw else {}
        except Exception as e:
            print(f"[AIStrategy] Failed to load state: {e}")
            return {}

    def save_state(self):
        try:
            with open(self.state_path, "w") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"[AIStrategy] Failed to save state: {e}")

    def run_strategy(self, wallet, receipts):
        try:
            ts = datetime.now(timezone.utc).isoformat()
            addr = wallet.address
            bal = wallet.get_balance()
            bal_msg = "unavailable" if bal is None else f"{bal:.6f} XRP"
            receipts.log(f"AI strategy heartbeat at {ts} for wallet {addr} | Balance: {bal_msg}")
            self.state["last_run"] = ts
            self.state["last_balance"] = bal
            self.save_state()
        except Exception as e:
            print(f"[AIStrategy] Error in run_strategy: {e}")
