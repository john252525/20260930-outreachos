import "next-auth";
import "next-auth/jwt";

declare module "next-auth" {
  interface Session {
    user: { id: string; email: string; name: string; tenantId: string; role: string };
    accessToken?: string;
  }
  interface User {
    tenantId: string;
    role: string;
    accessToken: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    tenantId: string;
    userId: string;
    role: string;
    accessToken: string;
  }
}
