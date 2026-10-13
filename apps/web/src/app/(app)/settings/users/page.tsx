"use client";

import { useState } from "react";
import Link from "next/link";
import { useMembers, useInvitations, useInviteUser, Membership } from "@/lib/hooks/use-users";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { ArrowLeft } from "lucide-react";

const ROLE_LABEL: Record<string, string> = {
  admin: "Администратор",
  manager: "Менеджер",
  viewer: "Наблюдатель",
};

export default function UsersSettingsPage() {
  const { data: members } = useMembers();
  const { data: invitations } = useInvitations();
  const invite = useInviteUser();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("manager");

  async function onInvite() {
    if (!email.includes("@")) {
      toast.error("Введите корректный email");
      return;
    }
    try {
      await invite.mutateAsync({ email, role });
      toast.success("Приглашение создано");
      setOpen(false);
      setEmail("");
    } catch {
      toast.error("Не удалось пригласить");
    }
  }

  const memberCols: Column<Record<string, unknown>>[] = [
    { key: "user_id", label: "User ID", render: (v) => <span className="font-mono text-xs">{String(v).slice(0, 8)}</span> },
    { key: "role", label: "Роль", render: (v) => <Badge>{ROLE_LABEL[String(v)] || String(v)}</Badge> },
    { key: "is_owner", label: "Владелец", render: (v) => (v ? "✓" : "—") },
    { key: "is_active", label: "Активен", render: (v) => (v ? "✓" : "—") },
    { key: "accepted_at", label: "Принял", render: (v) => (v ? new Date(String(v)).toLocaleDateString("ru") : "—") },
  ];

  const inviteCols: Column<Record<string, unknown>>[] = [
    { key: "email", label: "Email" },
    { key: "role", label: "Роль", render: (v) => ROLE_LABEL[String(v)] || String(v) },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{String(v)}</Badge> },
    { key: "expires_at", label: "Истекает", render: (v) => new Date(String(v)).toLocaleDateString("ru") },
  ];

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/settings" className="text-sm text-slate-500 hover:underline flex items-center gap-1">
            <ArrowLeft className="h-3.5 w-3.5" /> Настройки
          </Link>
          <h1 className="text-2xl font-semibold mt-1">Пользователи</h1>
        </div>
        <div className="flex gap-2">
          <Link href="/settings/audit" className="text-sm text-blue-600 hover:underline self-center">
            Журнал действий →
          </Link>
          <Button onClick={() => setOpen(true)}>Пригласить</Button>
        </div>
      </div>

      <div className="bg-white border rounded-lg p-4">
        <h2 className="font-medium mb-3">Участники</h2>
        <DataTable columns={memberCols} data={(members || []) as unknown as Record<string, unknown>[]} empty="Нет участников" />
      </div>

      <div className="bg-white border rounded-lg p-4">
        <h2 className="font-medium mb-3">Приглашения</h2>
        <DataTable columns={inviteCols} data={(invitations || []) as unknown as Record<string, unknown>[]} empty="Нет приглашений" />
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Пригласить пользователя</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input placeholder="email@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <select value={role} onChange={(e) => setRole(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm bg-white">
              <option value="manager">Менеджер</option>
              <option value="admin">Администратор</option>
              <option value="viewer">Наблюдатель</option>
            </select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={onInvite} disabled={invite.isPending}>Пригласить</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
