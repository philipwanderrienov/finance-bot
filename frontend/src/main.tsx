/// <reference types="vite/client" />

import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";

type Market = {
  name: string;
  status: string;
  confidence: string;
  lastPrice: string;
  change: string;
  volume: string;
};

type StockRecommendation = {
  symbol: string;
  signal: "Buy" | "Sell";
  target: string;
  entry: string;
  stopLoss: string;
  takeProfit: string;
  rationale: string;
};

type DashboardResponse = {
  ok: boolean;
  frontendBaseUrl?: string;
  dashboard?: {
    sections?: {
      marketsGrid?: {
        title?: string;
        items?: Array<{
          id?: string;
          title?: string;
          category?: string;
          source?: string;
          url?: string;
          score?: number;
          metadata?: Record<string, unknown>;
        }>;
      };
      stockRecommendations?: {
        title?: string;
        summary?: string;
        subsections?: {
          buy?: {
            label?: string;
            items?: Array<{
              symbol?: string;
              target?: string;
              entry?: string;
              stopLoss?: string;
              takeProfit?: string;
              rationale?: string;
            }>;
          };
          sell?: {
            label?: string;
            items?: Array<{
              symbol?: string;
              target?: string;
              entry?: string;
              stopLoss?: string;
              takeProfit?: string;
              rationale?: string;
            }>;
          };
        };
      };
    };
    sharedMeta?: {
      generatedAt?: string;
      reportId?: string | null;
      counts?: {
        markets?: number;
        buyRecommendations?: number;
        sellRecommendations?: number;
      };
    };
  };
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const DASHBOARD_ENDPOINT = `${API_BASE_URL.replace(/\/$/, "")}/api/dashboard?limit=20`;

function formatCurrency(value: unknown): string {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toFixed(2) : "—";
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      return numeric.toFixed(2);
    }
    return trimmed;
  }

  return "—";
}

function extractPrice(item: { metadata?: Record<string, unknown>; score?: number; title?: string }): string {
  const metadata = item.metadata ?? {};
  const candidate =
    metadata["lastPrice"] ??
    metadata["last_price"] ??
    metadata["price"] ??
    metadata["current_price"] ??
    metadata["probability"] ??
    metadata["yesPrice"] ??
    metadata["yes_price"] ??
    item.score ??
    undefined;

  if (typeof candidate === "number") {
    if (candidate > 1 && candidate <= 100) {
      return `${candidate.toFixed(2)}%`;
    }
    if (candidate >= 0 && candidate <= 1) {
      return `${(candidate * 100).toFixed(2)}%`;
    }
    return candidate.toFixed(2);
  }

  if (typeof candidate === "string") {
    const trimmed = candidate.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      if (numeric > 1 && numeric <= 100) {
        return `${numeric.toFixed(2)}%`;
      }
      if (numeric >= 0 && numeric <= 1) {
        return `${(numeric * 100).toFixed(2)}%`;
      }
      return numeric.toFixed(2);
    }
    return trimmed;
  }

  return "—";
}

function extractConfidence(item: { metadata?: Record<string, unknown>; score?: number }): string {
  const metadata = item.metadata ?? {};
  const candidate =
    metadata["confidence"] ??
    metadata["confidenceScore"] ??
    metadata["confidence_score"] ??
    metadata["liquidity"] ??
    metadata["volume"] ??
    item.score ??
    undefined;

  if (typeof candidate === "number") {
    if (candidate > 1 && candidate <= 100) {
      return `${candidate.toFixed(0)}%`;
    }
    if (candidate >= 0 && candidate <= 1) {
      return `${(candidate * 100).toFixed(0)}%`;
    }
    return candidate.toFixed(0);
  }

  if (typeof candidate === "string") {
    const trimmed = candidate.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      if (numeric > 1 && numeric <= 100) {
        return `${numeric.toFixed(0)}%`;
      }
      if (numeric >= 0 && numeric <= 1) {
        return `${(numeric * 100).toFixed(0)}%`;
      }
      return numeric.toFixed(0);
    }
    return trimmed;
  }

  return "—";
}

