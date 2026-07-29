export type Verdict = "buy" | "wait" | "sell";
export type Bias = "bull" | "range" | "bear";

export interface Probability {
  bull: number;
  range: number;
  bear: number;
}

export interface TradeSetup {
  direction: "long" | "short";
  entry: number;
  stop_loss: number;
  tp1: number;
  tp2: number;
  tp3: number;
  rr: number;
  probability: number;
}

export interface PriceTerrainLevel {
  zone: string;
  kind: "supply" | "demand" | "neutral" | "regime" | "current";
  note: string;
}

export interface SessionEvent {
  time_label: string;
  title: string;
  note: string;
  importance: "low" | "medium" | "high";
}

export interface ConfluenceSignal {
  name: string;
  status: "bullish" | "bearish" | "neutral";
  note: string;
}

export interface LimitOrderPlan {
  label: string;
  side: "buy" | "sell";
  entry: number;
  stop_loss: number;
  risk_usd: number;
  tp1: number;
  tp2: number;
  tp3: number;
  rr1: number;
  rr2: number;
  rr3: number;
  enabled: boolean;
}

export interface SessionDependencyScenario {
  code: "C1" | "C2" | "C3" | "C4" | "C5" | "C6" | "C7";
  title: string;
  conviction: "WEAK" | "MED" | "MED-HI" | "HI";
  confidence: number;
  expected_ny: string;
  setup_hint: string;
  why: string[];
}

export interface SessionDependencyCandidate {
  code: "C1" | "C2" | "C3" | "C4" | "C5" | "C6" | "C7";
  title: string;
  conviction: "WEAK" | "MED" | "MED-HI" | "HI";
  confidence: number;
  expected_ny: string;
  is_active: boolean;
  is_secondary: boolean;
}

export interface GoldbachRange {
  po3_range: number;
  actual_range: number;
  tick_size: number;
  use_pips: boolean;
  range_low: number;
  range_high: number;
  eq: number;
  ext_high_plus: number;
  ext_high_minus: number;
  ext_low_plus: number;
  ext_low_minus: number;
  sub_high: number;
  sub_low: number;
  sub_ext_high_plus: number;
  sub_ext_high_minus: number;
  sub_ext_low_plus: number;
  sub_ext_low_minus: number;
  prev_range_low: number;
  prev_range_high: number;
  next_range_low: number;
  next_range_high: number;
}

export interface GoldbachEntrySignal {
  label: string;
  side: "buy" | "sell";
  entry: number;
  stop_loss: number;
  tp1: number;
  tp2: number;
  tp3: number;
  rr1: number;
  rr2: number;
  rr3: number;
  score: number;
  anchor_level: string;
  reason: string;
}

export interface MarketStructureIntel {
  regime: "bullish" | "bearish" | "range" | "transitional";
  alignment_score: number;
  choch_state: "waiting" | "confirmed";
  sweep_state: "confirmed" | "pending";
  narrative: string;
}

export interface LiquidityIntel {
  nearest_side: "above" | "below" | "balanced";
  pool_above_points: number;
  pool_below_points: number;
  premium_zone: string;
  discount_zone: string;
  narrative: string;
}

export interface ProbabilityEngineIntel {
  continuation: number;
  reversal: number;
  mean_reversion: number;
  confidence_band: "LOW" | "MED" | "HIGH";
  narrative: string;
}

export interface SetupGeneratorIntel {
  primary_setup: string;
  secondary_setup: string;
  trigger: string;
  invalidation: string;
  execution_note: string;
}

export interface TradingIntelligence {
  market_structure: MarketStructureIntel;
  liquidity: LiquidityIntel;
  probability_engine: ProbabilityEngineIntel;
  setup_generator: SetupGeneratorIntel;
  overall_score: number;
  trade_filter: "ACTIVE" | "CAUTION" | "NO-TRADE";
  no_trade_threshold: number;
  no_trade_reason: string | null;
}

export interface AnalysisSnapshot {
  generated_at: string;
  symbol: string;
  current_price: number;
  price_source: string;
  price_live: boolean;
  bias: Bias;
  confidence: number;
  verdict: Verdict;
  probabilities: Probability;
  setup: TradeSetup;
  executive_summary: string;
  score_breakdown: Record<string, number>;
  price_terrain: PriceTerrainLevel[];
  sessions: SessionEvent[];
  session_dependency: SessionDependencyScenario;
  session_dependency_candidates: SessionDependencyCandidate[];
  goldbach_range: GoldbachRange;
  goldbach_entries: GoldbachEntrySignal[];
  trading_intelligence: TradingIntelligence;
  confluence: ConfluenceSignal[];
  limit_orders: LimitOrderPlan[];
}

export interface ProviderStatus {
  configured_provider: string;
  price_source: string;
  price_live: boolean;
  sampled_price: number;
  sampled_at: string;
  manual_override_active: boolean;
  manual_override_price: number | null;
  manual_override_source: string | null;
}
