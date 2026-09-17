import { NextResponse } from "next/server";

import { connectedInstallationId } from "@/github/session";
import { impactsForInstallation } from "@/inventory/inventory";

export async function GET() {
  try {
    return NextResponse.json(await impactsForInstallation(await connectedInstallationId()));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load impacts";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
