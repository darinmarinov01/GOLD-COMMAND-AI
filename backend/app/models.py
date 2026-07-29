from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


BiasType = Literal["bull", "range", "bear"]
VerdictType = Literal["buy", "wait", "sell"]


class MacroInputs(BaseModel):
    dxy_change_pct: float = Field(..., description="Daily DXY percent change")
    us10y_change_bps: float = Field(..., description="US10Y change in basis points")
    oil_change_pct: float = Field(..., description="Daily WTI percent change")
    silver_change_pct: float = Field(..., description="Daily Silver percent change")
    vix_change_pct: float = Field(..., description="Daily VIX percent change")
    fed_hawkish_score: float = Field(..., ge=0, le=100)


class StructureInputs(BaseModel):
    daily_bullish: bool
    h4_bullish: bool
    h1_bullish: bool
    m15_choch_waiting: bool
    sweep_confirmed: bool


class FlowInputs(BaseModel):
    delta_positive: bool
    smt_bullish: bool
    news_risk_high: bool


class Probability(BaseModel):
    bull: float
    range: float
    bear: float


class TradeSetup(BaseModel):
    direction: Literal["long", "short"]
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rr: float
    probability: float


class PriceTerrainLevel(BaseModel):
    zone: str
    kind: Literal["supply", "demand", "neutral", "regime", "current"]
    note: str


class SessionEvent(BaseModel):
    time_label: str
    title: str
    note: str
    importance: Literal["low", "medium", "high"]


class ConfluenceSignal(BaseModel):
    name: str
    status: Literal["bullish", "bearish", "neutral"]
    note: str


class LimitOrderPlan(BaseModel):
    label: str
    side: Literal["buy", "sell"]
    entry: float
    stop_loss: float
    risk_usd: float
    tp1: float
    tp2: float
    tp3: float
    rr1: float
    rr2: float
    rr3: float
    enabled: bool


class GoldbachRange(BaseModel):
    po3_range: float
    actual_range: float
    tick_size: float
    use_pips: bool
    range_low: float
    range_high: float
    eq: float
    ext_high_plus: float
    ext_high_minus: float
    ext_low_plus: float
    ext_low_minus: float
    sub_high: float
    sub_low: float
    sub_ext_high_plus: float
    sub_ext_high_minus: float
    sub_ext_low_plus: float
    sub_ext_low_minus: float
    prev_range_low: float
    prev_range_high: float
    next_range_low: float
    next_range_high: float


class GoldbachEntrySignal(BaseModel):
    label: str
    side: Literal["buy", "sell"]
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rr1: float
    rr2: float
    rr3: float
    score: float
    anchor_level: str
    reason: str


class MarketStructureIntel(BaseModel):
    regime: Literal["bullish", "bearish", "range", "transitional"]
    alignment_score: float
    choch_state: Literal["waiting", "confirmed"]
    sweep_state: Literal["confirmed", "pending"]
    narrative: str


class LiquidityIntel(BaseModel):
    nearest_side: Literal["above", "below", "balanced"]
    pool_above_points: float
    pool_below_points: float
    premium_zone: str
    discount_zone: str
    narrative: str


class ProbabilityEngineIntel(BaseModel):
    continuation: float
    reversal: float
    mean_reversion: float
    confidence_band: Literal["LOW", "MED", "HIGH"]
    narrative: str


class SetupGeneratorIntel(BaseModel):
    primary_setup: str
    secondary_setup: str
    trigger: str
    invalidation: str
    execution_note: str


class TradingIntelligence(BaseModel):
    market_structure: MarketStructureIntel
    liquidity: LiquidityIntel
    probability_engine: ProbabilityEngineIntel
    setup_generator: SetupGeneratorIntel
    overall_score: float
    trade_filter: Literal["ACTIVE", "CAUTION", "NO-TRADE"]
    no_trade_threshold: float
    no_trade_reason: Optional[str]


class SessionDependencyScenario(BaseModel):
    code: Literal["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    title: str
    conviction: Literal["WEAK", "MED", "MED-HI", "HI"]
    confidence: float
    expected_ny: str
    setup_hint: str
    why: list[str]


class SessionDependencyCandidate(BaseModel):
    code: Literal["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
    title: str
    conviction: Literal["WEAK", "MED", "MED-HI", "HI"]
    confidence: float
    expected_ny: str
    is_active: bool
    is_secondary: bool


class AnalysisSnapshot(BaseModel):
    generated_at: datetime
    symbol: str = "XAUUSD"
    current_price: float
    price_source: str
    price_live: bool
    bias: BiasType
    confidence: float
    verdict: VerdictType
    probabilities: Probability
    setup: TradeSetup
    executive_summary: str
    score_breakdown: dict[str, float]
    price_terrain: list[PriceTerrainLevel]
    sessions: list[SessionEvent]
    session_dependency: SessionDependencyScenario
    session_dependency_candidates: list[SessionDependencyCandidate]
    goldbach_range: GoldbachRange
    goldbach_entries: list[GoldbachEntrySignal]
    trading_intelligence: TradingIntelligence
    confluence: list[ConfluenceSignal]
    limit_orders: list[LimitOrderPlan]
