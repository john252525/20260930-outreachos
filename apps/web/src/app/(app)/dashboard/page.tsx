"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { KPICard } from "@/components/dashboard/KPICard";
import { FunnelChart } from "@/components/dashboard/FunnelChart";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";

type Funnel = { contacts_total?: number; contacted?: number; sent?: number; replied?: number; replied_positive?: number };

export default function DashboardPage() {
  const { data: funnel } = useQuery({
    queryKey: ["analytics", "funnel"],
    queryFn: () => apiClient<Funnel>("analytics/analytics/funnel"),
    refetchInterval: 60_000,
  });
  const { data: flows } = useQuery({
    queryKey: ["flows", "recent"],
    queryFn: () =>
      apiClient<
        Array<{
          id: string;
          flow_type: string;
          status: string;
          current_step: string | null;
          completed_steps: number;
          total_steps: number;
        }>
      >("orchestrator/flows?limit=5"),
    refetchInterval: 30_000,
  });
  const { data: reviews } = useQuery({
    queryKey: ["reviews", "pending-count"],
    queryFn: () => apiClient<unknown[]>("reviews/review-items?status=pending&limit=100"),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="grid grid-cols-4 gap-4">
        <KPICard label="Связались" value={funnel?.contacted ?? "—"} />
        <KPICard label="Отправлено" value={funnel?.sent ?? "—"} />
        <KPICard label="Ответили" value={funnel?.replied ?? "—"} accent="blue" />
        <KPICard label="На ревью" value={reviews?.length ?? "—"}
          accent={reviews && reviews.length > 20 ? "amber" : "default"} href="/reviews" />
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Funnel</h2>
          <FunnelChart data={funnel} />
        </div>
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Последние flows</h2>
          <ActivityFeed flows={flows || []} />
        </div>
      </div>
    </div>
  );
}
