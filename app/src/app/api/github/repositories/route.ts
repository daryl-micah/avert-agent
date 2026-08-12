import { NextResponse } from "next/server";

import {
  installationClientFromEnvironment,
  listInstallationRepositories,
} from "@/github/client";

export async function GET() {
  try {
    const github = await installationClientFromEnvironment();
    return NextResponse.json(await listInstallationRepositories(github));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load repositories";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
