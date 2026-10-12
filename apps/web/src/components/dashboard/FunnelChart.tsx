"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type FunnelData = {
  contacts_total?: number;
  contacted?: number;
  sent?: number;
  replied?: number;
  replied_positive?: number;
};

export function FunnelChart({ data }: { data?: FunnelData }) {
  if (!data) return <div className="text-slate-400">Нет данных</div>;
  const chartData = [
    { name: "Связались", value: data.contacted ?? 0 },
    { name: "Отправлено", value: data.sent ?? 0 },
    { name: "Ответили", value: data.replied ?? 0 },
    { name: "Positive", value: data.replied_positive ?? 0 },
  ];
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={chartData} layout="vertical">
        <XAxis type="number" />
        <YAxis dataKey="name" type="category" width={110} />
        <Tooltip />
        <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0] as [number, number, number, number]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
