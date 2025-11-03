from dataclasses import dataclass
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.account import get_account_root
from xrpl.transaction import autofill_and_sign, submit_and_wait
from xrpl.models.transactions import Payment


@dataclass
class WalletService:
    xrpl_url: str
    seed: str

    def __post_init__(self):
        if not self.seed:
            raise RuntimeError("TRADER_SEED missing in .env")
        self.client = JsonRpcClient(self.xrpl_url)
        self.wallet = Wallet.from_seed(self.seed)

    def snapshot(self):
        info = get_account_root(self.wallet.classic_address, self.client)
        data = info.result.get("account_data", {})
        bal_drops = int(data.get("Balance", 0))
        return {
            "address": self.wallet.classic_address,
            "drops": bal_drops,
            "xrp": bal_drops / 1_000_000,
        }

    def self_memo_payment(self, memo_hex: str) -> str:
        """
        Writes a memo to the ledger by sending 1 drop to self with memo attached.
        """
        payment = Payment(
            account=self.wallet.classic_address,
            amount="1",  # one drop
            destination=self.wallet.classic_address,
            memos=[{"memo": {"memo_data": memo_hex}}],
        )
        # autofill fields, sign, and submit
        signed_tx = autofill_and_sign(payment, self.client, self.wallet)
        result = submit_and_wait(signed_tx, self.client)
        return result.result.get("hash") or signed_tx.get_hash()
