# Avert app

The Week 4 demo is a read-only GitHub App client and inventory dashboard. The app never
requests repository write access.

## Local demo

1. Create a GitHub App with **Contents: read-only** repository permission and install it on
   the repositories to inventory.
2. Copy `.env.example` to `.env.local` and add the app ID, installation ID, and private key.
3. Generate inventory from a checked-out repository:

   ```bash
   cd ../engine
   uv run avert index /path/to/repository --repo owner/name --out ../calls.jsonl
   ```

4. Start the dashboard:

   ```bash
   cd ../app
   npm ci
   npm run dev
   ```

The dashboard reads the `CallSite` JSONL at `AVERT_INVENTORY_PATH`. The read-only repository
connection is available at `GET /api/github/repositories`; normalized inventory is available
at `GET /api/inventory`.

This iteration is a local demo path. User authentication, GitHub installation callbacks, and
server-side repository checkout/indexing are not included yet.
