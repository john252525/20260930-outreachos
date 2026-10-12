import Link from "next/link";
import { Badge } from "@/components/ui/badge";

type FlowRow = {
  id: string;
  flow_type: string;
  status: string;
  current_step: string | null;
  completed_steps: number;
  total_steps: number;
};

export function ActivityFeed({ flows }: { flows: FlowRow[] }) {
  if (!flows.length) return <div className="text-slate-400">Нет flows</div>;
  return (
    <div className="space-y-2">
      {flows.map((f) => (
        <Link key={f.id} href={`/flows/${f.id}`}
          className="flex items-center justify-between p-3 rounded border hover:bg-slate-50">
          <div className="min-w-0">
            <div className="font-mono text-xs text-slate-500">{f.id.slice(0, 8)}</div>
            <div className="text-sm truncate">{f.current_step || f.flow_type}</div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs text-slate-400">{f.completed_steps}/{f.total_steps}</span>
            <Badge variant="outline">{f.status}</Badge>
          </div>
        </Link>
      ))}
    </div>
  );
}
