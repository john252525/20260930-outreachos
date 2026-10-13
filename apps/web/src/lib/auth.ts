import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { z } from "zod";

const credentialsSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type EnvUser = { hash: string; tenantId: string; name: string };

function parseEnvUsers(): Map<string, EnvUser> {
  const raw = process.env.AUTH_USERS || "";
  const map = new Map<string, EnvUser>();
  for (const entry of raw.split(";").filter(Boolean)) {
    const parts = entry.split(":");
    if (parts.length < 3) continue;
    const [email, hash, tenantId, name] = parts;
    if (email && hash && tenantId) {
      map.set(email.toLowerCase(), { hash, tenantId, name: name || email });
    }
  }
  return map;
}

type AuthResult = {
  id: string;
  email: string;
  name: string;
  tenantId: string;
  role: string;
  accessToken: string;
};

/** Authenticate via users-service; fall back to env users (dev compatibility). */
async function authorizeWithUsersService(
  email: string,
  password: string,
): Promise<AuthResult | null> {
  const base = process.env.USERS_SERVICE_URL;
  if (!base) return null;
  try {
    const resp = await fetch(`${base}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    return {
      id: data.user_id,
      email,
      name: data.display_name || email,
      tenantId: data.tenant_id,
      role: data.role,
      accessToken: data.access_token,
    };
  } catch {
    return null;
  }
}

async function authorizeWithEnv(
  email: string,
  password: string,
): Promise<AuthResult | null> {
  const users = parseEnvUsers();
  const user = users.get(email.toLowerCase());
  if (!user) return null;
  const ok = await bcrypt.compare(password, user.hash);
  if (!ok) return null;
  return {
    id: email,
    email,
    name: user.name,
    tenantId: user.tenantId,
    role: "admin",
    accessToken: "",
  };
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const parsed = credentialsSchema.safeParse(credentials);
        if (!parsed.success) return null;
        const { email, password } = parsed.data;
        const viaUsers = await authorizeWithUsersService(email, password);
        if (viaUsers) return viaUsers;
        return authorizeWithEnv(email, password);
      },
    }),
  ],
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const u = user as unknown as AuthResult;
        token.tenantId = u.tenantId;
        token.userId = u.id;
        token.role = u.role;
        token.accessToken = u.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.userId as string;
      session.user.tenantId = token.tenantId as string;
      session.user.role = (token.role as string) || "viewer";
      session.accessToken = (token.accessToken as string) || "";
      return session;
    },
  },
  pages: { signIn: "/login" },
});
