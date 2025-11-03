import binascii

def _hex(s: str) -> str:
    return binascii.hexlify(s.encode()).decode().upper()

def publish_receipt_onledger(wallet_service, digest: str, tag: str="ADR:v1") -> str:
    """
    Writes a tamper-evident receipt of an AI decision to XRPL using a self-payment memo.
    - digest: sha256 hex string of the decision payload (client computes & submits)
    - tag: small text tag for grouping (default ADR:v1)
    Returns: tx hash
    """
    memo_text = f"{tag}|sha256={digest}"
    memo_hex  = _hex(memo_text)
    tx_hash = wallet_service.self_memo_payment(memo_hex)
    return tx_hash
