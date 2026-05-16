"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { BarChartData } from "@/types";

export interface BarChartWidgetProps {
  data: BarChartData;
}

export default function BarChartWidget({ data: chartData }: BarChartWidgetProps) {
  const color = "#22c55e";
  // Transform BarChartData into recharts format
  const data = chartData.labels.map((label, i) => ({
    name: label,
    value: chartData.datasets[0]?.values[i] ?? 0,
  }));
  const title = chartData.title;
  return (
    <div
      className="animate-fade-up hover-lift"
      style={{
        padding: 20,
        background: "#151515",
        border: "1px solid #2a2a2a",
        borderRadius: 14,
      }}
    >
      <p style={{
        fontSize: 12,
        fontWeight: 700,
        color: "#aaa",
        marginBottom: 16,
        letterSpacing: "-0.01em",
      }}>
        {title}
      </p>
      <div style={{ width: "100%", height: 200 }}>
        <ResponsiveContainer>
          <BarChart data={data} barSize={20}>
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#555", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#555", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a1a",
                border: "1px solid #333",
                borderRadius: 8,
                fontSize: 12,
                color: "#fafafa",
              }}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {data.map((_, i) => (
                <Cell key={i} fill={color} opacity={0.7 + (i % 3) * 0.1} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
