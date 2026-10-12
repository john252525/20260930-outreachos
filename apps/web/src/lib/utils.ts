import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function shortId(id?: string | null, len = 8): string {
  return id ? id.slice(0, len) : "—";
}

export function formatPercent(v?: number | null): string {
  if (v === undefined || v === null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}
