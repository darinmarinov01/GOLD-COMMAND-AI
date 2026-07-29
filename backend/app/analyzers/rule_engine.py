from __future__ import annotations

from datetime import datetime, timezone
import math

from app.models import (
    AnalysisSnapshot,
    ConfluenceSignal,
    FlowInputs,
    GoldbachEntrySignal,
    GoldbachRange,
    LimitOrderPlan,
    LiquidityIntel,
    MarketStructureIntel,
    MacroInputs,
    PriceTerrainLevel,
    ProbabilityEngineIntel,
    Probability,
    SessionDependencyCandidate,
    SessionEvent,
    SessionDependencyScenario,
    SetupGeneratorIntel,
    StructureInputs,
    TradeSetup,
    TradingIntelligence,
)


def _score_macro(macro: MacroInputs) -> tuple[float, dict[str, float]]:
    score = 0.0
    breakdown: dict[str, float] = {}

    if macro.dxy_change_pct < 0:
        score += 12
        breakdown["dxy_weakness"] = 12
    else:
        score -= 12
        breakdown["dxy_strength"] = -12

    if macro.us10y_change_bps < 0:
        score += 8
        breakdown["real_yields_down"] = 8
    else:
        score -= 8
        breakdown["real_yields_up"] = -8

    if macro.oil_change_pct < 0:
        score += 4
        breakdown["oil_down"] = 4

    if macro.silver_change_pct > 0:
        score += 5
        breakdown["silver_relative_strength"] = 5

    if macro.vix_change_pct > 3:
        score -= 5
        breakdown["risk_off_noise"] = -5

    if macro.fed_hawkish_score > 65:
        score -= 10
        breakdown["fed_hawkish"] = -10

    return score, breakdown


def _score_structure(structure: StructureInputs) -> tuple[float, dict[str, float]]:
    score = 0.0
    breakdown: dict[str, float] = {}

    if structure.daily_bullish:
        score += 10
        breakdown["daily_bull"] = 10
    if structure.h4_bullish:
        score += 8
        breakdown["h4_bull"] = 8
    if structure.h1_bullish:
        score += 7
        breakdown["h1_bull"] = 7
    if structure.m15_choch_waiting:
        score -= 4
        breakdown["m15_waiting_confirmation"] = -4
    if structure.sweep_confirmed:
        score += 10
        breakdown["liquidity_sweep_confirmed"] = 10

    return score, breakdown


def _score_flow(flow: FlowInputs) -> tuple[float, dict[str, float]]:
    score = 0.0
    breakdown: dict[str, float] = {}

    if flow.delta_positive:
        score += 8
        breakdown["delta_positive"] = 8
    else:
        score -= 8
        breakdown["delta_negative"] = -8

    if flow.smt_bullish:
        score += 6
        breakdown["smt_bull"] = 6

    if flow.news_risk_high:
        score -= 7
        breakdown["news_risk_high"] = -7

    return score, breakdown


def _to_probabilities(score: float) -> Probability:
    # Clamp to a stable range, then map to bull/range/bear probabilities.
    bounded = max(-60.0, min(60.0, score))
    bull = 50 + (bounded * 0.7)
    bear = 50 - (bounded * 0.7)

    bull = max(5.0, min(90.0, bull))
    bear = max(5.0, min(90.0, bear))
    range_prob = max(5.0, 100.0 - bull - bear)

    total = bull + bear + range_prob
    return Probability(
        bull=round((bull / total) * 100, 2),
        range=round((range_prob / total) * 100, 2),
        bear=round((bear / total) * 100, 2),
    )


