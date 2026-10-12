"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { FlowDetail } from "@/components/flows/FlowDetail";
import { use } from "react";

export default function FlowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: flow } = useQuery({
    queryKey: ["flows", id],
    queryFn: () => apiClient<never>(`orchestrator/flows/${id}`),
    refetchInterval: 10_000,
  });
  const { data: steps } = useQuery({
    queryKey: ["flows", id, "steps"],
    queryFn: () => apiClient<Array<Record<string, unknown>>>(`orchestrator/flows/${id}/steps`),
    refetchInterval: 10_000,
  });

  if (!flow) return <div className="text-slate-500">Загрузка...</div>;
  return <FlowDetail flow={flow as never} steps={steps || []} />;
}
