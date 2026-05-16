"use client";

import dynamic from "next/dynamic";
import type { UIComponent, BarChartData, DataTableData, CodeBlockData, ComparisonChartData } from "@/types";

// Dynamic imports with SSR disabled to avoid "window is not defined" errors
const BarChartWidget = dynamic(() => import("./BarChartWidget"), { ssr: false });
const DataTableWidget = dynamic(() => import("./DataTableWidget"), { ssr: false });
const CodeBlockWidget = dynamic(() => import("./CodeBlockWidget"), { ssr: false });
const ComparisonChart = dynamic(() => import("./ComparisonChart"), { ssr: false });

interface GenUIRouterProps {
  uiComponent: UIComponent;
}

export default function GenUIRouter({ uiComponent }: GenUIRouterProps) {
  const { component, data } = uiComponent;

  switch (component) {
    case "BarChart":
    case "LineChart":
      return <BarChartWidget data={data as BarChartData} />;

    case "DataTable":
      return <DataTableWidget data={data as DataTableData} />;

    case "CodeBlock":
      return <CodeBlockWidget data={data as CodeBlockData} />;

    case "ComparisonChart":
      const compData = data as ComparisonChartData;
      return <ComparisonChart title={compData.title} description={compData.description} data={compData.data} metrics={compData.metrics} />;

    case "PDFOverlay":
      // PDFOverlay triggers a side effect — just show a message
      return (
        <div className="glass-card rounded-2xl p-4 mt-4 border-emerald-100 bg-emerald-50/30 animate-slide-in-up">
          <p className="text-[11px] font-bold text-[#10B981] uppercase tracking-wider">
            ✓ Source highlighted in PDF viewer
          </p>
        </div>
      );

    default:
      return null;
  }
}
