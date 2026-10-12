"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type Message = {
  id: string;
  subject: string | null;
  body_text: string;
  body_html: string | null;
  channel: string;
  status: string;
  personalization: {
    template_id?: string;
    template_version?: string;
    factual_claims?: Array<{
      claim: string;
      evidence_url: string | null;
      confidence: number;
      is_hypothesis: boolean;
    }>;
    warnings?: string[];
  };
  sender: { from_name?: string; from_email?: string; signature?: string };
  recipient_snapshot: {
    email?: string;
    full_name?: string;
    position?: string;
    company_name?: string;
  };
  created_at: string;
};

export function useMessage(id: string) {
  return useQuery({
    queryKey: ["messages", id],
    queryFn: () => apiClient<Message>(`messages/messages/${id}`),
  });
}

export function useMessages(limit = 50) {
  return useQuery({
    queryKey: ["messages", "list", limit],
    queryFn: () => apiClient<Message[]>(`messages/messages?limit=${limit}`),
    refetchInterval: 30_000,
  });
}
