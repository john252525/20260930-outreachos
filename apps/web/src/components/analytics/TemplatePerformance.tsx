import { DataTable, Column } from "@/components/shared/DataTable";
import { formatPercent } from "@/lib/utils";

export function TemplatePerformance({ templates }: { templates: Array<Record<string, unknown>> }) {
  const columns: Column<Record<string, unknown>>[] = [
    { key: "template_id", label: "Template" },
    { key: "template_version", label: "Version" },
    { key: "sent", label: "Sent", align: "right" },
    { key: "replied", label: "Replied", align: "right" },
    { key: "reply_rate", label: "Reply rate", align: "right",
      render: (v) => formatPercent(v as number) },
    { key: "bounce_rate", label: "Bounce rate", align: "right",
      render: (v) => formatPercent(v as number) },
  ];
  return <DataTable columns={columns} data={templates} empty="Нет данных" />;
}
