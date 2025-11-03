#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Trader Agent (XRPL Testnet) — Flask microservice
Endpoints:
  GET  /               -> health check
  GET  /balance        -> {"address","xrp","drops"}
  POST /send           -> {"destination","amount_xrp", "memo"?} -> submits XRPL Payment

Env (.env optional):
  XRPL_ENDPOINT=https://s.altnet.rippletest.net:51234/
  WALLET_JSON=wallets/test_wallet.json
  HOST=0.0.0.0
  PORT=5003
"""

import os
import json
from decimal import Decimal
from flask import Flask, request, jsonify
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; ignore if not installed
    pass

from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment, Memo
from xrpl.transaction import autofill_and_sign, submit_and_wait

# ---------------------------
# Config
# ---------------------------
XRPL_ENDPOINT = os.getenv("XRPL_ENDPOINT", "https://s.altnet.rippletest.net:51234/")
WALLET_JSON = os.getenv("WALLET_JSON", "wallets/test_wallet.json")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5003"))

app = Flask("trader_agent")

# ---------------------------
# Utilities
# ---------------------------

def load_wallet(path: str) -> Wallet:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Wallet file not found: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    seed = data.get("seed")
    if not seed:
        raise KeyError("Wallet JSON must include 'seed'")
    # classicAddress is optional; Wallet can derive from seed
    return Wallet.from_seed(seed)

def get_client() -> JsonRpcClient:
    return JsonRpcClient(XRPL_ENDPOINT)

def get_balance_xrp(address: str) -> Decimal:
    client = get_client()
    req = AccountInfo(account=address, ledger_index="validated", strict=True)
    result = client.request(req).result
    drops = int(result["account_data"]["Balance"])
    return Decimal(drops) / Decimal(1_000_000)

def memo_to_hex(text: str) -> str:
    # XRPL memos must be hex-encoded
    return text.encode("utf-8").hex()

# ---------------------------
# Routes
# ---------------------------

@app.get("/")
def root():
    return jsonify({"status": "Trader Agent online ✅"})

@app.get("/balance")
def balance():
    try:
        wallet = load_wallet(WALLET_JSON)
        xrp = get_balance_xrp(wallet.classic_address)
        return jsonify({
            "address": wallet.classic_address,
            "xrp": float(xrp),
            "drops": int(xrp * Decimal(1_000_000))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.post("/send")
def send_payment():
    """
    JSON body:
      {
        "destination": "r.............",
        "amount_xrp": 1.25,
        "memo": "optional text"
      }
    """
    try:
        payload = request.get_json(force=True)
        dest = payload.get("destination")
        amt = payload.get("amount_xrp")
        memo_text = payload.get("memo")

        if not dest or amt is None:
            return jsonify({"error": "Fields 'destination' and 'amount_xrp' are required"}), 400

        amount_drops = int(Decimal(str(amt)) * Decimal(1_000_000))
        if amount_drops <= 0:
            return jsonify({"error": "amount_xrp must be > 0"}), 400

        wallet = load_wallet(WALLET_JSON)
        client = get_client()

        tx_kwargs = dict(
            account=wallet.classic_address,
            destination=dest,
            amount=str(amount_drops),
        )

        # Optional memo
        if memo_text:
            tx_kwargs["memos"] = [Memo(memo_data=memo_to_hex(memo_text))]

        payment = Payment(**tx_kwargs)

        # New xrpl-py flow: autofill -> sign -> submit_and_wait
        signed = autofill_and_sign(payment, wallet, client)
        submission = submit_and_wait(signed, client)

        # Extract a friendly hash if present
        tx_hash = submission.result.get("hash") or submission.result.get("tx_json", {}).get("hash")

        return jsonify({
            "status": "sent",
            "tx_hash": tx_hash,
            "destination": dest,
            "amount_xrp": float(Decimal(amount_drops) / Decimal(1_000_000))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------------------
# Entrypoint
# ---------------------------

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
