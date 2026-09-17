import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  installationClient,
} from "@/github/client";
import { githubOAuthConfig, INSTALLATION_COOKIE, verifyInstallationCookie } from "@/github/auth";
import { indexGitHubRepository } from "@/inventory/github-indexer";

interface IndexBody {
  fullName?: unknown;
  ref?: unknown;
}

export async function POST(request: Request) {
  try {
    const body = await request.json() as IndexBody;
    if (typeof body.fullName !== "string" || !/^[^/\s]+\/[^/\s]+$/.test(body.fullName)) {
      return NextResponse.json({ error: "A valid owner/repository name is required" }, { status: 400 });
    }
    if (body.ref !== undefined && (typeof body.ref !== "string" || !body.ref.trim())) {
      return NextResponse.json({ error: "ref must be a non-empty string" }, { status: 400 });
    }

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
    const inventory = await indexGitHubRepository(
      github,
      installationId,
      body.fullName,
      typeof body.ref === "string" ? body.ref : undefined,
    );
    return NextResponse.json(inventory);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not index repository";
    const status = message === "Repository is not available to this installation" ? 404 : 500;
    return NextResponse.json({ error: message }, { status });
  }
}
