"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { apiClient } from "@/lib/api-client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

type SettingsDict = Record<string, unknown>;

const BOOL_FIELDS = [
  ["auto_brief_to_icp", "Авто: brief → ICP"],
  ["auto_icp_to_sourcing", "Авто: ICP → sourcing"],
  ["auto_contacts_to_drafts", "Авто: контакты → черновики"],
  ["auto_drafts_to_review", "Авто: черновики → ревью"],
  ["auto_approved_to_send", "Авто: одобрено → отправка"],
  ["auto_revision_enabled", "Авто-ревизия"],
  ["email_enabled", "Email канал"],
  ["telegram_enabled", "Telegram канал"],
  ["linkedin_enabled", "LinkedIn канал"],
] as const;

export default function SettingsPage() {
  const { data: session } = useSession();
  const tenantId = session?.user?.tenantId;
  const [form, setForm] = useState<SettingsDict>({});

  const { data } = useQuery({
    queryKey: ["settings", tenantId],
    queryFn: () => apiClient<SettingsDict>(`tenants/tenants/${tenantId}/settings`),
    enabled: !!tenantId,
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const save = useMutation({
    mutationFn: (payload: SettingsDict) =>
      apiClient(`tenants/tenants/${tenantId}/settings`, {
        method: "PATCH",
        body: payload,
        idempotencyKey: `settings-${Date.now()}`,
      }),
    onSuccess: () => toast.success("Сохранено"),
    onError: () => toast.error("Ошибка сохранения"),
  });

  function onSave() {
    const payload: SettingsDict = {};
    for (const [k] of BOOL_FIELDS) {
      if (k in form) payload[k] = form[k];
    }
    for (const k of ["default_limit_per_source", "default_max_contacts_per_flow", "default_sender_daily_limit"]) {
      if (k in form) payload[k] = Number(form[k]);
    }
    save.mutate(payload);
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <div className="flex gap-3">
        <Link href="/settings/users" className="text-sm text-blue-600 hover:underline">
          Пользователи и роли →
        </Link>
        <Link href="/settings/audit" className="text-sm text-blue-600 hover:underline">
          Журнал действий →
        </Link>
      </div>
      <div className="bg-white border rounded-lg p-6 space-y-3">
        {BOOL_FIELDS.map(([key, label]) => (
          <label key={key} className="flex items-center gap-3 text-sm">
            <input
              type="checkbox"
              checked={Boolean(form[key])}
              onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
            />
            {label}
          </label>
        ))}
      </div>
      <div className="bg-white border rounded-lg p-6 space-y-3">
        <div className="font-medium">Лимиты</div>
        {[
          ["default_limit_per_source", "Лимит на источник"],
          ["default_max_contacts_per_flow", "Макс контактов на flow"],
          ["default_sender_daily_limit", "Дневной лимит отправки"],
        ].map(([key, label]) => (
          <div key={key}>
            <label className="text-sm text-slate-600">{label}</label>
            <Input
              type="number"
              value={String(form[key] ?? "")}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
          </div>
        ))}
      </div>
      <Button onClick={onSave} disabled={save.isPending}>
        {save.isPending ? "Сохранение..." : "Сохранить"}
      </Button>
    </div>
  );
}
