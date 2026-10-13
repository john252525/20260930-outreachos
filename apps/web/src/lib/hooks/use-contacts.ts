"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type Contact = {
  id: string;
  tenant_id: string;
  company_id: string | null;
  status: string;
  payload: {
    full_name?: { value?: string };
    position?: { value?: string };
    emails?: Array<{ value: string; is_primary?: boolean }>;
    phones?: Array<{ value: string; is_primary?: boolean }>;
  };
  replied_positive: boolean;
  last_contacted_at: string | null;
  last_reply_at: string | null;
  created_at: string;
};

export type Company = {
  id: string;
  tenant_id: string;
  status: string;
  payload: {
    name?: { value?: string };
    domain?: { value?: string };
    industry?: { value?: string };
  };
  contacts_count: number;
  created_at: string;
};

export function useContacts(status?: string, limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (status) params.set("status", status);
  return useQuery({
    queryKey: ["contacts", status, limit],
    queryFn: () => apiClient<Contact[]>(`contacts/contacts?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useCompanies(limit = 100) {
  return useQuery({
    queryKey: ["companies", limit],
    queryFn: () => apiClient<Company[]>(`companies/companies?limit=${limit}`),
    refetchInterval: 30_000,
  });
}
