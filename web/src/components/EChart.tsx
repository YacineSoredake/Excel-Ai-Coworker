"use client";

import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import { AriaComponent, GridComponent, LegendComponent, MarkPointComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { prefersReducedMotion } from "@/lib/motion";

echarts.use([BarChart, LineChart, PieChart, ScatterChart, AriaComponent, GridComponent, LegendComponent, MarkPointComponent, TooltipComponent, CanvasRenderer]);

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function EChart({ option, height = 260, onClick, label }: {
  option: any; height?: number; onClick?: (p: any) => void; label: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const c = echarts.init(el.current as HTMLDivElement, undefined, { renderer: "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current as HTMLDivElement);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    chart.current?.setOption({ ...option, animation: !prefersReducedMotion() }, true);
  }, [option]);

  useEffect(() => {
    const c = chart.current;
    if (!c || !onClick) return;
    c.on("click", onClick);
    return () => { c.off("click", onClick); };
  }, [onClick]);

  return <div ref={el} role="img" aria-label={label} style={{ height }} className="w-full" />;
}
