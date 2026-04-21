/// <reference types="vite/client" />

import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";

type SentimentTone = "bullish" | "neutral" | "bearish" | "unknown";
type RecommendationSignal = "Buy" | "Sell" | "Hold";

type PortfolioSummary = {
  totalValue: string;
  cash: string;
  invested: string;
  dayChange: string;
  dayChangePercent: string;
  riskLevel: string;
  allocationLabel: string;
};

type SentimentMetric = {
  label: string;
  value: string;
  hint?: string;
  tone: SentimentTone;
};

type ExplanationReason = {
  label: string;
  detail: string;
};

type AdvisorRecommendation = {
  symbol: string;
  signal: RecommendationSignal;
  confidence: string;
  target: string;
  entry: string;
  stopLoss: string;
  takeProfit: string;
  reasons: ExplanationReason[];
};

type DashboardState = {
  portfolio: PortfolioSummary;
  sentiment: SentimentMetric[];
  recommendations: AdvisorRecommendation[];
  generatedAt: string | null;
};

type BackendRecommendation = {
  symbol?: string;
  signal?: string;
  confidence?: number | string;
  target?: number | string;
  entry?: number | string;
  stopLoss?: number | string;
  takeProfit?: number | string;
  rationale?: string;
  reasons?: Array<string | { label?: string; detail?: string }>;
};

type BackendDashboardItem = {
  combined_score?: number | string;
  sentiment_score?: number | string;
  technical_score?: number | string;
  reasons?: Array<string | { label?: string; detail?: string }>;
  news_summary?: string;
  technical_verification?: {
    momentum_score?: number | string;
    volume_change_pct?: number | string;
    technical_confirmation?: boolean;
    verification_strength?: number | string;
    verification_reason?: string;
  };
  sentiment?: {
    score?: number | string;
    label?: string;
    direction?: string;
    confidence?: number | string;
    magnitude?: number | string;
    rationale?: string;
    keywords?: string[];
    method?: string;
  };
  market?: {
    id?: string | number;
    title?: string;
    category?: string;
    source?: string;
    url?: string;
  };
};

type RawDashboardPayload = unknown;

type DashboardResponse = {
  ok: boolean;
  decision_support_only?: boolean;
  disclaimer?: string;
  frontendBaseUrl?: string;
  dashboard?: {
    summary?: {
      portfolio?: {
        totalValue?: number | string;
        cash?: number | string;
        invested?: number | string;
        dayChange?: number | string;
        dayChangePercent?: number | string;
        riskLevel?: string;
        allocationLabel?: string;
      };
      sentiment?: {
        metrics?:
          | Array<{
              label?: string;
              value?: number | string;
              hint?: string;
              tone?: SentimentTone | string;
            }>
          | Record<string, unknown>;
      };
    };
    sections?: {
      stockRecommendations?: {
        title?: string;
        summary?: string;
        subsections?: {
          buy?: {
            label?: string;
            items?: BackendRecommendation[];
          };
          sell?: {
            label?: string;
            items?: BackendRecommendation[];
          };
          hold?: {
            label?: string;
            items?: BackendRecommendation[];
          };
        };
      };
    };
    sharedMeta?: {
      generatedAt?: string;
      reportId?: string | null;
      decisionSupportOnly?: boolean;
      disclaimer?: string;
    };
  };
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
const API_BASE_URL_NORMALIZED = API_BASE_URL.replace(/\/$/, "");
const DEFAULT_API_ORIGIN = "http://127.0.0.1:8000";
const DASHBOARD_ENDPOINT = `${API_BASE_URL_NORMALIZED || DEFAULT_API_ORIGIN}/api/dashboard?limit=20`;
const DEFAULT_DISCLAIMER =
  "Decision support only: this dashboard surfaces signals and explanations for human review. It is not an autonomous decision-maker, and users should review the underlying data before acting.";

function formatCurrency(value: unknown): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value) : "—";
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(numeric);
    }
    return trimmed;
  }

  return "—";
}

function formatPercent(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    const numeric = Math.abs(value) <= 1 ? value * 100 : value;
    return `${numeric.toFixed(2)}%`;
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    const normalized = trimmed.endsWith("%") ? trimmed.slice(0, -1) : trimmed;
    const numeric = Number(normalized);
    if (Number.isFinite(numeric)) {
      const display = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
      return `${display.toFixed(2)}%`;
    }
    return trimmed;
  }

  return "—";
}

