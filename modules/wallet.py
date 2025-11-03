# ~/governor_ai/modules/wallet.py

from datetime import datetime, timezone
from xrpl.wallet import Wallet
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountInfo

class WalletService:
    """
    XRPL wallet wrapper for Governor AI.
    - Loads wallet from family seed
    - Exposes .wallet and .address
    - Provides get_balance() via AccountInfo
    """

    def __init__(self, xrpl_url: str, seed: str):
        if not seed:
            raise ValueError("Missing XRPL seed")
        self.client = JsonRpcClient(xrpl_url)
        self.wallet = Wallet.from_seed(seed)   # correct for family seed
        self.address = self.wallet.classic_address

    def get_balance(self):
        """
        Returns XRP balance as float (XRP units), or None if unavailable.
        """
        try:
            req = AccountInfo(account=self.address, ledger_index="validated", strict=True)
            resp = self.client.request(req)
            drops = int(resp.result["account_data"]["Balance"])
            return drops / 1_000_000.0
        except Exception as e:
            print(f"[WalletService] Balance fetch failed: {e}")
            return None

    def log_balance(self):
        ts = datetime.now(timezone.utc).isoformat()
        bal = self.get_balance()
        if bal is None:
            print(f"[Governor AI] {ts} | Wallet {self.address} Balance: unavailable")
        else:
            print(f"[Governor AI] {ts} | Wallet {self.address} Balance: {bal:.6f} XRP")
