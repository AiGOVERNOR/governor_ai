# ~/governor_ai/agents/trader_agent.py
from flask import Flask, request, jsonify
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.models.requests import AccountInfo
import json, os

# --------- XRPL helper imports (handle different xrpl-py versions) ----------
# We'll try several function names/paths and fall back as needed.
safe_sign_autofill = None
autofill_and_sign_fn = None
submit_and_wait_fn = None
send_reliable_submission_fn = None
autofill = None
sign = None

try:
    from xrpl.transaction import safe_sign_and_autofill_transaction as safe_sign_autofill
except Exception:
    pass

try:
    from xrpl.transaction import autofill_and_sign as autofill_and_sign_fn
except Exception:
    pass

try:
    from xrpl.transaction import submit_and_wait as submit_and_wait_fn
except Exception:
    pass

try:
    from xrpl.transaction import send_reliable_submission as send_reliable_submission_fn
except Exception:
    # some builds rename to reliable_submission (rare)
    try:
        from xrpl.transaction import reliable_submission as send_reliable_submission_fn  # type: ignore
    except Exception:
        pass

try:
    from xrpl.transaction import autofill as _autofill, sign as _sign
    autofill, sign = _autofill, _sign
except Exception:
    pass


def sign_and_submit(tx, wallet, client):
    """
    Unified signer/submitter that adapts to whatever xrpl-py exposes.
    Returns the full submit result object.
    """
    # 1) Best: safe_sign + submit_and_wait in one/two steps
    if safe_sign_autofill and submit_and_wait_fn:
        signed = safe_sign_autofill(tx, wallet, client)
        return submit_and_wait_fn(signed, client)

    # 2) Newer split: autofill_and_sign + submit_and_wait
    if autofill_and_sign_fn and submit_and_wait_fn:
        signed = autofill_and_sign_fn(tx, wallet, client)
        return submit_and_wait_fn(signed, client)

    # 3) safe_sign + send_reliable_submission
    if safe_sign_autofill and send_reliable_submission_fn:
        signed = safe_sign_autofill(tx, wallet, client)
        return send_reliable_submission_fn(signed, client)

    # 4) Manual: autofill -> sign -> submit_and_wait
    if autofill and sign and submit_and_wait_fn:
        filled = autofill(tx, client)
        signed = sign(filled, wallet)
        return submit_and_wait_fn(signed, client)

    # 5) Manual: autofill -> sign -> send_reliable_submission
    if autofill and sign and send_reliable_submission_fn:
        filled = autofill(tx, client)
        signed = sign(filled, wallet)
        return send_reliable_submission_fn(signed, client)

    raise RuntimeError("xrpl-py functions not found: upgrade/downgrade xrpl-py or install a supported version.")


# --------------------------- Flask microservice ------------------------------
app = Flask(__name__)

XRPL_RPC_URL = os.getenv("XRPL_RPC_URL", "https://s.altnet.rippletest.net:51234")
client = JsonRpcClient(XRPL_RPC_URL)

# Load wallet (supports several JSON shapes)
def load_wallet():
    with open(os.path.join(os.path.dirname(__file__), "..", "wallets", "test_wallet.json")) as f:
        data = json.load(f)
    seed = data.get("seed") or data.get("secret") or data.get("seed_hex")
    if not seed:
        raise ValueError("Wallet JSON missing 'seed' (or 'secret' / 'seed_hex').")
    return Wallet.from_seed(seed)

WALLET = load_wallet()


@app.route("/")
def home():
    return jsonify({"status": "Trader Agent online ✅"})


@app.route("/balance")
def balance():
    try:
        req = AccountInfo(account=WALLET.classic_address, ledger_index="validated")
        info = client.request(req)
        drops = int(info.result["account_data"]["Balance"])
        return jsonify({
            "address": WALLET.classic_address,
            "balance_xrp": drops / 1_000_000
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/send", methods=["POST"])
def send_payment():
    try:
        body = request.get_json(force=True) or {}
        destination = body.get("destination")
        amount_xrp = float(body.get("amount_xrp", 0))

        if not destination or amount_xrp <= 0:
            return jsonify({"error": "Provide 'destination' and positive 'amount_xrp'."}), 400

        payment = Payment(
            account=WALLET.classic_address,
            destination=destination,
            amount=str(int(amount_xrp * 1_000_000)),  # drops
        )

        result = sign_and_submit(payment, WALLET, client)

        # Try to pull a hash regardless of exact response schema
        tx_hash = None
        if isinstance(result, dict):
            tx_hash = (
                result.get("result", {})
                .get("tx_json", {})
                .get("hash")
                or result.get("result", {}).get("hash")
            )
        else:
            # xrpl-py Response object
            try:
                tx_hash = result.result.get("tx_json", {}).get("hash") or result.result.get("hash")
            except Exception:
                pass

        return jsonify({
            "status": "sent",
            "tx_hash": tx_hash,
            "amount_xrp": amount_xrp,
            "destination": destination
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Host on all interfaces so your other micro-agents can reach it
    app.run(host="0.0.0.0", port=5003)