function formatGenericNumber(value: unknown): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? new Intl.NumberFormat("en-US").format(value) : "—";
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return new Intl.NumberFormat("en-US").format(numeric);
    }
    return trimmed;
  }

  return "—";
}

function toneForSignal(signal: RecommendationSignal): "success" | "danger" {
  return signal === "Buy" ? "success" : "danger";
}

function buildReasons(rec: BackendRecommendation): ExplanationReason[] {
  const reasons: ExplanationReason[] = [];

  if (Array.isArray(rec.reasons)) {
    rec.reasons.forEach((reason, index) => {
      if (typeof reason === "string" && reason.trim()) {
        reasons.push({ label: `Reason ${index + 1}`, detail: reason.trim() });
      } else if (reason && typeof reason === "object") {
        const label = typeof reason.label === "string" && reason.label.trim() ? reason.label.trim() : `Reason ${index + 1}`;
        const detail = typeof reason.detail === "string" && reason.detail.trim() ? reason.detail.trim() : "Supporting signal available from backend.";
        reasons.push({ label, detail });
      }
    });
  }

  if (reasons.length === 0 && typeof rec.rationale === "string" && rec.rationale.trim()) {
    reasons.push({ label: "Rationale", detail: rec.rationale.trim() });
  }

  if (reasons.length === 0) {
    reasons.push({ label: "Rationale", detail: "Recommendation details will appear once the backend returns explanation data." });
  }

  return reasons;
}

function buildPortfolioSummary(dashboard?: DashboardResponse["dashboard"]): PortfolioSummary {
  const portfolio = dashboard?.summary?.portfolio as
    | {
        totalValue?: number | string;
        cash?: number | string;
        invested?: number | string;
        dayChange?: number | string;
        dayChangePercent?: number | string;
        riskLevel?: string;
        allocationLabel?: string;
        portfolio_value?: number | string;
        risk_budget?: number | string;
        estimated_exposure_delta?: number | string;
        impact_label?: string;
      }
    | undefined;

  return {
    totalValue: formatCurrency(portfolio?.totalValue ?? portfolio?.portfolio_value ?? "—"),
    cash: formatCurrency(portfolio?.cash ?? portfolio?.risk_budget ?? "—"),
    invested: formatCurrency(portfolio?.invested ?? portfolio?.estimated_exposure_delta ?? "—"),
    dayChange: formatCurrency(portfolio?.dayChange ?? portfolio?.estimated_exposure_delta ?? "—"),
    dayChangePercent: formatPercent(portfolio?.dayChangePercent ?? portfolio?.estimated_exposure_delta ?? "—"),
    riskLevel: portfolio?.riskLevel?.trim() || portfolio?.impact_label?.trim() || "Balanced",
    allocationLabel: portfolio?.allocationLabel?.trim() || "Diversified allocation",
  };
}

