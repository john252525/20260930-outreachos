"use client";

import { useState } from "react";
import Link from "next/link";
import { useProjects, useCreateProject, BriefSummary } from "@/lib/hooks/use-projects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { PlusCircle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

const STATUS_LABEL: Record<string, string> = {
  in_progress: "В работе",
  complete: "Готов",
  draft: "Черновик",
  abandoned: "Отменён",
  archived: "Архив",
};

export default function ProjectsPage() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const router = useRouter();
  const { data, isLoading } = useProjects();
  const create = useCreateProject();

  async function onCreate() {
    if (text.trim().length < 10) {
      toast.error("Опишите проект хотя бы одним предложением");
      return;
    }
    try {
      const brief = await create.mutateAsync(text.trim());
      toast.success("Проект создан");
      setOpen(false);
      setText("");
      router.push(`/projects/${brief.id}`);
    } catch {
      toast.error("Не удалось создать проект");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Проекты</h1>
          <p className="text-sm text-slate-500 mt-1">
            Каждый проект — отдельная инициатива: вводные → ЦА → поиск → письма
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <PlusCircle className="h-4 w-4 mr-2" /> Новый проект
        </Button>
      </div>

      {isLoading && <div className="text-slate-500">Загрузка...</div>}
      {data && data.length === 0 && (
        <div className="text-slate-500 text-center py-12">
          Пока нет проектов. Нажмите «Новый проект», чтобы начать.
        </div>
      )}
      {data && data.length > 0 && (
        <div className="space-y-3">
          {data.map((p: BriefSummary) => (
            <Link key={p.id} href={`/projects/${p.id}`}
              className="block p-4 bg-white border rounded-lg hover:border-slate-400 transition">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium truncate">
                      {p.project_name || "Проект " + p.id.slice(0, 8)}
                    </span>
                    <Badge variant="outline">{STATUS_LABEL[p.status] || p.status}</Badge>
                  </div>
                  <div className="text-xs text-slate-500">
                    Полнота брифа: {(p.completeness_score * 100).toFixed(0)}%
                  </div>
                </div>
                <div className="text-xs text-slate-400 whitespace-nowrap">
                  {formatDistanceToNow(new Date(p.updated_at), { addSuffix: true, locale: ru })}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Новый проект</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <label className="text-sm text-slate-600">
              Опишите проект свободным текстом (что продаём, кому, зачем). Можно вставить ссылку на сайт.
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={8}
              placeholder="Например: Производим гидроборты для грузовиков, ищем дистрибьюторов в РФ. Сайт: https://..."
              className="w-full border rounded p-3 text-sm"
            />
            <p className="text-xs text-slate-400">
              Дальше система сама задаст уточняющие вопросы и определит целевую аудиторию.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Отмена</Button>
            <Button onClick={onCreate} disabled={create.isPending}>
              {create.isPending ? "Создание..." : "Создать"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