function extractChange(item: { metadata?: Record<string, unknown> }): string {
  const metadata = item.metadata ?? {};
  const candidate =
    metadata["change"] ??
    metadata["changePercent"] ??
    metadata["change_percent"] ??
    metadata["delta"] ??
    metadata["movement"] ??
    undefined;

  if (typeof candidate === "number") {
    const sign = candidate > 0 ? "+" : "";
    return `${sign}${candidate.toFixed(2)}%`;
  }

  if (typeof candidate === "string") {
    const trimmed = candidate.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed.replace("%", ""));
    if (Number.isFinite(numeric)) {
      const sign = numeric > 0 ? "+" : "";
      return `${sign}${numeric.toFixed(2)}%`;
    }
    return trimmed;
  }

  return "—";
}

function extractVolume(item: { metadata?: Record<string, unknown>; score?: number }): string {
  const metadata = item.metadata ?? {};
  const candidate =
    metadata["volume"] ??
    metadata["liquidity"] ??
    metadata["tradedVolume"] ??
    metadata["traded_volume"] ??
    item.score ??
    undefined;

  if (typeof candidate === "number") {
    if (candidate >= 1_000_000) {
      return `${(candidate / 1_000_000).toFixed(1)}M`;
    }
    if (candidate >= 1_000) {
      return `${(candidate / 1_000).toFixed(1)}K`;
    }
    return candidate.toFixed(0);
  }

  if (typeof candidate === "string") {
    const trimmed = candidate.trim();
    if (!trimmed) return "—";
    const numeric = Number(trimmed);
    if (Number.isFinite(numeric)) {
      if (numeric >= 1_000_000) {
        return `${(numeric / 1_000_000).toFixed(1)}M`;
      }
      if (numeric >= 1_000) {
        return `${(numeric / 1_000).toFixed(1)}K`;
      }
      return numeric.toFixed(0);
    }
    return trimmed;
  }

  return "—";
}

function buildStatus(item: { category?: string; source?: string; metadata?: Record<string, unknown> }): string {
  const statusFromMetadata = item.metadata?.["status"];
  if (typeof statusFromMetadata === "string" && statusFromMetadata.trim()) {
    return statusFromMetadata.trim();
  }

  const parts = [item.category, item.source].filter(Boolean);
  if (parts.length > 0) {
    return parts.map((value) => String(value)).join(" · ");
  }

  return "Live";
}

