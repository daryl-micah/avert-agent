import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import {
  downloadRepositoryArchive,
  installationClient,
  listInstallationRepositories,
} from "@/github/client";
import { githubOAuthConfig, INSTALLATION_COOKIE, verifyInstallationCookie } from "@/github/auth";
import { indexRepositoryArchive } from "@/inventory/github-indexer";

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
    const repositories = await listInstallationRepositories(github);
    const repository = repositories.find((candidate) => candidate.fullName === body.fullName);
    if (!repository) {
      return NextResponse.json({ error: "Repository is not available to this installation" }, { status: 404 });
    }
    const [owner, repo] = repository.fullName.split("/", 2);
    const ref = typeof body.ref === "string" ? body.ref : repository.defaultBranch;
    const archive = await downloadRepositoryArchive(github, owner, repo, ref);
    const inventory = await indexRepositoryArchive(archive, { repo: repository.fullName, commit: ref });
    return NextResponse.json(inventory);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not index repository";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
