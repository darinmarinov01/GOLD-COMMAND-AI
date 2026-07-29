from __future__ import annotations

from app.analyzers.rule_engine import generate_snapshot
from app.config import settings
from app.collectors.market_data import collect_market_data, get_price_provider_status
from app.models import AnalysisSnapshot


class AnalysisService:
    def __init__(self) -> None:
        self._latest: AnalysisSnapshot | None = None
        self._price_override: float | None = None
        self._price_override_source: str = "manual_override"

    def generate(self) -> AnalysisSnapshot:
        bundle = collect_market_data()

        current_price = bundle.current_price
        price_source = bundle.price_source
        price_live = bundle.price_live

        if self._price_override is not None:
            current_price = self._price_override
            price_source = self._price_override_source
            price_live = True

        snapshot = generate_snapshot(
            current_price=current_price,
            macro=bundle.macro,
            structure=bundle.structure,
            flow=bundle.flow,
            price_source=price_source,
            price_live=price_live,
            goldbach_po3_range=settings.goldbach_po3_range,
            goldbach_use_pips=settings.goldbach_use_pips,
            goldbach_tick_size=settings.goldbach_tick_size,
            goldbach_manual_range_low=settings.goldbach_manual_range_low,
            goldbach_manual_range_high=settings.goldbach_manual_range_high,
        )
        self._latest = snapshot
        return snapshot

    def latest(self) -> AnalysisSnapshot:
        if self._latest is None:
            return self.generate()
        return self._latest

    def set_price_override(self, price: float, source: str = "manual_override") -> None:
        self._price_override = round(price, 2)
        self._price_override_source = source

    def clear_price_override(self) -> None:
        self._price_override = None
        self._price_override_source = "manual_override"

    def provider_status(self, probe: bool = False) -> dict[str, object]:
        status = get_price_provider_status(probe=probe)
        status["manual_override_active"] = self._price_override is not None
        status["manual_override_price"] = self._price_override
        status["manual_override_source"] = self._price_override_source if self._price_override is not None else None
        return status


analysis_service = AnalysisService()
