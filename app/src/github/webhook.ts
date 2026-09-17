import { createHmac, timingSafeEqual } from "node:crypto";

export function verifyWebhookSignature(
  rawBody: string,
  signatureHeader: string | null,
  secret: string,
): boolean {
  if (!signatureHeader?.startsWith("sha256=")) return false;
  const expected = createHmac("sha256", secret).update(rawBody).digest("hex");
  const received = signatureHeader.slice("sha256=".length);
  if (received.length !== expected.length) return false;
  return timingSafeEqual(Buffer.from(received, "hex"), Buffer.from(expected, "hex"));
}

export interface PushTarget {
  installationId: number;
  fullName: string;
  commit: string;
}

// Only pushes to the default branch re-index; branch deletions (after is the
// zero SHA) and feature branches are ignored.
export function pushTarget(payload: unknown): PushTarget | null {
  if (typeof payload !== "object" || payload === null) return null;
  const event = payload as {
    ref?: unknown;
    after?: unknown;
    deleted?: unknown;
    installation?: { id?: unknown };
    repository?: { full_name?: unknown; default_branch?: unknown };
  };
  const installationId = event.installation?.id;
  const fullName = event.repository?.full_name;
  const defaultBranch = event.repository?.default_branch;
  if (
    typeof event.ref !== "string" ||
    typeof event.after !== "string" ||
    !/^[a-f0-9]{40}$/i.test(event.after) ||
    /^0+$/.test(event.after) ||
    event.deleted === true ||
    typeof installationId !== "number" ||
    typeof fullName !== "string" ||
    typeof defaultBranch !== "string" ||
    event.ref !== `refs/heads/${defaultBranch}`
  ) {
    return null;
  }
  return { installationId, fullName, commit: event.after };
}
