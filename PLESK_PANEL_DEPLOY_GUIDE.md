# Deploy the Vault API on Plesk with Docker

This guide deploys the Django API at `https://api.g4057.com`, uses the existing
Vault Supabase project, and allows the frontend at `https://g4057.com` (and
`https://www.g4057.com`) to call it. Product images remain in the separately
deployed frontend's `public/products/` directory.

## Before you start

- Confirm the Plesk server/account has the Docker extension and access to
  **Docker → Stacks**. Ask the Plesk administrator or hosting provider to enable
  it if it is missing.
- Point the `api.g4057.com` DNS A record to the Plesk server's public IP.
- Have the Vault Supabase Session Pooler URI ready. Do not reuse another
  application's database.
- Use the production template in `.env.plesk.example`; do not upload a real
  `.env`, `.venv`, or `db.sqlite3`.

## 1. Upload the backend source

1. On your Windows computer, open PowerShell in the `Vault-Backend` folder and
   run the release builder:

   ```powershell
   python .\scripts\make_plesk_release.py
   ```

   It creates a timestamped `vault-api-plesk-release-YYYYMMDD-HHMMSS.zip`
   in the `Vault-Backend` folder, validates the archive, and excludes your real
   `.env`, local database, virtual environment, and generated files. Keep the
   release ZIP for rollback; do not add `.env` to it.
2. In Plesk **Files**, open the home directory for the domain subscription
   (the directory above `httpdocs`).
3. Create a private folder named `vault-api` beside `httpdocs`, not inside it.
4. Upload the generated `vault-api-plesk-release-*.zip` into that folder. Select the ZIP and click
   **Extract Files**; use `vault-api` itself as the destination. The archive
   contains the project files at its root, so do not extract into an additional
   nested `Vault-Backend` folder.
5. Verify that `Dockerfile`, `docker-compose.prod.yml`, `entrypoint.sh`,
   `manage.py`, `requirements.txt`, `config`, and `apps` are directly inside
   `vault-api`. Do not include `.env`, `.venv`, `db.sqlite3`, or `staticfiles`.
6. Copy `.env.plesk.example` to a new file named `.env` in `vault-api`.

## 2. Set production environment values

Edit the server-side `vault-api/.env` file:

- Set `DJANGO_SECRET_KEY` to a newly generated random secret. Do not use a
  published example or reuse another project's key.
- Replace the sample `DATABASE_URL` with the complete **Session Pooler** URI
  copied from the Vault Supabase project's **Connect → Direct Connection →
  Method: Session Pooler** screen. Preserve its username, host, and port, and
  URL-encode special characters in the password.
- Keep `DJANGO_DEBUG=0` and `DATABASE_SSL_REQUIRE=1`.
- The frontend/API domain and CORS values in the template are prefilled for
  `g4057.com` and `api.g4057.com`; change them only if the actual deployed
  frontend uses a different origin.
- Keep `.env` private. Never include it in the upload archive or commit it.

The Compose service also requires a non-empty `DATABASE_URL` at startup, so a
missing production database configuration cannot silently fall back to an
ephemeral SQLite database.

## 3. Start the Docker Stack

1. In Plesk open **Docker → Stacks → Add Stack**.
2. Name the stack `vault-prod`.
3. Choose **Webspace** as the Compose source, select the subscription that
   contains `vault-api`, and select
   `vault-api/docker-compose.prod.yml`. Use the Webspace/build-context option
   so Plesk can access the Dockerfile and source files beside the Compose file.
4. Deploy/Run the Stack. The first build installs Python dependencies and may
   take several minutes. On startup, the API container runs Django migrations
   against Supabase before starting Gunicorn.
5. Check the `api-prod` container logs if it does not become healthy. Database
   DNS, credentials, or pooler URI errors will appear there.

The API is published only on host loopback port `8400` (`127.0.0.1:8400`).
Do not expose port `8400` publicly.

## 4. Connect the API subdomain and HTTPS

1. In Plesk open **Websites & Domains → api.g4057.com → Docker Proxy Rules →
   Add Rule**.
2. Set the rule path to `/`, choose the running `vault-prod-api-1` container,
   and select its `8400 → 8000` port mapping. Save the rule.
3. In **SSL/TLS Certificates**, issue/install a Let's Encrypt certificate for
   `api.g4057.com`, then enable HTTP-to-HTTPS redirection.
4. If Docker Proxy Rules are unavailable, ask the Plesk administrator to
   configure the equivalent reverse proxy and forward the `Host`,
   `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto` headers.

## 5. Verify the API and create an admin

Open `https://api.g4057.com/api/health/`; it should return
`{"status":"ok"}`. Open `https://api.g4057.com/admin/` for Django's admin site.

To create the Django superuser, open the API container's **Console/Exec** in
Plesk and run:

```sh
python manage.py createsuperuser
```

Create the account interactively and keep its password private. This account
can sign in to Django admin and to the frontend admin dashboard at
`https://g4057.com/admin`. It is approved as a Vault admin by the
project's account-creation signal. Only the configured owner account can grant
or remove admin roles.

If this is a new, empty Supabase project, seed the catalog once from the same
container console with `python manage.py seed_products`. It skips products
whose names already exist.

## 6. Point the frontend at the API

In the Vault frontend's production build environment set:

```dotenv
VITE_API_URL=https://api.g4057.com/api
```

Rebuild and redeploy the frontend to `https://g4057.com`. The frontend deploy
must include `public/products/` so the catalog images referenced by
`seed_products` are available.

## Future backend updates

Upload the changed backend source into `vault-api`, preserving the server's
`.env`. In Plesk **Docker → Stacks**, rebuild and redeploy `vault-prod` so the
image includes the new code. Review the API container logs and check the health
URL after deployment. Back up Supabase before schema changes.




# commands to setup plesk zip
# Backend ZIP:
Set-Location 'D:\workflows_void\cyberghostsolutions\Vault-Backend'
python .\scripts\make_plesk_release.py

# Vault frontend ZIP:
Set-Location 'D:\workflows_void\cyberghostsolutions\Vault-Frontend'
npm ci
npm run build:plesk