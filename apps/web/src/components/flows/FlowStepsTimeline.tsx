import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react";

type Step = {
  id: string;
  step_name: string;
  status: string;
  attempts: number;
  duration_ms: number | null;
  error: string | null;
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  completed: <CheckCircle2 className="h-5 w-5 text-green-500" />,
  running: <Clock className="h-5 w-5 text-blue-500" />,
  failed: <XCircle className="h-5 w-5 text-red-500" />,
  retry_scheduled: <AlertCircle className="h-5 w-5 text-amber-500" />,
  pending: <Clock className="h-5 w-5 text-slate-300" />,
  skipped: <Clock className="h-5 w-5 text-slate-300" />,
};

export function FlowStepsTimeline({ steps }: { steps: Step[] }) {
  if (steps.length === 0) return <div className="text-slate-400">Нет шагов</div>;
  return (
    <div className="space-y-3">
      {steps.map((step) => (
        <div key={step.id} className="flex items-start gap-3">
          <div className="mt-0.5">{STATUS_ICONS[step.status] || STATUS_ICONS.pending}</div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium">{step.step_name}</span>
              <Badge variant="outline">{step.status}</Badge>
              {step.attempts > 1 && <span className="text-xs text-slate-500">attempts: {step.attempts}</span>}
              {step.duration_ms != null && (
                <span className="text-xs text-slate-500">{(step.duration_ms / 1000).toFixed(1)}s</span>
              )}
            </div>
            {step.error && <div className="text-xs text-red-600 mt-1">{step.error}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
