"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FlowStepsTimeline } from "./FlowStepsTimeline";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Play, Pause, X } from "lucide-react";

type Flow = {
  id: string;
  flow_type: string;
  status: string;
  brief_id: string | null;
  icp_id: string | null;
  search_job_id: string | null;
  completed_steps: number;
  total_steps: number;
  error: string | null;
};

export function FlowDetail({ flow, steps }: { flow: Flow; steps: Array<Record<string, unknown>> }) {
  const qc = useQueryClient();

  async function action(name: string) {
    try {
      await apiClient(`orchestrator/flows/${flow.id}/${name}`, {
        method: "POST",
        idempotencyKey: `${name}-${flow.id}-${Date.now()}`,
      });
      toast.success(`OK: ${name}`);
      qc.invalidateQueries({ queryKey: ["flows", flow.id] });
    } catch {
      toast.error(`Ошибка: ${name}`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Flow {flow.id.slice(0, 8)}</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge>{flow.flow_type}</Badge>
            <Badge variant="outline">{flow.status}</Badge>
            <span className="text-sm text-slate-500">{flow.completed_steps}/{flow.total_steps} steps</span>
          </div>
        </div>
        <div className="flex gap-2">
          {flow.status === "running" && (
            <Button variant="outline" onClick={() => action("pause")}>
              <Pause className="h-4 w-4 mr-2" /> Пауза
            </Button>
          )}
          {flow.status === "paused" && (
            <Button variant="outline" onClick={() => action("resume")}>
              <Play className="h-4 w-4 mr-2" /> Продолжить
            </Button>
          )}
          {["running", "paused"].includes(flow.status) && (
            <Button variant="destructive" onClick={() => action("cancel")}>
              <X className="h-4 w-4 mr-2" /> Отменить
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <InfoBox label="Brief ID" value={flow.brief_id} />
        <InfoBox label="ICP ID" value={flow.icp_id} />
        <InfoBox label="Search Job ID" value={flow.search_job_id} />
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="font-semibold mb-4">Шаги</h2>
        <FlowStepsTimeline steps={steps as never} />
      </div>

      {flow.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{flow.error}</div>
      )}
    </div>
  );
}

function InfoBox({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="text-slate-500">{label}</div>
      <div className="font-mono text-xs mt-1">{value ? value.slice(0, 8) : "—"}</div>
    </div>
  );
}
