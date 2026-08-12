import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const INSTALLATION_COOKIE = "avert_github_installation";
export const INSTALL_STATE_COOKIE = "avert_github_install_state";
export const OAUTH_STATE_COOKIE = "avert_github_oauth_state";
export const OAUTH_VERIFIER_COOKIE = "avert_github_oauth_verifier";
export const PENDING_INSTALLATION_COOKIE = "avert_github_pending_installation";

export interface GitHubOAuthConfig {
  appSlug: string;
  clientId: string;
  clientSecret: string;
  callbackUrl: string;
  sessionSecret: string;
}

export function githubOAuthConfig(): GitHubOAuthConfig {
  const config = {
    appSlug: process.env.GITHUB_APP_SLUG,
    clientId: process.env.GITHUB_CLIENT_ID,
    clientSecret: process.env.GITHUB_CLIENT_SECRET,
    callbackUrl: process.env.GITHUB_CALLBACK_URL,
    sessionSecret: process.env.GITHUB_SESSION_SECRET,
  };
  if (Object.values(config).some((value) => !value)) {
    throw new Error(
      "GITHUB_APP_SLUG, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, " +
      "GITHUB_CALLBACK_URL, and GITHUB_SESSION_SECRET are required",
    );
  }
  if (config.sessionSecret!.length < 32) {
    throw new Error("GITHUB_SESSION_SECRET must be at least 32 characters");
  }
  return config as GitHubOAuthConfig;
}

export function randomToken(): string {
  return randomBytes(32).toString("base64url");
}

export function installUrl(appSlug: string, state: string): URL {
  const url = new URL(`https://github.com/apps/${encodeURIComponent(appSlug)}/installations/new`);
  url.searchParams.set("state", state);
  return url;
}

export function oauthUrl(config: GitHubOAuthConfig, state: string, verifier: string): URL {
  const url = new URL("https://github.com/login/oauth/authorize");
  url.searchParams.set("client_id", config.clientId);
  url.searchParams.set("redirect_uri", config.callbackUrl);
  url.searchParams.set("state", state);
  url.searchParams.set(
    "code_challenge",
    createHash("sha256").update(verifier).digest("base64url"),
  );
  url.searchParams.set("code_challenge_method", "S256");
  return url;
}

export function tokensMatch(received: string | null | undefined, expected: string | undefined): boolean {
  if (!received || !expected) return false;
  const left = Buffer.from(received);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function signInstallationId(
  installationId: number,
  secret: string,
  expiresAt = Math.floor(Date.now() / 1000) + 60 * 60 * 8,
): string {
  const payload = `${installationId}.${expiresAt}`;
  const signature = createHmac("sha256", secret).update(payload).digest("base64url");
  return `${payload}.${signature}`;
}

export function verifyInstallationCookie(value: string | undefined, secret: string): number | null {
  if (!value) return null;
  const [idValue, expiryValue, signature, extra] = value.split(".");
  const id = Number(idValue);
  const expiresAt = Number(expiryValue);
  if (
    extra !== undefined ||
    !signature ||
    !Number.isSafeInteger(id) ||
    id <= 0 ||
    !Number.isSafeInteger(expiresAt) ||
    expiresAt <= Math.floor(Date.now() / 1000)
  ) return null;
  return tokensMatch(value, signInstallationId(id, secret, expiresAt)) ? id : null;
}

export async function exchangeOAuthCode(
  config: GitHubOAuthConfig,
  code: string,
  verifier: string,
  request: typeof fetch = fetch,
): Promise<string> {
  const response = await request("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: config.clientId,
      client_secret: config.clientSecret,
      code,
      redirect_uri: config.callbackUrl,
      code_verifier: verifier,
    }),
  });
  const data = await response.json() as { access_token?: string; error_description?: string };
  if (!response.ok || !data.access_token) {
    throw new Error(data.error_description ?? "GitHub OAuth exchange failed");
  }
  return data.access_token;
}

export async function userInstallationIds(
  accessToken: string,
  request: typeof fetch = fetch,
): Promise<number[]> {
  const response = await request("https://api.github.com/user/installations?per_page=100", {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${accessToken}`,
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  const data = await response.json() as { installations?: Array<{ id: number }> };
  if (!response.ok || !data.installations) throw new Error("Could not verify GitHub installation");
  return data.installations.map((installation) => installation.id);
}
