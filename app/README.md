# Avert app

The Week 4 demo is a read-only GitHub App client and inventory dashboard. The app never
requests repository write access.

## Local demo

1. Create a GitHub App with **Contents: read-only** repository permission. Leave
   **Request user authorization (OAuth) during installation** disabled, then configure:

   - Setup URL: `http://localhost:3000/api/github/setup`
   - Callback URL: `http://localhost:3000/api/github/callback`

2. Copy `.env.example` to `.env.local` and add the app, OAuth, and private-key credentials.
3. Start the dashboard:

   ```bash
   npm ci
   npm run dev
   ```

4. Select **Connect GitHub**, install the app, authorize your user, and choose a repository.
   Avert resolves the selected branch to an immutable commit, downloads that archive with the
   installation's read-only token, indexes it under a temporary directory, returns the inventory,
   and deletes the source copy. Repository selection is paginated for installations with more
   than 100 repositories.

For offline development, the original JSONL path remains available:

```bash
cd ../engine
uv run avert index /path/to/repository --repo owner/name --out ../calls.jsonl
```

Set `AVERT_INVENTORY_PATH=../calls.jsonl` before starting the app. The read-only repository
connection is available at `GET /api/github/repositories`; ephemeral indexing is
`POST /api/github/repositories/index`; normalized offline inventory is `GET /api/inventory`.

This remains a local demo path. It does not persist installations or inventory, and its server
runtime must have the engine's `uv` environment available.

## Week 4 acceptance

- GitHub installation and user authorization are protected with separate state tokens; OAuth uses
  PKCE, and the user token is discarded after installation ownership is verified.
- The signed installation session is HTTP-only, expires after eight hours, and can only create an
  installation-scoped, read-only GitHub client.
- A requested repository must belong to the connected installation. The indexed revision and the
  recorded `commit_sha` are the same immutable SHA.
- Repository source is extracted without archive links, indexed in a temporary directory, and
  removed in a `finally` block.
- Unit tests cover authentication, repository pagination, immutable revision resolution, the full
  mocked GitHub-to-indexer sequence, archive cleanup, and inventory lifecycle normalization.