function buildSentimentMetrics(dashboard?: DashboardResponse["dashboard"], items: BackendDashboardItem[] = []): SentimentMetric[] {
  const rawMetrics = dashboard?.summary?.sentiment?.metrics ?? [];

  const metrics = Array.isArray(rawMetrics)
    ? rawMetrics
    : Object.values(rawMetrics as Record<string, unknown>).flatMap((value) => (Array.isArray(value) ? value : []) as Array<{
        label?: string;
        value?: number | string;
        hint?: string;
        tone?: SentimentTone | string;
      }>);

  if (metrics.length > 0) {
    return metrics.map((metric) => ({
      label: metric.label?.trim() || "Metric",
      value:
        typeof metric.value === "number" || typeof metric.value === "string"
          ? String(metric.value)
          : "—",
      hint: metric.hint?.trim(),
      tone:
        metric.tone === "bullish" || metric.tone === "neutral" || metric.tone === "bearish"
          ? metric.tone
          : "unknown",
    }));
  }

  if (rawMetrics && typeof rawMetrics === "object" && !Array.isArray(rawMetrics)) {
    const sentimentRecord = rawMetrics as Record<string, unknown>;
    const direction = typeof sentimentRecord.direction === "string" ? sentimentRecord.direction.trim().toLowerCase() : "unknown";
    const tone: SentimentTone =
      direction === "bullish" || direction === "neutral" || direction === "bearish" ? direction : "unknown";

    return [
      {
        label: "Sentiment label",
        value: typeof sentimentRecord.label === "string" ? sentimentRecord.label : "—",
        hint: typeof sentimentRecord.rationale === "string" ? sentimentRecord.rationale : "Derived from backend sentiment analysis.",
        tone,
      },
      {
        label: "Confidence",
        value: formatPercent(sentimentRecord.confidence ?? "—"),
        hint: `Items scored: ${formatGenericNumber(sentimentRecord.items_scored ?? 0)}`,
        tone,
      },
      {
        label: "Magnitude",
        value: formatPercent(sentimentRecord.magnitude ?? sentimentRecord.score ?? "—"),
        hint: Array.isArray(sentimentRecord.keywords) && sentimentRecord.keywords.length > 0 ? `Keywords: ${sentimentRecord.keywords.join(", ")}` : "No keywords returned by backend.",
        tone,
      },
    ];
  }

  const first = items[0];
  if (first) {
    const sentimentLabel = first.sentiment?.label?.trim() || "unknown";
    const tone: SentimentTone =
      sentimentLabel === "bullish" || sentimentLabel === "neutral" || sentimentLabel === "bearish" ? sentimentLabel : "unknown";

    return [
      {
        label: "Sentiment score",
        value: formatPercent(first.sentiment_score ?? first.sentiment?.score ?? "—"),
        hint: first.sentiment?.rationale?.trim() || "Derived from backend sentiment analysis.",
        tone,
      },
      {
        label: "Technical score",
        value: formatPercent(first.technical_score ?? first.technical_verification?.momentum_score ?? "—"),
        hint: first.technical_verification?.verification_reason?.trim() || "Derived from backend technical verification.",
        tone: "neutral",
      },
      {
        label: "Combined score",
        value: formatPercent(first.combined_score ?? "—"),
        hint: first.news_summary?.trim() || "Aggregated decision-support score from backend.",
        tone,
      },
    ];
  }

  return [
    { label: "Market sentiment", value: "—", hint: "Waiting for backend signal feed", tone: "unknown" },
    { label: "News polarity", value: "—", hint: "No news summary available yet", tone: "unknown" },
    { label: "Confidence", value: "—", hint: "Model output pending", tone: "unknown" },
  ];
}

function buildRecommendations(dashboard?: DashboardResponse["dashboard"], items: BackendDashboardItem[] = []): AdvisorRecommendation[] {
  const buyItems = dashboard?.sections?.stockRecommendations?.subsections?.buy?.items ?? [];
  const sellItems = dashboard?.sections?.stockRecommendations?.subsections?.sell?.items ?? [];
  const holdItems = dashboard?.sections?.stockRecommendations?.subsections?.hold?.items ?? [];

  const normalize = (item: BackendRecommendation & { market_title?: string; combined_score?: number | string; technical_score?: number | string; sentiment_score?: number | string }, signal: RecommendationSignal): AdvisorRecommendation => ({
    symbol: item.symbol?.trim() || item.market_title?.trim() || "UNKNOWN",
    signal,
    confidence: formatPercent(item.confidence ?? "—"),
    target: formatCurrency(item.target ?? item.combined_score ?? "—"),
    entry: formatCurrency(item.entry ?? item.sentiment_score ?? "—"),
    stopLoss: formatCurrency(item.stopLoss ?? item.technical_score ?? "—"),
    takeProfit: formatCurrency(item.takeProfit ?? item.combined_score ?? "—"),
    reasons: buildReasons(item),
  });

  const sectionRecommendations = [
    ...buyItems.map((item: BackendRecommendation) => normalize(item, "Buy")),
    ...sellItems.map((item: BackendRecommendation) => normalize(item, "Sell")),
    ...holdItems.map((item: BackendRecommendation) => normalize(item, "Hold")),
  ];

  if (sectionRecommendations.length > 0) {
    return sectionRecommendations;
  }

  return items.map((item) => {
    const combinedScore = Number(item.combined_score ?? 0);
    const signal: RecommendationSignal = combinedScore > 0.15 ? "Buy" : combinedScore < -0.15 ? "Sell" : "Hold";
    const confidenceSource = item.sentiment?.confidence ?? item.technical_verification?.verification_strength ?? Math.abs(combinedScore);

    return {
      symbol: item.market?.title?.trim() || String(item.market?.id ?? "UNKNOWN"),
      signal,
      confidence: formatPercent(confidenceSource ?? "—"),
      target: formatGenericNumber(item.market?.id ?? "—"),
      entry: formatPercent(item.sentiment_score ?? "—"),
      stopLoss: formatPercent(item.technical_score ?? "—"),
      takeProfit: formatPercent(item.combined_score ?? "—"),
      reasons: buildReasons({
        rationale: item.sentiment?.rationale || item.technical_verification?.verification_reason || item.news_summary,
        reasons: item.reasons,
      }),
    };
  });
}

