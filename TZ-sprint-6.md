# Спринт 6 — Web UI + LinkedIn sender + per-tenant settings + multi-region groundwork

Проверил: зависимости от Спринта 0–5 соблюдены, порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md`. Учёл, что Спринт 6 — **первый спринт, где система выходит за пределы «работает для одного технического пользователя»**. До сих пор всё управлялось через curl/Postman/агентов. Теперь появляется UI, второй серьёзный канал (LinkedIn) и per-tenant настройки.

## Что даёт Спринт 6

1. **Web UI.** Это не «дашборд ради дашборда». UI нужен для трёх вещей:
   - **Review queue** — человек должен удобно просматривать/редактировать/approve'ить письма. Через curl это не работает.
   - **Flow observability** — видеть, где застрял пайплайн, какие flows failed, что требует внимания.
   - **Analytics dashboards** — funnel, метрики, эксперименты. Без визуализации метрики не работают.

2. **LinkedIn sender.** Третий канал. Самый рискованный из всех (LinkedIn банит агрессивно). Но без него многие B2B-ниши не закрываются. Ограничения жёстче, чем у Telegram.

3. **Per-tenant settings.** До сих пор `auto_*` флаги — глобальные в env. Теперь — per tenant. Один tenant хочет всё автоматически, другой — только semi-auto, третий — только manual.

4. **Multi-region groundwork.** Не сам multi-region, а подготовка: где хранятся данные, как реплицируются, как роутить. Пока — только документация и конфиги, без реализации.

## Разбивка на под-спринты

**6A — Web UI (Next.js).** Основной UI. Review queue + flows + analytics. Самое важное.

**6B — LinkedIn sender.** Третий канал с жёсткими ограничениями.

**6C — Per-tenant settings.** Модель настроек + API + интеграция во все сервисы.

**6D — Multi-region groundwork.** Документация и подготовка (без реализации).

**Порядок:** 6A → 6B → 6C → 6D.

**Почему UI первым:** без UI LinkedIn и per-tenant settings некуда смотреть. UI — это «лицо» системы. И ещё: UI критичен для review-queue, без него смысл review падает — письма копятся, никто их не смотрит.

**Что НЕ в этом спринте:**
- WhatsApp sender — отдельный спринт 7.
- Мульти-armed bandit — спринт 7+.
- ML-модели для скоринга — спринт 7+.
- Real-time collaboration (несколько пользователей одновременно) — спринт 7+.
- Multi-region deploy — спринт 8.

---

# 6A — Web UI (Next.js)

## Что такое Web UI и почему Next.js

**Next.js 15 (App Router)** — стандарт для современных React-приложений. Причины:
1. **Server Components** — данные грузятся на сервере, UI быстрее.
2. **Route handlers** — BFF (backend-for-frontend) встроен. UI не ходит напрямую в микросервисы — ходит в Next.js API, который проксирует.
3. **TypeScript из коробки**, Tailwind, shadcn/ui — экосистема для быстрого UI.
4. **Auth.js** — аутентификация (email/password или OAuth).

**Ключевой принцип:** UI **никогда** не ходит напрямую в микросервисы. Всё через BFF (Next.js API routes). Причины:
- Секреты (service tokens) не утекают в браузер.
- BFF может агрегировать данные из нескольких сервисов.
- Кэширование на уровне BFF.
- CORS не нужен.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         Browser (React)               │
                    └──────────────┬───────────────────────┘
                                   │ HTTPS
                                   ▼
                    ┌──────────────────────────────────────┐
                    │         Next.js (BFF + SSR)           │
                    │                                       │
                    │  Pages:                               │
                    │   /login                              │
                    │   /dashboard                          │
                    │   /flows                              │
                    │   /flows/[id]                         │
                    │   /reviews                            │
                    │   /reviews/[id]                       │
                    │   /messages                           │
                    │   /analytics                          │
                    │   /experiments                        │
                    │   /revisions                          │
                    │   /settings                           │
                    │                                       │
                    │  API routes (BFF):                    │
                    │   /api/auth/*                         │
                    │   /api/flows/*                        │
                    │   /api/reviews/*                      │
                    │   /api/analytics/*                    │
                    │   /api/...                            │
                    │                                       │
                    │  Auth: Auth.js (credentials + OAuth)  │
                    │  Session: JWT + tenant_id             │
                    └──────────────┬───────────────────────┘
                                   │ Service tokens
                                   ▼
                    ┌──────────────────────────────────────┐
                    │  Микросервисы (orchestrator, etc.)    │
                    └──────────────────────────────────────┘
```

**Стек:**
- Next.js 15 (App Router, RSC).
- TypeScript.
- Tailwind CSS + shadcn/ui (компоненты).
- TanStack Query (data fetching на клиенте, где нужно).
- Zustand (легкий state management).
- Auth.js (NextAuth v5).
- Zod (валидация).
- Recharts или Tremor для графиков.

---

# Задача 6A.1 — Каркас Next.js + Auth + tenant

**Файл:** `docs/tasks/sprint-6a/6a.1-bootstrap.md`

## Цель

Создать каркас Next.js-приложения: структура, Auth.js, мульти-тенантность, layout с навигацией. Страница `/login` работает.

## Зависимости

Спринт 5 закрыт.

## Что создать

```
apps/web/
├── package.json
├── pnpm-lock.yaml
├── next.config.mjs
├── tsconfig.json
├── tailwind.config.ts
├── postcss.config.mjs
├── Dockerfile
├── .env.example
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  # redirect на /dashboard или /login
│   │   ├── globals.css
│   │   ├── (auth)/
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   └── layout.tsx
│   │   ├── (app)/
│   │   │   ├── layout.tsx            # с sidebar, nav
│   │   │   ├── dashboard/
│   │   │   │   └── page.tsx
│   │   │   ├── flows/
│   │   │   ├── reviews/
│   │   │   ├── analytics/
│   │   │   └── settings/
│   │   └── api/
│   │       ├── auth/
│   │       │   └── [...nextauth]/
│   │       │       └── route.ts
│   │       └── proxy/
│   │           └── [...path]/
│   │               └── route.ts      # BFF proxy
│   ├── lib/
│   │   ├── auth.ts                   # Auth.js config
│   │   ├── api-client.ts             # обёртка для BFF
│   │   ├── tenant.ts                 # tenant context
│   │   └── utils.ts
│   ├── components/
│   │   ├── ui/                       # shadcn компоненты
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   └── TenantSwitcher.tsx
│   │   └── shared/
│   │       ├── Loading.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── DataTable.tsx
│   └── types/
│       └── index.ts
└── middleware.ts                     # auth guard
```

## Детали

### `package.json`

```json
{
  "name": "outreach-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.0.3",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "next-auth": "5.0.0-beta.25",
    "@auth/core": "0.37.2",
    "@tanstack/react-query": "5.59.20",
    "zustand": "5.0.1",
    "zod": "3.23.8",
    "react-hook-form": "7.53.2",
    "@hookform/resolvers": "3.9.1",
    "tailwindcss": "3.4.14",
    "class-variance-authority": "0.7.0",
    "clsx": "2.1.1",
    "tailwind-merge": "2.5.4",
    "lucide-react": "0.454.0",
    "@radix-ui/react-dialog": "1.1.2",
    "@radix-ui/react-dropdown-menu": "2.1.2",
    "@radix-ui/react-tabs": "1.1.1",
    "@radix-ui/react-toast": "1.2.2",
    "@radix-ui/react-select": "2.1.2",
    "@radix-ui/react-label": "2.1.0",
    "@radix-ui/react-slot": "1.1.0",
    "sonner": "1.7.0",
    "recharts": "2.13.3",
    "date-fns": "4.1.0",
    "jose": "5.9.6",
    "bcryptjs": "2.4.3"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.9.0",
    "@types/react": "19.0.0",
    "@types/react-dom": "19.0.0",
    "@types/bcryptjs": "2.4.6",
    "eslint": "9.14.0",
    "eslint-config-next": "15.0.3",
    "postcss": "8.4.49",
    "autoprefixer": "10.4.20"
  },
  "packageManager": "pnpm@9.12.3"
}
```

**Используем pnpm** — быстрее, экономнее по диску.

### `.env.example`

