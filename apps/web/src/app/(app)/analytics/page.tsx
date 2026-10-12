"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { MetricsChart } from "@/components/analytics/MetricsChart";
import { TemplatePerformance } from "@/components/analytics/TemplatePerformance";
import { SenderHealth } from "@/components/analytics/SenderHealth";
import { formatPercent } from "@/lib/utils";
import { useState } from "react";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const fromDate = isoDaysAgo(days);
  const toDate = new Date().toISOString().slice(0, 10);

  const { data: overview } = useQuery({
    queryKey: ["analytics", "overview", days],
    queryFn: () => apiClient<Record<string, number>>(`analytics/analytics/overview?from_date=${fromDate}&to_date=${toDate}`),
  });
  const { data: templates } = useQuery({
    queryKey: ["analytics", "templates", days],
    queryFn: () => apiClient<Array<Record<string, unknown>>>(`analytics/analytics/by-template?from_date=${fromDate}&to_date=${toDate}`),
  });
  const { data: senders } = useQuery({
    queryKey: ["analytics", "senders", days],
    queryFn: () => apiClient<Array<Record<string, unknown>>>(`analytics/analytics/by-sender?from_date=${fromDate}&to_date=${toDate}`),
  });
  const { data: categories } = useQuery({
    queryKey: ["analytics", "categories", days],
    queryFn: () => apiClient<Array<{ category: string | null; count: number }>>(`analytics/analytics/reply-categories?from_date=${fromDate}&to_date=${toDate}`),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}
          className="border rounded px-3 py-2 text-sm bg-white">
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
        </select>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Sent" value={overview?.sent} />
        <StatCard label="Reply rate" value={formatPercent(overview?.reply_rate)} />
        <StatCard label="Positive reply rate" value={formatPercent(overview?.positive_reply_rate)} accent="green" />
        <StatCard label="Bounce rate" value={formatPercent(overview?.bounce_rate)} accent="red" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Reply categories</h2>
          <MetricsChart data={categories || []} />
        </div>
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Sender health</h2>
          <SenderHealth senders={senders || []} />
        </div>
      </div>
      <div className="bg-white border rounded-lg p-6">
        <h2 className="font-semibold mb-4">Template performance</h2>
        <TemplatePerformance templates={templates || []} />
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: number | string | undefined; accent?: string }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold mt-2 ${accent === "green" ? "text-green-600" : accent === "red" ? "text-red-600" : ""}`}>
        {value ?? "—"}
      </div>
    </div>
  );
}
