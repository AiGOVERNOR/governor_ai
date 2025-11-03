import requests, json
from dotenv import load_dotenv
import os

load_dotenv()

AGENTS = {
    "validator": "http://127.0.0.1:5001",
    "auditor":   "http://127.0.0.1:5002"
}

def call_agent(agent, endpoint, payload=None):
    url = f"{AGENTS[agent]}{endpoint}"
    try:
        if payload:
            r = requests.post(url, json=payload, timeout=10)
        else:
            r = requests.get(url, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    print("Governor online 🧭")
    print("Commands:")
    print("  ledger        → latest XRPL ledger info")
    print("  snapshot      → wallet balance + txs")
    print("  exit          → quit\n")

    with open("wallets/test_wallet.json") as f:
        address = json.load(f)["address"]

    while True:
        cmd = input("> ").strip().lower()
        if cmd == "exit":
            break
        elif cmd == "ledger":
            print(json.dumps(call_agent("validator", "/ledger"), indent=2))
        elif cmd == "snapshot":
            print(json.dumps(call_agent("auditor", f"/snapshot/{address}"), indent=2))
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()
