from flask import Flask, jsonify
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import Ledger, AccountInfo
import os, json

app = Flask(__name__)

XRPL_RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234")
client = JsonRpcClient(XRPL_RPC_URL)

@app.route("/")
def home():
    return jsonify({"status": "Validator Agent online ✅"})

@app.route("/ledger")
def ledger_status():
    try:
        response = client.request(Ledger(ledger_index="validated"))
        return jsonify(response.result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/account/<address>")
def account_info(address):
    try:
        response = client.request(AccountInfo(account=address, ledger_index="validated"))
        return jsonify(response.result)
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
