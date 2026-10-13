"use client";

import { useState } from "react";
import { useContacts, useCompanies, Contact, Company } from "@/lib/hooks/use-contacts";
import { Badge } from "@/components/ui/badge";
import { DataTable, Column } from "@/components/shared/DataTable";

const STATUS_LABEL: Record<string, string> = {
  candidate: "Кандидат",
  approved: "Одобрен",
  contacted: "Написали",
  replied: "Ответил",
  qualified: "Квалифицирован",
  disqualified: "Отказ",
  unsubscribed: "Отписка",
  bounced: "Недоставлено",
  archived: "Архив",
};

function fullName(c: Contact): string {
  return c.payload?.full_name?.value || "—";
}
function primaryEmail(c: Contact): string {
  const emails = c.payload?.emails || [];
  return emails.find((e) => e.is_primary)?.value || emails[0]?.value || "—";
}

export default function ContactsPage() {
  const [tab, setTab] = useState<"contacts" | "companies">("contacts");
  const { data: contacts, isLoading: lc } = useContacts();
  const { data: companies, isLoading: lco } = useCompanies();

  const contactCols: Column<Record<string, unknown>>[] = [
    { key: "id", label: "ID", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 8)}</span> },
    { key: "name", label: "Имя", render: (_v, r) => fullName(r as unknown as Contact) },
    { key: "position", label: "Должность", render: (_v, r) => (r as unknown as Contact).payload?.position?.value || "—" },
    { key: "email", label: "Email", render: (_v, r) => primaryEmail(r as unknown as Contact) },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{STATUS_LABEL[String(v)] || String(v)}</Badge> },
    { key: "replied_positive", label: "Позитив", render: (v) => (v ? "✓" : "—") },
  ];

  const companyCols: Column<Record<string, unknown>>[] = [
    { key: "id", label: "ID", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 8)}</span> },
    { key: "name", label: "Компания", render: (_v, r) => (r as unknown as Company).payload?.name?.value || "—" },
    { key: "domain", label: "Домен", render: (_v, r) => (r as unknown as Company).payload?.domain?.value || "—" },
    { key: "industry", label: "Отрасль", render: (_v, r) => (r as unknown as Company).payload?.industry?.value || "—" },
    { key: "contacts_count", label: "Контактов", align: "right" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{STATUS_LABEL[String(v)] || String(v)}</Badge> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Контакты</h1>
        <p className="text-sm text-slate-500 mt-1">База контактов и компаний, найденных системой</p>
      </div>

      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("contacts")}
          className={`px-4 py-2 text-sm border-b-2 -mb-px ${tab === "contacts" ? "border-slate-900 font-medium" : "border-transparent text-slate-500"}`}
        >
          Контакты {contacts ? `(${contacts.length})` : ""}
        </button>
        <button
          onClick={() => setTab("companies")}
          className={`px-4 py-2 text-sm border-b-2 -mb-px ${tab === "companies" ? "border-slate-900 font-medium" : "border-transparent text-slate-500"}`}
        >
          Компании {companies ? `(${companies.length})` : ""}
        </button>
      </div>

      <div className="bg-white border rounded-lg p-4">
        {tab === "contacts" && (
          lc ? <div className="text-slate-400 py-6 text-center">Загрузка...</div>
          : <DataTable columns={contactCols} data={(contacts || []) as unknown as Record<string, unknown>[]} empty="Нет контактов" />
        )}
        {tab === "companies" && (
          lco ? <div className="text-slate-400 py-6 text-center">Загрузка...</div>
          : <DataTable columns={companyCols} data={(companies || []) as unknown as Record<string, unknown>[]} empty="Нет компаний" />
        )}
      </div>
    </div>
  );
}
