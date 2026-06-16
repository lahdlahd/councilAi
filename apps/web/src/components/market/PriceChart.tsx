"use client";

import {
  CandlestickSeriesOptions,
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";
import { fetchCandles } from "@/lib/api";
import { useMarketStore } from "@/stores/marketStore";
import { useSessionStore } from "@/stores/sessionStore";

// Compact candlestick of the council's current subject. Loads candles on symbol
// change and nudges the last bar with live ticks.
export function PriceChart() {
  const symbol = useSessionStore((s) => s.symbol);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastRef = useRef<{ time: number; close: number } | null>(null);

  // Create the chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { color: "transparent" },
        textColor: "#8C8579",
        fontFamily: "var(--font-plex-mono)",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(42,47,53,0.5)" },
        horzLines: { color: "rgba(42,47,53,0.5)" },
      },
      rightPriceScale: { borderColor: "#2A2F35" },
      timeScale: { borderColor: "#2A2F35", timeVisible: true, secondsVisible: false },
      crosshair: { vertLine: { color: "#C9A227" }, horzLine: { color: "#C9A227" } },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#2B8A6E",
      downColor: "#A54B4B",
      borderUpColor: "#2B8A6E",
      borderDownColor: "#A54B4B",
      wickUpColor: "#2B8A6E",
      wickDownColor: "#A54B4B",
    } as Partial<CandlestickSeriesOptions>);
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Load candles when the subject changes.
  useEffect(() => {
    if (!symbol || !seriesRef.current) return;
    let cancelled = false;
    fetchCandles(symbol)
      .then((candles) => {
        if (cancelled || !seriesRef.current) return;
        seriesRef.current.setData(
          candles.map((c) => ({
            time: c.time as Time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }))
        );
        const last = candles[candles.length - 1];
        if (last) lastRef.current = { time: last.time, close: last.close };
        chartRef.current?.timeScale().fitContent();
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Nudge the last bar with the live price tick.
  const tick = useMarketStore((s) => (symbol ? s.bySymbol[symbol] : undefined));
  useEffect(() => {
    if (!tick || !seriesRef.current || !lastRef.current) return;
    const { time } = lastRef.current;
    seriesRef.current.update({
      time: time as Time,
      open: lastRef.current.close,
      high: Math.max(lastRef.current.close, tick.price),
      low: Math.min(lastRef.current.close, tick.price),
      close: tick.price,
    });
  }, [tick]);

  return (
    <div className="border border-hairline bg-surface">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2">
        <span className="eyebrow">Price — {symbol ?? "—"}</span>
        <span className="eyebrow">15m</span>
      </div>
      <div ref={containerRef} className="h-[180px] w-full" />
    </div>
  );
}