def _rr(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        return 0.0
    return round(reward / risk, 2)


def _build_goldbach_range(
    current_price: float,
    po3_range: float,
    use_pips: bool,
    tick_size: float,
    manual_range_low: float,
    manual_range_high: float,
) -> GoldbachRange:
    safe_tick = max(tick_size, 0.01)
    raw_po3 = max(po3_range, safe_tick)
    actual_po3 = raw_po3 * safe_tick * 10.0 if use_pips else raw_po3
    actual_po3 = max(actual_po3, safe_tick)

    if manual_range_low > 0 and manual_range_high > manual_range_low:
        range_low = manual_range_low
        range_high = manual_range_high
        actual_po3 = manual_range_high - manual_range_low
    else:
        range_low = math.floor(current_price / actual_po3) * actual_po3
        range_high = range_low + actual_po3

    range_size = range_high - range_low
    ext_offset = range_size * 0.111
    sub_size = range_size / 3.0
    sub_high = range_high - sub_size
    sub_low = range_low + sub_size
    sub_ext_offset = sub_size * 0.111

    return GoldbachRange(
        po3_range=round(raw_po3, 5),
        actual_range=round(range_size, 5),
        tick_size=round(safe_tick, 5),
        use_pips=use_pips,
        range_low=round(range_low, 2),
        range_high=round(range_high, 2),
        eq=round(range_high - (range_size * 0.50), 2),
        ext_high_plus=round(range_high + ext_offset, 2),
        ext_high_minus=round(range_high - ext_offset, 2),
        ext_low_plus=round(range_low + ext_offset, 2),
        ext_low_minus=round(range_low - ext_offset, 2),
        sub_high=round(sub_high, 2),
        sub_low=round(sub_low, 2),
        sub_ext_high_plus=round(sub_high + sub_ext_offset, 2),
        sub_ext_high_minus=round(sub_high - sub_ext_offset, 2),
        sub_ext_low_plus=round(sub_low + sub_ext_offset, 2),
        sub_ext_low_minus=round(sub_low - sub_ext_offset, 2),
        prev_range_low=round(range_low - range_size, 2),
        prev_range_high=round(range_low, 2),
        next_range_low=round(range_high, 2),
        next_range_high=round(range_high + range_size, 2),
    )


def _build_goldbach_entries(
    goldbach: GoldbachRange,
    direction: str,
    current_price: float,
    news_risk_high: bool,
) -> list[GoldbachEntrySignal]:
    candidates: list[tuple[str, str, float, float, float, float, float, str, str, float]]
    if direction == "long":
        candidates = [
            (
                "Sub-range discount retest",
                "buy",
                goldbach.sub_low,
                goldbach.sub_ext_low_minus,
                goldbach.eq,
                goldbach.sub_high,
                goldbach.range_high,
                "sub_low",
                "Primary long trigger near discount third after rejection.",
                74.0,
            ),
            (
                "Main range extreme bid",
                "buy",
                goldbach.ext_low_plus,
                goldbach.ext_low_minus,
                goldbach.sub_low,
                goldbach.eq,
                goldbach.sub_high,
                "ext_low_plus",
                "Deeper liquidity sweep into lower extension before expansion.",
                80.0,
            ),
            (
                "EQ reclaim continuation",
                "buy",
                goldbach.eq,
                goldbach.sub_ext_low_minus,
                goldbach.sub_high,
                goldbach.range_high,
                goldbach.ext_high_plus,
                "eq",
                "Continuation setup after equilibrium reclaim.",
                68.0,
            ),
        ]
    else:
        candidates = [
            (
                "Sub-range premium retest",
                "sell",
                goldbach.sub_high,
                goldbach.sub_ext_high_plus,
                goldbach.eq,
                goldbach.sub_low,
                goldbach.range_low,
                "sub_high",
                "Primary short trigger near premium third after rejection.",
                74.0,
            ),
            (
                "Main range extreme offer",
                "sell",
                goldbach.ext_high_minus,
                goldbach.ext_high_plus,
                goldbach.sub_high,
                goldbach.eq,
                goldbach.sub_low,
                "ext_high_minus",
                "Deeper liquidity sweep into upper extension before markdown.",
                80.0,
            ),
            (
                "EQ breakdown continuation",
                "sell",
                goldbach.eq,
                goldbach.sub_ext_high_plus,
                goldbach.sub_low,
                goldbach.range_low,
                goldbach.ext_low_minus,
                "eq",
                "Continuation setup after equilibrium rejection.",
                68.0,
            ),
        ]

    signals: list[GoldbachEntrySignal] = []
    for label, side, entry, stop_loss, tp1, tp2, tp3, anchor_level, reason, base_score in candidates:
        distance_points = abs(current_price - entry)
        proximity_boost = max(0.0, 35.0 - (distance_points / goldbach.actual_range) * 40.0)
        rr2 = _rr(entry, stop_loss, tp2)
        rr_boost = min(25.0, rr2 * 11.0)
        news_penalty = 7.0 if news_risk_high else 0.0
        quality = min(95.0, max(35.0, base_score + proximity_boost + rr_boost - news_penalty))

        signals.append(
            GoldbachEntrySignal(
                label=label,
                side=side,
                entry=round(entry, 2),
                stop_loss=round(stop_loss, 2),
                tp1=round(tp1, 2),
                tp2=round(tp2, 2),
                tp3=round(tp3, 2),
                rr1=_rr(entry, stop_loss, tp1),
                rr2=rr2,
                rr3=_rr(entry, stop_loss, tp3),
                score=round(quality, 2),
                anchor_level=anchor_level,
                reason=reason,
            )
        )

    return sorted(signals, key=lambda item: item.score, reverse=True)


def _build_setup(current_price: float, score: float, goldbach_entries: list[GoldbachEntrySignal] | None = None) -> TradeSetup:
    long_bias = score >= 0

    if goldbach_entries:
        preferred_side = "buy" if long_bias else "sell"
        selected = next((item for item in goldbach_entries if item.side == preferred_side), goldbach_entries[0])
        direction = "long" if selected.side == "buy" else "short"
        entry = round(selected.entry, 2)
        sl = round(selected.stop_loss, 2)
        tp1 = round(selected.tp1, 2)
        tp2 = round(selected.tp2, 2)
        tp3 = round(selected.tp3, 2)
    elif long_bias:
        entry = round(current_price - 4.0, 2)
        sl = round(entry - 8.0, 2)
        tp1 = round(entry + 12.0, 2)
        tp2 = round(entry + 24.0, 2)
        tp3 = round(entry + 36.0, 2)
        direction = "long"
    else:
        entry = round(current_price + 4.0, 2)
        sl = round(entry + 8.0, 2)
        tp1 = round(entry - 12.0, 2)
        tp2 = round(entry - 24.0, 2)
        tp3 = round(entry - 36.0, 2)
        direction = "short"

    risk = abs(entry - sl)
    reward = abs(tp2 - entry)
    rr = round(reward / risk, 2) if risk else 0.0
    probability_boost = 0.0
    if goldbach_entries:
        probability_boost = max(0.0, (goldbach_entries[0].score - 60.0) * 0.12)

    return TradeSetup(
        direction=direction,
        entry=entry,
        stop_loss=sl,
        tp1=tp1,
        tp2=tp2,
        tp3=tp3,
        rr=rr,
        probability=round(min(94.0, max(51.0, 50 + score * 0.6 + probability_boost)), 2),
    )


def _build_price_terrain(current_price: float, setup: TradeSetup, goldbach: GoldbachRange) -> list[PriceTerrainLevel]:
    band_half_width = max(0.3, goldbach.actual_range * 0.03)

    def _band(center: float) -> str:
        return f"{round(center - band_half_width, 2)}-{round(center + band_half_width, 2)}"

    return [
        PriceTerrainLevel(
            zone=_band(goldbach.ext_high_plus),
            kind="supply",
            note="Main range upper extension where distribution/fade setups often trigger.",
        ),
        PriceTerrainLevel(
            zone=_band(goldbach.sub_high),
            kind="neutral",
            note="Upper third decision area used for premium reactions.",
        ),
        PriceTerrainLevel(
            zone=_band(goldbach.eq),
            kind="neutral",
            note="Equilibrium pivot. Reclaim/reject behavior confirms continuation or fade.",
        ),
        PriceTerrainLevel(
            zone=f"{round(current_price, 2)}",
            kind="current",
            note="Live market reference for timing reactions into Goldbach anchors.",
        ),
        PriceTerrainLevel(
            zone=_band(goldbach.sub_low),
            kind="demand",
            note="Lower third discount area used for primary buy reactions.",
        ),
        PriceTerrainLevel(
            zone=_band(goldbach.ext_low_minus),
            kind="regime",
            note="Lower extension invalidation threshold for long intraday structure.",
        ),
    ]


def _build_sessions(flow: FlowInputs) -> list[SessionEvent]:
    ny_note = "US open can confirm direction if volume expands."
    if flow.news_risk_high:
        ny_note = "US open can be volatile due to high news risk."

    return [
        SessionEvent(
            time_label="07:30 EET",
            title="Daily report generated",
            note="Baseline scenario, levels, and risk map published.",
            importance="medium",
        ),
        SessionEvent(
            time_label="08:30 EET",
            title="London rhythm check",
            note="Validate sweep and CHoCH behavior in active flow.",
            importance="high",
        ),
        SessionEvent(
            time_label="12:30 EET",
            title="Mid-session fix",
            note="Confirm whether trend continuation or mean reversion dominates.",
            importance="medium",
        ),
        SessionEvent(
            time_label="16:30 EET",
            title="US open",
            note=ny_note,
            importance="high",
        ),
        SessionEvent(
            time_label="22:30 EET",
            title="Final hourly update",
            note="Close-of-day state before next session reset.",
            importance="low",
        ),
    ]


def _infer_session_dependency(
    structure: StructureInputs,
    flow: FlowInputs,
    macro: MacroInputs,
    probs: Probability,
    total_score: float,
) -> tuple[SessionDependencyScenario, list[SessionDependencyCandidate]]:
    trend_strength = sum([structure.daily_bullish, structure.h4_bullish, structure.h1_bullish])
    flow_conflict = (trend_strength >= 2 and not flow.delta_positive) or (trend_strength <= 1 and flow.delta_positive)

    score_map: dict[str, int] = {
        "C1": 0,
        "C2": 0,
        "C3": 0,
        "C4": 0,
        "C5": 0,
        "C6": 0,
        "C7": 1,
    }
    reasons_map: dict[str, list[str]] = {
        "C1": [],
        "C2": [],
        "C3": [],
        "C4": [],
        "C5": [],
        "C6": [],
        "C7": [],
    }

    if structure.sweep_confirmed:
        score_map["C1"] += 3
        reasons_map["C1"].append("Sweep is already confirmed")
        score_map["C5"] += 2
        reasons_map["C5"].append("Sweep condition supports raid/both-sides profile")
        score_map["C7"] += 1
        reasons_map["C7"].append("Sweep direction creates mild close bias")
    else:
        score_map["C6"] += 1
        reasons_map["C6"].append("No clean London sweep yet")

    if structure.m15_choch_waiting:
        score_map["C1"] += 2
        reasons_map["C1"].append("Waiting CHoCH stage matches manipulation phase")
        score_map["C4"] += 1
        reasons_map["C4"].append("No break confirmation increases range probability")
        score_map["C5"] += 2
        reasons_map["C5"].append("Unclear break can evolve into double-sweep")
        score_map["C6"] += 1
        reasons_map["C6"].append("Late trap behavior likely around NY open")

    if trend_strength >= 3:
        score_map["C2"] += 3
        reasons_map["C2"].append("Strong Daily/H4/H1 directional alignment")

    if abs(total_score) >= 18:
        score_map["C2"] += 2
        reasons_map["C2"].append("Momentum score supports continuation")
    if abs(total_score) >= 24:
        score_map["C3"] += 2
        reasons_map["C3"].append("Extension score is elevated")

    if flow.delta_positive:
        score_map["C2"] += 1
        reasons_map["C2"].append("Positive delta supports continuation")
    else:
        score_map["C3"] += 1
        reasons_map["C3"].append("Negative delta can signal exhaustion")

    if flow_conflict:
        score_map["C3"] += 2
        reasons_map["C3"].append("Order-flow conflicts with higher timeframe trend")
        score_map["C5"] += 2
        reasons_map["C5"].append("Conflict profile often appears in sweep/reversal days")

    if probs.range >= 26 or abs(total_score) <= 8:
        score_map["C4"] += 3
        reasons_map["C4"].append("Range probability is elevated")
    if probs.range >= 20 and abs(total_score) <= 12:
        score_map["C7"] += 2
        reasons_map["C7"].append("Bias edge is weak without stronger confirmation")

    if flow.news_risk_high:
        score_map["C6"] += 3
        reasons_map["C6"].append("High-impact news shifts manipulation into NY open")
        score_map["C3"] += 1
        reasons_map["C3"].append("News can trigger overextension then reversal")

    if macro.vix_change_pct > 2.0:
        score_map["C3"] += 1
        reasons_map["C3"].append("Risk-off volatility favors sharp reversals")

    scenarios: dict[str, tuple[str, str, str]] = {
        "C1": (
            "Classic AMD",
            "NY distribution opposite to London sweep",
            "NY AM killzone retrace into London POI/FVG",
        ),
        "C2": (
            "London Continuation",
            "Continuation bias into NY if ADR is not exhausted",
            "Continuation setup with pullback entry",
        ),
        "C3": (
            "Overextended -> NY Reversal",
            "Higher chance for reversal/redistribution in NY",
            "Fade London extreme near premium/discount HTF zone",
        ),
        "C4": (
            "Double Accumulation / Z-Day",
            "Low-quality distribution, range/scalper conditions",
            "Avoid trend chasing; favor mean-revert",
        ),
        "C5": (
            "Double-Sweep / Raid Both Sides",
            "Potential large move after second sweep + MSS",
            "Wait second raid confirmation before commit",
        ),
        "C6": (
            "Late London Trap -> NY Open Manip",
            "NY open manipulation likely before expansion",
            "Wait NY open sweep then follow expansion",
        ),
        "C7": (
            "Sweep-Direction Bias (Calibration)",
            "Only mild directional edge; needs HTF + MSS",
            "Use as filter, not standalone trigger",
        ),
    }

    best_code = max(score_map, key=score_map.get)
    best_score = score_map[best_code]

    if best_score >= 7:
        conviction = "HI"
    elif best_score >= 5:
        conviction = "MED-HI"
    elif best_score >= 3:
        conviction = "MED"
    else:
        conviction = "WEAK"

    normalized_confidence = round(min(95.0, max(45.0, 45.0 + best_score * 6.5)), 2)
    title, expected_ny, setup_hint = scenarios[best_code]
    why = reasons_map[best_code] if reasons_map[best_code] else ["Base profile selected by default calibration"]

    primary = SessionDependencyScenario(
        code=best_code,
        title=title,
        conviction=conviction,
        confidence=normalized_confidence,
        expected_ny=expected_ny,
        setup_hint=setup_hint,
        why=why,
    )

    sorted_codes = sorted(score_map.keys(), key=lambda code: score_map[code], reverse=True)
    secondary_code = sorted_codes[1] if len(sorted_codes) > 1 else None

    candidates: list[SessionDependencyCandidate] = []
    for code in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]:
        c_title, c_expected_ny, _ = scenarios[code]
        c_score = score_map[code]
        c_confidence = round(min(95.0, max(35.0, 35.0 + c_score * 7.0)), 2)
        if c_score >= 7:
            c_conviction = "HI"
        elif c_score >= 5:
            c_conviction = "MED-HI"
        elif c_score >= 3:
            c_conviction = "MED"
        else:
            c_conviction = "WEAK"

        candidates.append(
            SessionDependencyCandidate(
                code=code,
                title=c_title,
                conviction=c_conviction,
                confidence=c_confidence,
                expected_ny=c_expected_ny,
                is_active=(code == best_code),
                is_secondary=(code == secondary_code),
            )
        )

    return primary, candidates


