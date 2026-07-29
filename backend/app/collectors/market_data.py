from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from app.config import settings
from app.models import FlowInputs, MacroInputs, StructureInputs


@dataclass
class MarketDataBundle:
    current_price: float
    price_source: str
    price_live: bool
    macro: MacroInputs
    structure: StructureInputs
    flow: FlowInputs


_last_price_status: dict[str, object] = {}


def _fetch_yahoo_price() -> tuple[float, str, bool]:
    """
    Pull delayed public quote from Yahoo Finance.
    Tries spot first, then futures as fallback.
    """
    candidates = [
        ("XAUUSD=X", "Yahoo Finance XAUUSD"),
        ("GC=F", "Yahoo Finance GC=F"),
    ]

    for symbol, source in candidates:
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        try:
            with urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, json.JSONDecodeError):
            continue

        results = payload.get("quoteResponse", {}).get("result", [])
        if not results:
            continue

        value = results[0].get("regularMarketPrice")
        if isinstance(value, (int, float)):
            return float(value), source, True

    return 3402.45, "fallback_stub", False


def _as_positive_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _fetch_twelvedata_price() -> tuple[float, str, bool]:
    if not settings.twelvedata_api_key:
        return 0.0, "twelvedata_missing_api_key", False

    symbol = settings.twelvedata_symbol
    base_url = settings.twelvedata_base_url.rstrip("/")
    query = urlencode({"symbol": symbol, "apikey": settings.twelvedata_api_key})
    url = f"{base_url}/price?{query}"

    try:
        with urlopen(url, timeout=settings.price_request_timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return 0.0, "twelvedata_request_failed", False

    value = payload.get("price")
    if value is None:
        return 0.0, "twelvedata_invalid_payload", False

    price = _as_positive_float(value)
    if price is None:
        return 0.0, "twelvedata_invalid_price", False

    return float(price), "twelvedata", True


def _fetch_polygon_price() -> tuple[float, str, bool]:
    if not settings.polygon_api_key:
        return 0.0, "polygon_missing_api_key", False

    base_url = settings.polygon_base_url.rstrip("/")
    ticker = quote(settings.polygon_ticker, safe="")
    url = f"{base_url}/v2/snapshot/locale/global/markets/fx/tickers/{ticker}?apiKey={settings.polygon_api_key}"

    try:
        with urlopen(url, timeout=settings.price_request_timeout_sec) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, json.JSONDecodeError):
        return 0.0, "polygon_request_failed", False

    ticker_data = payload.get("ticker")
    if not isinstance(ticker_data, dict):
        return 0.0, "polygon_invalid_payload", False

    # Prefer real-time trade price when available.
    for path in [("lastTrade", "p"), ("lastQuote", "a"), ("lastQuote", "b"), ("min", "c")]:
        node = ticker_data.get(path[0])
        if isinstance(node, dict):
            price = _as_positive_float(node.get(path[1]))
            if price is not None:
                return float(price), "polygon", True

    return 0.0, "polygon_missing_price", False


def _fetch_first_available(chain: list[tuple[str, Callable[[], tuple[float, str, bool]]]]) -> tuple[float, str, bool]:
    failures: list[str] = []

    for provider_name, fetcher in chain:
        price, source, live = fetcher()
        if live:
            if failures:
                return price, f"{source}_after_{'_'.join(failures)}", True
            return price, source, True
        failures.append(source or provider_name)

    if failures:
        return 3402.45, f"fallback_stub_after_{'_'.join(failures)}", False
    return 3402.45, "fallback_stub", False


def _fetch_current_price() -> tuple[float, str, bool]:
    provider = settings.price_provider.strip().lower()

    if provider == "twelvedata":
        return _fetch_first_available(
            [
                ("twelvedata", _fetch_twelvedata_price),
                ("polygon", _fetch_polygon_price),
                ("yahoo", _fetch_yahoo_price),
            ]
        )

    if provider == "polygon":
        return _fetch_first_available(
            [
                ("polygon", _fetch_polygon_price),
                ("twelvedata", _fetch_twelvedata_price),
                ("yahoo", _fetch_yahoo_price),
            ]
        )

    if provider == "yahoo":
        return _fetch_first_available([("yahoo", _fetch_yahoo_price)])

    # Default auto mode prioritizes API-key providers over public endpoints.
    return _fetch_first_available(
        [
            ("twelvedata", _fetch_twelvedata_price),
            ("polygon", _fetch_polygon_price),
            ("yahoo", _fetch_yahoo_price),
        ]
    )


def _update_last_price_status(price: float, source: str, live: bool) -> None:
    _last_price_status.update(
        {
            "configured_provider": settings.price_provider.strip().lower(),
            "price_source": source,
            "price_live": live,
            "sampled_price": round(price, 5),
            "sampled_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def get_price_provider_status(probe: bool = False) -> dict[str, object]:
    if probe or not _last_price_status:
        price, source, live = _fetch_current_price()
        _update_last_price_status(price=price, source=source, live=live)
    return dict(_last_price_status)


def collect_market_data() -> MarketDataBundle:
    """
    V1 stub collector.
    Replace with provider integrations in V2:
    - price feed (XAUUSD / GC)
    - macro feeds (DXY, US10Y, Oil, Silver, VIX)
    - calendar/news APIs
    - order-flow provider
    """
    macro = MacroInputs(
        dxy_change_pct=-0.35,
        us10y_change_bps=-3.1,
        oil_change_pct=-0.8,
        silver_change_pct=0.5,
        vix_change_pct=1.2,
        fed_hawkish_score=42,
    )

    structure = StructureInputs(
        daily_bullish=True,
        h4_bullish=True,
        h1_bullish=True,
        m15_choch_waiting=True,
        sweep_confirmed=False,
    )

    flow = FlowInputs(
        delta_positive=False,
        smt_bullish=True,
        news_risk_high=False,
    )

    current_price, price_source, price_live = _fetch_current_price()
    _update_last_price_status(price=current_price, source=price_source, live=price_live)

    return MarketDataBundle(
        current_price=current_price,
        price_source=price_source,
        price_live=price_live,
        macro=macro,
        structure=structure,
        flow=flow,
    )
