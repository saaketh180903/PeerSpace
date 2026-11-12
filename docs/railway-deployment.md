# Railway deployment notes

These settings prepare a small trial. The app has not yet been deployed or reviewed for public production use. Check Railway's current free-tier limits before creating services.

## Before deploying

- Use a new, private repository or the Railway CLI to provide the code. Do not upload `.env` files or the local SQLite database.
- The online database should start with curated opportunities only. Do not run `backend.seed_real_opportunities` online: it creates public-password demo accounts.
- Review the dates and eligibility of the snapshot in `backend/curated_opportunities.json` against each official link before importing it.
- Configure backups, access controls, rate limits, and other public-facing security before inviting real participants.

## Backend service

- Source root: repository root (`/`).
- Set `RAILWAY_DOCKERFILE_PATH` to `Dockerfile.backend`.
- Attach a Railway volume at `/data` and set `DATABASE_URL` to `sqlite:////data/peerspace.db`.
- Set `ALLOWED_ORIGINS` to the exact HTTPS frontend URL, with no trailing slash. Separate multiple trusted origins with commas.
- Generate a public Railway domain and use `/health` as the health-check path. Keep one replica because the SQLite file is local to the volume.

## Frontend service

- Use the same source with root directory `/` and set `RAILWAY_DOCKERFILE_PATH` to `frontend/Dockerfile`.
- Set `NEXT_PUBLIC_API_URL` to the backend's HTTPS public URL, without a trailing slash. It must be present during the frontend build; redeploy the frontend when it changes.
- Generate a frontend public domain, then put its exact URL in the backend `ALLOWED_ORIGINS` and redeploy the backend.

The volume must be attached and `DATABASE_URL` configured before the first backend start intended to persist data. Test persistence after restarting the service. Railway mounts volumes at runtime, not build time.

## Curated data

After the database exists, create a real owner account through the application. Only after reviewing the snapshot, an authorized operator can grant this account administrator access and import the curated records from inside the backend container:

```sh
python -m backend.manage make-admin your-email@example.com
python -m backend.manage import-curated your-email@example.com backend/curated_opportunities.json
```

Use Railway's authenticated shell for the running backend, if available on the account. Do not upload or run the local demo seeder. Confirm the hosted records, then test accounts, requests, messaging, privacy and restart persistence before inviting testers.

## Important limitations

SQLite uses a single writable volume and does not provide multi-instance database failover. A volume is not a substitute for an independently tested backup. The free allowance may be exhausted before the end of the month. The local MVP does not yet have login rate limiting, email verification or a production security review; open signup remains the agreed product policy.
