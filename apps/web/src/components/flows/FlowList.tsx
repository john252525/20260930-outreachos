import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { DataTable, Column } from "@/components/shared/DataTable";

type FlowRow = {
  id: string;
  flow_type: string;
  status: string;
  brief_id: string | null;
  current_step: string | null;
  completed_steps: number;
  total_steps: number;
  created_at: string;
};

export function FlowList({ items }: { items: FlowRow[] }) {
  const columns: Column<Record<string, unknown>>[] = [
    { key: "id", label: "ID", render: (v) => (
      <Link className="text-blue-600 hover:underline font-mono text-xs" href={`/flows/${v}`}>
        {String(v).slice(0, 8)}
      </Link>
    ) },
    { key: "flow_type", label: "Тип" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "current_step", label: "Шаг", render: (v) => String(v ?? "—") },
    { key: "completed_steps", label: "Прогресс", render: (_v, row) => `${row.completed_steps}/${row.total_steps}` },
    { key: "brief_id", label: "Brief", render: (v) => (
      <span className="font-mono text-xs">{v ? String(v).slice(0, 8) : "—"}</span>
    ) },
  ];
  return <DataTable columns={columns} data={items as unknown as Record<string, unknown>[]} empty="Нет flows" />;
}
