import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { x as extractTar } from "tar";

import {
  downloadRepositoryArchive,
  listInstallationRepositories,
  resolveRepositoryCommit,
  type GitHubRequester,
} from "../github/client";
import type { Inventory } from "@/types/inventory";
import { indexIntoDatabase, loadInventory, syncRegistry, type IndexRequest } from "./engine";

type IndexRunner = (sourcePath: string, request: IndexRequest) => Promise<Inventory>;

type ArchiveIndexer = (archive: Buffer, request: IndexRequest) => Promise<Inventory>;

async function runEngine(sourcePath: string, request: IndexRequest): Promise<Inventory> {
  await indexIntoDatabase(sourcePath, request);
  await syncRegistry();
  return loadInventory(request.installationId);
}

export async function indexRepositoryArchive(
  archive: Buffer,
  request: IndexRequest,
  runIndexer: IndexRunner = runEngine,
): Promise<Inventory> {
  const temporaryRoot = await mkdtemp(path.join(tmpdir(), "avert-index-"));
  const archivePath = path.join(temporaryRoot, "repository.tar.gz");
  const sourcePath = path.join(temporaryRoot, "repository");
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
    return await runIndexer(sourcePath, request);
  } finally {
    await rm(temporaryRoot, { recursive: true, force: true });
  }
}

export async function indexGitHubRepository(
  github: GitHubRequester,
  installationId: number,
  fullName: string,
  requestedRef?: string,
  archiveIndexer: ArchiveIndexer = indexRepositoryArchive,
): Promise<Inventory> {
  const repositories = await listInstallationRepositories(github);
  const repository = repositories.find((candidate) => candidate.fullName === fullName);
  if (!repository) throw new Error("Repository is not available to this installation");

  const [owner, repo] = repository.fullName.split("/", 2);
  const ref = requestedRef ?? repository.defaultBranch;
  const commit = await resolveRepositoryCommit(github, owner, repo, ref);
  const archive = await downloadRepositoryArchive(github, owner, repo, commit);
  return archiveIndexer(archive, { repo: repository.fullName, commit, installationId });
}
