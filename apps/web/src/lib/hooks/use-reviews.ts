"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ReviewItem = {
  id: string;
  message_id: string;
  contact_id: string;
  channel: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  reviewed_by: string | null;
  snapshot: {
    subject: string | null;
    body_preview: string;
    warnings: string[];
    factual_claims_count: number;
  };
  created_at: string;
};

export function useReviews(filters: { status?: string; priority?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.priority) params.set("priority", filters.priority);
  return useQuery({
    queryKey: ["reviews", filters],
    queryFn: () => apiClient<ReviewItem[]>(`reviews/review-items?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useReview(id: string) {
  return useQuery({
    queryKey: ["reviews", id],
    queryFn: () => apiClient<ReviewItem>(`reviews/review-items/${id}`),
  });
}

export function useApproveReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, scheduledAt }: { id: string; scheduledAt?: string }) =>
      apiClient(`reviews/review-items/${id}/approve`, {
        method: "POST",
        body: { scheduled_send_at: scheduledAt || null },
        idempotencyKey: `approve-${id}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}

export function useRejectReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason, note }: { id: string; reason: string; note?: string }) =>
      apiClient(`reviews/review-items/${id}/reject`, {
        method: "POST",
        body: { reason, note },
        idempotencyKey: `reject-${id}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}

export function useEditReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, subject, bodyText }: { id: string; subject?: string; bodyText: string }) =>
      apiClient(`reviews/review-items/${id}/edit`, {
        method: "POST",
        body: { subject, body_text: bodyText },
        idempotencyKey: `edit-${id}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}
