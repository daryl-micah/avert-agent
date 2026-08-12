import { describe, expect, it, vi } from "vitest";

import {
  downloadRepositoryArchive,
  getRepositoryFile,
  listInstallationRepositories,
} from "../src/github/client";

describe("read-only GitHub client", () => {
  it("lists repositories visible to an installation", async () => {
    const request = vi.fn().mockResolvedValue({
      data: {
        repositories: [{
          id: 7,
          full_name: "acme/api",
          private: true,
          default_branch: "main",
        }],
      },
    });

    await expect(listInstallationRepositories({ request })).resolves.toEqual([{
      id: 7,
      fullName: "acme/api",
      private: true,
      defaultBranch: "main",
    }]);
    expect(request).toHaveBeenCalledWith("GET /installation/repositories", { per_page: 100 });
  });

  it("fetches file content without a write request", async () => {
    const request = vi.fn().mockResolvedValue({
      data: { type: "file", encoding: "base64", content: Buffer.from("hello").toString("base64") },
    });

    await expect(getRepositoryFile({ request }, "acme", "api", "src/app.py", "main"))
      .resolves.toBe("hello");
    expect(request.mock.calls[0][0]).toBe("GET /repos/{owner}/{repo}/contents/{path}");
  });

  it("rejects directories", async () => {
    const request = vi.fn().mockResolvedValue({ data: { type: "dir" } });
    await expect(getRepositoryFile({ request }, "acme", "api", "src"))
      .rejects.toThrow("not a downloadable file");
  });

  it("downloads a repository archive with a read request", async () => {
    const request = vi.fn().mockResolvedValue({ data: new Uint8Array([1, 2, 3]) });
    await expect(downloadRepositoryArchive({ request }, "acme", "api", "main"))
      .resolves.toEqual(Buffer.from([1, 2, 3]));
    expect(request.mock.calls[0][0]).toBe("GET /repos/{owner}/{repo}/tarball/{ref}");
  });
});
