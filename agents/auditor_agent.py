from flask import Flask, request, jsonify
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo, AccountTx
import os, json

app = Flask(__name__)

XRPL_RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234")
client = JsonRpcClient(XRPL_RPC_URL)

@app.route("/")
def home():
    return jsonify({"status": "Auditor Agent online ✅"})

@app.route("/snapshot/<address>")
def snapshot(address):
    try:
        # Account info
        info = client.request(AccountInfo(account=address, ledger_index="validated"))
        balance = info.result["account_data"]["Balance"]

        # Last few transactions
        txs = client.request(AccountTx(account=address, limit=5))
        return jsonify({
            "status": "ok",
            "balance_drops": balance,
            "recent_txs": txs.result.get("transactions", [])
        })
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)

