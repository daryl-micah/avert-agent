import { NextResponse } from "next/server";

import { githubOAuthConfig, INSTALL_STATE_COOKIE, installUrl, randomToken } from "@/github/auth";

export async function GET(request: Request) {
  try {
    const config = githubOAuthConfig();
    const state = randomToken();
    const response = NextResponse.redirect(installUrl(config.appSlug, state));
    response.cookies.set(INSTALL_STATE_COOKIE, state, {
      httpOnly: true,
      sameSite: "lax",
      secure: new URL(request.url).protocol === "https:",
      maxAge: 600,
      path: "/",
    });
    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not start GitHub connection";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
