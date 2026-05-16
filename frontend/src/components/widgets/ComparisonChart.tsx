"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ComparisonData {
  category: string;
  [key: string]: string | number; // e.g. "Q1 2023": 4500, "Q1 2024": 5200
}

interface ComparisonChartProps {
  title: string;
  description?: string;
  data: ComparisonData[];
  metrics: { key: string; color: string; name: string }[];
}

export default function ComparisonChart({
  title,
  description,
  data,
  metrics,
}: ComparisonChartProps) {
  return (
    <div
      style={{
        background: "#151515",
        border: "1px solid #2a2a2a",
        borderRadius: 12,
        padding: 20,
        width: "100%",
        marginTop: 16,
        marginBottom: 16,
      }}
    >
      <div style={{ marginBottom: 20 }}>
        <h3
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: "#fafafa",
            marginBottom: 4,
          }}
        >
          {title}
        </h3>
        {description && (
          <p style={{ fontSize: 13, color: "#888", lineHeight: 1.5 }}>
            {description}
          </p>
        )}
      </div>

      <div style={{ width: "100%", height: 300 }}>
        <ResponsiveContainer>
          <BarChart
            data={data}
            margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#222" vertical={false} />
            <XAxis
              dataKey="category"
              stroke="#555"
              tick={{ fill: "#888", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              stroke="#555"
              tick={{ fill: "#888", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#111",
                border: "1px solid #333",
                borderRadius: 8,
                fontSize: 12,
                color: "#fff",
              }}
              itemStyle={{ color: "#fff" }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
            {metrics.map((metric, idx) => (
              <Bar
                key={metric.key}
                dataKey={metric.key}
                name={metric.name}
                fill={metric.color}
                radius={[4, 4, 0, 0]}
                barSize={30}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
