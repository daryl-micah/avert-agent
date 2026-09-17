import type { ImpactReport } from "@/types/impact";
import type { Inventory } from "@/types/inventory";

import { loadImpacts, loadInventory } from "./engine";

export function emptyInventory(): Inventory {
  return {
    generated_at: new Date().toISOString(),
    repositories: [],
    providers: [],
    call_site_count: 0,
    attention_count: 0,
    dependencies: [],
  };
}

// The dashboard's initial render: nothing to show until GitHub is connected
// and a database is configured. Errors surface on the explicit index action.
export async function inventoryForInstallation(installationId: number | null): Promise<Inventory> {
  if (installationId === null || !process.env.AVERT_DATABASE_URL) return emptyInventory();
  return loadInventory(installationId);
}

export function emptyImpacts(): ImpactReport {
  return { generated_at: new Date().toISOString(), impacts: [] };
}

export async function impactsForInstallation(installationId: number | null): Promise<ImpactReport> {
  if (installationId === null || !process.env.AVERT_DATABASE_URL) return emptyImpacts();
  return loadImpacts(installationId);
}
