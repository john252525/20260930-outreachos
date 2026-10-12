import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ReviewItem } from "@/lib/hooks/use-reviews";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  normal: "bg-slate-100 text-slate-700",
  low: "bg-slate-50 text-slate-500",
};

export function ReviewList({ items }: { items: ReviewItem[] }) {
  if (items.length === 0) {
    return <div className="text-slate-500 text-center py-12">Очередь пуста</div>;
  }
  return (
    <div className="space-y-3">
      {items.map((item) => {
        const snap = item.snapshot || { subject: null, body_preview: "", warnings: [], factual_claims_count: 0 };
        return (
          <Link
            key={item.id}
            href={`/reviews/${item.id}`}
            className="block p-4 bg-white border rounded-lg hover:border-slate-400 transition"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <Badge className={PRIORITY_COLORS[item.priority] || PRIORITY_COLORS.normal}>
                    {item.priority}
                  </Badge>
                  <Badge variant="outline">{item.channel}</Badge>
                  {snap.warnings && snap.warnings.length > 0 && (
                    <Badge className="bg-amber-100 text-amber-700">{snap.warnings.length} warnings</Badge>
                  )}
                  {snap.factual_claims_count > 0 && (
                    <Badge variant="outline">{snap.factual_claims_count} claims</Badge>
                  )}
                </div>
                <div className="font-medium truncate">{snap.subject || "(без темы)"}</div>
                <div className="text-sm text-slate-500 line-clamp-2 mt-1">{snap.body_preview}</div>
              </div>
              <div className="text-xs text-slate-400 whitespace-nowrap">
                {item.created_at
                  ? formatDistanceToNow(new Date(item.created_at), { addSuffix: true, locale: ru })
                  : ""}
              </div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
