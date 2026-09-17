import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { c as createTar } from "tar";
import { describe, expect, it, vi } from "vitest";

import { indexGitHubRepository, indexRepositoryArchive } from "../src/inventory/github-indexer";

const inventory = {
  generated_at: "2026-09-18T00:00:00Z",
  repositories: ["acme/api"],
  providers: [],
  call_site_count: 0,
  attention_count: 0,
  dependencies: [],
};

describe("ephemeral GitHub indexing", () => {
  it("indexes an installation repository at its resolved commit", async () => {
    const sha = "b".repeat(40);
    const archive = Buffer.from([1, 2, 3]);
    const request = vi.fn()
      .mockResolvedValueOnce({ data: { repositories: [{
        id: 7,
        full_name: "acme/api",
        private: true,
        default_branch: "main",
      }] } })
      .mockResolvedValueOnce({ data: { sha } })
      .mockResolvedValueOnce({ data: archive });
    const archiveIndexer = vi.fn().mockResolvedValue(inventory);

    await indexGitHubRepository({ request }, 42, "acme/api", undefined, archiveIndexer);

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "GET /installation/repositories",
      "GET /repos/{owner}/{repo}/commits/{ref}",
      "GET /repos/{owner}/{repo}/tarball/{ref}",
    ]);
    expect(archiveIndexer).toHaveBeenCalledWith(archive, { repo: "acme/api", commit: sha, installationId: 42 });
  });

  it("extracts, indexes, and removes the repository copy", async () => {
    const fixtureRoot = await mkdtemp(path.join(tmpdir(), "avert-index-fixture-"));
    const archivePath = path.join(fixtureRoot, "repository.tar.gz");
    const sourceRoot = path.join(fixtureRoot, "archive-root");
    let extractedPath = "";
    try {
      await mkdir(path.join(sourceRoot, "src"), { recursive: true });
      await writeFile(path.join(sourceRoot, "src", "client.py"), "print('fixture')\n");
      await createTar({ gzip: true, cwd: fixtureRoot, file: archivePath }, ["archive-root"]);
      const archive = await readFile(archivePath);

      const result = await indexRepositoryArchive(
        archive,
        { repo: "acme/api", commit: "main", installationId: 42 },
        async (sourcePath, request) => {
          extractedPath = sourcePath;
          await access(path.join(sourcePath, "src", "client.py"));
          expect(request.installationId).toBe(42);
          return inventory;
        },
      );

      expect(result).toBe(inventory);
      await expect(access(extractedPath)).rejects.toThrow();
    } finally {
      await rm(fixtureRoot, { recursive: true, force: true });
    }
  });
});
