"use client";

import Header from "@/components/Header";
import MonitoringDashboard from "@/components/MonitoringDashboard";

export default function AnalyticsPage() {
  return (
    <>
      <Header />
      <div style={{ flex: 1, overflow: "auto", padding: 32 }}>
        <MonitoringDashboard />
      </div>
    </>
  );
}
