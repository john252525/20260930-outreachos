"use client";

import { signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

export function Header({
  user,
}: {
  user: { id: string; email: string; name: string; tenantId: string };
}) {
  return (
    <header className="h-14 border-b bg-white flex items-center justify-between px-6">
      <div className="text-sm text-slate-500">
        tenant: <span className="font-mono">{user.tenantId.slice(0, 8)}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm">{user.name}</span>
        <Button variant="ghost" size="sm" onClick={() => signOut({ callbackUrl: "/login" })}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
