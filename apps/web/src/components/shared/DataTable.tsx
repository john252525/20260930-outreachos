import * as React from "react";

export type Column<T> = {
  key: string;
  label: string;
  align?: "left" | "right";
  render?: (value: unknown, row: T) => React.ReactNode;
};

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  empty = "Нет данных",
}: {
  columns: Column<T>[];
  data: T[];
  empty?: string;
}) {
  if (!data.length) return <div className="text-slate-400 py-6 text-center">{empty}</div>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b text-left text-slate-500">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={`py-2 px-3 font-medium ${c.align === "right" ? "text-right" : ""}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b last:border-0 hover:bg-slate-50">
              {columns.map((c) => (
                <td key={c.key} className={`py-2 px-3 ${c.align === "right" ? "text-right" : ""}`}>
                  {c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