```bash
# NextAuth
NEXTAUTH_URL=https://app.dev.aitler.ru
NEXTAUTH_SECRET=                    # openssl rand -base64 32
AUTH_TRUST_HOST=true

# Service tokens (для BFF proxy)
SERVICE_TOKEN=                      # общий токен для всех микросервисов
ORCHESTRATOR_URL=http://orchestrator:8000
REVIEW_QUEUE_URL=http://review-queue:8000
COMPOSER_URL=http://composer-service:8000
ANALYTICS_URL=http://analytics-service:8000
EXPERIMENTS_URL=http://experiments-service:8000
REVISION_URL=http://auto-revision:8000
ICP_URL=http://icp-service:8000
BRIEF_URL=http://brief-service:8000
SOURCING_URL=http://sourcing-service:8000
CONTACT_STORE_URL=http://contact-store:8000

# Users (для MVP — в env; в будущем — БД)
AUTH_USERS=sergey:$(bcrypt_hash):tenant-uuid-1;ivan:$(bcrypt_hash):tenant-uuid-1
```

**Важно:** для MVP — пользователи в env. В Спринте 7 — переедем в БД (`users` таблица с tenant_id).

### `src/lib/auth.ts`

```typescript
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { z } from "zod";

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

function parseEnvUsers(): Map<string, { hash: string; tenantId: string; name: string }> {
  const raw = process.env.AUTH_USERS || "";
  const map = new Map();
  for (const entry of raw.split(";").filter(Boolean)) {
    const [email, hash, tenantId, name] = entry.split(":");
    if (email && hash && tenantId) {
      map.set(email.toLowerCase(), { hash, tenantId, name: name || email });
    }
  }
  return map;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const parsed = credentialsSchema.safeParse(credentials);
        if (!parsed.success) return null;

        const users = parseEnvUsers();
        const user = users.get(parsed.data.email.toLowerCase());
        if (!user) return null;

        const ok = await bcrypt.compare(parsed.data.password, user.hash);
        if (!ok) return null;

        return {
          id: parsed.data.email,
          email: parsed.data.email,
          name: user.name,
          tenantId: user.tenantId,
        };
      },
    }),
  ],
  session: {
    strategy: "jwt",
    maxAge: 7 * 24 * 60 * 60,  // 7 дней
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.tenantId = (user as any).tenantId;
        token.userId = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.userId as string;
      session.user.tenantId = token.tenantId as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
```

**Расширить типы:**

```typescript
// src/types/next-auth.d.ts
import "next-auth";

declare module "next-auth" {
  interface Session {
    user: {
      id: string;
      email: string;
      name: string;
      tenantId: string;
    };
  }
  interface User {
    tenantId: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    tenantId: string;
    userId: string;
  }
}
```

### `src/app/api/auth/[...nextauth]/route.ts`

```typescript
import { handlers } from "@/lib/auth";

export const { GET, POST } = handlers;
```

### `src/app/api/proxy/[...path]/route.ts` — BFF proxy

```typescript
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";

const SERVICE_ROUTES: Record<string, string> = {
  orchestrator: process.env.ORCHESTRATOR_URL!,
  reviews: process.env.REVIEW_QUEUE_URL!,
  messages: process.env.COMPOSER_URL!,
  analytics: process.env.ANALYTICS_URL!,
  experiments: process.env.EXPERIMENTS_URL!,
  revisions: process.env.REVISION_URL!,
  icps: process.env.ICP_URL!,
  briefs: process.env.BRIEF_URL!,
  sourcing: process.env.SOURCING_URL!,
  contacts: process.env.CONTACT_STORE_URL!,
  companies: process.env.CONTACT_STORE_URL!,
};

async function handler(req: NextRequest, { params }: { params: { path: string[] } }) {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const [service, ...rest] = params.path;
  const baseUrl = SERVICE_ROUTES[service];
  if (!baseUrl) {
    return NextResponse.json({ error: "unknown_service", service }, { status: 404 });
  }

  const path = rest.join("/");
  const url = new URL(req.url);
  const target = `${baseUrl}/${path}${url.search}`;

  const headers = new Headers();
  headers.set("X-Tenant-ID", session.user.tenantId);
  headers.set("X-User-Id", session.user.id);
  headers.set("Authorization", `Bearer ${process.env.SERVICE_TOKEN}`);
  headers.set("Content-Type", req.headers.get("Content-Type") || "application/json");
  if (req.headers.get("Idempotency-Key")) {
    headers.set("Idempotency-Key", req.headers.get("Idempotency-Key")!);
  }

  const body = ["POST", "PUT", "PATCH"].includes(req.method)
    ? await req.text()
    : undefined;

  const response = await fetch(target, {
    method: req.method,
    headers,
    body,
  });

  const contentType = response.headers.get("Content-Type") || "application/json";
  const responseBody = await response.text();

  return new NextResponse(responseBody, {
    status: response.status,
    headers: { "Content-Type": contentType },
  });
}

export { handler as GET, handler as POST, handler as PUT, handler as PATCH, handler as DELETE };
```

### `src/lib/api-client.ts`

```typescript
type ApiOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
};

export async function apiClient<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const url = `/api/proxy/${path.replace(/^\//, "")}`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }

  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: response.statusText }));
    throw new ApiError(response.status, error.message || "Request failed", error);
  }

  return response.json();
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public details?: unknown) {
    super(message);
  }
}
```

### `middleware.ts`

```typescript
import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isAuth = !!req.auth;
  const isLoginPage = req.nextUrl.pathname.startsWith("/login");
  const isAuthApi = req.nextUrl.pathname.startsWith("/api/auth");

  if (isAuthApi) return NextResponse.next();

  if (!isAuth && !isLoginPage) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  if (isAuth && isLoginPage) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

### `src/app/(app)/layout.tsx`

```tsx
import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session) redirect("/login");

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header user={session.user} />
        <main className="flex-1 p-6 bg-slate-50">{children}</main>
      </div>
    </div>
  );
}
```

### `src/components/layout/Sidebar.tsx`

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, GitBranch, CheckSquare, Send, BarChart3,
  FlaskConical, Wand2, Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
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
    <aside className="w-64 border-r bg-white">
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
```

### `src/app/(auth)/login/page.tsx`

```tsx
"use client";

