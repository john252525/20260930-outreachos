"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuditEvents, AuditEvent } from "@/lib/hooks/use-users";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ArrowLeft } from "lucide-react";

const ACTION_LABEL: Record<string, string> = {
  "user.registered": "Регистрация",
  "user.invited": "Приглашение",
  "user.role_changed": "Смена роли",
  "message.drafted": "Черновик письма",
  "message.approved": "Письмо одобрено",
  "revision.approved": "Ревизия одобрена",
};

export default function AuditSettingsPage() {
  const [action, setAction] = useState("");
  const { data } = useAuditEvents(action || undefined);

  const columns: Column<Record<string, unknown>>[] = [
    { key: "occurred_at", label: "Когда", render: (v) => new Date(String(v)).toLocaleString("ru") },
    { key: "actor_type", label: "Кто", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "action", label: "Действие", render: (v) => ACTION_LABEL[String(v)] || String(v) },
    { key: "resource_type", label: "Ресурс" },
    { key: "result", label: "Результат", render: (v) => (
      <Badge className={v === "success" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}>{String(v)}</Badge>
    ) },
    { key: "ip_address", label: "IP", render: (v) => String(v || "—") },
  ];

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <Link href="/settings/users" className="text-sm text-slate-500 hover:underline flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Пользователи
        </Link>
        <h1 className="text-2xl font-semibold mt-1">Журнал действий</h1>
        <p className="text-sm text-slate-500 mt-1">Audit log — для compliance и разбора инцидентов</p>
      </div>

      <Input placeholder="Фильтр по действию (напр. user.registered)" value={action}
        onChange={(e) => setAction(e.target.value)} className="max-w-md" />

      <div className="bg-white border rounded-lg p-4">
        <DataTable columns={columns}
          data={(data || []) as unknown as (Record<string, unknown> & AuditEvent)[]}
          empty="Нет событий" />
      </div>
    </div>
  );
}
