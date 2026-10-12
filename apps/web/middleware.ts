import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const isAuth = !!req.auth;
  const path = req.nextUrl.pathname;
  const isLoginPage = path.startsWith("/login");
  const isAuthApi = path.startsWith("/api/auth");
  const isHealth = path === "/api/health";

  if (isAuthApi || isHealth) return NextResponse.next();

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
