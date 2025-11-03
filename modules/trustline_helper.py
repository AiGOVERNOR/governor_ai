# ~/governor_ai/modules/trustline_helper.py
from xrpl.clients import JsonRpcClient
from xrpl.models.transactions import TrustSet
from xrpl.transaction import safe_sign_and_autofill_transaction, send_reliable_submission
from xrpl.models.requests import AccountLines
from datetime import datetime, timezone

class TrustlineHelper:
    """
    Handles XRPL trustlines for the Governor AI wallet.
    Allows the wallet to hold issued tokens (like USD, EUR, etc).
    """

    def __init__(self, xrpl_url: str, wallet):
        self.client = JsonRpcClient(xrpl_url)
        self.wallet = wallet
        self.address = wallet.classic_address

    def has_trustline(self, issuer: str, currency: str) -> bool:
        """
        Checks if the wallet already has a trustline for a specific issuer + currency.
        """
        try:
            req = AccountLines(account=self.address)
            resp = self.client.request(req)
            for line in resp.result.get("lines", []):
                if line["account"] == issuer and line["currency"] == currency:
                    return True
            return False
        except Exception as e:
            print(f"[TrustlineHelper] Trustline check failed: {e}")
            return False

    def create_trustline(self, issuer: str, currency: str, limit="1000000000"):
        """
        Creates a trustline to a given issuer (like a USD gateway).
        """
        try:
            if self.has_trustline(issuer, currency):
                print(f"[TrustlineHelper] Wallet already has trustline for {currency}:{issuer}")
                return

            print(f"[TrustlineHelper] Creating trustline for {currency}:{issuer}...")
            tx = TrustSet(
                account=self.address,
                limit_amount={
                    "currency": currency,
                    "issuer": issuer,
                    "value": limit,
                }
            )
            signed_tx = safe_sign_and_autofill_transaction(tx, self.wallet, self.client)
            tx_result = send_reliable_submission(signed_tx, self.client)
            ts = datetime.now(timezone.utc).isoformat()
            print(f"[TrustlineHelper] {ts} | Trustline transaction result: {tx_result.result['engine_result']}")
        except Exception as e:
            print(f"[TrustlineHelper] Failed: {e}")
