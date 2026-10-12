import { DataTable, Column } from "@/components/shared/DataTable";
import { formatPercent } from "@/lib/utils";

export function SenderHealth({ senders }: { senders: Array<Record<string, unknown>> }) {
  const columns: Column<Record<string, unknown>>[] = [
    { key: "sender_email", label: "Sender" },
    { key: "sent", label: "Sent", align: "right" },
    { key: "bounced", label: "Bounced", align: "right" },
    { key: "bounce_rate", label: "Bounce rate", align: "right",
      render: (v) => formatPercent(v as number) },
  ];
  return <DataTable columns={columns} data={senders} empty="Нет данных" />;
}