function App() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [stockRecommendations, setStockRecommendations] = useState<StockRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(DASHBOARD_ENDPOINT, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const payload = (await response.json()) as DashboardResponse;

        if (!payload.ok) {
          throw new Error("Backend returned a non-ok dashboard payload");
        }

        const dashboard = payload.dashboard;
        const marketsItems = dashboard?.sections?.marketsGrid?.items ?? [];
        const buyItems = dashboard?.sections?.stockRecommendations?.subsections?.buy?.items ?? [];
        const sellItems = dashboard?.sections?.stockRecommendations?.subsections?.sell?.items ?? [];

        setMarkets(
          marketsItems
            .map((item) => ({
              name: item.title ?? "Unnamed market",
              status: buildStatus(item),
              confidence: extractConfidence(item),
              lastPrice: extractPrice(item),
              change: extractChange(item),
              volume: extractVolume(item),
            }))
            .filter((item) => item.name !== "Unnamed market" || item.lastPrice !== "—"),
        );

        setStockRecommendations([
          ...buyItems.map((item) => ({
            symbol: item.symbol ?? "UNKNOWN",
            signal: "Buy" as const,
            target: item.target ?? "—",
            entry: item.entry ?? "—",
            stopLoss: item.stopLoss ?? "—",
            takeProfit: item.takeProfit ?? "—",
            rationale: item.rationale ?? "",
          })),
          ...sellItems.map((item) => ({
            symbol: item.symbol ?? "UNKNOWN",
            signal: "Sell" as const,
            target: item.target ?? "—",
            entry: item.entry ?? "—",
            stopLoss: item.stopLoss ?? "—",
            takeProfit: item.takeProfit ?? "—",
            rationale: item.rationale ?? "",
          })),
        ]);

        setGeneratedAt(dashboard?.sharedMeta?.generatedAt ?? null);
      } catch (loadError) {
        if (loadError instanceof DOMException && loadError.name === "AbortError") {
          return;
        }
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Failed to load dashboard data from the backend API",
        );
        setMarkets([]);
        setStockRecommendations([]);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();

    return () => controller.abort();
  }, []);

  const statusLabel = useMemo(() => {
    if (loading) return "Loading live dashboard data...";
    if (error) return "Unable to load live data";
    return generatedAt ? `Updated at ${generatedAt}` : "Live dashboard data";
  }, [error, generatedAt, loading]);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", background: "#f7f9fc", color: "#0f172a" }}>
      <header style={{ marginBottom: "2rem" }}>
        <h1 style={{ margin: 0, fontSize: "2rem" }}>Finance Bot Dashboard</h1>
        <p style={{ margin: "0.5rem 0 0", color: "#475569" }}>
          Frontend dashboard for market snapshots and recommended stock actions.
        </p>
        <p style={{ margin: "0.5rem 0 0", color: error ? "#b91c1c" : "#64748b" }}>{statusLabel}</p>
      </header>

      {error ? (
        <section style={{ marginBottom: "2rem", padding: "1rem", borderRadius: "12px", background: "#fef2f2", color: "#991b1b" }}>
          {error}
        </section>
      ) : null}

      <section style={{ marginBottom: "2rem" }}>
        <h2 style={{ marginBottom: "1rem" }}>Markets</h2>
        {loading ? (
          <div style={{ color: "#64748b" }}>Loading markets...</div>
        ) : markets.length === 0 ? (
          <div style={{ color: "#64748b" }}>No markets available.</div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "1rem",
            }}
          >
            {markets.map((market) => (
              <article
                key={market.name}
                style={{
                  background: "white",
                  borderRadius: "16px",
                  padding: "1rem",
                  boxShadow: "0 8px 20px rgba(15, 23, 42, 0.08)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
                  <h3 style={{ margin: 0 }}>{market.name}</h3>
                  <strong>{market.status}</strong>
                </div>
                <p style={{ margin: "0.75rem 0 0.25rem", fontSize: "1.5rem", fontWeight: 700 }}>{market.lastPrice}</p>
                <p style={{ margin: 0, color: market.change.startsWith("-") ? "#dc2626" : "#16a34a" }}>{market.change}</p>
                <dl
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: "0.75rem",
                    marginTop: "1rem",
                  }}
                >
                  <div>
                    <dt style={{ fontSize: "0.85rem", color: "#64748b" }}>Confidence</dt>
                    <dd style={{ margin: "0.25rem 0 0", fontWeight: 600 }}>{market.confidence}</dd>
                  </div>
                  <div>
                    <dt style={{ fontSize: "0.85rem", color: "#64748b" }}>Volume</dt>
                    <dd style={{ margin: "0.25rem 0 0", fontWeight: 600 }}>{market.volume}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 style={{ marginBottom: "1rem" }}>Recommended Stocks</h2>
        {loading ? (
          <div style={{ color: "#64748b" }}>Loading recommendations...</div>
        ) : stockRecommendations.length === 0 ? (
          <div style={{ color: "#64748b" }}>No stock recommendations available.</div>
        ) : (
          <div style={{ display: "grid", gap: "1rem" }}>
            {stockRecommendations.map((stock) => (
              <article
                key={`${stock.signal}-${stock.symbol}`}
                style={{
                  background: "white",
                  borderRadius: "16px",
                  padding: "1.25rem",
                  boxShadow: "0 8px 20px rgba(15, 23, 42, 0.08)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.2rem" }}>{stock.symbol}</h3>
                    <p style={{ margin: "0.35rem 0 0", color: "#64748b" }}>{stock.rationale}</p>
                  </div>
                  <div
                    style={{
                      alignSelf: "flex-start",
                      background: stock.signal === "Buy" ? "#dcfce7" : "#fee2e2",
                      color: stock.signal === "Buy" ? "#166534" : "#991b1b",
                      padding: "0.35rem 0.75rem",
                      borderRadius: "999px",
                      fontWeight: 700,
                    }}
                  >
                    {stock.signal}
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                    gap: "1rem",
                    marginTop: "1rem",
                  }}
                >
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Entry</div>
                    <div style={{ fontWeight: 700 }}>{stock.entry}</div>
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Target</div>
                    <div style={{ fontWeight: 700 }}>{stock.target}</div>
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Stop Loss</div>
                    <div style={{ fontWeight: 700 }}>{stock.stopLoss}</div>
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.85rem" }}>Take Profit</div>
                    <div style={{ fontWeight: 700 }}>{stock.takeProfit}</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
