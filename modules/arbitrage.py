# ~/governor_ai/modules/arbitrage.py
import os
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import BookOffers
from xrpl.models.transactions import OfferCreate
from xrpl.transaction import submit_and_wait
from xrpl.utils import xrp_to_drops

# Helper: Issued Currency object for JSON-RPC
def _ic(currency: str, issuer: str) -> Dict[str, str]:
    return {"currency": currency, "issuer": issuer}

class ArbitrageEngine:
    """
    Minimal XRPL DEX arbitrage skeleton.
    - DRY_RUN by default (no real orders).
    - Fetches best bid/ask from the XRPL book (XRP vs Issued Currency).
    - If external/reference price indicates edge, prepares (or places) an offer.
    """

    def __init__(self,
                 rpc_url: str,
                 base: str = "XRP",
                 quote_currency: Optional[str] = None,
                 quote_issuer: Optional[str] = None,
                 min_spread_bps: int = 30,
                 max_slippage_bps: int = 20,
                 dry_run: bool = True):
        self.client = JsonRpcClient(rpc_url)
        self.base = base  # "XRP"
        self.quote_currency = quote_currency  # e.g., "USD"
        self.quote_issuer = quote_issuer      # rXXXX issuer of USD IOU on XRPL
        self.min_spread_bps = min_spread_bps
        self.max_slippage_bps = max_slippage_bps
        self.dry_run = dry_run

    # ---- Public API ---------------------------------------------------------

    def cycle(self, wallet_service, receipts, ref_price_xrp_in_quote: Optional[float] = None):
        """
        One arbitrage cycle:
          1) Pull best bid/ask from XRPL order book (if pair configured).
          2) Compare to reference price (if given).
          3) If edge > threshold, prepare (or place) offer.
        """
        ts = datetime.now(timezone.utc).isoformat()
        addr = getattr(getattr(wallet_service, "wallet", wallet_service), "classic_address", "unknown")

        # Guardrails: need a quote currency + issuer to read a real book
        if not (self.quote_currency and self.quote_issuer):
            receipts.log(f"[Arb] {ts} | Pair not configured. Set QUOTE_CURRENCY & QUOTE_ISSUER in .env")
            return

        best = self._best_bid_ask()
        if best is None:
            receipts.log(f"[Arb] {ts} | No orderbook data available.")
            return

        best_bid_xrp, best_ask_xrp = best  # prices in QUOTE per 1 XRP
        receipts.log(f"[Arb] {ts} | XRPL best bid {best_bid_xrp:.6f} {self.quote_currency}/XRP, "
                     f"best ask {best_ask_xrp:.6f} {self.quote_currency}/XRP")

        # If no external price, just stop here (market-making modules can be added later)
        if ref_price_xrp_in_quote is None:
            return

        # Simple edge checks (buy if XRPL ask is cheap vs ref; sell if XRPL bid is rich vs ref)
        buy_edge_bps = 10000.0 * (ref_price_xrp_in_quote - best_ask_xrp) / ref_price_xrp_in_quote
        sell_edge_bps = 10000.0 * (best_bid_xrp - ref_price_xrp_in_quote) / ref_price_xrp_in_quote

        if buy_edge_bps >= self.min_spread_bps:
            # BUY XRP (pay QUOTE)
            self._place_buy_xrp(wallet_service, receipts, amount_xrp=5.0, limit_price=best_ask_xrp)
        elif sell_edge_bps >= self.min_spread_bps:
            # SELL XRP (receive QUOTE)
            self._place_sell_xrp(wallet_service, receipts, amount_xrp=5.0, limit_price=best_bid_xrp)
        else:
            receipts.log(f"[Arb] {ts} | No actionable edge (buy {buy_edge_bps:.1f}bps / sell {sell_edge_bps:.1f}bps).")

    # ---- Internals ----------------------------------------------------------

    def _best_bid_ask(self) -> Optional[Tuple[float, float]]:
        """
        Returns (best_bid_price, best_ask_price) for XRP quoted in the IOU: QUOTE/XRP.
        Price is QUOTE per 1 XRP.
        """
        try:
            # Book where taker GETS XRP and PAYS QUOTE -> asks (people selling XRP for QUOTE)
            asks = self.client.request(BookOffers(
                taker_gets={"currency": "XRP"},
                taker_pays=_ic(self.quote_currency, self.quote_issuer),
                limit=5
            )).result.get("offers", [])

            # Book where taker GETS QUOTE and PAYS XRP -> bids (people buying XRP with QUOTE)
            bids = self.client.request(BookOffers(
                taker_gets=_ic(self.quote_currency, self.quote_issuer),
                taker_pays={"currency": "XRP"},
                limit=5
            )).result.get("offers", [])

            def _price_quote_per_xrp(offer: Dict[str, Any], side: str) -> Optional[float]:
                # Offers have "TakerGets" and "TakerPays"
                gets = offer.get("taker_gets")
                pays = offer.get("taker_pays")

                # Normalize to dict forms
                if isinstance(gets, str):
                    gets = {"currency": "XRP", "value": gets}  # drops for XRP
                if isinstance(pays, str):
                    pays = {"currency": "XRP", "value": pays}

                # Convert to numeric amounts
                def _amt(a):
                    if a.get("currency") == "XRP":
                        return float(a["value"]) / 1_000_000.0  # drops -> XRP
                    else:
                        # IOU: expect "value" as string float
                        return float(a["value"])

                try:
                    if side == "ask":
                        # taker pays QUOTE (IOU), gets XRP
                        xrp = _amt(gets)   # XRP the taker gets
                        quote = _amt(pays) # QUOTE the taker pays
                    else:  # "bid"
                        # taker pays XRP, gets QUOTE
                        xrp = _amt(pays)   # XRP the taker pays
                        quote = _amt(gets) # QUOTE the taker gets

                    return quote / xrp if xrp > 0 else None
                except Exception:
                    return None

            best_ask = min([_price_quote_per_xrp(o, "ask") for o in asks if _price_quote_per_xrp(o, "ask")], default=None)
            best_bid = max([_price_quote_per_xrp(o, "bid") for o in bids if _price_quote_per_xrp(o, "bid")], default=None)

            if best_bid is None or best_ask is None:
                return None
            return (best_bid, best_ask)
        except Exception:
            return None

    def _place_buy_xrp(self, wallet_service, receipts, amount_xrp: float, limit_price: float):
        """
        BUY XRP: pay QUOTE IOU, receive XRP.
        """
        ts = datetime.now(timezone.utc).isoformat()
        addr = getattr(getattr(wallet_service, "wallet", wallet_service), "classic_address", "unknown")
        spend_quote = amount_xrp * limit_price  # QUOTE units

        if self.dry_run:
            receipts.log(f"[Arb] {ts} | DRY_RUN BUY {amount_xrp:.4f} XRP @≤ {limit_price:.6f} "
                         f"spend ~{spend_quote:.2f} {self.quote_currency} from {addr}")
            return

        try:
            tx = OfferCreate(
                account=addr,
                taker_gets={  # taker pays QUOTE
                    "currency": self.quote_currency,
                    "issuer": self.quote_issuer,
                    "value": f"{spend_quote:.6f}",
                },
                taker_pays=xrp_to_drops(amount_xrp),  # taker gets XRP
            )
            result = submit_and_wait(tx, self.client, wallet=wallet_service.wallet)
            receipts.log(f"[Arb] {ts} | BUY submitted {result.result.get('hash')}")
        except Exception as e:
            receipts.log(f"[Arb] {ts} | BUY error: {e}")

    def _place_sell_xrp(self, wallet_service, receipts, amount_xrp: float, limit_price: float):
        """
        SELL XRP: receive QUOTE IOU, pay XRP.
        """
        ts = datetime.now(timezone.utc).isoformat()
        addr = getattr(getattr(wallet_service, "wallet", wallet_service), "classic_address", "unknown")
        receive_quote = amount_xrp * limit_price  # QUOTE units

        if self.dry_run:
            receipts.log(f"[Arb] {ts} | DRY_RUN SELL {amount_xrp:.4f} XRP @≥ {limit_price:.6f} "
                         f"receive ~{receive_quote:.2f} {self.quote_currency} to {addr}")
            return

        try:
            tx = OfferCreate(
                account=addr,
                taker_gets=xrp_to_drops(amount_xrp),  # taker pays XRP
                taker_pays={  # taker gets QUOTE
                    "currency": self.quote_currency,
                    "issuer": self.quote_issuer,
                    "value": f"{receive_quote:.6f}",
                },
            )
            result = submit_and_wait(tx, self.client, wallet=wallet_service.wallet)
            receipts.log(f"[Arb] {ts} | SELL submitted {result.result.get('hash')}")
        except Exception as e:
            receipts.log(f"[Arb] {ts} | SELL error: {e}")
