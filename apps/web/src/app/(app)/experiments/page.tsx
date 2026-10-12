"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";

export default function ExperimentsPage() {
  const { data } = useQuery({
    queryKey: ["experiments"],
    queryFn: () => apiClient<Array<Record<string, unknown>>>("experiments/experiments?limit=100"),
    refetchInterval: 30_000,
  });
  const columns: Column<Record<string, unknown>>[] = [
    { key: "name", label: "Название" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "variable_type", label: "Переменная" },
    { key: "variants", label: "Вариантов", render: (v) => String((v as unknown[])?.length ?? 0) },
    { key: "results", label: "Победитель",
      render: (v) => String((v as Record<string, unknown>)?.winner_variant_id ?? "—") },
  ];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Experiments</h1>
      <DataTable columns={columns} data={data || []} empty="Нет экспериментов" />
    </div>
  );
}
