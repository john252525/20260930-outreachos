import Link from "next/link";
import { cn } from "@/lib/utils";

const ACCENTS: Record<string, string> = {
  default: "text-slate-900",
  blue: "text-blue-600",
  amber: "text-amber-600",
  red: "text-red-600",
};

export function KPICard({
  label,
  value,
  accent = "default",
  href,
}: {
  label: string;
  value: number | string;
  accent?: string;
  href?: string;
}) {
  const content = (
    <div className="bg-white border rounded-lg p-6 hover:border-slate-400 transition">
      <div className="text-sm text-slate-500">{label}</div>
      <div className={cn("text-3xl font-semibold mt-2", ACCENTS[accent])}>{value}</div>
    </div>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}
