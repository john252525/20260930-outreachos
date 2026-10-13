"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, GitBranch, CheckSquare, Send, BarChart3,
  FlaskConical, Wand2, Settings, FolderKanban, Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Проекты", icon: FolderKanban },
  { href: "/contacts", label: "Контакты", icon: Users },
  { href: "/flows", label: "Flows", icon: GitBranch },
  { href: "/reviews", label: "Reviews", icon: CheckSquare },
  { href: "/messages", label: "Messages", icon: Send },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/revisions", label: "Revisions", icon: Wand2 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-64 border-r bg-white shrink-0">
      <div className="p-4 border-b">
        <h1 className="text-lg font-semibold">Outreach OS</h1>
      </div>
      <nav className="p-2">
        {NAV_ITEMS.map((item) => {
          const active = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm",
                active ? "bg-slate-100 font-medium" : "text-slate-600 hover:bg-slate-50",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
