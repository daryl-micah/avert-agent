import { type NextRequest, NextResponse } from "next/server";

import {
  exchangeOAuthCode,
  githubOAuthConfig,
  INSTALLATION_COOKIE,
  OAUTH_STATE_COOKIE,
  OAUTH_VERIFIER_COOKIE,
  PENDING_INSTALLATION_COOKIE,
  signInstallationId,
  tokensMatch,
  userInstallationIds,
} from "@/github/auth";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const expectedState = request.cookies.get(OAUTH_STATE_COOKIE)?.value;
  const verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE)?.value;
  const installationId = Number(request.cookies.get(PENDING_INSTALLATION_COOKIE)?.value);
  if (
    !code ||
    !verifier ||
    !Number.isSafeInteger(installationId) ||
    installationId <= 0 ||
    !tokensMatch(state, expectedState)
  ) {
    return NextResponse.json({ error: "Invalid GitHub OAuth callback" }, { status: 400 });
  }

  try {
    const config = githubOAuthConfig();
    const accessToken = await exchangeOAuthCode(config, code, verifier);
    const installationIds = await userInstallationIds(accessToken);
    if (!installationIds.includes(installationId)) {
      return NextResponse.json({ error: "Installation is not accessible to this user" }, { status: 403 });
    }

    const response = NextResponse.redirect(new URL("/", request.url));
    response.cookies.set(
      INSTALLATION_COOKIE,
      signInstallationId(installationId, config.sessionSecret),
      {
        httpOnly: true,
        sameSite: "lax",
        secure: request.nextUrl.protocol === "https:",
        maxAge: 60 * 60 * 8,
        path: "/",
      },
    );
    response.cookies.delete(OAUTH_STATE_COOKIE);
    response.cookies.delete(OAUTH_VERIFIER_COOKIE);
    response.cookies.delete(PENDING_INSTALLATION_COOKIE);
    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not complete GitHub connection";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
