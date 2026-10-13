"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type BriefSummary = {
  id: string;
  status: string;
  completeness_score: number;
  project_name: string | null;
  created_at: string;
  updated_at: string;
};

export type QAItem = {
  question?: string;
  priority?: string;
  answer?: string | null;
  answered_at?: string | null;
  generated_by?: string;
};

export type Brief = {
  id: string;
  tenant_id: string;
  status: string;
  completeness_score: number;
  raw_input: { text?: string | null; urls?: string[] };
  qa_history: QAItem[];
  identity: Record<string, unknown>;
  offering: Record<string, unknown>;
  targeting_hints: Record<string, unknown>;
  outreach_goals: Record<string, unknown>;
  missing_info: Array<{ field?: string; label?: string; weight?: number }>;
  created_at: string;
  updated_at: string;
};

export type ICP = {
  id: string;
  brief_id: string;
  version: number;
  is_active: boolean;
  payload: {
    segments?: Array<{
      id: string;
      name?: string;
      description?: string;
      priority?: string;
      firmographic?: Record<string, unknown>;
    }>;
  };
  segments_count: number;
  llm_confidence: number;
};

export type SearchJob = {
  id: string;
  icp_id: string;
  segment_id: string;
  status: string;
  candidates_raw_count: number;
  candidates_persisted_count: number;
  total_cost_usd: number;
  duration_ms: number | null;
  created_at: string;
};

export function useProjects(status?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  return useQuery({
    queryKey: ["projects", status],
    queryFn: () => apiClient<BriefSummary[]>(`briefs/briefs?${params.toString()}&limit=100`),
    refetchInterval: 30_000,
  });
}

export function useProject(id: string) {
  return useQuery({
    queryKey: ["projects", id],
    queryFn: () => apiClient<Brief>(`briefs/briefs/${id}`),
    refetchInterval: 15_000,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) =>
      apiClient<Brief>("briefs/briefs", {
        method: "POST",
        body: { text },
        idempotencyKey: `project-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useAnswerQuestion(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ questionIndex, answer }: { questionIndex: number; answer: string }) =>
      apiClient<Brief>(`briefs/briefs/${projectId}/answers`, {
        method: "POST",
        body: { question_index: questionIndex, answer },
        idempotencyKey: `answer-${projectId}-${questionIndex}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", projectId] }),
  });
}

export function useCompleteProject(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient<Brief>(`briefs/briefs/${projectId}/complete`, {
        method: "POST",
        idempotencyKey: `complete-${projectId}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects", projectId] }),
  });
}

export function useActiveICP(briefId: string) {
  return useQuery({
    queryKey: ["icp", briefId],
    queryFn: async () => {
      try {
        return await apiClient<ICP>(`icps/icps/active/by-brief/${briefId}`);
      } catch {
        return null;
      }
    },
    refetchInterval: 20_000,
  });
}

export function useSearches(limit = 100) {
  return useQuery({
    queryKey: ["searches", limit],
    queryFn: () => apiClient<SearchJob[]>(`sourcing/searches?limit=${limit}`),
    refetchInterval: 20_000,
  });
}