import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    const result = await signIn("credentials", {
      email, password, redirect: false,
    });
    setLoading(false);
    if (result?.error) {
      setError("Неверный email или пароль");
    } else {
      router.push("/dashboard");
      router.refresh();
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white p-8 rounded-lg shadow">
        <h1 className="text-2xl font-semibold mb-6">Вход в Outreach OS</h1>
        {error && <div className="mb-4 text-sm text-red-600">{error}</div>}
        <div className="space-y-4">
          <Input
            type="email" placeholder="Email" value={email}
            onChange={(e) => setEmail(e.target.value)} required
          />
          <Input
            type="password" placeholder="Пароль" value={password}
            onChange={(e) => setPassword(e.target.value)} required
          />
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Вход..." : "Войти"}
          </Button>
        </div>
      </form>
    </div>
  );
}
```

### Dockerfile

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN corepack enable && corepack prepare pnpm@9.12.3 --activate
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**`next.config.mjs`:** `output: "standalone"`.

### Добавить в `infra/docker-compose.dev.yml`

```yaml
  web:
    <<: *service-defaults
    build:
      context: ../apps/web
      dockerfile: Dockerfile
    container_name: outreach-web
    environment:
      <<: *common-env
      NODE_ENV: production
      NEXTAUTH_URL: https://app.dev.aitler.ru
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET:?required}
      AUTH_TRUST_HOST: "true"
      SERVICE_TOKEN: ${SERVICE_TOKEN:?required}
      AUTH_USERS: ${AUTH_USERS:?required}
      ORCHESTRATOR_URL: http://orchestrator:8000
      REVIEW_QUEUE_URL: http://review-queue:8000
      COMPOSER_URL: http://composer-service:8000
      ANALYTICS_URL: http://analytics-service:8000
      EXPERIMENTS_URL: http://experiments-service:8000
      REVISION_URL: http://auto-revision:8000
      ICP_URL: http://icp-service:8000
      BRIEF_URL: http://brief-service:8000
      SOURCING_URL: http://sourcing-service:8000
      CONTACT_STORE_URL: http://contact-store:8000
    depends_on:
      orchestrator:
        condition: service_started
      review-queue:
        condition: service_started
    labels:
      caddy: app.dev.aitler.ru
      caddy.reverse_proxy: "{{upstreams 3000}}"
    healthcheck:
      test: ["CMD", "wget", "-q", "-O", "-", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
```

**Добавить `/api/health` route:**

```typescript
// src/app/api/health/route.ts
import { NextResponse } from "next/server";
export function GET() {
  return NextResponse.json({ status: "ok" });
}
```

**Обновить `.env.example`:**

```bash
NEXTAUTH_SECRET=
SERVICE_TOKEN=
# Сгенерировать хеши: docker run --rm node:22-alpine sh -c "npm i -g bcryptjs-cli && bcryptjs 'password'"
AUTH_USERS=
```

**Сгенерировать `SERVICE_TOKEN`** — общий токен для BFF → сервисы. Все сервисы должны его проверять.

**Важно:** сейчас сервисы не проверяют `Authorization: Bearer`. Нужно добавить middleware во все сервисы (fastapi dependency), который проверяет `SERVICE_TOKEN`. Это изменение — добавить в `libs/common` и подключить в каждом сервисе.

**Обновить `libs/common`:**

```python
# common/auth.py
import os
from fastapi import Header, HTTPException


async def require_service_token(authorization: str | None = Header(None)) -> None:
    expected = os.environ.get("SERVICE_TOKEN")
    if not expected:
        # В dev можно отключить
        if os.environ.get("ENV", "dev") == "dev":
            return
        raise HTTPException(status_code=500, detail="SERVICE_TOKEN not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing service token")
    token = authorization.removeprefix("Bearer ")
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid service token")
```

**Подключить в каждом сервисе** через `dependencies=[Depends(require_service_token)]` на уровне `include_router`.

**Это изменение Спринта 0–5.** Нужно вернуться и добавить.

**Или:** сделать проще — отдельный API-gateway, который проверяет токен. Но это лишний сервис.

**Решение:** добавить `require_service_token` в `libs/common`, подключить во всех сервисах. Плюс `SKIP_PATHS` для `/healthz`, `/readyz`, `/metrics`, `/docs`, `/openapi.json`.

## Acceptance criteria

```bash
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev build web
docker compose -f infra/docker-compose.dev.yml --env-file .env.dev up -d web
# Ожидание: service_started

curl -fsS https://app.dev.aitler.ru/api/health
# Ожидание: {"status":"ok"}

# Открыть в браузере https://app.dev.aitler.ru
# Ожидание: редирект на /login

# Войти (email/password из AUTH_USERS)
# Ожидание: редирект на /dashboard
```

## Подсказки

- **BFF proxy** — все сервисы через `/api/proxy/<service>/<path>`. `SERVICE_TOKEN` не утекает в браузер.
- **`AUTH_USERS`** — временно в env. Потом в БД.
- **`X-Tenant-ID`** — из сессии. Один пользователь = один tenant (пока). Мульти-tenant пользователи — Спринт 7.
- **Middleware Auth.js** — защищает все страницы кроме `/login` и `/api/auth/*`.

## Анти-паттерны

- ❌ Не ходить в микросервисы напрямую из браузера.
- ❌ Не хранить `SERVICE_TOKEN` в браузере.
- ❌ Не делать auth на клиенте — только на сервере (middleware).

---

# Задача 6A.2 — Review Queue UI

**Файл:** `docs/tasks/sprint-6a/6a.2-reviews.md`

## Цель

Основной экран для работы с очередью писем на ревью. Список + просмотр + approve/reject/edit.

## Что создать

```
apps/web/src/app/(app)/reviews/
├── page.tsx                   # список
├── [id]/
│   └── page.tsx               # детальный просмотр

apps/web/src/components/reviews/
├── ReviewList.tsx
├── ReviewFilters.tsx
├── ReviewDetail.tsx
├── ReviewActions.tsx
├── MessagePreview.tsx
├── FactualClaimsList.tsx
└── EditDialog.tsx

apps/web/src/lib/hooks/
└── use-reviews.ts             # React Query hooks
```

## Детали

### `use-reviews.ts`

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ReviewItem = {
  id: string;
  message_id: string;
  contact_id: string;
  channel: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  reviewed_by: string | null;
  snapshot: {
    subject: string | null;
    body_preview: string;
    warnings: string[];
    factual_claims_count: number;
  };
  created_at: string;
};

export function useReviews(filters: { status?: string; priority?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.priority) params.set("priority", filters.priority);

  return useQuery({
    queryKey: ["reviews", filters],
    queryFn: () => apiClient<ReviewItem[]>(`reviews/?${params.toString()}`),
    refetchInterval: 30_000,
  });
}

export function useReview(id: string) {
  return useQuery({
    queryKey: ["reviews", id],
    queryFn: () => apiClient<ReviewItem>(`reviews/${id}`),
  });
}

export function useApproveReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, scheduledAt }: { id: string; scheduledAt?: string }) =>
      apiClient(`reviews/${id}/approve`, {
        method: "POST",
        body: { scheduled_send_at: scheduledAt || null },
        idempotencyKey: `approve-${id}-${Date.now()}`,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reviews"] });
    },
  });
}

export function useRejectReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason, note }: { id: string; reason: string; note?: string }) =>
      apiClient(`reviews/${id}/reject`, {
        method: "POST",
        body: { reason, note },
        idempotencyKey: `reject-${id}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}

export function useEditReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, subject, bodyText }: { id: string; subject?: string; bodyText: string }) =>
      apiClient(`reviews/${id}/edit`, {
        method: "POST",
        body: { subject, body_text: bodyText },
        idempotencyKey: `edit-${id}-${Date.now()}`,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reviews"] }),
  });
}
```

### `reviews/page.tsx`

```tsx
"use client";

import { useReviews } from "@/lib/hooks/use-reviews";
import { ReviewList } from "@/components/reviews/ReviewList";
import { ReviewFilters } from "@/components/reviews/ReviewFilters";
import { useState } from "react";

export default function ReviewsPage() {
  const [filters, setFilters] = useState({ status: "pending", priority: undefined });
  const { data, isLoading, error } = useReviews(filters);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reviews</h1>
        <p className="text-sm text-slate-500 mt-1">
          Письма, ожидающие проверки перед отправкой
        </p>
      </div>
      <ReviewFilters filters={filters} onChange={setFilters} />
      {isLoading && <div>Загрузка...</div>}
      {error && <div className="text-red-600">Ошибка загрузки</div>}
      {data && <ReviewList items={data} />}
    </div>
  );
}
```

### `ReviewList.tsx`

```tsx
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ReviewItem } from "@/lib/hooks/use-reviews";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

const PRIORITY_COLORS = {
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
      {items.map((item) => (
        <Link
          key={item.id}
          href={`/reviews/${item.id}`}
          className="block p-4 bg-white border rounded-lg hover:border-slate-400 transition"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge className={PRIORITY_COLORS[item.priority as keyof typeof PRIORITY_COLORS]}>
                  {item.priority}
                </Badge>
                <Badge variant="outline">{item.channel}</Badge>
                {item.snapshot.warnings.length > 0 && (
                  <Badge className="bg-amber-100 text-amber-700">
                    {item.snapshot.warnings.length} warnings
                  </Badge>
                )}
                {item.snapshot.factual_claims_count > 0 && (
                  <Badge variant="outline">
                    {item.snapshot.factual_claims_count} claims
                  </Badge>
                )}
              </div>
              <div className="font-medium truncate">
                {item.snapshot.subject || "(без темы)"}
              </div>
              <div className="text-sm text-slate-500 line-clamp-2 mt-1">
                {item.snapshot.body_preview}
              </div>
            </div>
            <div className="text-xs text-slate-400 whitespace-nowrap">
              {formatDistanceToNow(new Date(item.created_at), { addSuffix: true, locale: ru })}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}
```

### `reviews/[id]/page.tsx`

```tsx
"use client";

import { useReview } from "@/lib/hooks/use-reviews";
import { ReviewDetail } from "@/components/reviews/ReviewDetail";
import { use } from "react";

export default function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useReview(id);

  if (isLoading) return <div>Загрузка...</div>;
  if (!data) return <div>Не найдено</div>;

  return <ReviewDetail item={data} />;
}
```

### `ReviewDetail.tsx`

```tsx
"use client";

import { useState } from "react";
import { MessagePreview } from "./MessagePreview";
import { FactualClaimsList } from "./FactualClaimsList";
import { ReviewActions } from "./ReviewActions";
import { EditDialog } from "./EditDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReviewItem } from "@/lib/hooks/use-reviews";
import { Pencil } from "lucide-react";
import { useMessage } from "@/lib/hooks/use-messages";

export function ReviewDetail({ item }: { item: ReviewItem }) {
  const [editOpen, setEditOpen] = useState(false);
  const { data: message, isLoading } = useMessage(item.message_id);

  if (isLoading) return <div>Загрузка письма...</div>;
  if (!message) return <div>Письмо не найдено</div>;

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{message.subject || "(без темы)"}</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge>{item.channel}</Badge>
            <Badge variant="outline">{item.priority}</Badge>
            {message.personalization?.template_id && (
              <Badge variant="outline">
                {message.personalization.template_id}:{message.personalization.template_version}
              </Badge>
            )}
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4 mr-2" /> Редактировать
        </Button>
      </div>

      {item.snapshot.warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="font-medium text-amber-800 mb-2">Предупреждения</div>
          <ul className="text-sm text-amber-700 space-y-1">
            {item.snapshot.warnings.map((w, i) => <li key={i}>• {w}</li>)}
          </ul>
        </div>
      )}

      <MessagePreview message={message} />

      <FactualClaimsList claims={message.personalization?.factual_claims || []} />

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="bg-white border rounded-lg p-4">
          <div className="font-medium mb-2">Получатель</div>
          <div>{message.recipient_snapshot?.full_name}</div>
          <div className="text-slate-500">{message.recipient_snapshot?.position}</div>
          <div className="text-slate-500">{message.recipient_snapshot?.company_name}</div>
          <div className="text-slate-500 mt-2">{message.recipient_snapshot?.email}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="font-medium mb-2">Отправитель</div>
          <div>{message.sender?.from_name}</div>
          <div className="text-slate-500">{message.sender?.from_email}</div>
          {message.sender?.signature && (
            <div className="text-slate-500 mt-2 whitespace-pre-line">{message.sender.signature}</div>
          )}
        </div>
      </div>

      <ReviewActions item={item} message={message} />

      <EditDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        item={item}
        message={message}
      />
    </div>
  );
}
```

### `MessagePreview.tsx`

```tsx
import { Message } from "@/lib/hooks/use-messages";

export function MessagePreview({ message }: { message: Message }) {
  return (
    <div className="bg-white border rounded-lg p-6">
      <div className="text-sm text-slate-500 border-b pb-3 mb-4">
        <div><strong>От:</strong> {message.sender?.from_name} &lt;{message.sender?.from_email}&gt;</div>
        <div><strong>Кому:</strong> {message.recipient_snapshot?.email}</div>
        <div><strong>Тема:</strong> {message.subject}</div>
      </div>
      <div className="whitespace-pre-line text-slate-800 leading-relaxed">
        {message.body_text}
      </div>
    </div>
  );
}
```

### `FactualClaimsList.tsx`

```tsx
import { Badge } from "@/components/ui/badge";
import { ExternalLink, AlertTriangle } from "lucide-react";

type FactualClaim = {
  claim: string;
  evidence_url: string | null;
  confidence: number;
  is_hypothesis: boolean;
};

export function FactualClaimsList({ claims }: { claims: FactualClaim[] }) {
  if (claims.length === 0) return null;

  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="font-medium mb-3">Утверждения в письме</div>
      <div className="space-y-2">
        {claims.map((claim, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            {claim.is_hypothesis ? (
              <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
            ) : (
              <div className="h-4 w-4 rounded-full bg-green-500 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <div>{claim.claim}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-500">
                  confidence: {(claim.confidence * 100).toFixed(0)}%
                </span>
                {claim.is_hypothesis && (
                  <Badge className="bg-amber-100 text-amber-700 text-xs">гипотеза</Badge>
                )}
                {claim.evidence_url && (
                  <a
                    href={claim.evidence_url}
                    target="_blank"
                    rel="noopener"
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    источник <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### `ReviewActions.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useApproveReview, useRejectReview } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { Check, X } from "lucide-react";

export function ReviewActions({ item, message }: { item: any; message: any }) {
  const router = useRouter();
  const approve = useApproveReview();
  const reject = useRejectReview();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  async function onApprove() {
    try {
      await approve.mutateAsync({ id: item.id });
      toast.success("Одобрено");
      router.push("/reviews");
    } catch (e) {
      toast.error("Ошибка одобрения");
    }
  }

  async function onReject() {
    if (!reason.trim()) {
      toast.error("Укажите причину");
      return;
    }
    try {
      await reject.mutateAsync({ id: item.id, reason });
      toast.success("Отклонено");
      router.push("/reviews");
    } catch (e) {
      toast.error("Ошибка отклонения");
    }
  }

  return (
    <div className="bg-white border rounded-lg p-4 sticky bottom-4">
      {!rejecting ? (
        <div className="flex gap-3">
          <Button onClick={onApprove} disabled={approve.isPending} className="flex-1">
            <Check className="h-4 w-4 mr-2" />
            {approve.isPending ? "Отправка..." : "Одобрить и отправить"}
          </Button>
          <Button variant="outline" onClick={() => setRejecting(true)} className="flex-1">
            <X className="h-4 w-4 mr-2" /> Отклонить
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Причина отклонения..."
            className="w-full border rounded p-2 text-sm"
            rows={3}
          />
          <div className="flex gap-3">
            <Button variant="destructive" onClick={onReject} disabled={reject.isPending}>
              {reject.isPending ? "Отклонение..." : "Подтвердить отклонение"}
            </Button>
            <Button variant="outline" onClick={() => setRejecting(false)}>Отмена</Button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### `EditDialog.tsx`

```tsx
"use client";

import { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEditReview } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";

export function EditDialog({ open, onOpenChange, item, message }: any) {
  const [subject, setSubject] = useState(message.subject || "");
  const [body, setBody] = useState(message.body_text || "");
  const edit = useEditReview();

  async function onSave() {
    try {
      await edit.mutateAsync({ id: item.id, subject, bodyText: body });
      toast.success("Сохранено");
      onOpenChange(false);
    } catch (e) {
      toast.error("Ошибка сохранения");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Редактирование письма</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Тема</label>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium">Тело письма</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="w-full border rounded p-3 text-sm font-mono"
              rows={20}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Отмена</Button>
          <Button onClick={onSave} disabled={edit.isPending}>
            {edit.isPending ? "Сохранение..." : "Сохранить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

### `use-messages.ts`

```typescript
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type Message = {
  id: string;
  subject: string | null;
  body_text: string;
  body_html: string | null;
  channel: string;
  status: string;
  personalization: {
    template_id?: string;
    template_version?: string;
    factual_claims?: Array<{
      claim: string;
      evidence_url: string | null;
      confidence: number;
      is_hypothesis: boolean;
    }>;
    warnings?: string[];
  };
  sender: { from_name?: string; from_email?: string; signature?: string };
  recipient_snapshot: {
    email?: string;
    full_name?: string;
    position?: string;
    company_name?: string;
  };
};

export function useMessage(id: string) {
  return useQuery({
    queryKey: ["messages", id],
    queryFn: () => apiClient<Message>(`messages/${id}`),
  });
}
```

## Acceptance criteria

```bash
# Открыть https://app.dev.aitler.ru/reviews
# Ожидание: список pending review items

# Кликнуть на item → детальный просмотр
# Ожидание: письмо, получатель, отправитель, claims, actions

# Approve → item уходит из pending, message становится approved
# Reject → item уходит из pending
# Edit → тело письма обновляется
```

## Подсказки

- **`refetchInterval: 30_000`** — обновление раз в 30 секунд. Realtime (WebSocket) — Спринт 7.
- **Idempotency-Key** для мутаций — `approve-${id}-${Date.now()}`. При retry — тот же.
- **Toast** через `sonner`.
- **EditDialog** — простой textarea. Markdown preview — Спринт 7.

## Анти-паттерны

- ❌ Не забывать refetch после мутаций.
- ❌ Не позволять approve без явного действия.
- ❌ Не терять unsaved edits при закрытии dialog.

---

# Задача 6A.3 — Dashboard, Flows, Analytics UI

**Файл:** `docs/tasks/sprint-6a/6a.3-dashboard.md`

## Цель

Dashboard с общей картиной, Flows list/detail, Analytics с графиками.

## Что создать

```
apps/web/src/app/(app)/
├── dashboard/page.tsx
├── flows/
│   ├── page.tsx
│   └── [id]/page.tsx
├── analytics/page.tsx
├── experiments/
│   ├── page.tsx
│   └── [id]/page.tsx
├── revisions/
│   ├── page.tsx
│   └── [id]/page.tsx
└── settings/page.tsx

apps/web/src/components/
├── dashboard/
│   ├── KPICard.tsx
│   ├── FunnelChart.tsx
│   └── ActivityFeed.tsx
├── flows/
│   ├── FlowList.tsx
│   ├── FlowDetail.tsx
│   └── FlowStepsTimeline.tsx
├── analytics/
│   ├── MetricsChart.tsx
│   ├── TemplatePerformance.tsx
│   └── SenderHealth.tsx
└── shared/
    └── DataTable.tsx
```

## Детали

### `dashboard/page.tsx`

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { KPICard } from "@/components/dashboard/KPICard";
import { FunnelChart } from "@/components/dashboard/FunnelChart";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";

export default function DashboardPage() {
  const { data: funnel } = useQuery({
    queryKey: ["analytics", "funnel"],
    queryFn: () => apiClient<any>("analytics/funnel"),
    refetchInterval: 60_000,
  });

  const { data: flows } = useQuery({
    queryKey: ["flows", "recent"],
    queryFn: () => apiClient<any[]>("orchestrator/flows?limit=5"),
    refetchInterval: 30_000,
  });

  const { data: reviews } = useQuery({
    queryKey: ["reviews", "pending-count"],
    queryFn: () => apiClient<any[]>("reviews/?status=pending&limit=100"),
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="grid grid-cols-4 gap-4">
        <KPICard label="Контактов всего" value={funnel?.contacts_total ?? "—"} />
        <KPICard label="Отправлено" value={funnel?.sent ?? "—"} />
        <KPICard label="Ответили" value={funnel?.replied ?? "—"} accent="blue" />
        <KPICard
          label="На ревью"
          value={reviews?.length ?? "—"}
          accent={reviews && reviews.length > 20 ? "amber" : "default"}
          href="/reviews"
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Funnel</h2>
          <FunnelChart data={funnel} />
        </div>
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Последние flows</h2>
          <ActivityFeed flows={flows || []} />
        </div>
      </div>
    </div>
  );
}
```

### `KPICard.tsx`

```tsx
import Link from "next/link";
import { cn } from "@/lib/utils";

const ACCENTS = {
  default: "text-slate-900",
  blue: "text-blue-600",
  amber: "text-amber-600",
  red: "text-red-600",
};

export function KPICard({
  label, value, accent = "default", href,
}: {
  label: string;
  value: number | string;
  accent?: keyof typeof ACCENTS;
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
```

### `FunnelChart.tsx`

```tsx
"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export function FunnelChart({ data }: { data: any }) {
  if (!data) return <div className="text-slate-400">Нет данных</div>;

  const chartData = [
    { name: "Контакты", value: data.contacts_total ?? 0 },
    { name: "Связались", value: data.contacted ?? 0 },
    { name: "Отправлено", value: data.sent ?? 0 },
    { name: "Ответили", value: data.replied ?? 0 },
    { name: "Positive", value: data.replied_positive ?? 0 },
  ];

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} layout="vertical">
        <XAxis type="number" />
        <YAxis dataKey="name" type="category" width={100} />
        <Tooltip />
        <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### `flows/page.tsx`

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { FlowList } from "@/components/flows/FlowList";
import { useState } from "react";

export default function FlowsPage() {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const { data } = useQuery({
    queryKey: ["flows", status],
    queryFn: () => apiClient<any[]>(`orchestrator/flows${status ? `?status=${status}` : ""}`),
    refetchInterval: 15_000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Flows</h1>
        <select
          value={status || ""}
          onChange={(e) => setStatus(e.target.value || undefined)}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value="">Все</option>
          <option value="running">Running</option>
          <option value="paused">Paused</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      <FlowList items={data || []} />
    </div>
  );
}
```

### `flows/[id]/page.tsx`

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { FlowDetail } from "@/components/flows/FlowDetail";
import { use } from "react";

export default function FlowDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: flow } = useQuery({
    queryKey: ["flows", id],
    queryFn: () => apiClient<any>(`orchestrator/flows/${id}`),
    refetchInterval: 10_000,
  });
  const { data: steps } = useQuery({
    queryKey: ["flows", id, "steps"],
    queryFn: () => apiClient<any[]>(`orchestrator/flows/${id}/steps`),
    refetchInterval: 10_000,
  });

  if (!flow) return <div>Загрузка...</div>;

  return <FlowDetail flow={flow} steps={steps || []} />;
}
```

### `FlowDetail.tsx`

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FlowStepsTimeline } from "./FlowStepsTimeline";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Play, Pause, X } from "lucide-react";

export function FlowDetail({ flow, steps }: { flow: any; steps: any[] }) {
  const qc = useQueryClient();

  async function action(name: string) {
    try {
      await apiClient(`orchestrator/flows/${flow.id}/${name}`, {
        method: "POST",
        idempotencyKey: `${name}-${flow.id}-${Date.now()}`,
      });
      toast.success(`OK: ${name}`);
      qc.invalidateQueries({ queryKey: ["flows", flow.id] });
    } catch (e) {
      toast.error(`Ошибка: ${name}`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Flow {flow.id.slice(0, 8)}</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge>{flow.flow_type}</Badge>
            <Badge variant="outline">{flow.status}</Badge>
            <span className="text-sm text-slate-500">
              {flow.completed_steps}/{flow.total_steps} steps
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {flow.status === "running" && (
            <Button variant="outline" onClick={() => action("pause")}>
              <Pause className="h-4 w-4 mr-2" /> Пауза
            </Button>
          )}
          {flow.status === "paused" && (
            <Button variant="outline" onClick={() => action("resume")}>
              <Play className="h-4 w-4 mr-2" /> Продолжить
            </Button>
          )}
          {["running", "paused"].includes(flow.status) && (
            <Button variant="destructive" onClick={() => action("cancel")}>
              <X className="h-4 w-4 mr-2" /> Отменить
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="bg-white border rounded-lg p-4">
          <div className="text-slate-500">Brief ID</div>
          <div className="font-mono text-xs mt-1">{flow.brief_id || "—"}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-slate-500">ICP ID</div>
          <div className="font-mono text-xs mt-1">{flow.icp_id?.slice(0, 8) || "—"}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="text-slate-500">Search Job ID</div>
          <div className="font-mono text-xs mt-1">{flow.search_job_id?.slice(0, 8) || "—"}</div>
        </div>
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="font-semibold mb-4">Шаги</h2>
        <FlowStepsTimeline steps={steps} />
      </div>

      {flow.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {flow.error}
        </div>
      )}
    </div>
  );
}
```

### `FlowStepsTimeline.tsx`

```tsx
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Clock, AlertCircle } from "lucide-react";

const STATUS_ICONS = {
  completed: <CheckCircle2 className="h-5 w-5 text-green-500" />,
  running: <Clock className="h-5 w-5 text-blue-500 animate-spin" />,
  failed: <XCircle className="h-5 w-5 text-red-500" />,
  retry_scheduled: <AlertCircle className="h-5 w-5 text-amber-500" />,
  pending: <Clock className="h-5 w-5 text-slate-300" />,
  skipped: <Clock className="h-5 w-5 text-slate-300" />,
};

export function FlowStepsTimeline({ steps }: { steps: any[] }) {
  if (steps.length === 0) return <div className="text-slate-400">Нет шагов</div>;

  return (
    <div className="space-y-3">
      {steps.map((step) => (
        <div key={step.id} className="flex items-start gap-3">
          <div className="mt-0.5">
            {STATUS_ICONS[step.status as keyof typeof STATUS_ICONS] || STATUS_ICONS.pending}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{step.step_name}</span>
              <Badge variant="outline">{step.status}</Badge>
              {step.attempts > 1 && (
                <span className="text-xs text-slate-500">attempts: {step.attempts}</span>
              )}
              {step.duration_ms && (
                <span className="text-xs text-slate-500">
                  {(step.duration_ms / 1000).toFixed(1)}s
                </span>
              )}
            </div>
            {step.error && (
              <div className="text-xs text-red-600 mt-1">{step.error}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
```

### `analytics/page.tsx`

```tsx
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import { MetricsChart } from "@/components/analytics/MetricsChart";
import { TemplatePerformance } from "@/components/analytics/TemplatePerformance";
import { SenderHealth } from "@/components/analytics/SenderHealth";
import { useState } from "react";
import { format, subDays } from "date-fns";

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const fromDate = format(subDays(new Date(), days), "yyyy-MM-dd");
  const toDate = format(new Date(), "yyyy-MM-dd");

  const { data: overview } = useQuery({
    queryKey: ["analytics", "overview", days],
    queryFn: () => apiClient<any>(`analytics/overview?from_date=${fromDate}&to_date=${toDate}`),
  });

  const { data: templates } = useQuery({
    queryKey: ["analytics", "templates", days],
    queryFn: () => apiClient<any[]>(`analytics/by-template?from_date=${fromDate}&to_date=${toDate}`),
  });

  const { data: senders } = useQuery({
    queryKey: ["analytics", "senders", days],
    queryFn: () => apiClient<any[]>(`analytics/by-sender?from_date=${fromDate}&to_date=${toDate}`),
  });

  const { data: categories } = useQuery({
    queryKey: ["analytics", "categories", days],
    queryFn: () => apiClient<any[]>(`analytics/reply-categories?from_date=${fromDate}&to_date=${toDate}`),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="border rounded px-3 py-2 text-sm"
        >
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
        </select>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Sent" value={overview?.sent} />
        <StatCard label="Reply rate" value={formatPercent(overview?.reply_rate)} />
        <StatCard label="Positive reply rate" value={formatPercent(overview?.positive_reply_rate)} accent="green" />
        <StatCard label="Bounce rate" value={formatPercent(overview?.bounce_rate)} accent="red" />
      </div>

      <div className="grid grid-cols-2 gap-6">
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Reply categories</h2>
          <MetricsChart data={categories || []} />
        </div>
        <div className="bg-white border rounded-lg p-6">
          <h2 className="font-semibold mb-4">Sender health</h2>
          <SenderHealth senders={senders || []} />
        </div>
      </div>

      <div className="bg-white border rounded-lg p-6">
        <h2 className="font-semibold mb-4">Template performance</h2>
        <TemplatePerformance templates={templates || []} />
      </div>
    </div>
  );
}

function StatCard({ label, value, accent }: any) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold mt-2 ${accent === "green" ? "text-green-600" : accent === "red" ? "text-red-600" : ""}`}>
        {value ?? "—"}
      </div>
    </div>
  );
}

function formatPercent(v?: number) {
  if (v === undefined || v === null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}
```

### `TemplatePerformance.tsx`

```tsx
import { DataTable } from "@/components/shared/DataTable";

export function TemplatePerformance({ templates }: { templates: any[] }) {
  const columns = [
    { key: "template_id", label: "Template" },
    { key: "template_version", label: "Version" },
    { key: "sent", label: "Sent", align: "right" as const },
    { key: "replied", label: "Replied", align: "right" as const },
    {
      key: "reply_rate", label: "Reply rate", align: "right" as const,
      render: (v: number) => `${(v * 100).toFixed(2)}%`,
    },
    {
      key: "bounce_rate", label: "Bounce rate", align: "right" as const,
      render: (v: number) => `${(v * 100).toFixed(2)}%`,
    },
  ];
  return <DataTable columns={columns} data={templates} />;
}
```

### `DataTable.tsx`

```tsx
export function DataTable({
  columns, data,
}: {
  columns: Array<{ key: string; label: string; align?: "left" | "right"; render?: (v: any, row: any) => React.ReactNode }>;
  data: any[];
}) {
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
                  {c.render ? c.render(row[c.key], row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

## Acceptance criteria

```bash
# Dashboard
# Открыть https://app.dev.aitler.ru/dashboard
# Ожидание: KPI, funnel, последние flows

# Flows
# Открыть /flows → список
# Кликнуть → detail со шагами, кнопки pause/resume/cancel

# Analytics
# Открыть /analytics → overview, categories, senders, templates
```

## Подсказки

- **Recharts** — простой, работает с RSC через `"use client"`.
- **TanStack Query** — кэш + refetch.
- **DataTable** — минимальный, без внешних библиотек.

## Анти-паттерны

- ❌ Не использовать `useEffect` для fetch — только React Query.
- ❌ Не забывать "use client" для интерактивных компонентов.
- ❌ Не дублировать логику между страницами — выносить в components.

---

# 6B — LinkedIn sender

## Что такое LinkedIn sender и почему он самый рискованный

LinkedIn банит **очень агрессивно**. Автоматизация — против ToS. Реалистично: через unofficial API (например, `linkedin-api` Python или через Selenium). Риски:
1. **Бан аккаунта** — навсегда.
2. **Бан по IP** — сложнее восстановить.
3. **Юридические риски** — LinkedIn подаёт в суд на автоматизаторов (были прецеденты).

**Ключевое решение:**
- **Только для тех, с кем уже есть контакт** (connection request accepted).
- **Очень жёсткий rate limit** — 10-20 сообщений в день.
- **Warm-up 30+ дней.**
- **Один аккаунт = один IP** (proxy).
- **Каждый аккаунт — на отдельном прокси.**
- **Human-in-the-loop обязателен** — auto-send только после 30 дней успешной работы.
- **Opt-in на уровне tenant.** По умолчанию LinkedIn sender **выключен**.

## Архитектура

```
                    ┌──────────────────────────────────────┐
                    │         linkedin-sender               │
                    │                                       │
   message.approved►│  LinkedInSenderService                │
                    │       │                               │
                    │       ├──► SessionManager (cookies)   │
                    │       ├──► ProxyRotator               │
                    │       ├──► RateLimiter (жёсткий)      │
                    │       ├──► CaptchaDetector            │
                    │       └──► Publisher (NATS)           │
                    │                                       │
                    │  Events:                              │
                    │   - message.sent                      │
                    │   - message.failed                    │
                    │   - linkedin.ban_detected             │
                    └──────────────────────────────────────┘
```

---

# Задача 6B.1 — Каркас + модели + LinkedIn account

**Файл:** `docs/tasks/sprint-6b/6b.1-bootstrap.md`

## Детали

### `models.py`

```python
class LinkedInAccount(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "linkedin_accounts"

    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    cookies_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Proxy
    proxy_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proxy_type: Mapped[str | None] = mapped_column(String(16), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified", index=True)
    # unverified | active | paused | captcha_required | banned | error

    # Ramp-up
    daily_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    daily_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    weekly_limit_current: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    warmup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ban detection
    ban_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### Зависимости

```toml
"linkedin-api>=2.3.1",      # unofficial
"playwright>=1.48",          # fallback
"playwright-stealth>=1.0.6", # anti-detection
"cryptography>=43.0",
```

**Важно:** `linkedin-api` — unofficial, работает через cookies. Может сломаться в любой момент. Плюс `playwright` — для fallback, когда API не работает.

## Acceptance criteria

```bash
docker compose ... run --rm linkedin-sender alembic upgrade head
docker compose ... up -d linkedin-sender
curl -fsS https://linkedin.dev.aitler.ru/healthz
bash scripts/psql.sh -c "\d+ linkedin_accounts"
```

---

# Задача 6B.2 — Session manager + anti-detection + captcha

**Файл:** `docs/tasks/sprint-6b/6b.2-session.md`

## Детали

### `session/manager.py`

```python
from linkedin_api import Linkedin
from cryptography.fernet import Fernet

import structlog


logger = structlog.get_logger()


class LinkedInSessionManager:
    """Управляет сессиями LinkedIn. Один аккаунт = одна сессия."""

    def __init__(self, encryptor: Fernet) -> None:
        self._encryptor = encryptor
        self._sessions: dict[UUID, Linkedin] = {}

    async def get_session(self, account: LinkedInAccount) -> Linkedin:
        if account.id in self._sessions:
            return self._sessions[account.id]

        # Восстанавливаем cookies
        cookies_str = self._encryptor.decrypt(account.cookies_encrypted).decode() if account.cookies_encrypted else None
        password = self._encryptor.decrypt(account.password_encrypted).decode()

        # linkedin-api — синхронный, оборачиваем
        import asyncio
        loop = asyncio.get_event_loop()

        def _create():
            return Linkedin(account.email, password, cookies=cookies_str)

        try:
            client = await loop.run_in_executor(None, _create)
            self._sessions[account.id] = client
            return client
        except Exception as e:
            logger.exception("linkedin_session_failed", account=account.email, error=str(e))
            raise

    async def save_cookies(self, account: LinkedInAccount, client: Linkedin) -> None:
        # Экспорт cookies
        cookies = client.client.session.cookies.get_dict()
        cookies_str = json.dumps(cookies)
        account.cookies_encrypted = self._encryptor.encrypt(cookies_str.encode()).decode()

    def invalidate(self, account_id: UUID) -> None:
        self._sessions.pop(account_id, None)
```

### `anti_detection.py`

```python
import random
import asyncio


class HumanBehavior:
    """Имитация человеческого поведения."""

    @staticmethod
    async def random_delay(min_sec: float = 2.0, max_sec: float = 8.0) -> None:
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def typing_pause() -> None:
        # Пауза перед отправкой — имитация набора текста
        await asyncio.sleep(random.uniform(1.5, 4.0))

    @staticmethod
    def random_user_agent() -> str:
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            # ...
        ]
        return random.choice(agents)
```

### `captcha_detector.py`

```python
class CaptchaDetector:
    """Определяет captcha / checkpoint challenge."""

    PATTERNS = [
        "checkpoint/challenge",
        "captcha",
        "security verification",
        "unusual activity",
    ]

    @classmethod
    def detect(cls, response_text: str) -> bool:
        lower = response_text.lower()
        return any(p in lower for p in cls.PATTERNS)

    @classmethod
    def handle(cls, account: LinkedInAccount) -> None:
        """При обнаружении captcha — паузим аккаунт и алертим."""
        account.status = "captcha_required"
        account.last_error = "CAPTCHA detected — требуется ручное вмешательство"
```

**Важно:** при captcha — **не пытаться обойти**. Паузим аккаунт, алертим. Человек должен зайти вручную, решить captcha, и только потом возобновить.

## Acceptance criteria

```bash
# E2E с реальным аккаунтом (осторожно!)
# 1. Создать аккаунт
curl -sX POST https://linkedin.dev.aitler.ru/accounts \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: acc-1" \
  -d '{"email":"...","password":"...","proxy_url":"http://user:pass@proxy:port"}' | jq .

# 2. Verify
curl -sX POST https://linkedin.dev.aitler.ru/accounts/$ACC_ID/verify \
  -H "X-Tenant-ID: $TENANT" -H "Idempotency-Key: v-1" | jq .status
# Ожидание: "active" или "captcha_required" или "error"
```

## Подсказки

- **Прокси обязателен.** LinkedIn банит по IP. Один аккаунт — один прокси (residential).
- **Cookies сохранять.** Иначе каждый раз логин — подозрительно.
- **Captcha → пауза.** Не пытаться обойти.
- **Rate limit жёсткий.** 5-20 сообщений/день в зависимости от возраста аккаунта.

## Анти-паттерны

- ❌ Не использовать datacenter proxies — только residential.
- ❌ Не логиниться каждый раз заново.
- ❌ Не обходить captcha автоматически.
- ❌ Не превышать 20 сообщений/день даже на старом аккаунте.

---

# Задача 6B.3 — SenderService + opt-in + API

**Файл:** `docs/tasks/sprint-6b/6b.3-service.md`

## Детали

### Opt-in на уровне tenant

**Обновить `tenant-service`:** добавить поля:

```python
# tenant-service/models.py
class Tenant(Base, ...):
    ...
    linkedin_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linkedin_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
```

**Миграция** — добавить колонки.

**Обновить `TenantRead`, `TenantUpdate`** — включить новые поля.

**В LinkedIn sender** — проверять перед отправкой:

```python
async def send_approved_message(self, *, tenant_id, message_id, trace_id) -> SendAttempt:
    # Проверить opt-in
    tenant = await self._tenant_client.get_tenant(tenant_id)
    if not tenant.get("linkedin_enabled"):
        raise ValidationError("LinkedIn sender not enabled for tenant")

    # ... остальное
```

### Логика отправки

```python
class LinkedInSenderService:
    async def send_approved_message(self, *, tenant_id, message_id, trace_id):
        # 1. Проверка opt-in tenant
        # 2. Получить Message из composer
        # 3. Проверить, что channel == "linkedin"
        # 4. Проверить connection request accepted (в contact.messengers)
        # 5. Выбрать аккаунт
        # 6. Проверить rate limit
        # 7. Отправить через session
        # 8. Записать attempt
        # 9. Обновить Message
        # 10. Опубликовать событие
```

**Ключевая проверка:** LinkedIn — только для тех, у кого `contact.messengers[linkedin].is_connected == true`. Иначе — ошибка.

**Обновить Contact schema в contact-store:** добавить в `messengers` поле `is_connected`.

### API

```python
@router.post("/accounts", ...)
@router.get("/accounts", ...)
@router.post("/accounts/{id}/verify", ...)
@router.post("/accounts/{id}/pause", ...)
@router.get("/attempts", ...)
@router.post("/accounts/{id}/solve-captcha", ...)   # ручное подтверждение решения
```

`/solve-captcha` — переводит аккаунт из `captcha_required` в `active` (после ручного решения).

## Acceptance criteria

```bash
# 1. Включить LinkedIn для tenant
curl -sX PATCH https://tenant.dev.aitler.ru/tenants/$TENANT \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: upd-1" \
  -d '{"linkedin_enabled": true}' | jq .linkedin_enabled
# Ожидание: true

# 2. Создать аккаунт, verify
# 3. Draft с channel=linkedin
# 4. Approve → отправится (если контакт connected)
```

## Подсказки

- **Opt-in обязателен.** По умолчанию выключено.
- **Connection check обязателен.** Нельзя писать тем, кто не принял connection request.
- **Captcha → ручное решение.** Через API.

## Анти-паттерны

- ❌ Не отправлять без opt-in tenant.
- ❌ Не отправлять тем, кто не connected.
- ❌ Не пытаться обойти captcha автоматически.

---

# Задача 6B.4 — Тесты, E2E, CI

**Файл:** `docs/tasks/sprint-6b/6b.4-tests.md`

## Acceptance criteria

```bash
uv run pytest services/linkedin-sender/tests/ -v --cov=linkedin_sender --cov-report=term-missing
# Ожидание: coverage >= 75% (LinkedIn сложно тестировать)
```

---

# 6C — Per-tenant settings

## Что даёт

До сих пор все настройки — глобальные в env. Теперь — per-tenant. Каждый tenant имеет свои:
- Automation levels (`auto_brief_to_icp`, `auto_icp_to_sourcing` и т.д.).
- Default sources для sourcing.
- Default limits (max contacts, max sends).
- Enabled channels (email, telegram, linkedin).
- Alert thresholds.
- Branding (для UI — логотип, цвета).

## Модель данных

**Новая таблица `tenant_settings` в tenant-service:**

```python
class TenantSettings(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "tenant_settings"

    # Automation
    auto_brief_to_icp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_icp_to_sourcing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_contacts_to_drafts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_drafts_to_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_approved_to_send: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_revision_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Sourcing
    default_sources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    default_limit_per_source: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_sources_per_search: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    # Outreach
    default_channel: Mapped[str] = mapped_column(String(16), nullable=False, default="email")
    default_max_contacts_per_flow: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    default_sender_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # Channels
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    linkedin_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Alerts
    alert_reply_rate_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.02)
    alert_bounce_rate_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)

    # Limits / quotas
    quota_llm_tokens_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_messages_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quota_contacts_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Branding (для UI)
    branding: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # {logo_url, primary_color, company_name}
```

---

# Задача 6C.1 — Модель + миграция + API

**Файл:** `docs/tasks/sprint-6c/6c.1-model.md`

## Детали

### Миграция

Добавить таблицу `tenant_settings` в tenant-service. RLS.

При создании tenant — автоматически создавать `TenantSettings` с дефолтами.

### API

```python
@router.get("/tenants/{tenant_id}/settings", response_model=TenantSettingsRead)
async def get_settings(tenant_id: UUID, svc=Depends(get_service)) -> TenantSettingsRead:
    ...


@router.patch("/tenants/{tenant_id}/settings", response_model=TenantSettingsRead)
async def update_settings(
    tenant_id: UUID,
    data: TenantSettingsUpdate,
    svc=Depends(get_service),
) -> TenantSettingsRead:
    ...
```

### Сервис: получение settings

**Проблема:** orchestrator, sender-email и другие сервисы должны читать settings. Это дополнительный HTTP-вызов.

**Решение:** кэшировать в Redis на 5 минут. `TenantClient.get_settings(tenant_id)`.

**Обновить orchestrator:** в каждом handler'е читать settings tenant'а (с кэшем).

```python
# orchestrator/clients/tenant_client.py
class TenantClient:
    def __init__(self, base_url: str, redis) -> None:
        self._client = httpx.AsyncClient(base_url=base_url)
        self._redis = redis

    async def get_settings(self, tenant_id: str) -> dict:
        cache_key = f"tenant:settings:{tenant_id}"
        cached = await self._redis.get(cache_key)
        if cached:
            return json.loads(cached)

        resp = await self._client.get(
            f"/tenants/{tenant_id}/settings",
            headers={"X-Tenant-ID": tenant_id, "Authorization": f"Bearer {service_token}"},
        )
        resp.raise_for_status()
        settings = resp.json()
        await self._redis.setex(cache_key, 300, json.dumps(settings))
        return settings
```

## Acceptance criteria

```bash
# 1. Получить настройки
curl -s -H "X-Tenant-ID: $TENANT" https://tenant.dev.aitler.ru/tenants/$TENANT/settings | jq .
# Ожидание: дефолтные настройки

# 2. Изменить
curl -sX PATCH https://tenant.dev.aitler.ru/tenants/$TENANT/settings \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT" \
  -H "Idempotency-Key: upd-1" \
  -d '{"auto_contacts_to_drafts": true, "telegram_enabled": true}' | jq .
# Ожидание: обновлённые

# 3. Orchestrator читает settings
# Создать brief → flow должен использовать auto_contacts_to_drafts=true
```

## Подсказки

- **Кэш в Redis** на 5 минут. Не дёргать tenant-service на каждый handler.
- **Инвалидация кэша** при PATCH settings — публиковать событие `tenant.settings_updated`, orchestrator сбрасывает кэш.
- **Дефолты в коде**, не в БД. При создании tenant — создаём settings с дефолтами.

## Анти-паттерны

- ❌ Не читать settings на каждый HTTP-вызов — кэш.
- ❌ Не хранить дефолты в БД — в коде.
- ❌ Не забывать инвалидацию кэша.

---

# Задача 6C.2 — Интеграция во все сервисы

**Файл:** `docs/tasks/sprint-6c/6c.2-integration.md`

## Детали

### Orchestrator

Заменить `settings.auto_brief_to_icp` на `tenant_settings["auto_brief_to_icp"]`.

```python
async def handle(self, envelope):
    tenant_settings = await self._tenant_client.get_settings(str(envelope.tenant_id))
    if not tenant_settings.get("auto_brief_to_icp"):
        return
    ...
```

### Sender-email

Проверять `default_sender_daily_limit` из settings перед отправкой.

### Analytics

Использовать `alert_reply_rate_threshold` из settings вместо глобального.

### Composer

Проверять `email_enabled` / `telegram_enabled` / `linkedin_enabled` перед draft.

### Sourcing

Использовать `default_sources`, `default_limit_per_source` из settings.

## Acceptance criteria

```bash
# 1. Изменить настройки tenant
curl -sX PATCH .../settings -d '{"auto_contacts_to_drafts": true}'

# 2. Создать brief → flow должен автоматически запустить drafts
# (без ручного trigger)
```

---

# Задача 6C.3 — Settings UI + тесты

**Файл:** `docs/tasks/sprint-6c/6c.3-ui-tests.md`

## Детали

### UI: `apps/web/src/app/(app)/settings/page.tsx`

Форма с секциями:
- Automation levels (чекбоксы).
- Sourcing (sources, limits).
- Outreach (default channel, max contacts).
- Channels (email, telegram, linkedin, whatsapp).
- Alerts (thresholds).
- Quotas.

Использовать React Hook Form + Zod.

### Тесты

Unit + E2E.

## Acceptance criteria

```bash
# Открыть /settings → форма → изменить → сохранить
# Ожидание: настройки обновлены
```

---

# 6D — Multi-region groundwork

## Что это

Не реализация multi-region, а **подготовка**. Сейчас всё в одном регионе (один VPS). Если нужно масштабироваться:
- Данные в разных регионах (data residency — для EU клиентов).
- Отправка из разных регионов (лучшая deliverability).
- Failover.

## Что делаем в 6D

**Только документация.** Без реализации.

### `docs/multi-region.md`

- Модель данных: где что живёт.
- Стратегия репликации (logical replication для Postgres, mirror для NATS).
- Роутинг (geo-DNS, или app-level).
- Стоимость.
- Пошаговый план миграции.

### `docs/runbook-multi-region.md`

- Как добавить новый регион.
- Как переключить tenant на другой регион.
- Как делать failover.

## Acceptance criteria

- Документы написаны.
- Реализация — Спринт 8.

---

## Финальная E2E-проверка Спринта 6

```bash
# 1. Web UI
# Открыть https://app.dev.aitler.ru
# Войти, увидеть dashboard

# 2. Review queue
# Перейти /reviews → approve письмо
# Проверить: письмо ушло из pending, message → approved

# 3. Flows
# Перейти /flows → кликнуть flow → увидеть шаги → pause/resume

# 4. Analytics
# Перейти /analytics → графики, метрики

# 5. LinkedIn
# Включить linkedin_enabled для tenant
# Создать LinkedIn аккаунт, verify
# Draft с channel=linkedin, approve, отправить (если connected)

# 6. Per-tenant settings
# Изменить auto_contacts_to_drafts=true
# Создать brief → flow автоматически создаёт drafts

# 7. CI
git push origin develop
# Все jobs зелёные
```

---

## Проверка: что я перепроверил

- [x] Порядок задач: 6A.1 → 6A.2 → 6A.3 → 6B.1 → 6B.2 → 6B.3 → 6B.4 → 6C.1 → 6C.2 → 6C.3 → 6D, зависимости соблюдены.
- [x] Web UI: Next.js 15, Auth.js, BFF proxy, SERVICE_TOKEN.
- [x] `require_service_token` в libs/common — изменение Спринта 0.
- [x] Review queue UI — основной экран.
- [x] Dashboard, Flows, Analytics — покрыты.
- [x] LinkedIn sender: opt-in per tenant, connection check, captcha → ручное решение, residential proxy.
- [x] `tenant_settings` таблица, миграция в tenant-service.
- [x] Инвалидация кэша settings через событие.
- [x] Per-tenant settings интегрированы в orchestrator, sender, analytics, composer, sourcing.
- [x] Multi-region — только документация.
- [x] Mypy strict, ruff, pytest.
- [x] Никаких cross-service импортов.
- [x] Idempotency-Key на всех POST.
- [x] RLS на всех таблицах.
- [x] Web UI использует BFF — секреты не утекают в браузер.

---

## Что дальше (Спринт 7)

После Спринта 6 система — **готовый продукт для B2B outreach**:
- Автоматический pipeline от brief до отправки.
- Обратная связь через reply-классификацию и experiments.
- Auto-revision.
- Email + Telegram + LinkedIn.
- Web UI.
- Per-tenant settings.

**Спринт 7** — улучшения:
- WhatsApp sender (Business API).
- Мульти-armed bandit.
- ML-модели для скоринга контактов.
- Real-time collaboration (несколько пользователей).
- Users + roles в БД (вместо env).
- Campaign entity (группировка outreach по кампаниям).
- Audit log.

**Спринт 8** — multi-region (реализация).

**Что от тебя нужно сейчас:**
1. Разложить эти 11 задач по файлам в `docs/tasks/sprint-6/` (6A, 6B, 6C, 6D).
2. Дать агенту: «Начинай с 6A.1. 6A — обязательно до конца (UI), потом 6B (LinkedIn), потом 6C (settings), потом 6D (docs)».
3. Сообщить мне, когда Спринт 6 закрыт.

**Критичные вопросы к тебе:**
- **`require_service_token` в libs/common** — это изменение Спринта 0, которое затронет все сервисы. Альтернатива — отдельный API-gateway. **Рекомендую middleware в libs/common** — проще.
- **LinkedIn sender** — использовать `linkedin-api` (unofficial, может сломаться) или Playwright (медленнее, но стабильнее)? **Рекомендую оба** — linkedin-api как основной, Playwright как fallback.
- **Users в env vs БД** — на Спринте 6 env, на Спринте 7 — БД. Ок?

Если хочешь что-то поправить сейчас — скажи.