def _build_confluence(macro: MacroInputs, structure: StructureInputs, flow: FlowInputs) -> list[ConfluenceSignal]:
    return [
        ConfluenceSignal(
            name="DXY pressure",
            status="bullish" if macro.dxy_change_pct < 0 else "bearish",
            note="Weak DXY supports gold; strong DXY caps upside.",
        ),
        ConfluenceSignal(
            name="Real yields",
            status="bullish" if macro.us10y_change_bps < 0 else "bearish",
            note="Falling yields usually improve gold demand.",
        ),
        ConfluenceSignal(
            name="Oil and inflation pulse",
            status="bullish" if macro.oil_change_pct < 0 else "neutral",
            note="Cooling oil can ease inflation expectations.",
        ),
        ConfluenceSignal(
            name="Structure alignment",
            status="bullish" if structure.daily_bullish and structure.h4_bullish and structure.h1_bullish else "neutral",
            note="Daily/H4/H1 agreement increases directional quality.",
        ),
        ConfluenceSignal(
            name="Order-flow delta",
            status="bullish" if flow.delta_positive else "bearish",
            note="Directional moves are healthier with positive delta.",
        ),
        ConfluenceSignal(
            name="Event risk",
            status="bearish" if flow.news_risk_high else "neutral",
            note="High-impact events can reduce setup reliability.",
        ),
    ]