function toneStyles(tone: SentimentTone): { background: string; color: string; border: string } {
  switch (tone) {
    case "bullish":
      return { background: "#dcfce7", color: "#166534", border: "#86efac" };
    case "bearish":
      return { background: "#fee2e2", color: "#991b1b", border: "#fecaca" };
    case "neutral":
      return { background: "#e0f2fe", color: "#075985", border: "#bae6fd" };
    default:
      return { background: "#f1f5f9", color: "#334155", border: "#e2e8f0" };
  }
}

function signalStyles(signal: RecommendationSignal): { background: string; color: string } {
  if (signal === "Buy") {
    return { background: "#dcfce7", color: "#166534" };
  }

  if (signal === "Hold") {
    return { background: "#e0f2fe", color: "#075985" };
  }

  return { background: "#fee2e2", color: "#991b1b" };
}

function App() {
  const [dashboard, setDashboard] = useState<DashboardState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const disclaimer = DEFAULT_DISCLAIMER;

  useEffect(() => {
    const controller = new AbortController();

    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(DASHBOARD_ENDPOINT, { signal: controller.signal });

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const payload = (await response.json()) as RawDashboardPayload;
        const dashboardPayload: DashboardResponse | null =
          payload && typeof payload === "object" && !Array.isArray(payload) && "dashboard" in payload
            ? (payload as DashboardResponse)
            : null;
        const items: BackendDashboardItem[] = Array.isArray(payload)
          ? payload as BackendDashboardItem[]
          : payload && typeof payload === "object" && !Array.isArray(payload) && "dashboard" in payload
            ? []
            : payload && typeof payload === "object"
              ? [payload as BackendDashboardItem]
              : [];

        if (dashboardPayload && !dashboardPayload.ok) {
          throw new Error("Backend returned a non-ok dashboard payload");
        }

        setDashboard({
          portfolio: buildPortfolioSummary(dashboardPayload?.dashboard),
          sentiment: buildSentimentMetrics(dashboardPayload?.dashboard, items),
          recommendations: buildRecommendations(dashboardPayload?.dashboard, items),
          generatedAt: dashboardPayload?.dashboard?.sharedMeta?.generatedAt ?? null,
        });
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }

        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard data from the backend API");
        setDashboard(null);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();

    return () => controller.abort();
  }, []);

  const statusLabel = useMemo(() => {
    if (loading) return "Loading advisor dashboard...";
    if (error) return "Unable to load live advisory data";
    return dashboard?.generatedAt ? `Updated at ${dashboard.generatedAt}` : "Live advisor dashboard";
  }, [dashboard?.generatedAt, error, loading]);

  const hasRecommendations = (dashboard?.recommendations?.length ?? 0) > 0;
  const hasSentiment = (dashboard?.sentiment?.length ?? 0) > 0;

  return (
    <main
      style={{
        minHeight: "100vh",
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
        color: "#0f172a",
      }}
    >
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 20px 48px" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "20px",
            alignItems: "flex-start",
            flexWrap: "wrap",
            marginBottom: "24px",
          }}
        >
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 12px",
                borderRadius: "999px",
                background: "#e0e7ff",
                color: "#4338ca",
                fontSize: "0.85rem",
                fontWeight: 700,
                marginBottom: "14px",
              }}
            >
              Advisor Co-Pilot
            </div>
            <h1 style={{ margin: 0, fontSize: "clamp(2rem, 4vw, 3rem)", lineHeight: 1.1 }}>Finance Advisor Dashboard</h1>
            <p style={{ margin: "10px 0 0", color: "#475569", maxWidth: "760px" }}>
              A decision-support dashboard for portfolio snapshots, sentiment intelligence, and explainable buy/sell guidance. It is not an autonomous decision-maker, and every signal should be reviewed before acting.
            </p>
            <div
              style={{
                marginTop: "14px",
                padding: "12px 14px",
                borderRadius: "14px",
                background: "#fff7ed",
                border: "1px solid #fed7aa",
                color: "#9a3412",
                maxWidth: "760px",
                lineHeight: 1.55,
                fontSize: "0.95rem",
              }}
            >
              {disclaimer}
            </div>
          </div>

          <div
            style={{
              minWidth: "240px",
              padding: "16px 18px",
              borderRadius: "18px",
              background: "#ffffff",
              boxShadow: "0 10px 30px rgba(15, 23, 42, 0.08)",
              border: "1px solid #e2e8f0",
            }}
          >
            <div style={{ fontSize: "0.82rem", color: "#64748b", marginBottom: "6px" }}>Status</div>
            <div style={{ fontWeight: 700 }}>{statusLabel}</div>
          </div>
        </header>

        {error ? (
          <section
            style={{
              marginBottom: "24px",
              padding: "16px 18px",
              borderRadius: "16px",
              background: "#fef2f2",
              color: "#991b1b",
              border: "1px solid #fecaca",
            }}
          >
            {error}
          </section>
        ) : null}

        {loading ? (
          <section
            style={{
              display: "grid",
              gap: "16px",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            }}
          >
            {Array.from({ length: 4 }).map((_, index) => (
              <div
                key={index}
                style={{
                  height: "132px",
                  borderRadius: "18px",
                  background: "#ffffff",
                  border: "1px solid #e2e8f0",
                  boxShadow: "0 10px 30px rgba(15, 23, 42, 0.05)",
                }}
              />
            ))}
          </section>
        ) : dashboard ? (
          <>
            <section
              style={{
                display: "grid",
                gap: "16px",
                gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                marginBottom: "24px",
              }}
            >
              <Card title="Portfolio value" value={dashboard.portfolio.totalValue} note={dashboard.portfolio.allocationLabel} />
              <Card title="Cash available" value={dashboard.portfolio.cash} note={`Risk profile: ${dashboard.portfolio.riskLevel}`} />
              <Card title="Invested capital" value={dashboard.portfolio.invested} note={`Daily change: ${dashboard.portfolio.dayChange}`} />
              <Card title="Daily performance" value={dashboard.portfolio.dayChangePercent} note="Change vs. previous close" />
            </section>

            <section style={{ display: "grid", gap: "24px", gridTemplateColumns: "repeat(12, minmax(0, 1fr))" }}>
              <Panel title="Sentiment metrics" subtitle="Market and news signals distilled into an at-a-glance view" span={4}>
                {hasSentiment ? (
                  <div style={{ display: "grid", gap: "12px" }}>
                    {dashboard.sentiment.map((metric) => {
                      const styles = toneStyles(metric.tone);
                      return (
                        <div
                          key={`${metric.label}-${metric.value}`}
                          style={{
                            padding: "14px",
                            borderRadius: "14px",
                            background: styles.background,
                            border: `1px solid ${styles.border}`,
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", alignItems: "baseline" }}>
                            <div style={{ fontWeight: 700 }}>{metric.label}</div>
                            <div style={{ fontWeight: 800 }}>{metric.value}</div>
                          </div>
                          {metric.hint ? (
                            <div style={{ marginTop: "6px", color: "#475569", fontSize: "0.92rem" }}>{metric.hint}</div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState message="No sentiment metrics available yet." />
                )}
              </Panel>

              <Panel title="Advisor actions" subtitle="Decision-support recommendations with explanation reasons" span={8}>
                <div
                  style={{
                    marginBottom: "14px",
                    padding: "12px 14px",
                    borderRadius: "14px",
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    color: "#475569",
                    lineHeight: 1.55,
                    fontSize: "0.94rem",
                  }}
                >
                  This section is for human review only. The advisor highlights signals, but it does not make autonomous decisions.
                </div>
                {hasRecommendations ? (
                  <div style={{ display: "grid", gap: "14px" }}>
                    {dashboard.recommendations.map((recommendation) => {
                      const styles = signalStyles(recommendation.signal);
                      return (
                        <article
                          key={`${recommendation.signal}-${recommendation.symbol}`}
                          style={{
                            padding: "18px",
                            borderRadius: "18px",
                            background: "#ffffff",
                            border: "1px solid #e2e8f0",
                            boxShadow: "0 10px 30px rgba(15, 23, 42, 0.05)",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
                            <div>
                              <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                                <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{recommendation.symbol}</h3>
                                <span
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    padding: "5px 10px",
                                    borderRadius: "999px",
                                    background: styles.background,
                                    color: styles.color,
                                    fontSize: "0.8rem",
                                    fontWeight: 800,
                                  }}
                                >
                                  {recommendation.signal}
                                </span>
                                <span style={{ color: "#64748b", fontSize: "0.9rem" }}>Confidence {recommendation.confidence}</span>
                              </div>
                            </div>
                          </div>

                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                              gap: "12px",
                              marginTop: "16px",
                            }}
                          >
                            <MetricBlock label="Entry" value={recommendation.entry} />
                            <MetricBlock label="Target" value={recommendation.target} />
                            <MetricBlock label="Stop loss" value={recommendation.stopLoss} />
                            <MetricBlock label="Take profit" value={recommendation.takeProfit} />
                          </div>

                          <div style={{ marginTop: "16px" }}>
                            <div style={{ fontWeight: 700, marginBottom: "10px" }}>Explanation reasons</div>
                            <div style={{ display: "grid", gap: "10px" }}>
                              {recommendation.reasons.map((reason) => (
                                <div
                                  key={`${recommendation.symbol}-${reason.label}-${reason.detail}`}
                                  style={{
                                    padding: "12px 14px",
                                    borderRadius: "12px",
                                    background: "#f8fafc",
                                    border: "1px solid #e2e8f0",
                                  }}
                                >
                                  <div style={{ fontWeight: 700, marginBottom: "4px" }}>{reason.label}</div>
                                  <div style={{ color: "#475569", lineHeight: 1.55 }}>{reason.detail}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyState message="No buy/sell recommendations available right now." />
                )}
              </Panel>
            </section>
          </>
        ) : (
          <section
            style={{
              padding: "24px",
              borderRadius: "18px",
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              boxShadow: "0 10px 30px rgba(15, 23, 42, 0.05)",
            }}
          >
            <EmptyState message="Dashboard data is not available." />
          </section>
        )}
      </div>
    </main>
  );
}

function Card({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <section
      style={{
        padding: "18px",
        borderRadius: "18px",
        background: "#ffffff",
        border: "1px solid #e2e8f0",
        boxShadow: "0 10px 30px rgba(15, 23, 42, 0.05)",
      }}
    >
      <div style={{ color: "#64748b", fontSize: "0.88rem", marginBottom: "10px" }}>{title}</div>
      <div style={{ fontSize: "1.8rem", fontWeight: 800, letterSpacing: "-0.02em" }}>{value}</div>
      <div style={{ marginTop: "8px", color: "#475569", fontSize: "0.92rem" }}>{note}</div>
    </section>
  );
}

function Panel({
  title,
  subtitle,
  span,
  children,
}: {
  title: string;
  subtitle: string;
  span: number;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        gridColumn: `span ${span} / span ${span}`,
        padding: "20px",
        borderRadius: "20px",
        background: "rgba(255, 255, 255, 0.9)",
        border: "1px solid #e2e8f0",
        boxShadow: "0 10px 30px rgba(15, 23, 42, 0.05)",
      }}
    >
      <header style={{ marginBottom: "16px" }}>
        <h2 style={{ margin: 0, fontSize: "1.2rem" }}>{title}</h2>
        <p style={{ margin: "6px 0 0", color: "#64748b" }}>{subtitle}</p>
      </header>
      {children}
    </section>
  );
}

function MetricBlock({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: "14px",
        background: "#f8fafc",
        border: "1px solid #e2e8f0",
      }}
    >
      <div style={{ fontSize: "0.82rem", color: "#64748b", marginBottom: "4px" }}>{label}</div>
      <div style={{ fontWeight: 800 }}>{value}</div>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        padding: "18px",
        borderRadius: "14px",
        background: "#f8fafc",
        border: "1px dashed #cbd5e1",
        color: "#64748b",
      }}
    >
      {message}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
