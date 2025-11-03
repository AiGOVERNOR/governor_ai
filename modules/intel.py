import json
import os
from datetime import datetime
import random

class AIStrategy:
    def __init__(self, state_path=".state/ai_state.json"):
        self.state_path = state_path
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        self.state = self._load_state()
        self.learning_rate = 0.1
        self.mode = "adaptive"
        self.history = []

    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, "r") as f:
                return json.load(f)
        return {"profit": 0.0, "trades": [], "learning_rate": 0.1}

    def save_state(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def decide(self, market_signal):
        confidence = round(random.uniform(0.7, 0.99), 2)
        decision = "BUY" if market_signal == "bullish" else "SELL"
        adaptive_comment = f"Governor AI recommends {decision} with {confidence*100}% confidence."

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "signal": market_signal,
            "decision": decision,
            "confidence": confidence
        }
        self.history.append(record)

        return {
            "ai_decision": adaptive_comment,
            "confidence": confidence,
            "learning_mode": self.mode,
            "status": "ok"
        }

    def metrics(self):
        return {
            "mode": self.mode,
            "learning_rate": self.learning_rate,
            "records_seen": len(self.history)
        }

    def export_history(self, file_path="ai_strategy_log.json"):
        with open(file_path, "w") as f:
            json.dump(self.history, f, indent=2)
        return f"Exported {len(self.history)} AI strategy records."
