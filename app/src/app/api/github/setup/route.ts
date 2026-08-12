import { type NextRequest, NextResponse } from "next/server";

import {
  githubOAuthConfig,
  INSTALL_STATE_COOKIE,
  oauthUrl,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
  PENDING_INSTALLATION_COOKIE,
  randomToken,
  tokensMatch,
} from "@/github/auth";

export async function GET(request: NextRequest) {
  const installationId = Number(request.nextUrl.searchParams.get("installation_id"));
  const state = request.nextUrl.searchParams.get("state");
  if (
    !Number.isSafeInteger(installationId) ||
    installationId <= 0 ||
    !tokensMatch(state, request.cookies.get(INSTALL_STATE_COOKIE)?.value)
  ) {
    return NextResponse.json({ error: "Invalid GitHub installation callback" }, { status: 400 });
  }

  try {
    const config = githubOAuthConfig();
    const oauthState = randomToken();
    const verifier = randomToken();
    const response = NextResponse.redirect(oauthUrl(config, oauthState, verifier));
    const options = {
      httpOnly: true,
      sameSite: "lax" as const,
      secure: request.nextUrl.protocol === "https:",
      maxAge: 600,
      path: "/",
    };
    response.cookies.delete(INSTALL_STATE_COOKIE);
    response.cookies.set(OAUTH_STATE_COOKIE, oauthState, options);
    response.cookies.set(OAUTH_VERIFIER_COOKIE, verifier, options);
    response.cookies.set(PENDING_INSTALLATION_COOKIE, String(installationId), options);
    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not authorize GitHub user";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
