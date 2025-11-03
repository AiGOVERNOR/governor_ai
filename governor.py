import os, json, time, hashlib
from pathlib import Path
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# === Local modules ===
from modules.wallet import WalletService
from modules.intel import AIStrategy
from modules.receipts import publish_receipt_onledger

load_dotenv()

PORT          = int(os.environ.get("PORT", "5050"))
XRPL_RPC_URL  = os.environ.get("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234/")
TRADER_SEED   = os.environ.get("TRADER_SEED", "")
SERVICE_ADDR  = os.environ.get("SERVICE_ADDRESS", "")
API_KEY       = os.environ.get("API_KEY", "localdev")

app = Flask("governor")

# Boot services
wallet = WalletService(xrpl_url=XRPL_RPC_URL, seed=TRADER_SEED)
ai     = AIStrategy(state_path=".state/ai_state.json")

def auth_guard(req):
    token = req.headers.get("X-API-Key")
    return (API_KEY and token == API_KEY) or (API_KEY == "localdev")

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "node_connection": XRPL_RPC_URL,
        "ai_core": "idle" if ai.empty() else "ready"
    })

@app.route("/wallet", methods=["GET"])
def wallet_status():
    try:
        info = wallet.snapshot()
        return jsonify({"status":"ok", **info})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500

@app.route("/price", methods=["GET"])
def price():
    # Optional: simple passthrough to feed the AI learner
    sym = request.args.get("symbol", "XRP")
    src = ai.fetch_price(symbol=sym)
    return jsonify(src)

@app.route("/ai/learn", methods=["POST"])
def ai_learn():
    if not auth_guard(request): return jsonify({"status":"forbidden"}), 403
    data = request.get_json(silent=True) or {}
    price = data.get("price")
    ts    = data.get("ts", time.time())
    if price is None: return jsonify({"status":"error","message":"price required"}), 400
    ai.ingest(float(price), ts)
    return jsonify({"status":"ok","buffer_len":ai.buffer_len()})

@app.route("/ai/strategy", methods=["POST"])
def ai_strategy():
    """
    Body:
    {
      "market_signal": "bullish|bearish|neutral" (optional),
      "risk_aversion": 0..1 (default 0.5)
    }
    """
    try:
        body = request.get_json(silent=True) or {}
        market_hint  = body.get("market_signal")
        risk_averse  = float(body.get("risk_aversion", 0.5))
        decision = ai.decide(market_hint=market_hint, risk_aversion=risk_averse)

        # Prepare ADR (audit receipt) materials even if user doesn’t publish
        receipt = {
            "t": int(time.time()),
            "kind": "strategy_decision",
            "decision": decision["action"],
            "confidence": decision["confidence"],
            "sl": decision["risk"].get("stop"),
            "tp": decision["risk"].get("take"),
            "signal": decision["explain"]["signal"],
        }
        digest = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
        decision["adr_digest"] = digest
        decision["adr_hint"]   = "POST /receipts/attest to write this decision hash on-ledger"

        return jsonify({"status":"ok","ai_decision":decision})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500

@app.route("/receipts/attest", methods=["POST"])
def receipts_attest():
    """
    Body:
    {
      "digest": "<sha256 hex>",  # required
      "tag": "ADR:v1",           # optional memo tag
      "fee_drops": 12            # optional fee, default auto
    }
    """
    if not auth_guard(request): return jsonify({"status":"forbidden"}), 403
    body = request.get_json(silent=True) or {}
    digest = body.get("digest")
    tag    = body.get("tag", "ADR:v1")
    if not digest: return jsonify({"status":"error","message":"digest required"}), 400

    try:
        tx_hash = publish_receipt_onledger(wallet, digest=digest, tag=tag)
        return jsonify({"status":"ok","tx_hash":tx_hash})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)}), 500

# --- Convenience: create minimal dirs on first run ---
Path(".state").mkdir(exist_ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
