import { NextResponse } from "next/server";
import { cookies } from "next/headers";

import {
  installationClient,
  listInstallationRepositories,
} from "@/github/client";
import { githubOAuthConfig, INSTALLATION_COOKIE, verifyInstallationCookie } from "@/github/auth";

export async function GET() {
  try {
    const config = githubOAuthConfig();
    const cookieStore = await cookies();
    const installationId = verifyInstallationCookie(
      cookieStore.get(INSTALLATION_COOKIE)?.value,
      config.sessionSecret,
    );
    if (!installationId) {
      return NextResponse.json({ error: "GitHub is not connected" }, { status: 401 });
    }
    const github = await installationClient(installationId);
    return NextResponse.json(await listInstallationRepositories(github));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load repositories";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