def _build_limit_orders(setup: TradeSetup, goldbach_entries: list[GoldbachEntrySignal]) -> list[LimitOrderPlan]:
    if goldbach_entries:
        from_goldbach: list[LimitOrderPlan] = []
        for signal in goldbach_entries[:3]:
            from_goldbach.append(
                LimitOrderPlan(
                    label=f"Goldbach: {signal.label}",
                    side=signal.side,
                    entry=round(signal.entry, 2),
                    stop_loss=round(signal.stop_loss, 2),
                    risk_usd=round(abs(signal.entry - signal.stop_loss), 2),
                    tp1=round(signal.tp1, 2),
                    tp2=round(signal.tp2, 2),
                    tp3=round(signal.tp3, 2),
                    rr1=signal.rr1,
                    rr2=signal.rr2,
                    rr3=signal.rr3,
                    enabled=signal.score >= 55.0,
                )
            )
        return from_goldbach

    risk_unit = abs(setup.entry - setup.stop_loss)
    risk_usd = round(risk_unit, 2)

    if setup.direction == "long":
        alt_entry = round(setup.entry - 8.0, 2)
        alt_stop = round(alt_entry - 8.0, 2)
        fade_entry = round(setup.tp2 + 2.0, 2)
        fade_stop = round(fade_entry + 10.0, 2)
        fade_tp1 = round(setup.tp1, 2)
        fade_tp2 = round(setup.entry, 2)
        fade_tp3 = round(setup.stop_loss + 2.0, 2)
        side_primary = "buy"
        side_fade = "sell"
    else:
        alt_entry = round(setup.entry + 8.0, 2)
        alt_stop = round(alt_entry + 8.0, 2)
        fade_entry = round(setup.tp2 - 2.0, 2)
        fade_stop = round(fade_entry - 10.0, 2)
        fade_tp1 = round(setup.tp1, 2)
        fade_tp2 = round(setup.entry, 2)
        fade_tp3 = round(setup.stop_loss - 2.0, 2)
        side_primary = "sell"
        side_fade = "buy"

    primary = LimitOrderPlan(
        label="Primary retest",
        side=side_primary,
        entry=round(setup.entry, 2),
        stop_loss=round(setup.stop_loss, 2),
        risk_usd=risk_usd,
        tp1=round(setup.tp1, 2),
        tp2=round(setup.tp2, 2),
        tp3=round(setup.tp3, 2),
        rr1=_rr(setup.entry, setup.stop_loss, setup.tp1),
        rr2=_rr(setup.entry, setup.stop_loss, setup.tp2),
        rr3=_rr(setup.entry, setup.stop_loss, setup.tp3),
        enabled=True,
    )

    judas = LimitOrderPlan(
        label="Deeper sweep entry",
        side=side_primary,
        entry=alt_entry,
        stop_loss=alt_stop,
        risk_usd=round(abs(alt_entry - alt_stop), 2),
        tp1=round(setup.entry, 2),
        tp2=round(setup.tp1, 2),
        tp3=round(setup.tp2, 2),
        rr1=_rr(alt_entry, alt_stop, setup.entry),
        rr2=_rr(alt_entry, alt_stop, setup.tp1),
        rr3=_rr(alt_entry, alt_stop, setup.tp2),
        enabled=True,
    )

    fade = LimitOrderPlan(
        label="Extension fade scalp",
        side=side_fade,
        entry=fade_entry,
        stop_loss=fade_stop,
        risk_usd=round(abs(fade_entry - fade_stop), 2),
        tp1=fade_tp1,
        tp2=fade_tp2,
        tp3=fade_tp3,
        rr1=_rr(fade_entry, fade_stop, fade_tp1),
        rr2=_rr(fade_entry, fade_stop, fade_tp2),
        rr3=_rr(fade_entry, fade_stop, fade_tp3),
        enabled=True,
    )

    return [primary, judas, fade]


