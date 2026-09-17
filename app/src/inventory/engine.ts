import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

import type { Inventory } from "@/types/inventory";

const execFileAsync = promisify(execFile);

export interface IndexRequest {
  repo: string;
  commit: string;
  installationId: number;
}

export function databaseUrl(): string {
  const url = process.env.AVERT_DATABASE_URL;
  if (!url) throw new Error("AVERT_DATABASE_URL is required");
  return url;
}

async function avert(args: string[], timeout: number): Promise<string> {
  const enginePath = path.resolve(process.cwd(), "../engine");
  const { stdout } = await execFileAsync("uv", ["run", "avert", ...args], {
    cwd: enginePath,
    timeout,
    maxBuffer: 16 * 1024 * 1024,
  });
  return stdout;
}

// Incremental persistence (SPEC §8.2): the engine skips files whose content
// hash is unchanged since the last index of this repository.
export async function indexIntoDatabase(sourcePath: string, request: IndexRequest): Promise<void> {
  await avert(
    [
      "index", sourcePath,
      "--repo", request.repo,
      "--commit", request.commit,
      "--installation", String(request.installationId),
      "--database", databaseUrl(),
    ],
    120_000,
  );
}

export async function syncRegistry(): Promise<void> {
  await avert(["registry", "--database", databaseUrl()], 30_000);
}

export async function loadInventory(installationId: number): Promise<Inventory> {
  const stdout = await avert(
    ["inventory", "--database", databaseUrl(), "--installation", String(installationId)],
    30_000,
  );
  return JSON.parse(stdout) as Inventory;
}
