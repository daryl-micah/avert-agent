import { NextResponse } from "next/server";

import { loadInventoryFromEnvironment } from "@/inventory/inventory";

export async function GET() {
  try {
    return NextResponse.json(await loadInventoryFromEnvironment());
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not load inventory";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
