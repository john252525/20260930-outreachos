"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";

export default function MessagesPage() {
  const { data } = useQuery({
    queryKey: ["messages", "list"],
    queryFn: () => apiClient<Array<Record<string, unknown>>>("messages/messages?limit=100"),
    refetchInterval: 30_000,
  });
  const columns: Column<Record<string, unknown>>[] = [
    { key: "subject", label: "Тема", render: (v) => String(v || "(без темы)") },
    { key: "channel", label: "Канал" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "word_count", label: "Слов", align: "right" },
    { key: "created_at", label: "Создано",
      render: (v) => (v ? new Date(String(v)).toLocaleString("ru") : "—") },
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Messages</h1>
      <DataTable columns={columns} data={data || []} empty="Нет писем" />
    </div>
  );
}
