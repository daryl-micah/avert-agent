import { App } from "@octokit/app";

export interface RepositorySummary {
  id: number;
  fullName: string;
  private: boolean;
  defaultBranch: string;
}

export interface GitHubRequester {
  request(route: string, parameters: Record<string, unknown>): Promise<{ data: unknown }>;
}

interface GitHubRepository {
  id: number;
  full_name: string;
  private: boolean;
  default_branch: string;
}

export async function listInstallationRepositories(
  github: GitHubRequester,
): Promise<RepositorySummary[]> {
  const response = await github.request("GET /installation/repositories", { per_page: 100 });
  const data = response.data as { repositories: GitHubRepository[] };
  return data.repositories.map((repository) => ({
    id: repository.id,
    fullName: repository.full_name,
    private: repository.private,
    defaultBranch: repository.default_branch,
  }));
}

export async function getRepositoryFile(
  github: GitHubRequester,
  owner: string,
  repo: string,
  filePath: string,
  ref?: string,
): Promise<string> {
  const response = await github.request("GET /repos/{owner}/{repo}/contents/{path}", {
    owner,
    repo,
    path: filePath,
    ...(ref ? { ref } : {}),
  });
  const data = response.data as { type?: string; content?: string; encoding?: string };
  if (data.type !== "file" || data.encoding !== "base64" || !data.content) {
    throw new Error(`${owner}/${repo}:${filePath} is not a downloadable file`);
  }
  return Buffer.from(data.content.replace(/\n/g, ""), "base64").toString("utf8");
}

export async function installationClientFromEnvironment(): Promise<GitHubRequester> {
  const appId = process.env.GITHUB_APP_ID;
  const privateKey = process.env.GITHUB_PRIVATE_KEY?.replace(/\\n/g, "\n");
  const installationId = process.env.GITHUB_INSTALLATION_ID;
  if (!appId || !privateKey || !installationId) {
    throw new Error(
      "GITHUB_APP_ID, GITHUB_PRIVATE_KEY, and GITHUB_INSTALLATION_ID are required",
    );
  }
  const app = new App({ appId, privateKey });
  return app.getInstallationOctokit(Number(installationId));
}
