import { readFile } from "node:fs/promises";
import path from "node:path";

import type { CallSite } from "@/types/call_site";

export type LifecycleStatus = "current" | "retiring" | "retired" | "unknown";

export interface LifecycleRecord {
  provider: string;
  resource: string;
  operation: string;
  model: string;
  replacement: string;
  effective_at: string;
}

export interface InventoryLocation {
  repo: string;
  filePath: string;
  line: number;
  confidence: number;
}

export interface InventoryDependency {
  provider: string;
  resource: string;
  operation: string | null;
  model: string | null;
  valueBinding: CallSite["value_binding"];
  status: LifecycleStatus;
  effectiveAt: string | null;
  replacement: string | null;
  locations: InventoryLocation[];
}

export interface Inventory {
  repositories: string[];
  providers: string[];
  callSiteCount: number;
  attentionCount: number;
  dependencies: InventoryDependency[];
}

function isCallSite(value: unknown): value is CallSite {
  if (typeof value !== "object" || value === null) return false;
  const item = value as Record<string, unknown>;
  const surface = item.surface as Record<string, unknown> | undefined;
  const lineStart = item.line_start;
  const lineEnd = item.line_end;
  const confidence = item.confidence;
  return (
    typeof item.repo === "string" && item.repo.length > 0 &&
    typeof item.file_path === "string" && item.file_path.length > 0 &&
    Number.isInteger(lineStart) && (lineStart as number) >= 1 &&
    Number.isInteger(lineEnd) && (lineEnd as number) >= (lineStart as number) &&
    (item.language === "python" || item.language === "typescript") &&
    (item.value_binding === "literal" ||
      item.value_binding === "dynamic" ||
      item.value_binding === "absent") &&
    typeof confidence === "number" && confidence >= 0 && confidence <= 1 &&
    typeof item.extractor === "string" &&
    typeof item.file_content_hash === "string" && /^[a-f0-9]{64}$/.test(item.file_content_hash) &&
    typeof surface?.provider === "string" &&
    typeof surface.resource === "string" &&
    (surface.operation === undefined || surface.operation === null || typeof surface.operation === "string") &&
    (surface.value === undefined || surface.value === null || typeof surface.value === "string")
  );
}

export function parseCallSitesJsonl(content: string): CallSite[] {
  return content
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line, index) => {
      let value: unknown;
      try {
        value = JSON.parse(line);
      } catch {
        throw new Error(`Invalid JSON on inventory line ${index + 1}`);
      }
      if (!isCallSite(value)) {
        throw new Error(`Invalid CallSite on inventory line ${index + 1}`);
      }
      return value;
    });
}

function dependencyKey(callSite: CallSite): string {
  const surface = callSite.surface;
  return [
    surface.provider,
    surface.resource,
    surface.operation ?? "",
    surface.value ?? "",
    callSite.value_binding,
  ].join("\u0000");
}

function lifecycleFor(
  callSite: CallSite,
  records: LifecycleRecord[],
  today: string,
): Pick<InventoryDependency, "status" | "effectiveAt" | "replacement"> {
  if (callSite.value_binding !== "literal" || !callSite.surface.value) {
    return { status: "unknown", effectiveAt: null, replacement: null };
  }
  const record = records.find(
    (candidate) =>
      candidate.provider === callSite.surface.provider &&
      candidate.resource === callSite.surface.resource &&
      candidate.operation === callSite.surface.operation &&
      candidate.model === callSite.surface.value,
  );
  if (!record) return { status: "current", effectiveAt: null, replacement: null };
  return {
    status: record.effective_at <= today ? "retired" : "retiring",
    effectiveAt: record.effective_at,
    replacement: record.replacement,
  };
}

export function buildInventory(
  callSites: CallSite[],
  lifecycleRecords: LifecycleRecord[],
  today = new Date().toISOString().slice(0, 10),
): Inventory {
  const dependencies = new Map<string, InventoryDependency>();
  for (const callSite of callSites) {
    const key = dependencyKey(callSite);
    let dependency = dependencies.get(key);
    if (!dependency) {
      dependency = {
        provider: callSite.surface.provider,
        resource: callSite.surface.resource,
        operation: callSite.surface.operation ?? null,
        model: callSite.surface.value ?? null,
        valueBinding: callSite.value_binding,
        ...lifecycleFor(callSite, lifecycleRecords, today),
        locations: [],
      };
      dependencies.set(key, dependency);
    }
    dependency.locations.push({
      repo: callSite.repo,
      filePath: callSite.file_path,
      line: callSite.line_start,
      confidence: callSite.confidence,
    });
  }

  const rows = [...dependencies.values()].sort((left, right) => {
    const rank: Record<LifecycleStatus, number> = {
      retired: 0,
      retiring: 1,
      unknown: 2,
      current: 3,
    };
    return rank[left.status] - rank[right.status] || left.provider.localeCompare(right.provider);
  });
  return {
    repositories: [...new Set(callSites.map((site) => site.repo))].sort(),
    providers: [...new Set(callSites.map((site) => site.surface.provider))].sort(),
    callSiteCount: callSites.length,
    attentionCount: callSites.filter((site) => {
      const status = lifecycleFor(site, lifecycleRecords, today).status;
      return status === "retired" || status === "retiring";
    }).length,
    dependencies: rows,
  };
}

export function emptyInventory(): Inventory {
  return { repositories: [], providers: [], callSiteCount: 0, attentionCount: 0, dependencies: [] };
}

export async function loadInventory(inventoryPath: string): Promise<Inventory> {
  return inventoryFromJsonl(await readFile(inventoryPath, "utf8"));
}

export async function inventoryFromJsonl(inventoryJsonl: string): Promise<Inventory> {
  const registryPath = path.resolve(process.cwd(), "../engine/avert/detect/registry/models.json");
  const registryJson = await readFile(registryPath, "utf8");
  return buildInventory(parseCallSitesJsonl(inventoryJsonl), JSON.parse(registryJson));
}

export async function loadInventoryFromEnvironment(): Promise<Inventory> {
  const inventoryPath = process.env.AVERT_INVENTORY_PATH;
  return inventoryPath ? loadInventory(path.resolve(inventoryPath)) : emptyInventory();
}
