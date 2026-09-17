import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { c as createTar } from "tar";
import { describe, expect, it, vi } from "vitest";

import { indexGitHubRepository, indexRepositoryArchive } from "../src/inventory/github-indexer";

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
    const archiveIndexer = vi.fn().mockResolvedValue({
      repositories: ["acme/api"],
      providers: [],
      callSiteCount: 0,
      attentionCount: 0,
      dependencies: [],
    });

    await indexGitHubRepository({ request }, "acme/api", undefined, archiveIndexer);

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      "GET /installation/repositories",
      "GET /repos/{owner}/{repo}/commits/{ref}",
      "GET /repos/{owner}/{repo}/tarball/{ref}",
    ]);
    expect(archiveIndexer).toHaveBeenCalledWith(archive, { repo: "acme/api", commit: sha });
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

      const inventory = await indexRepositoryArchive(
        archive,
        { repo: "acme/api", commit: "main" },
        async (sourcePath, outputPath) => {
          extractedPath = sourcePath;
          await access(path.join(sourcePath, "src", "client.py"));
          await writeFile(outputPath, JSON.stringify({
            surface: {
              provider: "openai",
              resource: "chat.completions",
              operation: "create",
              field_path: "model",
              value: "gpt-4-0613",
            },
            repo: "acme/api",
            commit_sha: "main",
            file_path: "src/client.py",
            line_start: 1,
            line_end: 1,
            language: "python",
            value_binding: "literal",
            confidence: 1,
            extractor: "tree_sitter.python",
            file_content_hash: "a".repeat(64),
          }) + "\n");
        },
      );

      expect(inventory).toMatchObject({ callSiteCount: 1, attentionCount: 1 });
      await expect(access(extractedPath)).rejects.toThrow();
    } finally {
      await rm(fixtureRoot, { recursive: true, force: true });
    }
  });
});
