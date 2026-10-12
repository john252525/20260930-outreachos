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
  session: { strategy: "jwt", maxAge: 7 * 24 * 60 * 60 },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.tenantId = user.tenantId;
        token.userId = user.id ?? "";
      }
      return token;
    },
    async session({ session, token }) {
      session.user.id = token.userId as string;
      session.user.tenantId = token.tenantId as string;
      return session;
    },
  },
  pages: { signIn: "/login" },
});
