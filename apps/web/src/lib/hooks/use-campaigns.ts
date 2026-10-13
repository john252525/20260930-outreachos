"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type Campaign = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  goals: Record<string, unknown>;
  metrics: Record<string, number>;
  created_at: string;
};

export function useCampaigns(status?: string) {
  const params = new URLSearchParams({ limit: "100" });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: ["campaigns", status],
    queryFn: () => apiClient<Campaign[]>(`campaigns/campaigns?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      apiClient("campaigns/campaigns", {
        method: "POST",
        body: { name },
        idempotencyKey: `campaign-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}
