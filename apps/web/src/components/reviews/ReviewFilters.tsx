"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function ReviewFilters({
  filters,
  onChange,
}: {
  filters: { status?: string; priority?: string };
  onChange: (f: { status?: string; priority?: string }) => void;
}) {
  return (
    <div className="flex gap-3">
      <Select
        value={filters.status || "all"}
        onValueChange={(v) => onChange({ ...filters, status: v === "all" ? undefined : v })}
      >
        <SelectTrigger className="w-[180px]"><SelectValue placeholder="Статус" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Все статусы</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
          <SelectItem value="approved">Approved</SelectItem>
          <SelectItem value="rejected">Rejected</SelectItem>
        </SelectContent>
      </Select>
      <Select
        value={filters.priority || "all"}
        onValueChange={(v) => onChange({ ...filters, priority: v === "all" ? undefined : v })}
      >
        <SelectTrigger className="w-[180px]"><SelectValue placeholder="Приоритет" /></SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Все</SelectItem>
          <SelectItem value="high">High</SelectItem>
          <SelectItem value="normal">Normal</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
