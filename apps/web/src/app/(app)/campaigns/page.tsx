"use client";

import { useState } from "react";
import { useCampaigns, useCreateCampaign, Campaign } from "@/lib/hooks/use-campaigns";
import { DataTable, Column } from "@/components/shared/DataTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { PlusCircle } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик", active: "Активна", paused: "Пауза",
  completed: "Завершена", archived: "Архив",
};

export default function CampaignsPage() {
  const { data } = useCampaigns();
  const create = useCreateCampaign();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");

  async function onCreate() {
    if (!name.trim()) { toast.error("Введите название"); return; }
    try {
      await create.mutateAsync(name.trim());
      toast.success("Кампания создана");
      setOpen(false); setName("");
    } catch { toast.error("Не удалось создать"); }
  }

  const columns: Column<Record<string, unknown>>[] = [
    { key: "name", label: "Кампания" },
    { key: "status", label: "Статус", render: (v) => <Badge variant="outline">{STATUS_LABEL[String(v)] || String(v)}</Badge> },
    { key: "start_date", label: "Начало", render: (v) => (v ? String(v) : "—") },
    { key: "end_date", label: "Конец", render: (v) => (v ? String(v) : "—") },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Кампании</h1>
          <p className="text-sm text-slate-500 mt-1">Бизнес-инициативы, объединяющие несколько проектов</p>
        </div>
        <Button onClick={() => setOpen(true)}><PlusCircle className="h-4 w-4 mr-2" /> Новая кампания</Button>
      </div>
      <div className="bg-white border rounded-lg p-4">
        <DataTable columns={columns} data={(data || []) as unknown as Record<string, unknown>[]} empty="Нет кампаний" />
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Новая кампания</DialogTitle></DialogHeader>
          <Input placeholder="Напр. Q1 2026 — гидроборты" value={name} onChange={(e) => setName(e.target.value)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={onCreate} disabled={create.isPending}>Создать</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
