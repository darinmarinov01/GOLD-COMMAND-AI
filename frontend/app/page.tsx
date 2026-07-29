"use client";

import { useEffect, useMemo, useState } from "react";
import PriceChart from "../components/PriceChart";

import { fetchLatestAnalysis, fetchProviderStatus, generateAnalysis, setPriceOverride } from "../lib/api";
import type { AnalysisSnapshot, ConfluenceSignal, GoldbachEntrySignal, LimitOrderPlan, PriceTerrainLevel, ProviderStatus, SessionEvent } from "../types/analysis";

interface TimelineEvent {
  id: string;
  sourceTs: string;
  timeLabel: string;
  summary: string;
  mood: "up" | "down" | "flat";
}

interface ScenarioPlaybook {
  title: string;
  conditions: string[];
  trigger: string;
  invalidation: string;
  execution: string;
}

interface ContextMenuState {
  x: number;
  y: number;
  kind: "scenario" | "entry";
  scenarioCode?: string;
  entry?: GoldbachEntrySignal;
}

type ContextAction =
  | "select_scenario"
  | "copy_scenario"
  | "copy_entry"
  | "copy_entry_json"
  | "override_entry"
  | "risk_025"
  | "risk_050"
  | "risk_100"
  | "set_account_size"
  | "copy_position_size"
  | "copy_alert_template";

const SESSION_PLAYBOOKS: Record<string, ScenarioPlaybook> = {
  C1: {
    title: "Classic AMD",
    conditions: [
      "Asia in tight accumulation",
      "London sweeps one side and shows MSS shift",
      "NY expected to distribute opposite of the sweep",
    ],
    trigger: "Wait NY AM killzone retrace into London POI/FVG with rejection.",
    invalidation: "No MSS follow-through or reclaim of sweep side with strong delta.",
    execution: "Scale-in after retest confirmation; prioritize first expansion leg.",
  },
  C2: {
    title: "London Continuation",
    conditions: [
      "Asia already directional/manipulative",
      "London continues in same direction",
      "ADR still has room",
    ],
    trigger: "Continuation pullback in trend direction during NY overlap.",
    invalidation: "ADR exhausted and delta divergence appears near London extreme.",
    execution: "Trade with trend, partial at intraday extension levels.",
  },
  C3: {
    title: "Overextended -> NY Reversal",
    conditions: [
      "London extension is aggressive",
      "Price reaches HTF premium/discount array",
      "Flow starts diverging against move",
    ],
    trigger: "NY open rejection + MSS against London extension.",
    invalidation: "Extension keeps printing higher highs/lower lows with strong confirming delta.",
    execution: "Fade extremum with tight risk; expect redistribution rather than immediate trend day.",
  },
  C4: {
    title: "Double Accumulation / Z-Day",
    conditions: [
      "Asia range persists",
      "London also remains balanced without clean break",
      "No directional displacement",
    ],
    trigger: "Only mean-revert setups at range edges.",
    invalidation: "Sudden displacement + sweep + MSS breaks equilibrium.",
    execution: "Lower size or skip trend trades; protect capital.",
  },
  C5: {
    title: "Double-Sweep / Raid Both Sides",
    conditions: [
      "Tight Asia range",
      "Both sides of liquidity get raided",
      "Second sweep creates asymmetry",
    ],
    trigger: "Enter only after second sweep confirmation and structure shift.",
    invalidation: "No follow-through after second raid; returns to midpoint equilibrium.",
    execution: "Expect larger expansion, but wait confirmation to avoid chop.",
  },
  C6: {
    title: "Late London Trap -> NY Open Manip",
    conditions: [
      "London manipulation is weak/scruffy",
      "No clean directional break before NY",
      "NY open likely performs true sweep",
    ],
    trigger: "NY open sweep into HTF discount/premium then MSS return.",
    invalidation: "NY fails to reverse sweep and keeps trending in sweep direction.",
    execution: "Be patient for NY open impulse; avoid chasing late London noise.",
  },
  C7: {
    title: "Sweep Direction Bias (Calibration)",
    conditions: [
      "Only sweep-direction bias is present",
      "No strong HTF alignment",
      "No solid MSS follow-through",
    ],
    trigger: "Use as filter with additional confluence only.",
    invalidation: "Treat as invalid if traded standalone without HTF + flow support.",
    execution: "Do not run as primary setup; pair with C1-C3 logic.",
  },
};

function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}

function verdictClass(verdict: string): string {
  if (verdict === "buy") return "badge buy";
  if (verdict === "sell") return "badge sell";
  return "badge wait";
}

function terrainClass(kind: PriceTerrainLevel["kind"]): string {
  return `terrain-level ${kind}`;
}

function confluenceClass(status: ConfluenceSignal["status"]): string {
  if (status === "bullish") return "signal bullish";
  if (status === "bearish") return "signal bearish";
  return "signal neutral";
}

