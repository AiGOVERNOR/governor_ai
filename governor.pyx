import os
from flask import Flask, jsonify, request
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo

# ==========================================================
# GOVERNOR AI CORE
# ==========================================================

app = Flask(__name__)

# Default XRPL Testnet Node
XRPL_RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234")
TRADER_SEED = os.getenv("TRADER_SEED", "snYourTestnetSeedHere")
API_KEY = os.getenv("API_KEY", "governor_demo_key")

# Connect to XRPL Node
client = JsonRpcClient(XRPL_RPC_URL)

# ==========================================================
# ROOT + HEALTH
# ==========================================================

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Governor AI Superintelligent Trader Online",
        "version": "2.0",
        "docs": {
            "/wallet": "Get wallet address + balance",
            "/charge": "Charge for a Governor AI service",
            "/health": "Check system health"
        }
    })

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "system": "XRPL + Flask operational",
        "ai_mode": "learning"
    })

# ==========================================================
# WALLET STATUS
# ==========================================================

@app.route("/wallet", methods=["GET"])
def wallet_info():
    """Return wallet balance and details"""
    try:
        wallet = Wallet(seed=TRADER_SEED, sequence=0)

        # Prepare Account Info request
        req = AccountInfo(
            account=wallet.classic_address,
            ledger_index="validated",
            strict=True
        )

        # Send request
        response = client.request(req)

        return jsonify({
            "status": "ok",
            "address": wallet.classic_address,
            "balance_drops": response.result["account_data"]["Balance"],
            "node": XRPL_RPC_URL
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# ==========================================================
# CHARGE FOR SERVICE (SIMULATED MICRO-TRANSACTION)
# ==========================================================

@app.route("/charge", methods=["POST"])
def charge_for_service():
    """Simulate billing a user for AI-driven transaction"""
    data = request.get_json(force=True)
    user = data.get("user", "anonymous")
    service = data.get("service", "ai_analysis")
    amount = data.get("amount", "0.5")  # XRP default

    # Simulated transaction log
    return jsonify({
        "status": "processing",
        "user": user,
        "service": service,
        "amount_xrp": amount,
        "note": "Governor AI agent recorded billing request",
        "tx_status": "queued"
    })

# ==========================================================
# FUTURE EXTENSION: AI STRATEGY AGENT
# ==========================================================

@app.route("/ai/strategy", methods=["POST"])
def ai_strategy():
    """Analyze market input and return AI-driven action (stub)"""
    data = request.get_json(force=True)
    signal = data.get("market_signal", "neutral")

    if signal == "bullish":
        decision = "Governor AI recommends BUY"
    elif signal == "bearish":
        decision = "Governor AI recommends SELL"
    else:
        decision = "Governor AI recommends HOLD"

    return jsonify({
        "ai_decision": decision,
        "confidence": "0.91",
        "strategy_mode": "adaptive",
        "note": "Future module will connect to real market data + LLM"
    })

# ==========================================================
# MAIN EXECUTION
# ==========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
