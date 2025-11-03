# ~/governor_ai/agents/arbitrage_monitor.py
"""
Arbitrage Monitor
- Reads arbitrage.log produced by arbitrage_agent.py.
- Calculates simulated P&L (profit/loss) and strategy performance.
- Outputs real-time metrics and saves summary to monitor_report.json.
"""

import os
import json
import re
import time
from datetime import datetime, timezone

LOG_PATH = os.getenv("ARB_LOG_PATH", "./logs/arbitrage.log")
REPORT_PATH = os.getenv("ARB_REPORT_PATH", "./logs/monitor_report.json")
POLL_INTERVAL = float(os.getenv("ARB_MONITOR_INTERVAL", "30.0"))

# Regex to capture simulated trades from arbitrage_agent.py
BUY_PATTERN = re.compile(r"\[Arb\]\[SIM\] BUY (\d+\.\d+) XRP @ (\d+\.\d+)")
SELL_PATTERN = re.compile(r"\[Arb\]\[SIM\] SELL (\d+\.\d+) XRP @ (\d+\.\d+)")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def parse_trades(log_path):
    """Parse simulated trades and compute round-trip profits."""
    trades = []
    if not os.path.exists(log_path):
        return trades
    with open(log_path, "r") as f:
        lines = f.readlines()
    current = {}
    for line in lines:
        buy_match = BUY_PATTERN.search(line)
        sell_match = SELL_PATTERN.search(line)
        if buy_match:
            qty, price = map(float, buy_match.groups())
            current = {"side": "buy", "qty": qty, "price": price, "time": line[:26]}
        elif sell_match and current:
            qty, price = map(float, sell_match.groups())
            pnl = (price - current["price"]) * qty
            trades.append({
                "buy_price": current["price"],
                "sell_price": price,
                "qty": qty,
                "profit": pnl,
                "timestamp": line[:26]
            })
            current = {}
    return trades

def summarize(trades):
    """Summarize total profit, average profit per trade, success rate."""
    total_profit = sum(t["profit"] for t in trades)
    profitable = [t for t in trades if t["profit"] > 0]
    win_rate = (len(profitable) / len(trades) * 100) if trades else 0
    avg_profit = total_profit / len(trades) if trades else 0
    return {
        "total_trades": len(trades),
        "total_profit": total_profit,
        "average_profit": avg_profit,
        "win_rate": win_rate,
        "last_updated": now_iso()
    }

def monitor_loop():
    print(f"[Monitor] Watching {LOG_PATH} ...")
    last_report = {}
    while True:
        try:
            trades = parse_trades(LOG_PATH)
            summary = summarize(trades)
            if summary != last_report:
                with open(REPORT_PATH, "w") as f:
                    json.dump(summary, f, indent=2)
                print(f"[Monitor] {now_iso()} | Trades={summary['total_trades']} "
                      f"Profit={summary['total_profit']:.6f} XRP | WinRate={summary['win_rate']:.1f}%")
                last_report = summary
        except Exception as e:
            print(f"[Monitor] Error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    monitor_loop()
