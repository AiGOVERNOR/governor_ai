import requests, json
from pathlib import Path

resp = requests.post("https://faucet.altnet.rippletest.net/accounts")
resp.raise_for_status()
acct = resp.json()["account"]
Path("wallets/test_wallet.json").write_text(json.dumps(acct, indent=2))
print("Wallet created & funded on XRPL Testnet ✅")
print("Address:", acct["address"])

