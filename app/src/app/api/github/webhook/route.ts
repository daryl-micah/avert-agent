import { after, NextResponse } from "next/server";

import { installationClient } from "@/github/client";
import { pushTarget, verifyWebhookSignature } from "@/github/webhook";
import { indexGitHubRepository } from "@/inventory/github-indexer";

export async function POST(request: Request) {
  const secret = process.env.GITHUB_WEBHOOK_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "GITHUB_WEBHOOK_SECRET is required" }, { status: 500 });
  }
  const rawBody = await request.text();
  if (!verifyWebhookSignature(rawBody, request.headers.get("x-hub-signature-256"), secret)) {
    return NextResponse.json({ error: "Invalid webhook signature" }, { status: 401 });
  }
  if (request.headers.get("x-github-event") !== "push") {
    return NextResponse.json({ ignored: true });
  }

  const target = pushTarget(JSON.parse(rawBody));
  if (!target) return NextResponse.json({ ignored: true });

  // GitHub gives a webhook ten seconds; indexing runs after the response.
  after(async () => {
    try {
      const github = await installationClient(target.installationId);
      await indexGitHubRepository(github, target.installationId, target.fullName, target.commit);
    } catch (error) {
      console.error(`webhook re-index failed for ${target.fullName}@${target.commit}`, error);
    }
  });
  return NextResponse.json({ queued: target }, { status: 202 });
}
