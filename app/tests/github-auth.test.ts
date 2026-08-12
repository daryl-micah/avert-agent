import { describe, expect, it, vi } from "vitest";

import {
  exchangeOAuthCode,
  installUrl,
  oauthUrl,
  signInstallationId,
  userInstallationIds,
  verifyInstallationCookie,
  type GitHubOAuthConfig,
} from "../src/github/auth";

const config: GitHubOAuthConfig = {
  appSlug: "avert-demo",
  clientId: "client-id",
  clientSecret: "client-secret",
  callbackUrl: "https://avert.test/api/github/callback",
  sessionSecret: "session-secret",
};

describe("GitHub connection authentication", () => {
  it("preserves state through install and PKCE OAuth URLs", () => {
    expect(installUrl(config.appSlug, "install-state").searchParams.get("state"))
      .toBe("install-state");
    const url = oauthUrl(config, "oauth-state", "verifier");
    expect(url.searchParams.get("state")).toBe("oauth-state");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("code_challenge")).not.toBe("verifier");
  });

  it("rejects tampered installation cookies", () => {
    const cookie = signInstallationId(42, config.sessionSecret);
    expect(verifyInstallationCookie(cookie, config.sessionSecret)).toBe(42);
    expect(verifyInstallationCookie(cookie.replace(/^42/, "43"), config.sessionSecret)).toBeNull();
    expect(verifyInstallationCookie(signInstallationId(42, config.sessionSecret, 1), config.sessionSecret))
      .toBeNull();
  });

  it("exchanges an OAuth code without retaining the user token", async () => {
    const request = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ access_token: "ghu_token" }),
      { status: 200 },
    ));
    await expect(exchangeOAuthCode(config, "code", "verifier", request)).resolves.toBe("ghu_token");
    const body = request.mock.calls[0][1]?.body as URLSearchParams;
    expect(body.get("code_verifier")).toBe("verifier");
  });

  it("loads installations accessible to the authorizing user", async () => {
    const request = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ installations: [{ id: 10 }, { id: 20 }] }),
      { status: 200 },
    ));
    await expect(userInstallationIds("ghu_token", request)).resolves.toEqual([10, 20]);
    expect(request.mock.calls[0][1]?.headers.Authorization).toBe("Bearer ghu_token");
  });
});