function sessionClass(level: SessionEvent["importance"]): string {
  return `session-item ${level}`;
}

function dependencyBadgeClass(conviction: string): string {
  if (conviction === "HI") return "dependency-badge hi";
  if (conviction === "MED-HI") return "dependency-badge medhi";
  if (conviction === "MED") return "dependency-badge med";
  return "dependency-badge weak";
}

function dependencyRowClass(isActive: boolean, isSecondary: boolean): string {
  if (isActive) return "dependency-matrix-row active";
  if (isSecondary) return "dependency-matrix-row secondary";
  return "dependency-matrix-row";
}

function intelBandClass(band: "LOW" | "MED" | "HIGH"): string {
  if (band === "HIGH") return "dependency-badge hi";
  if (band === "MED") return "dependency-badge medhi";
  return "dependency-badge weak";
}

function tradeFilterClass(filter: "ACTIVE" | "CAUTION" | "NO-TRADE"): string {
  if (filter === "ACTIVE") return "dependency-badge hi";
  if (filter === "CAUTION") return "dependency-badge medhi";
  return "dependency-badge weak";
}

function signed(value: number, digits = 2): string {
  const formatted = value.toFixed(digits);
  return value > 0 ? `+${formatted}` : formatted;
}

function buildTimelineEvent(previous: AnalysisSnapshot | null, next: AnalysisSnapshot): TimelineEvent {
  const timeLabel = new Date(next.generated_at).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" });

  if (!previous) {
    return {
      id: next.generated_at,
      sourceTs: next.generated_at,
      timeLabel,
      mood: "flat",
      summary: `Initial snapshot loaded at ${num(next.current_price)} with ${next.verdict.toUpperCase()} verdict.`,
    };
  }

  const changes: string[] = [];

  if (previous.verdict !== next.verdict) {
    changes.push(`verdict ${previous.verdict.toUpperCase()} -> ${next.verdict.toUpperCase()}`);
  }

  if (previous.bias !== next.bias) {
    changes.push(`bias ${previous.bias.toUpperCase()} -> ${next.bias.toUpperCase()}`);
  }

  const confidenceDelta = next.confidence - previous.confidence;
  if (Math.abs(confidenceDelta) >= 0.5) {
    changes.push(`confidence ${signed(confidenceDelta)}%`);
  }

  const bullDelta = next.probabilities.bull - previous.probabilities.bull;
  if (Math.abs(bullDelta) >= 0.5) {
    changes.push(`bull prob ${signed(bullDelta)}%`);
  }

  const totalBefore = previous.score_breakdown.total_score ?? 0;
  const totalAfter = next.score_breakdown.total_score ?? 0;
  const totalDelta = totalAfter - totalBefore;
  if (Math.abs(totalDelta) >= 0.5) {
    changes.push(`score ${signed(totalDelta)}`);
  }

  const entryDelta = next.setup.entry - previous.setup.entry;
  if (Math.abs(entryDelta) >= 0.25) {
    changes.push(`entry ${signed(entryDelta)}`);
  }

  if (changes.length === 0) {
    changes.push("No material change in the hourly state.");
  }

  const mood: TimelineEvent["mood"] = totalDelta > 0.5 ? "up" : totalDelta < -0.5 ? "down" : "flat";

  return {
    id: next.generated_at,
    sourceTs: next.generated_at,
    timeLabel,
    summary: changes.join(" | "),
    mood,
  };
}

