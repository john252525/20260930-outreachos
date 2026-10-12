"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function RevisionsPage() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["revisions"],
    queryFn: () => apiClient<Array<Record<string, unknown>>>("revisions/revisions?limit=100"),
    refetchInterval: 30_000,
  });

  const approve = useMutation({
    mutationFn: (id: string) =>
      apiClient(`revisions/revisions/${id}/approve`, {
        method: "POST",
        idempotencyKey: `approve-${id}-${Date.now()}`,
      }),
    onSuccess: () => {
      toast.success("Одобрено");
      qc.invalidateQueries({ queryKey: ["revisions"] });
    },
    onError: () => toast.error("Ошибка"),
  });

  const columns: Column<Record<string, unknown>>[] = [
    { key: "template_id", label: "Шаблон" },
    { key: "trigger_type", label: "Триггер" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "llm_confidence", label: "Confidence",
      render: (v) => `${(Number(v) * 100).toFixed(0)}%` },
    { key: "diagnosis", label: "Диагноз",
      render: (v) => (
        <span className="line-clamp-2 max-w-md text-xs text-slate-600">{String(v || "")}</span>
      ) },
    { key: "id", label: "", render: (v, row) =>
      row.status === "pending" ? (
        <Button size="sm" variant="outline" onClick={() => approve.mutate(String(v))}>
          Approve
        </Button>
      ) : null },
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Revisions</h1>
      <DataTable columns={columns} data={data || []} empty="Нет ревизий" />
    </div>
  );
}
