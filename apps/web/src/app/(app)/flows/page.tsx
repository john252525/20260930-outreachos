"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { FlowList } from "@/components/flows/FlowList";
import { useState } from "react";

export default function FlowsPage() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data } = useQuery({
    queryKey: ["flows", status],
    queryFn: () => apiClient<Array<Record<string, unknown>>>(
      `orchestrator/flows${status ? `?status=${status}` : ""}`,
    ),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Flows</h1>
        <select value={status || ""} onChange={(e) => setStatus(e.target.value || undefined)}
          className="border rounded px-3 py-2 text-sm bg-white">
          <option value="">Все</option>
          <option value="running">Running</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      <FlowList items={(data || []) as never} />
    </div>
  );
}
