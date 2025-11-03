# ~/governor_ai/governor.py
import os
import time
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify
from dotenv import load_dotenv

import json
import urllib.request

# Load .env early
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from modules.wallet import WalletService
from modules.receipts import ReceiptHandler
from modules.intel import AIStrategy
# If you're already using arbitrage, re-enable these two lines later
# from modules.arbitrage import ArbitrageEngine

app = Flask(__name__)

wallet = None
receipts = None
ai_strategy = None
# arb = None

XRPL_RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234")
TRADER_SEED = os.getenv("TRADER_SEED")
XRPL_NETWORK = os.getenv("XRPL_NETWORK", "testnet")
AUTO_FAUCET = os.getenv("AUTO_FAUCET", "0") == "1"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.now(timezone.utc).isoformat()}), 200


def fund_testnet_if_needed(address: str):
    """
    Calls XRPL testnet faucet if AUTO_FAUCET=1 and balance is missing/zero.
    Safe on testnet; does nothing on mainnet.
    """
    if XRPL_NETWORK != "testnet" or not AUTO_FAUCET:
        return

    try:
        url = "https://faucet.altnet.rippletest.net/accounts"
        body = json.dumps({"destination": address}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        print(f"[Governor AI] Testnet faucet request OK for {address}: {data.get('account',{})}")
    except Exception as e:
        print(f"[Governor AI] Testnet faucet request failed: {e}")


def initialize_governor():
    global wallet, receipts, ai_strategy
    print("[Governor AI] Initializing core modules...")

    if not TRADER_SEED:
        raise RuntimeError("TRADER_SEED missing in .env file.")

    wallet = WalletService(xrpl_url=XRPL_RPC_URL, seed=TRADER_SEED)
    receipts = ReceiptHandler(log_path="./logs/receipts.log")
    ai_strategy = AIStrategy(state_path="./.state")

    # Auto-fund if needed (testnet only)
    bal = wallet.get_balance()
    if (bal is None or bal == 0.0) and XRPL_NETWORK == "testnet" and AUTO_FAUCET:
        print(f"[Governor AI] No balance detected. Attempting testnet funding for {wallet.address}...")
        fund_testnet_if_needed(wallet.address)
        # Give the network a moment, then re-check
        time.sleep(3)
        bal = wallet.get_balance()
        print(f"[Governor AI] Post-faucet balance: {bal}")

    print(f"[Governor AI] Wallet loaded: {wallet.address}")
    print("[Governor AI] Initialization complete.")

    # (Optional) Enable arbitrage later when you have a live IOU with liquidity
    # global arb
    # arb = ArbitrageEngine(
    #     rpc_url=XRPL_RPC_URL,
    #     quote_currency=os.getenv("QUOTE_CURRENCY"),
    #     quote_issuer=os.getenv("QUOTE_ISSUER"),
    #     min_spread_bps=int(os.getenv("ARB_MIN_SPREAD_BPS", "30")),
    #     max_slippage_bps=int(os.getenv("ARB_MAX_SLIPPAGE_BPS", "20")),
    #     dry_run=os.getenv("ARB_DRY_RUN", "1") == "1",
    # )
    # print(f"[Governor AI] Arbitrage engine ready (DRY_RUN={arb.dry_run})")


def ai_background_loop():
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            print(f"[Governor AI] Running background loop at {now}")
            ai_strategy.run_strategy(wallet, receipts)

            # If arbitrage wired and you have a liquid pair:
            # ref_price = None
            # arb.cycle(wallet, receipts, ref_price_xrp_in_quote=ref_price)

        except Exception as e:
            receipts.log(f"[Governor AI] Error in background loop: {e}")
        time.sleep(10)


if __name__ == "__main__":
    # Ensure state/log folders exist
    os.makedirs("./logs", exist_ok=True)
    if not os.path.exists("./.state"):
        with open("./.state", "w") as f:
            f.write("{}")

    initialize_governor()
    t = threading.Thread(target=ai_background_loop, daemon=True)
    t.start()
    print("[Governor AI] Flask server starting on port 5050...")
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")))
