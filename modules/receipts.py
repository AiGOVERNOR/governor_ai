# ~/governor_ai/modules/receipts.py
import os
from datetime import datetime, timezone

class ReceiptHandler:
    """
    Timestamped logger to file + stdout.
    """

    def __init__(self, log_path="./logs/receipts.log"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log(self, message: str):
        ts = datetime.now(timezone.utc).isoformat()
        line = f"[{ts}] {message}\n"
        with open(self.log_path, "a") as f:
            f.write(line)
        print(f"[ReceiptHandler] {message}")
