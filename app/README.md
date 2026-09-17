# Avert app

The Week 4 demo is a read-only GitHub App client and inventory dashboard. The app never
requests repository write access.

## Local demo

1. Create a GitHub App with **Contents: read-only** repository permission. Leave
   **Request user authorization (OAuth) during installation** disabled, then configure:

   - Setup URL: `http://localhost:3000/api/github/setup`
   - Callback URL: `http://localhost:3000/api/github/callback`
   - Webhook URL: `http://localhost:3000/api/github/webhook`, subscribed to **Push** events, with a
     webhook secret (use a tunnel such as `gh webhook forward` or ngrok for local development)

2. Copy `.env.example` to `.env.local` and add the app, OAuth, private-key, and webhook credentials.
   `AVERT_DATABASE_URL` points at the compose Postgres (`docker compose up -d` from the repository
   root).
3. Start the dashboard:

   ```bash
   npm ci
   npm run dev
   ```

4. Select **Connect GitHub**, install the app, authorize your user, and choose a repository.
   Avert resolves the selected branch to an immutable commit, downloads that archive with the
   installation's read-only token, indexes it incrementally into Postgres under the installation,
   deletes the source copy, and renders the inventory the engine builds from the impact join.
   Subsequent pushes to the repository's default branch re-index it through the webhook.

The app owns no inventory logic: every route shells out to `avert index`, `avert registry`, and
`avert inventory` (see `src/inventory/engine.ts`), so lifecycle status has exactly one definition,
`engine/avert/join.py`. The inventory shape is `shared/schemas/inventory.schema.json`.

For development without GitHub, index a local checkout directly and open the dashboard after
connecting — or read the JSON the dashboard would render:

```bash
cd ../engine
uv run avert index /path/to/repository --repo owner/name --database $AVERT_DATABASE_URL
uv run avert registry --database $AVERT_DATABASE_URL
uv run avert inventory --database $AVERT_DATABASE_URL
```

Endpoints: `GET /api/github/repositories`, `POST /api/github/repositories/index`,
`POST /api/github/webhook`, `GET /api/inventory`, `GET /api/impacts` (the change feed rendered in
the dashboard's Changes section). The server runtime must have the engine's `uv`
environment and Postgres reachable. Webhook re-indexing runs inline after the response; a queue
and worker (STRUCTURE.md `db/queue.py`, `workers/`) are still to come.

## Week 4 acceptance

- GitHub installation and user authorization are protected with separate state tokens; OAuth uses
  PKCE, and the user token is discarded after installation ownership is verified.
- The signed installation session is HTTP-only, expires after eight hours, and can only create an
  installation-scoped, read-only GitHub client.
- A requested repository must belong to the connected installation. The indexed revision and the
  recorded `commit_sha` are the same immutable SHA.
- Repository source is extracted without archive links, indexed in a temporary directory, and
  removed in a `finally` block.
- Webhook deliveries are verified against `GITHUB_WEBHOOK_SECRET`; only default-branch pushes
  re-index, at the pushed commit.
- Unit tests cover authentication, repository pagination, immutable revision resolution, the full
  mocked GitHub-to-indexer sequence, archive cleanup, and webhook verification. Lifecycle status is
  tested where it is computed, in the engine's Postgres suite.
