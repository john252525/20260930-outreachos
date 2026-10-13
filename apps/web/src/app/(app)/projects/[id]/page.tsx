"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  useProject,
  useAnswerQuestion,
  useCompleteProject,
  useActiveICP,
  useSearches,
  QAItem,
} from "@/lib/hooks/use-projects";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { CheckCircle2, Circle, GitBranch, Send, Target, Search, MessageSquare } from "lucide-react";

const STATUS_LABEL: Record<string, string> = {
  in_progress: "В работе",
  complete: "Готов",
  draft: "Черновик",
  abandoned: "Отменён",
  archived: "Архив",
};

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: brief, isLoading } = useProject(id);
  const { data: icp } = useActiveICP(id);
  const { data: searches } = useSearches();
  const answer = useAnswerQuestion(id);
  const complete = useCompleteProject(id);
  const [drafts, setDrafts] = useState<Record<number, string>>({});

  if (isLoading) return <div className="text-slate-500">Загрузка...</div>;
  if (!brief) return <div className="text-slate-500">Проект не найден</div>;

  const qa = brief.qa_history || [];
  const pendingIndex = qa.findIndex((q: QAItem) => !q.answered_at);
  const isComplete = brief.status === "complete";

  const projectSearches = (searches || []).filter(
    (s) => icp && s.icp_id === icp.id,
  );

  async function onAnswer(idx: number) {
    const value = (drafts[idx] || "").trim();
    if (!value) {
      toast.error("Введите ответ");
      return;
    }
    try {
      await answer.mutateAsync({ questionIndex: idx, answer: value });
      setDrafts((d) => ({ ...d, [idx]: "" }));
      toast.success("Ответ сохранён");
    } catch {
      toast.error("Не удалось сохранить ответ");
    }
  }

  async function onComplete() {
    try {
      await complete.mutateAsync();
      toast.success("Проект завершён. Система анализирует ЦА.");
    } catch {
      toast.error("Не удалось завершить проект");
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">
            {(brief.identity?.project_name as string) || "Проект " + brief.id.slice(0, 8)}
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge variant="outline">{STATUS_LABEL[brief.status] || brief.status}</Badge>
            <span className="text-sm text-slate-500">
              Полнота: {(brief.completeness_score * 100).toFixed(0)}%
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {!isComplete && (
            <Button variant="outline" onClick={onComplete} disabled={complete.isPending}>
              <CheckCircle2 className="h-4 w-4 mr-2" /> Завершить бриф
            </Button>
          )}
        </div>
      </div>

      {/* Этапы пайплайна */}
      <Stages brief={brief} icp={icp ?? null} searches={projectSearches} />

      {/* Вводные */}
      <Section title="Вводные" icon={<MessageSquare className="h-4 w-4" />}>
        <div className="text-sm whitespace-pre-line text-slate-700">
          {(brief.raw_input?.text as string) || "(нет текста)"}
        </div>
        {(brief.raw_input?.urls || []).length > 0 && (
          <div className="mt-2 text-xs text-slate-500">
            Источники: {(brief.raw_input.urls || []).join(", ")}
          </div>
        )}
      </Section>

      {/* Вопросы/ответы */}
      <Section title="Уточняющие вопросы" icon={<Circle className="h-4 w-4" />}>
        {qa.length === 0 && <div className="text-sm text-slate-400">Вопросов пока нет</div>}
        <div className="space-y-4">
          {qa.map((q: QAItem, idx: number) => {
            const answered = Boolean(q.answered_at);
            const isPending = idx === pendingIndex && !answered;
            return (
              <div key={idx} className="border rounded-lg p-4">
                <div className="flex items-start gap-2">
                  {answered
                    ? <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                    : <Circle className="h-4 w-4 text-slate-300 mt-0.5 shrink-0" />}
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-800">{q.question}</div>
                    {q.priority && (
                      <Badge variant="outline" className="mt-1 text-xs">{q.priority}</Badge>
                    )}
                    {answered ? (
                      <div className="mt-2 text-sm text-slate-600 whitespace-pre-line">
                        {q.answer}
                      </div>
                    ) : isPending ? (
                      <div className="mt-3 flex gap-2">
                        <Input
                          value={drafts[idx] || ""}
                          onChange={(e) => setDrafts((d) => ({ ...d, [idx]: e.target.value }))}
                          placeholder="Ваш ответ..."
                          onKeyDown={(e) => { if (e.key === "Enter") onAnswer(idx); }}
                        />
                        <Button onClick={() => onAnswer(idx)} disabled={answer.isPending}>
                          Ответить
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ЦА / ICP */}
      <Section title="Целевая аудитория" icon={<Target className="h-4 w-4" />}>
        {!icp && (
          <div className="text-sm text-slate-400">
            {isComplete
              ? "Система анализирует ЦА... (появится здесь автоматически)"
              : "Завершите бриф, чтобы система определила ЦА и сегменты"}
          </div>
        )}
        {icp && (
          <div className="space-y-3">
            <div className="text-xs text-slate-500">
              Версия {icp.version} · сегментов: {icp.segments_count} · уверенность:{" "}
              {(icp.llm_confidence * 100).toFixed(0)}%
            </div>
            {(icp.payload?.segments || []).map((seg) => (
              <div key={seg.id} className="border rounded-lg p-4">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{seg.name}</span>
                  {seg.priority && <Badge variant="outline">{seg.priority}</Badge>}
                </div>
                {seg.description && (
                  <div className="text-sm text-slate-600 mt-1">{seg.description}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Поиски */}
      <Section title="Поиск контактов" icon={<Search className="h-4 w-4" />}>
        {projectSearches.length === 0 && (
          <div className="text-sm text-slate-400">
            {icp ? "Поиски запустятся автоматически..." : "Сначала нужна ЦА"}
          </div>
        )}
        {projectSearches.length > 0 && (
          <div className="space-y-2">
            {projectSearches.map((s) => (
              <div key={s.id} className="flex items-center justify-between border rounded p-3 text-sm">
                <div>
                  <Badge variant="outline">{s.status}</Badge>
                  <span className="ml-2 text-slate-500">
                    найдено: {s.candidates_persisted_count} из {s.candidates_raw_count}
                  </span>
                </div>
                <span className="text-xs text-slate-400">
                  {s.duration_ms ? (s.duration_ms / 1000).toFixed(1) + "s" : ""}
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <div className="flex gap-3">
        <Link href="/flows" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          <GitBranch className="h-3.5 w-3.5" /> Смотреть flows
        </Link>
        <Link href="/reviews" className="text-sm text-blue-600 hover:underline flex items-center gap-1">
          <Send className="h-3.5 w-3.5" /> Ревью и отправка
        </Link>
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="bg-white border rounded-lg p-6">
      <div className="flex items-center gap-2 font-semibold mb-4">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function Stages({
  brief,
  icp,
  searches,
}: {
  brief: { status: string; completeness_score: number };
  icp: { segments_count: number } | null;
  searches: Array<{ candidates_persisted_count: number }>;
}) {
  const doneBrief = brief.status === "complete";
  const doneICP = Boolean(icp);
  const doneSearch = searches.some((s) => s.candidates_persisted_count > 0) || searches.length > 0;
  const contacts = searches.reduce((acc, s) => acc + s.candidates_persisted_count, 0);

  const steps = [
    { label: "Бриф", done: doneBrief, active: !doneBrief },
    { label: "ЦА / сегменты", done: doneICP, active: !doneICP && doneBrief },
    { label: "Поиск контактов", done: doneSearch, active: !doneSearch && doneICP, hint: contacts ? `${contacts} контактов` : undefined },
  ];

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {steps.map((s, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs ${
            s.done ? "bg-green-50 text-green-700" : s.active ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-400"
          }`}>
            {s.done ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
            {s.label}
            {s.hint && <span className="text-slate-400">· {s.hint}</span>}
          </div>
          {i < steps.length - 1 && <span className="text-slate-300">→</span>}
        </div>
      ))}
    </div>
  );
}
