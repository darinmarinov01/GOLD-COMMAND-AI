"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp } from "lightweight-charts";

interface PricePoint {
  time: number;
  value: number;
}

interface PriceChartProps {
  points: PricePoint[];
}

export default function PriceChart({ points }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 280,
      layout: {
        background: { type: ColorType.Solid, color: "#131610" },
        textColor: "#8b8974",
      },
      grid: {
        vertLines: { color: "#2a2e1f" },
        horzLines: { color: "#2a2e1f" },
      },
      rightPriceScale: {
        borderColor: "#2a2e1f",
      },
      timeScale: {
        borderColor: "#2a2e1f",
        timeVisible: true,
        secondsVisible: false,
      },
      localization: {
        locale: "bg-BG",
      },
      crosshair: {
        vertLine: { color: "#e8b34b" },
        horzLine: { color: "#e8b34b" },
      },
    });

    const lineSeries = chart.addLineSeries({
      color: "#e8b34b",
      lineWidth: 2,
      priceLineColor: "#7ec98f",
      lastValueVisible: true,
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;

    const resizeObserver = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth });
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;

    const data = points.map((point) => ({
      time: Math.floor(point.time / 1000) as UTCTimestamp,
      value: point.value,
    }));

    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [points]);

  return <div className="chart-container" ref={containerRef} />;
}
