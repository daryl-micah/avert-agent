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
   Avert downloads the repository archive with the installation's read-only token, indexes it
   under a temporary directory, returns the inventory, and deletes the source copy.

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