def _build_trading_intelligence(
    current_price: float,
    structure: StructureInputs,
    flow: FlowInputs,
    probs: Probability,
    setup: TradeSetup,
    goldbach: GoldbachRange,
    goldbach_entries: list[GoldbachEntrySignal],
) -> TradingIntelligence:
    trend_votes = sum([structure.daily_bullish, structure.h4_bullish, structure.h1_bullish])
    alignment_score = round((trend_votes / 3.0) * 100.0, 2)

    if probs.range >= 30.0:
        regime = "range"
    elif trend_votes == 3 and probs.bull >= 50.0:
        regime = "bullish"
    elif trend_votes == 0 and probs.bear >= 50.0:
        regime = "bearish"
    else:
        regime = "transitional"

    market_structure = MarketStructureIntel(
        regime=regime,
        alignment_score=alignment_score,
        choch_state="waiting" if structure.m15_choch_waiting else "confirmed",
        sweep_state="confirmed" if structure.sweep_confirmed else "pending",
        narrative=(
            f"HTF alignment {alignment_score}% with {regime.upper()} regime. "
            f"CHoCH is {'awaiting confirmation' if structure.m15_choch_waiting else 'already confirmed'} "
            f"and liquidity sweep is {'in place' if structure.sweep_confirmed else 'still pending'}."
        ),
    )

    pool_above_points = round(max(0.0, goldbach.ext_high_plus - current_price), 2)
    pool_below_points = round(max(0.0, current_price - goldbach.ext_low_minus), 2)
    if abs(pool_above_points - pool_below_points) <= 0.25:
        nearest_side = "balanced"
    elif pool_above_points < pool_below_points:
        nearest_side = "above"
    else:
        nearest_side = "below"

    liquidity = LiquidityIntel(
        nearest_side=nearest_side,
        pool_above_points=pool_above_points,
        pool_below_points=pool_below_points,
        premium_zone=f"{goldbach.sub_high}-{goldbach.ext_high_plus}",
        discount_zone=f"{goldbach.ext_low_minus}-{goldbach.sub_low}",
        narrative=(
            f"Nearest external liquidity is {nearest_side.upper()} with "
            f"{pool_above_points} pts above and {pool_below_points} pts below. "
            "Use premium/discount thirds to frame sweep-to-expansion entries."
        ),
    )

    continuation = probs.bull if setup.direction == "long" else probs.bear
    continuation += 4.0 if flow.delta_positive else -4.0
    reversal = (probs.bear if setup.direction == "long" else probs.bull) + (6.0 if flow.news_risk_high else 2.0)
    mean_reversion = probs.range + (6.0 if structure.m15_choch_waiting else 0.0)

    continuation = max(1.0, continuation)
    reversal = max(1.0, reversal)
    mean_reversion = max(1.0, mean_reversion)
    total = continuation + reversal + mean_reversion
    continuation_n = round((continuation / total) * 100.0, 2)
    reversal_n = round((reversal / total) * 100.0, 2)
    mean_rev_n = round((mean_reversion / total) * 100.0, 2)
    top_prob = max(continuation_n, reversal_n, mean_rev_n)

    if top_prob >= 55.0:
        confidence_band = "HIGH"
    elif top_prob >= 42.0:
        confidence_band = "MED"
    else:
        confidence_band = "LOW"

    probability_engine = ProbabilityEngineIntel(
        continuation=continuation_n,
        reversal=reversal_n,
        mean_reversion=mean_rev_n,
        confidence_band=confidence_band,
        narrative=(
            f"Continuation {continuation_n}%, Reversal {reversal_n}%, Mean-reversion {mean_rev_n}%. "
            f"Confidence band is {confidence_band} given current flow and structure conditions."
        ),
    )

    primary = goldbach_entries[0] if goldbach_entries else None
    secondary = goldbach_entries[1] if len(goldbach_entries) > 1 else None

    if primary:
        primary_setup = f"{primary.side.upper()} {primary.label} @ {primary.entry}"
        trigger = (
            f"Trigger on reaction at {primary.anchor_level} with directional confirmation; "
            f"then execute toward TP2 {primary.tp2}."
        )
        invalidation = f"Invalidate on clean break through {primary.stop_loss} with no immediate reclaim."
    else:
        primary_setup = f"{setup.direction.upper()} baseline setup @ {setup.entry}"
        trigger = "Trigger after confirmation candle in setup direction."
        invalidation = f"Invalidate on stop-loss breach at {setup.stop_loss}."

    secondary_setup = (
        f"{secondary.side.upper()} {secondary.label} @ {secondary.entry}"
        if secondary
        else "No secondary setup ranked"
    )

    setup_generator = SetupGeneratorIntel(
        primary_setup=primary_setup,
        secondary_setup=secondary_setup,
        trigger=trigger,
        invalidation=invalidation,
        execution_note=(
            f"Use {setup.direction.upper()} bias with staged exits at TP1/TP2/TP3. "
            f"Current engine probability: {setup.probability}%."
        ),
    )

    structure_component = alignment_score
    liquidity_component = 100.0 - (abs(pool_above_points - pool_below_points) * 1.2)
    liquidity_component = max(20.0, min(90.0, liquidity_component))
    probability_component = max(continuation_n, reversal_n, mean_rev_n)
    setup_component = goldbach_entries[0].score if goldbach_entries else 50.0

    overall_score = round(
        (structure_component * 0.25)
        + (liquidity_component * 0.20)
        + (probability_component * 0.25)
        + (setup_component * 0.30),
        2,
    )

    no_trade_threshold = 45.0
    if overall_score < no_trade_threshold:
        trade_filter = "NO-TRADE"
        no_trade_reason = "Edge is below threshold: structure/flow/setup alignment is weak."
    elif overall_score < 60.0:
        trade_filter = "CAUTION"
        no_trade_reason = "Edge is moderate: reduce size and require extra confirmation."
    else:
        trade_filter = "ACTIVE"
        no_trade_reason = None

    return TradingIntelligence(
        market_structure=market_structure,
        liquidity=liquidity,
        probability_engine=probability_engine,
        setup_generator=setup_generator,
        overall_score=overall_score,
        trade_filter=trade_filter,
        no_trade_threshold=no_trade_threshold,
        no_trade_reason=no_trade_reason,
    )


