import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { x as extractTar } from "tar";

import { inventoryFromJsonl, type Inventory } from "./inventory";

const execFileAsync = promisify(execFile);

export interface IndexRequest {
  repo: string;
  commit: string;
}

type IndexRunner = (
  sourcePath: string,
  outputPath: string,
  request: IndexRequest,
) => Promise<void>;

async function runEngineIndexer(
  sourcePath: string,
  outputPath: string,
  request: IndexRequest,
): Promise<void> {
  const enginePath = path.resolve(process.cwd(), "../engine");
  await execFileAsync(
    "uv",
    [
      "run",
      "avert",
      "index",
      sourcePath,
      "--repo",
      request.repo,
      "--commit",
      request.commit,
      "--out",
      outputPath,
    ],
    { cwd: enginePath, timeout: 120_000, maxBuffer: 1024 * 1024 },
  );
}

export async function indexRepositoryArchive(
  archive: Buffer,
  request: IndexRequest,
  runIndexer: IndexRunner = runEngineIndexer,
): Promise<Inventory> {
  const temporaryRoot = await mkdtemp(path.join(tmpdir(), "avert-index-"));
  const archivePath = path.join(temporaryRoot, "repository.tar.gz");
  const sourcePath = path.join(temporaryRoot, "repository");
  const outputPath = path.join(temporaryRoot, "calls.jsonl");
  try {
    await mkdir(sourcePath);
    await writeFile(archivePath, archive);
    await extractTar({
      file: archivePath,
      cwd: sourcePath,
      strip: 1,
      strict: true,
      filter: (_entryPath, entry) => {
        if (!("type" in entry)) return !entry.isSymbolicLink();
        return entry.type !== "SymbolicLink" && entry.type !== "Link";
      },
    });
    await runIndexer(sourcePath, outputPath, request);
    return inventoryFromJsonl(await readFile(outputPath, "utf8"));
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
}
