# agents/trader_agent.py
import os
import time
from decimal import Decimal, ROUND_DOWN
from flask import Flask, request, jsonify, abort
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.requests import AccountInfo
from xrpl.models.transactions import Payment, Memo
from xrpl.utils import xrp_to_drops, drops_to_xrp
from xrpl.transaction import autofill, sign, submit_and_wait
from xrpl.account import does_account_exist

# ---------- Config ----------
RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234/")  # default testnet
SERVICE_ADDRESS = os.getenv("SERVICE_ADDRESS", "")          # (optional) your public revenue address
SERVICE_SEED = os.getenv("SERVICE_SEED", "")                # (optional) seed for fee-collection wallet (use only if the service wallet sends)
TRADER_SEED = os.getenv("TRADER_SEED")                      # seed of the wallet that actually pays
API_KEY = os.getenv("API_KEY", "")                          # simple header auth
FEE_BPS = int(os.getenv("FEE_BPS", "50"))                   # basis points (50 = 0.50%)
MAX_XRP = Decimal(os.getenv("MAX_XRP_PER_SEND", "250"))     # guardrail

if not TRADER_SEED:
    raise RuntimeError("TRADER_SEED is required")

client = JsonRpcClient(RPC_URL)
TRADER = Wallet(seed=TRADER_SEED, sequence=0)

app = Flask(__name__)

# ---------- tiny auth ----------
def check_auth():
    if not API_KEY:
        return True  # no api key set -> open (for your own use)
    sent = request.headers.get("X-API-Key", "")
    return sent == API_KEY

def require_auth():
    if not check_auth():
        abort(401)

# ---------- helpers ----------
def service_fee_xrp(amount_xrp: Decimal) -> Decimal:
    # Round fee DOWN to avoid overcharging by a drop due to rounding
    fee = (amount_xrp * Decimal(FEE_BPS) / Decimal(10_000)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
    return fee

def ensure_account(address: str) -> bool:
    try:
        return does_account_exist(address, client)
    except Exception:
        return False

def xrpl_balance(address: str):
    req = AccountInfo(account=address, ledger_index="validated", strict=True)
    resp = client.request(req)
    if resp.is_successful():
        return Decimal(drops_to_xrp(resp.result["account_data"]["Balance"]))
    return Decimal("0")

# ---------- endpoints ----------
@app.route("/")
def root():
    return jsonify({"status": "ok", "message": "Governor AI Trader Online"})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

@app.route("/wallet/balance")
def wallet_balance():
    require_auth()
    addr = TRADER.classic_address
    bal = xrpl_balance(addr)
    return jsonify({"address": addr, "xrp": float(bal)})

@app.route("/quote", methods=["POST"])
def quote():
    """
    Body: { "destination": "r...", "amount_xrp": 1.23 }
    Returns total debited, fee, and net to recipient.
    """
    require_auth()
    data = request.get_json(force=True)
    amount = Decimal(str(data.get("amount_xrp", "0")))
    if amount <= 0:
        return jsonify({"error": "amount_xrp must be > 0"}), 400
    fee = service_fee_xrp(amount)
    total = amount + fee
    return jsonify({
        "fee_bps": FEE_BPS,
        "fee_xrp": float(fee),
        "amount_to_recipient_xrp": float(amount),
        "total_debited_xrp": float(total),
    })

@app.route("/send", methods=["POST"])
def send_payment():
    """
    Body: {
      "destination": "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe",
      "amount_xrp": 1.0,
      "memo": "optional string",
      "bill_payer": true|false  # if true, fee added on top (payer pays); else fee subtracted (recipient gets less)
    }
    """
    require_auth()
    payload = request.get_json(force=True)
    dest = payload.get("destination", "").strip()
    amount = Decimal(str(payload.get("amount_xrp", "0")))
    memo_str = str(payload.get("memo", ""))[:256]
    bill_payer = bool(payload.get("bill_payer", True))

    if amount <= 0 or amount > MAX_XRP:
        return jsonify({"error": f"amount_xrp must be > 0 and <= {MAX_XRP}"}), 400
    if not dest or not ensure_account(dest):
        return jsonify({"error": "destination not found on ledger"}), 400

    # balances
    trader_addr = TRADER.classic_address
    bal = xrpl_balance(trader_addr)

    fee = service_fee_xrp(amount)
    if bill_payer:
        total_debit = amount + fee
        send_to_dest = amount
    else:
        # subtract fee from amount; recipient receives less
        total_debit = amount
        send_to_dest = (amount - fee).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
        if send_to_dest <= 0:
            return jsonify({"error": "amount too small after fee"}), 400

    if bal < total_debit + Decimal("0.000012"):  # tiny margin for tx fee
        return jsonify({"error": "insufficient balance", "balance_xrp": float(bal)}), 400

    # Build primary payment
    memos = []
    if memo_str:
        memos = [Memo(memo_data=memo_str.encode("utf-8").hex())]

    pay1 = Payment(
        account=trader_addr,
        destination=dest,
        amount=str(xrp_to_drops(float(send_to_dest))),
        memos=memos if memos else None,
    )
    # Autofill, sign, submit, wait
    pay1 = autofill(pay1, client)
    signed1 = sign(pay1, TRADER)
    res1 = submit_and_wait(signed1, client)

    result1 = res1.result.get("meta", {}).get("TransactionResult", res1.result)

    # Optional: collect service fee to revenue wallet (only if a revenue address provided and fee > 0)
    fee_tx_hash = None
    if SERVICE_ADDRESS and fee > 0:
        pay_fee = Payment(
            account=trader_addr,
            destination=SERVICE_ADDRESS,
            amount=str(xrp_to_drops(float(fee))),
            memos=[Memo(memo_data="service_fee".encode("utf-8").hex())],
        )
        pay_fee = autofill(pay_fee, client)
        signed_fee = sign(pay_fee, TRADER)
        res_fee = submit_and_wait(signed_fee, client)
        fee_tx_hash = res_fee.result.get("hash")

    return jsonify({
        "status": "submitted",
        "payer": trader_addr,
        "destination": dest,
        "amount_sent_xrp": float(send_to_dest),
        "fee_xrp": float(fee),
        "total_debited_xrp": float((send_to_dest + fee) if bill_payer else amount),
        "tx_hash": res1.result.get("hash"),
        "tx_result": result1,
        "fee_tx_hash": fee_tx_hash,
        "network": "mainnet" if "xrplcluster.com" in RPC_URL else "testnet",
    })