def generate_snapshot(
    current_price: float,
    macro: MacroInputs,
    structure: StructureInputs,
    flow: FlowInputs,
    price_source: str,
    price_live: bool,
    goldbach_po3_range: float = 27.0,
    goldbach_use_pips: bool = False,
    goldbach_tick_size: float = 0.25,
    goldbach_manual_range_low: float = 0.0,
    goldbach_manual_range_high: float = 0.0,
) -> AnalysisSnapshot:
    macro_score, macro_breakdown = _score_macro(macro)
    structure_score, structure_breakdown = _score_structure(structure)
    flow_score, flow_breakdown = _score_flow(flow)

    total_score = macro_score + structure_score + flow_score
    probs = _to_probabilities(total_score)
    confidence = round(min(95.0, max(55.0, 60 + abs(total_score) * 0.45)), 2)

    if probs.bull >= 60:
        bias = "bull"
        verdict = "buy" if not flow.news_risk_high else "wait"
    elif probs.bear >= 60:
        bias = "bear"
        verdict = "sell" if not flow.news_risk_high else "wait"
    else:
        bias = "range"
        verdict = "wait"

    baseline_direction = "long" if total_score >= 0 else "short"
    goldbach_range = _build_goldbach_range(
        current_price=current_price,
        po3_range=goldbach_po3_range,
        use_pips=goldbach_use_pips,
        tick_size=goldbach_tick_size,
        manual_range_low=goldbach_manual_range_low,
        manual_range_high=goldbach_manual_range_high,
    )
    goldbach_entries = _build_goldbach_entries(
        goldbach=goldbach_range,
        direction=baseline_direction,
        current_price=current_price,
        news_risk_high=flow.news_risk_high,
    )

    setup = _build_setup(current_price, total_score, goldbach_entries=goldbach_entries)

    summary = (
        f"Bias {bias.upper()} with confidence {confidence}%. "
        f"Macro+Structure+Flow score is {round(total_score, 2)}. "
        f"Primary action: {verdict.upper()}."
    )

    breakdown: dict[str, float] = {
        **macro_breakdown,
        **structure_breakdown,
        **flow_breakdown,
        "total_score": round(total_score, 2),
        "goldbach_top_entry_score": round(goldbach_entries[0].score, 2) if goldbach_entries else 0.0,
    }

    terrain = _build_price_terrain(current_price, setup, goldbach_range)
    sessions = _build_sessions(flow)
    session_dependency, session_dependency_candidates = _infer_session_dependency(
        structure=structure,
        flow=flow,
        macro=macro,
        probs=probs,
        total_score=total_score,
    )
    confluence = _build_confluence(macro, structure, flow)
    limit_orders = _build_limit_orders(setup, goldbach_entries)
    trading_intelligence = _build_trading_intelligence(
        current_price=current_price,
        structure=structure,
        flow=flow,
        probs=probs,
        setup=setup,
        goldbach=goldbach_range,
        goldbach_entries=goldbach_entries,
    )

    return AnalysisSnapshot(
        generated_at=datetime.now(timezone.utc),
        current_price=current_price,
        price_source=price_source,
        price_live=price_live,
        bias=bias,
        confidence=confidence,
        verdict=verdict,
        probabilities=probs,
        setup=setup,
        executive_summary=summary,
        score_breakdown=breakdown,
        price_terrain=terrain,
        sessions=sessions,
        session_dependency=session_dependency,
        session_dependency_candidates=session_dependency_candidates,
        goldbach_range=goldbach_range,
        goldbach_entries=goldbach_entries,
        trading_intelligence=trading_intelligence,
        confluence=confluence,
        limit_orders=limit_orders,
    )
