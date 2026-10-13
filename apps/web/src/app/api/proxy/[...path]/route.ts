import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

const SERVICE_ROUTES: Record<string, string | undefined> = {
  orchestrator: process.env.ORCHESTRATOR_URL,
  reviews: process.env.REVIEW_QUEUE_URL,
  messages: process.env.COMPOSER_URL,
  analytics: process.env.ANALYTICS_URL,
  experiments: process.env.EXPERIMENTS_URL,
  revisions: process.env.REVISION_URL,
  icps: process.env.ICP_URL,
  briefs: process.env.BRIEF_URL,
  sourcing: process.env.SOURCING_URL,
  contacts: process.env.CONTACT_STORE_URL,
  companies: process.env.CONTACT_STORE_URL,
  tenants: process.env.TENANT_URL,
  users: process.env.USERS_SERVICE_URL,
  campaigns: process.env.CAMPAIGN_SERVICE_URL,
};

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { path: segments } = await ctx.params;
  const [service, ...rest] = segments;
  const baseUrl = SERVICE_ROUTES[service];
  if (!baseUrl) {
    return NextResponse.json({ error: "unknown_service", service }, { status: 404 });
  }

  const path = rest.join("/");
  const url = new URL(req.url);
  const target = `${baseUrl.replace(/\/$/, "")}/${path}${url.search}`;

  const headers = new Headers();
  headers.set("X-Tenant-ID", session.user.tenantId);
  headers.set("X-User-Id", session.user.id);
  headers.set("X-Trace-Id", crypto.randomUUID());
  const userToken = (session as { accessToken?: string }).accessToken;
  if (userToken) {
    headers.set("Authorization", `Bearer ${userToken}`);
  } else if (process.env.SERVICE_TOKEN) {
    headers.set("Authorization", `Bearer ${process.env.SERVICE_TOKEN}`);
  }
  headers.set("Content-Type", req.headers.get("Content-Type") || "application/json");
  const idem = req.headers.get("Idempotency-Key");
  if (idem) headers.set("Idempotency-Key", idem);

  const body = ["POST", "PUT", "PATCH"].includes(req.method) ? await req.text() : undefined;

  try {
    const response = await fetch(target, { method: req.method, headers, body, cache: "no-store" });
    const responseBody = await response.text();
    return new NextResponse(responseBody, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" },
    });
  } catch (e) {
    return NextResponse.json({ error: "upstream_error", message: String(e) }, { status: 502 });
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
