import { createHmac } from "node:crypto";

import { describe, expect, it } from "vitest";

import { pushTarget, verifyWebhookSignature } from "../src/github/webhook";

const secret = "s3cret";
const body = JSON.stringify({ hello: "world" });
const sign = (payload: string, key = secret) =>
  `sha256=${createHmac("sha256", key).update(payload).digest("hex")}`;

describe("GitHub webhook", () => {
  it("accepts only a matching sha256 signature", () => {
    expect(verifyWebhookSignature(body, sign(body), secret)).toBe(true);
    expect(verifyWebhookSignature(body, sign(body, "other"), secret)).toBe(false);
    expect(verifyWebhookSignature(body, sign(body).slice(0, -2), secret)).toBe(false);
    expect(verifyWebhookSignature(body, null, secret)).toBe(false);
    expect(verifyWebhookSignature(body, "sha1=abc", secret)).toBe(false);
  });

  const push = {
    ref: "refs/heads/main",
    after: "c".repeat(40),
    deleted: false,
    installation: { id: 42 },
    repository: { full_name: "acme/api", default_branch: "main" },
  };

  it("re-indexes pushes to the default branch at the pushed commit", () => {
    expect(pushTarget(push)).toEqual({ installationId: 42, fullName: "acme/api", commit: "c".repeat(40) });
  });

  it("ignores other branches, deletions, and malformed payloads", () => {
    expect(pushTarget({ ...push, ref: "refs/heads/feature" })).toBeNull();
    expect(pushTarget({ ...push, after: "0".repeat(40), deleted: true })).toBeNull();
    expect(pushTarget({ ...push, installation: undefined })).toBeNull();
    expect(pushTarget({ ...push, after: "not-a-sha" })).toBeNull();
    expect(pushTarget("push")).toBeNull();
  });
});
