"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type Membership = {
  id: string;
  user_id: string;
  role: string;
  is_owner: boolean;
  is_active: boolean;
  accepted_at: string | null;
};

export type Invitation = {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
};

export type AuditEvent = {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  actor_type: string;
  action: string;
  resource_type: string;
  result: string;
  ip_address: string | null;
  occurred_at: string;
};

export function useMembers() {
  return useQuery({
    queryKey: ["members"],
    queryFn: () => apiClient<Membership[]>("users/tenant-users"),
    refetchInterval: 30_000,
  });
}

export function useInvitations() {
  return useQuery({
    queryKey: ["invitations"],
    queryFn: () => apiClient<Invitation[]>("users/invitations"),
    refetchInterval: 30_000,
  });
}

export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, role }: { email: string; role: string }) =>
      apiClient("users/invitations", {
        method: "POST",
        body: { email, role },
        idempotencyKey: `invite-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invitations"] }),
  });
}

export function useAuditEvents(action?: string) {
  const params = new URLSearchParams({ limit: "200" });
  if (action) params.set("action", action);
  return useQuery({
    queryKey: ["audit", action],
    queryFn: () => apiClient<AuditEvent[]>(`users/audit/events?${params.toString()}`),
    refetchInterval: 30_000,
  });
}