export default function HomePage() {
  const [snapshot, setSnapshot] = useState<AnalysisSnapshot | null>(null);
  const [history, setHistory] = useState<AnalysisSnapshot[]>([]);
  const [liveTape, setLiveTape] = useState<Array<{ time: number; value: number }>>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);
  const [selectedDependencyCode, setSelectedDependencyCode] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [riskPercent, setRiskPercent] = useState(0.5);
  const [accountSizeUsd, setAccountSizeUsd] = useState(10000);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function ingestSnapshot(next: AnalysisSnapshot) {
    setSnapshot((previous) => {
      if (previous && previous.generated_at === next.generated_at) {
        return previous;
      }

      const event = buildTimelineEvent(previous, next);
      setTimeline((current) => {
        const sameTsCount = current.filter((item) => item.sourceTs === event.sourceTs).length;
        const uniqueEvent: TimelineEvent = {
          ...event,
          id: `${event.sourceTs}-${sameTsCount + 1}`,
        };
        return [uniqueEvent, ...current].slice(0, 16);
      });
      return next;
    });

    setHistory((current) => {
      if (current.some((item) => item.generated_at === next.generated_at)) {
        return current;
      }
      return [...current, next].slice(-120);
    });
  }

  function ingestLivePoint(nextSnapshot: AnalysisSnapshot, provider: ProviderStatus | null) {
    const ts = provider ? new Date(provider.sampled_at).getTime() : new Date(nextSnapshot.generated_at).getTime();
    const value = provider ? provider.sampled_price : nextSnapshot.current_price;

    if (!Number.isFinite(ts) || !Number.isFinite(value)) return;

    setLiveTape((current) => {
      const last = current[current.length - 1];
      if (last && Math.abs(last.time - ts) < 500 && Math.abs(last.value - value) < 0.00001) {
        return current;
      }

      const nextPoint = { time: ts, value };
      return [...current, nextPoint].slice(-360);
    });
  }

  async function loadLatest() {
    setError(null);
    const [next, provider] = await Promise.all([fetchLatestAnalysis(), fetchProviderStatus()]);
    ingestSnapshot(next);
    ingestLivePoint(next, provider);
    setProviderStatus(provider);
  }

  async function onGenerate() {
    try {
      setBusy(true);
      setError(null);
      const [next, provider] = await Promise.all([generateAnalysis(), fetchProviderStatus()]);
      ingestSnapshot(next);
      ingestLivePoint(next, provider);
      setProviderStatus(provider);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let active = true;

    async function boot() {
      try {
        await loadLatest();
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Cannot load dashboard data");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    boot();

    const timer = setInterval(() => {
      loadLatest().catch((err) => {
        setError(err instanceof Error ? err.message : "Cannot refresh dashboard data");
      });
    }, 60000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;

    async function tickTape() {
      try {
        const provider = await fetchProviderStatus();
        if (!active) return;

        setProviderStatus(provider);
        if (snapshot) {
          ingestLivePoint(snapshot, provider);
        }
      } catch {
        // Keep the main dashboard loop responsible for user-facing fetch errors.
      }
    }

    const timer = setInterval(() => {
      tickTape();
    }, 15000);

    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [snapshot]);

  const generatedLabel = useMemo(() => {
    if (!snapshot) return "-";
    return new Date(snapshot.generated_at).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" });
  }, [snapshot]);

  const chartPoints = useMemo(() => {
    if (liveTape.length > 0) {
      return liveTape;
    }

    const source = history.length > 0 ? history : snapshot ? [snapshot] : [];
    return source.map((item) => ({
      time: new Date(item.generated_at).getTime(),
      value: item.current_price,
    }));
  }, [liveTape, history, snapshot]);

  const headerFeedClass = providerStatus?.price_live ? "feed-badge live" : "feed-badge fallback";
  const headerFeedLabel = providerStatus?.price_live ? "LIVE FEED" : "FALLBACK";

  useEffect(() => {
    if (!snapshot) return;
    setSelectedDependencyCode((current) => current ?? snapshot.session_dependency.code);
  }, [snapshot]);

  useEffect(() => {
    function closeMenu() {
      setContextMenu(null);
    }

    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeMenu();
      }
    }

    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("keydown", onEscape);

    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("keydown", onEscape);
    };
  }, []);

  function openScenarioMenu(event: React.MouseEvent, scenarioCode: string) {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      kind: "scenario",
      scenarioCode,
    });
  }

  function openEntryMenu(event: React.MouseEvent, entry: GoldbachEntrySignal) {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      kind: "entry",
      entry,
    });
  }

  async function copyToClipboard(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Ignore clipboard failures in restricted browsers.
    }
  }

  function calculatePositionSize(entry: GoldbachEntrySignal): {
    riskUsd: number;
    stopDistance: number;
    unitsOz: number;
    standardLots: number;
    miniLots: number;
    microLots: number;
  } {
    const riskUsd = accountSizeUsd * (riskPercent / 100.0);
    const stopDistance = Math.abs(entry.entry - entry.stop_loss);
    const unitsOz = stopDistance > 0 ? riskUsd / stopDistance : 0;

    // Common XAU sizing convention: 1 standard lot = 100 oz, mini = 10 oz, micro = 1 oz.
    const standardLots = unitsOz / 100.0;
    const miniLots = unitsOz / 10.0;
    const microLots = unitsOz;

    return {
      riskUsd,
      stopDistance,
      unitsOz,
      standardLots,
      miniLots,
      microLots,
    };
  }

  function buildAlertTemplate(entry: GoldbachEntrySignal): string {
    const sideText = entry.side.toUpperCase();
    return [
      `ALERT | ${sideText} | ${entry.label}`,
      `Entry=${num(entry.entry)} SL=${num(entry.stop_loss)} TP1=${num(entry.tp1)} TP2=${num(entry.tp2)} TP3=${num(entry.tp3)}`,
      `Anchor=${entry.anchor_level} Quality=${num(entry.score)}% RR2=${num(entry.rr2)}`,
      `Invalidation: Break through SL with displacement candle and confirming delta.`,
    ].join("\n");
  }

  async function handleContextAction(action: ContextAction) {
    if (!contextMenu) return;
    if (!snapshot) return;

    if (action === "risk_025") {
      setRiskPercent(0.25);
      return;
    }

    if (action === "risk_050") {
      setRiskPercent(0.5);
      return;
    }

    if (action === "risk_100") {
      setRiskPercent(1.0);
      return;
    }

    if (action === "set_account_size") {
      const answer = window.prompt("Account size (USD)", String(accountSizeUsd));
      if (answer) {
        const parsed = Number(answer);
        if (Number.isFinite(parsed) && parsed > 0) {
          setAccountSizeUsd(parsed);
        }
      }
      return;
    }

    if (action === "select_scenario" && contextMenu.scenarioCode) {
      setSelectedDependencyCode(contextMenu.scenarioCode);
      setContextMenu(null);
      return;
    }

    if (action === "copy_scenario" && contextMenu.scenarioCode) {
      const item = snapshot.session_dependency_candidates.find((candidate) => candidate.code === contextMenu.scenarioCode);
      const playbook = SESSION_PLAYBOOKS[contextMenu.scenarioCode];
      if (item && playbook) {
        await copyToClipboard(
          [
            `Scenario ${item.code}: ${item.title}`,
            `Expected NY: ${item.expected_ny}`,
            `Conviction: ${item.conviction} | Confidence: ${num(item.confidence)}%`,
            `Trigger: ${playbook.trigger}`,
            `Invalidation: ${playbook.invalidation}`,
            `Execution: ${playbook.execution}`,
          ].join("\n")
        );
      }
      setContextMenu(null);
      return;
    }

    if (
      (
        action === "copy_entry"
        || action === "copy_entry_json"
        || action === "override_entry"
        || action === "copy_position_size"
        || action === "copy_alert_template"
      )
      && contextMenu.entry
    ) {
      const entry = contextMenu.entry;

      if (action === "copy_entry") {
        await copyToClipboard(
          [
            `${entry.label} (${entry.side.toUpperCase()})`,
            `Entry: ${num(entry.entry)} | SL: ${num(entry.stop_loss)}`,
            `TPs: ${num(entry.tp1)} / ${num(entry.tp2)} / ${num(entry.tp3)}`,
            `RR2: ${num(entry.rr2)} | Score: ${num(entry.score)}%`,
            `Anchor: ${entry.anchor_level}`,
          ].join("\n")
        );
      } else if (action === "copy_entry_json") {
        await copyToClipboard(JSON.stringify(entry, null, 2));
      } else if (action === "copy_position_size") {
        const sizing = calculatePositionSize(entry);
        await copyToClipboard(
          [
            `${entry.label} (${entry.side.toUpperCase()})`,
            `Account: $${num(accountSizeUsd)} | Risk: ${num(riskPercent, 2)}% | Risk$=${num(sizing.riskUsd)}`,
            `Entry: ${num(entry.entry)} | SL: ${num(entry.stop_loss)} | StopDist: ${num(sizing.stopDistance)}`,
            `Position Size (oz): ${num(sizing.unitsOz, 3)}`,
            `Standard lot (100 oz): ${num(sizing.standardLots, 3)}`,
            `Mini lot (10 oz): ${num(sizing.miniLots, 3)}`,
            `Micro lot (1 oz): ${num(sizing.microLots, 3)}`,
            `Note: Lot contract size can vary by broker/instrument symbol.`,
          ].join("\n")
        );
      } else if (action === "copy_alert_template") {
        await copyToClipboard(buildAlertTemplate(entry));
      } else if (action === "override_entry") {
        try {
          await setPriceOverride(entry.entry, `goldbach_${entry.anchor_level}`);
          const provider = await fetchProviderStatus(true);
          setProviderStatus(provider);
        } catch (err) {
          setError(err instanceof Error ? err.message : "Cannot set manual override");
        }
      }
    }

    setContextMenu(null);
  }

  if (loading) {
    return (
      <main className="wrap">
        <section className="panel">
          <div className="sec-title">LOADING DASHBOARD</div>
          <p className="muted">Fetching latest analysis snapshot...</p>
        </section>
      </main>
    );
  }

  if (!snapshot) {
    return (
      <main className="wrap">
        <section className="panel">
          <div className="sec-title">NO DATA</div>
          <p className="muted">Cannot load data from backend API.</p>
          {error ? <p className="error-box">{error}</p> : null}
        </section>
      </main>
    );
  }

  return (
    <main className="wrap">
      <header className="header">
        <div className="header-top">GOLD COMMAND AI · NEXT DASHBOARD</div>
        <div className="header-sub">
          {snapshot.symbol} · Updated {generatedLabel} · Rule Engine Active
        </div>
        <div className="header-status">
          <span className={headerFeedClass}>{headerFeedLabel}</span>
          {providerStatus ? <span className="header-source">{providerStatus.price_source}</span> : null}
          <span className={`ti-score-badge ${snapshot.trading_intelligence.overall_score >= 60 ? "up" : snapshot.trading_intelligence.overall_score >= snapshot.trading_intelligence.no_trade_threshold ? "nt" : "dn"}`}>
            TI {num(snapshot.trading_intelligence.overall_score)}
          </span>
          <span className={tradeFilterClass(snapshot.trading_intelligence.trade_filter)}>
            {snapshot.trading_intelligence.trade_filter}
          </span>
        </div>
      </header>

      <section className="hero">
        <div className="hero-label">Current Price</div>
        <div className="hero-price">${num(snapshot.current_price)}</div>
        <div className="hero-note">{snapshot.executive_summary}</div>
        <div className="hero-note">
          Source: {snapshot.price_source} · {snapshot.price_live ? "LIVE FEED" : "FALLBACK"}
        </div>
      </section>

      <section className="panel provider-panel">
        <div className="sec-title">Provider Status</div>
        {providerStatus ? (
          <div className="provider-grid">
            <div><span>Configured:</span> <strong>{providerStatus.configured_provider.toUpperCase()}</strong></div>
            <div><span>Active Source:</span> <strong>{providerStatus.price_source}</strong></div>
            <div><span>Mode:</span> <strong className={providerStatus.price_live ? "up" : "dn"}>{providerStatus.price_live ? "LIVE" : "FALLBACK"}</strong></div>
            <div><span>Sampled Price:</span> <strong>{num(providerStatus.sampled_price, 5)}</strong></div>
            <div><span>Sampled At:</span> <strong>{new Date(providerStatus.sampled_at).toLocaleString("bg-BG", { timeZone: "Europe/Sofia" })}</strong></div>
            <div>
              <span>Manual Override:</span>{" "}
              <strong className={providerStatus.manual_override_active ? "up" : "nt"}>
                {providerStatus.manual_override_active ? `ON (${providerStatus.manual_override_price})` : "OFF"}
              </strong>
            </div>
          </div>
        ) : (
          <p className="muted">Provider status is loading...</p>
        )}
      </section>

      <section className="panel dependency-panel">
        <div className="sec-title">Session Dependency Matrix</div>
        <div className="dependency-head">
          <div className="dependency-code">{snapshot.session_dependency.code}</div>
          <div>
            <div className="dependency-title">{snapshot.session_dependency.title}</div>
            <div className="dependency-sub">
              Expected NY: {snapshot.session_dependency.expected_ny}
            </div>
          </div>
          <div className={dependencyBadgeClass(snapshot.session_dependency.conviction)}>
            {snapshot.session_dependency.conviction}
          </div>
        </div>
        <div className="dependency-row">
          <span>Model confidence</span>
          <strong>{num(snapshot.session_dependency.confidence)}%</strong>
        </div>
        <div className="dependency-row">
          <span>Setup hint</span>
          <strong>{snapshot.session_dependency.setup_hint}</strong>
        </div>
        <div className="dependency-why">
          {snapshot.session_dependency.why.map((item, idx) => (
            <div key={`${snapshot.session_dependency.code}-${idx}`} className="dependency-why-item">
              {item}
            </div>
          ))}
        </div>

        <div className="dependency-matrix">
          <div className="dependency-matrix-head">C1-C7 Matrix Board</div>
          {snapshot.session_dependency_candidates.map((item) => (
            <button
              type="button"
              key={item.code}
              className={`${dependencyRowClass(item.is_active, item.is_secondary)}${selectedDependencyCode === item.code ? " selected" : ""}`}
              onClick={() => setSelectedDependencyCode(item.code)}
              onContextMenu={(event) => openScenarioMenu(event, item.code)}
            >
              <div className="dependency-matrix-code">{item.code}</div>
              <div className="dependency-matrix-main">
                <div className="dependency-matrix-title">{item.title}</div>
                <div className="dependency-matrix-sub">{item.expected_ny}</div>
              </div>
              <div className="dependency-matrix-stats">
                <span>{num(item.confidence)}%</span>
                <span>{item.conviction}</span>
                {item.is_active ? <span className="tag-active">ACTIVE</span> : null}
                {item.is_secondary ? <span className="tag-secondary">SECONDARY</span> : null}
              </div>
            </button>
          ))}

          {selectedDependencyCode ? (
            <div className="dependency-playbook">
              <div className="dependency-playbook-title">
                Playbook: {selectedDependencyCode} · {SESSION_PLAYBOOKS[selectedDependencyCode].title}
              </div>
              <div className="dependency-playbook-block">
                <div className="dependency-playbook-label">If conditions</div>
                <ul>
                  {SESSION_PLAYBOOKS[selectedDependencyCode].conditions.map((condition) => (
                    <li key={`${selectedDependencyCode}-${condition}`}>{condition}</li>
                  ))}
                </ul>
              </div>
              <div className="dependency-playbook-line">
                <span>Trigger</span>
                <strong>{SESSION_PLAYBOOKS[selectedDependencyCode].trigger}</strong>
              </div>
              <div className="dependency-playbook-line">
                <span>Invalidation</span>
                <strong>{SESSION_PLAYBOOKS[selectedDependencyCode].invalidation}</strong>
              </div>
              <div className="dependency-playbook-line">
                <span>Execution</span>
                <strong>{SESSION_PLAYBOOKS[selectedDependencyCode].execution}</strong>
              </div>
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel chart-panel">
        <div className="sec-title">Live Price Tape</div>
        <PriceChart points={chartPoints} />
      </section>

      <section className="panel">
        <div className="sec-title">Trading Intelligence</div>
        <div className="dependency-row">
          <span>Overall Score / Threshold</span>
          <strong>
            {num(snapshot.trading_intelligence.overall_score)} / {num(snapshot.trading_intelligence.no_trade_threshold)}
          </strong>
        </div>
        <div className="dependency-row">
          <span>Trade Filter</span>
          <strong className={snapshot.trading_intelligence.trade_filter === "ACTIVE" ? "up" : snapshot.trading_intelligence.trade_filter === "CAUTION" ? "nt" : "dn"}>
            {snapshot.trading_intelligence.trade_filter}
          </strong>
        </div>
        {snapshot.trading_intelligence.no_trade_reason ? (
          <p className="muted intel-note">{snapshot.trading_intelligence.no_trade_reason}</p>
        ) : null}
        <div className="grid-two">
          <article className="panel intel-card">
            <div className="intel-head">
              <span>Market Structure</span>
              <strong className="nt">{snapshot.trading_intelligence.market_structure.regime.toUpperCase()}</strong>
            </div>
            <div className="dependency-row">
              <span>Alignment</span>
              <strong>{num(snapshot.trading_intelligence.market_structure.alignment_score)}%</strong>
            </div>
            <div className="dependency-row">
              <span>CHoCH / Sweep</span>
              <strong>
                {snapshot.trading_intelligence.market_structure.choch_state.toUpperCase()} / {snapshot.trading_intelligence.market_structure.sweep_state.toUpperCase()}
              </strong>
            </div>
            <p className="muted intel-note">{snapshot.trading_intelligence.market_structure.narrative}</p>
          </article>

          <article className="panel intel-card">
            <div className="intel-head">
              <span>Liquidity</span>
              <strong className="nt">{snapshot.trading_intelligence.liquidity.nearest_side.toUpperCase()}</strong>
            </div>
            <div className="dependency-row">
              <span>Pool Above / Below</span>
              <strong>
                {num(snapshot.trading_intelligence.liquidity.pool_above_points)} / {num(snapshot.trading_intelligence.liquidity.pool_below_points)} pts
              </strong>
            </div>
            <div className="dependency-row">
              <span>Premium / Discount</span>
              <strong>
                {snapshot.trading_intelligence.liquidity.premium_zone} / {snapshot.trading_intelligence.liquidity.discount_zone}
              </strong>
            </div>
            <p className="muted intel-note">{snapshot.trading_intelligence.liquidity.narrative}</p>
          </article>
        </div>

        <div className="grid-two">
          <article className="panel intel-card">
            <div className="intel-head">
              <span>Probability Engine</span>
              <span className={intelBandClass(snapshot.trading_intelligence.probability_engine.confidence_band)}>
                {snapshot.trading_intelligence.probability_engine.confidence_band}
              </span>
            </div>
            <div className="prob-row">
              <span>Continuation</span>
              <div className="bar-bg"><div className="bar bull" style={{ width: `${snapshot.trading_intelligence.probability_engine.continuation}%` }} /></div>
              <span>{num(snapshot.trading_intelligence.probability_engine.continuation)}%</span>
            </div>
            <div className="prob-row">
              <span>Reversal</span>
              <div className="bar-bg"><div className="bar bear" style={{ width: `${snapshot.trading_intelligence.probability_engine.reversal}%` }} /></div>
              <span>{num(snapshot.trading_intelligence.probability_engine.reversal)}%</span>
            </div>
            <div className="prob-row">
              <span>Mean Rev</span>
              <div className="bar-bg"><div className="bar range" style={{ width: `${snapshot.trading_intelligence.probability_engine.mean_reversion}%` }} /></div>
              <span>{num(snapshot.trading_intelligence.probability_engine.mean_reversion)}%</span>
            </div>
            <p className="muted intel-note">{snapshot.trading_intelligence.probability_engine.narrative}</p>
          </article>

          <article className="panel intel-card">
            <div className="intel-head">
              <span>Setup Generator</span>
              <strong className="up">ACTIVE</strong>
            </div>
            <div className="dependency-row">
              <span>Primary</span>
              <strong>{snapshot.trading_intelligence.setup_generator.primary_setup}</strong>
            </div>
            <div className="dependency-row">
              <span>Secondary</span>
              <strong>{snapshot.trading_intelligence.setup_generator.secondary_setup}</strong>
            </div>
            <div className="dependency-row">
              <span>Trigger</span>
              <strong>{snapshot.trading_intelligence.setup_generator.trigger}</strong>
            </div>
            <div className="dependency-row">
              <span>Invalidation</span>
              <strong>{snapshot.trading_intelligence.setup_generator.invalidation}</strong>
            </div>
            <p className="muted intel-note">{snapshot.trading_intelligence.setup_generator.execution_note}</p>
          </article>
        </div>
      </section>

      <section className="kpis">
        <article className="kpi">
          <div className="k">Bias</div>
          <div className="v blue">{snapshot.bias.toUpperCase()}</div>
        </article>
        <article className="kpi">
          <div className="k">Verdict</div>
          <div className={verdictClass(snapshot.verdict)}>{snapshot.verdict.toUpperCase()}</div>
        </article>
        <article className="kpi">
          <div className="k">Confidence</div>
          <div className="v amber">{num(snapshot.confidence)}%</div>
        </article>
        <article className="kpi">
          <div className="k">Direction</div>
          <div className="v">{snapshot.setup.direction.toUpperCase()}</div>
        </article>
        <article className="kpi">
          <div className="k">Entry</div>
          <div className="v">{num(snapshot.setup.entry)}</div>
        </article>
        <article className="kpi">
          <div className="k">RR</div>
          <div className="v green">1:{num(snapshot.setup.rr)}</div>
        </article>
      </section>

      <div className="toolbar">
        <button type="button" onClick={() => loadLatest().catch(() => setError("Refresh failed"))} disabled={busy}>
          Refresh
        </button>
        <button type="button" onClick={onGenerate} disabled={busy}>
          {busy ? "Generating..." : "Generate New"}
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="grid-two">
        <section className="panel">
          <div className="sec-title">1 · Price Terrain</div>
          <div className="terrain">
            {snapshot.price_terrain.map((level) => (
              <div key={`${level.zone}-${level.kind}`} className={terrainClass(level.kind)}>
                <div className="px">{level.zone}</div>
                <div className="ds">{level.note}</div>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <div className="sec-title">Probability Engine</div>
          <div className="prob-row">
            <span>Bull</span>
            <div className="bar-bg"><div className="bar bull" style={{ width: `${snapshot.probabilities.bull}%` }} /></div>
            <span>{num(snapshot.probabilities.bull)}%</span>
          </div>
          <div className="prob-row">
            <span>Range</span>
            <div className="bar-bg"><div className="bar range" style={{ width: `${snapshot.probabilities.range}%` }} /></div>
            <span>{num(snapshot.probabilities.range)}%</span>
          </div>
          <div className="prob-row">
            <span>Bear</span>
            <div className="bar-bg"><div className="bar bear" style={{ width: `${snapshot.probabilities.bear}%` }} /></div>
            <span>{num(snapshot.probabilities.bear)}%</span>
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="sec-title">2 · Sessions</div>
        <div className="session-grid">
          {snapshot.sessions.map((event) => (
            <article key={`${event.time_label}-${event.title}`} className={sessionClass(event.importance)}>
              <div className="time">{event.time_label}</div>
              <h4>{event.title}</h4>
              <p>{event.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="sec-title">Hourly Timeline Diff</div>
        <div className="timeline-list">
          {timeline.map((item) => (
            <article key={item.id} className={`timeline-item ${item.mood}`}>
              <div className="timeline-time">{item.timeLabel}</div>
              <div className="timeline-summary">{item.summary}</div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="sec-title">3 · Confluence Matrix</div>
        <div className="confluence-list">
          {snapshot.confluence.map((item) => (
            <article key={item.name} className={confluenceClass(item.status)}>
              <div className="signal-head">
                <span>{item.name}</span>
                <strong>{item.status.toUpperCase()}</strong>
              </div>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="sec-title">4 · Goldbach Entry Engine</div>
        <div className="provider-grid goldbach-grid">
          <div><span>PO3 Range:</span> <strong>{num(snapshot.goldbach_range.po3_range, 0)}</strong></div>
          <div><span>Actual Range:</span> <strong>{num(snapshot.goldbach_range.actual_range)}</strong></div>
          <div><span>Main Low/High:</span> <strong>{num(snapshot.goldbach_range.range_low)} / {num(snapshot.goldbach_range.range_high)}</strong></div>
          <div><span>EQ:</span> <strong>{num(snapshot.goldbach_range.eq)}</strong></div>
          <div><span>Sub Low/High:</span> <strong>{num(snapshot.goldbach_range.sub_low)} / {num(snapshot.goldbach_range.sub_high)}</strong></div>
          <div><span>Ext Low-/High+:</span> <strong>{num(snapshot.goldbach_range.ext_low_minus)} / {num(snapshot.goldbach_range.ext_high_plus)}</strong></div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Signal</th>
                <th>Side</th>
                <th>Anchor</th>
                <th>Entry / SL</th>
                <th>TP1 / TP2 / TP3</th>
                <th>RR2</th>
                <th>Quality</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.goldbach_entries.map((entry: GoldbachEntrySignal) => (
                <tr key={`${entry.label}-${entry.anchor_level}`} onContextMenu={(event) => openEntryMenu(event, entry)}>
                  <td>
                    <strong>{entry.label}</strong>
                    <div className="muted">{entry.reason}</div>
                  </td>
                  <td className={entry.side === "buy" ? "buy-txt" : "sell-txt"}>{entry.side.toUpperCase()}</td>
                  <td>{entry.anchor_level}</td>
                  <td>{num(entry.entry)} / {num(entry.stop_loss)}</td>
                  <td>{num(entry.tp1)} / {num(entry.tp2)} / {num(entry.tp3)}</td>
                  <td>{num(entry.rr2)}</td>
                  <td className={entry.score >= 80 ? "up" : entry.score >= 65 ? "nt" : "dn"}>{num(entry.score)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="sec-title">5 · Limit Orders</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Order</th>
                <th>Side</th>
                <th>Entry</th>
                <th>SL</th>
                <th>Risk</th>
                <th>TP1 / TP2 / TP3</th>
                <th>RR1 / RR2 / RR3</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.limit_orders.map((order: LimitOrderPlan) => (
                <tr key={order.label}>
                  <td>{order.label}</td>
                  <td className={order.side === "buy" ? "buy-txt" : "sell-txt"}>{order.side.toUpperCase()}</td>
                  <td>{num(order.entry)}</td>
                  <td>{num(order.stop_loss)}</td>
                  <td>${num(order.risk_usd)}</td>
                  <td>
                    {num(order.tp1)} / {num(order.tp2)} / {num(order.tp3)}
                  </td>
                  <td>
                    {num(order.rr1)} / {num(order.rr2)} / {num(order.rr3)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="sec-title">Score Breakdown</div>
        <ul className="score-list">
          {Object.entries(snapshot.score_breakdown).map(([key, value]) => (
            <li key={key}>
              <span>{key}</span>
              <strong className={value > 0 ? "up" : value < 0 ? "dn" : "nt"}>{value > 0 ? `+${num(value)}` : num(value)}</strong>
            </li>
          ))}
        </ul>
      </section>

      {contextMenu ? (
        <div
          className="context-menu"
          style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
          onClick={(event) => event.stopPropagation()}
        >
          {contextMenu.kind === "scenario" ? (
            <>
              <div className="context-menu-title">Scenario Actions</div>
              <button type="button" onClick={() => handleContextAction("select_scenario")}>Select Playbook</button>
              <button type="button" onClick={() => handleContextAction("copy_scenario")}>Copy Scenario Notes</button>
            </>
          ) : (
            <>
              <div className="context-menu-title">Entry Actions</div>
              <button type="button" onClick={() => handleContextAction("copy_entry")}>Copy Entry Plan</button>
              <button type="button" onClick={() => handleContextAction("copy_entry_json")}>Copy Entry JSON</button>
              <button type="button" onClick={() => handleContextAction("override_entry")}>Set Manual Price Override</button>

              <div className="context-menu-divider" />
              <div className="context-menu-title">Quick Risk</div>
              <button type="button" onClick={() => handleContextAction("risk_025")}>Set Risk 0.25%</button>
              <button type="button" onClick={() => handleContextAction("risk_050")}>Set Risk 0.50%</button>
              <button type="button" onClick={() => handleContextAction("risk_100")}>Set Risk 1.00%</button>
              <button type="button" onClick={() => handleContextAction("set_account_size")}>Set Account Size (USD)</button>

              <div className="context-menu-divider" />
              <div className="context-menu-title">Execution Tools</div>
              <button type="button" onClick={() => handleContextAction("copy_position_size")}>Copy Position Size</button>
              <button type="button" onClick={() => handleContextAction("copy_alert_template")}>Copy Alert Template</button>

              <div className="context-menu-meta">Risk: {num(riskPercent, 2)}% · Account: ${num(accountSizeUsd)}</div>
            </>
          )}
        </div>
      ) : null}
    </main>
  );
}
