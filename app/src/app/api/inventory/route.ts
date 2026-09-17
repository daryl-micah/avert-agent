import { NextResponse } from "next/server";

import { connectedInstallationId } from "@/github/session";
import { inventoryForInstallation } from "@/inventory/inventory";

export async function GET() {
  try {
    return NextResponse.json(await inventoryForInstallation(await connectedInstallationId()));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load inventory";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
