# Cube Setup

## Why a Service Account Key Is Required

Cube looks up each user's Google Workspace group membership at query time using
the Admin Directory API. It calls the API as a service account with
[domain-wide delegation](https://developers.google.com/workspace/guides/create-credentials#optional_set_up_domain-wide_delegation_for_a_service_account)
— a mechanism that lets the service account impersonate a Workspace super-admin,
which is required for cross-domain group lookups.

Keyless authentication (Workload Identity Federation) would eliminate the need
for a stored key, but it requires the workload to present an OIDC token from a
trusted identity provider to Google's Security Token Service. Cube Cloud is
managed SaaS running on Cube's infrastructure — KIPP cannot configure Workload
Identity on those pods. A service account key is the only viable credential for
this deployment.

If Cube is ever migrated to a self-hosted deployment on KIPP's GKE cluster,
Workload Identity can replace the key — `GoogleAuth` would pick up ambient ADC
credentials automatically and `GOOGLE_DIRECTORY_SA_KEY` could be removed.

## Directory API Service Account Setup

Performed once by an admin. Creates the service account used by Cube to look up
Workspace group membership.

### 1. Enable the Admin SDK API

In the [GCP Console](https://console.cloud.google.com/apis/library) for project
`teamster-332318`, search for **Admin SDK API** and enable it.

### 2. Create the service account

In **IAM & Admin → Service Accounts**, create a new service account:

- Name: `cube-directory-reader`
- ID: `cube-directory-reader@teamster-332318.iam.gserviceaccount.com`
- No GCP IAM roles — access is granted via Workspace DWD, not GCP IAM

Do not reuse the BigQuery service account (`CUBEJS_DB_BQ_CREDENTIALS`). The
BigQuery SA has GCP data access; combining it with DWD means a single key
compromise grants both warehouse access and domain-wide group enumeration.

### 3. Create a JSON key

In the service account details, go to **Keys → Add key → Create new key →
JSON**. Download the file and keep it secure.

### 4. Grant domain-wide delegation in Google Workspace

In [Google Workspace Admin](https://admin.google.com), go to **Security → Access
and data control → API controls → Domain-wide delegation → Add new**:

- **Client ID**: the numeric client ID from the service account details page in
  GCP
- **OAuth scopes**:
  `https://www.googleapis.com/auth/admin.directory.group.readonly`

### 5. Encode the key and set environment variables

Base64-encode the JSON key (no line wrapping):

```bash
base64 -w 0 key.json
```

Set the following in Cube Cloud:

- `GOOGLE_DIRECTORY_SA_KEY` — the base64-encoded output
- `GOOGLE_DIRECTORY_SA_SUBJECT` — email of the dedicated Workspace admin account
  used as the impersonation subject (see below)

!!! warning "Delete the key file after encoding — never store the raw JSON."

### Key rotation

Rotate the key if it is ever exposed. In GCP, create a new key on the service
account, update `GOOGLE_DIRECTORY_SA_KEY` in Cube Cloud, then delete the old
key.

### 6. Create the impersonation subject account

The Directory API requires the service account to act as a Workspace super-admin
— this is the `GOOGLE_DIRECTORY_SA_SUBJECT` value. It must be a **dedicated
shared admin account**, not a personal one. If the account is suspended,
deleted, or has super-admin revoked, every Cube query will fail with a default
deny (no data visible to any user).

In [Google Workspace Admin](https://admin.google.com):

1. **Directory → Users → Add new user** — create
   `cube-service@apps.teamschools.org` (or similar)
2. **Account → Admin roles → Super Admin → Assign** on that user

Set `GOOGLE_DIRECTORY_SA_SUBJECT` to that account's email in Cube Cloud.

!!! warning "Never use a personal admin account as the impersonation subject."

## Cube Cloud One-Time Setup

Performed in the Cube Cloud UI by an admin:

1. Create a new Cube Cloud deployment
2. Connect the `TEAMSchools/teamster` GitHub repository
3. Set the Cube project path to `src/cube/`
4. Set the production branch to `main` — merges trigger automatic redeploy
5. Set the following environment variables in Cube Cloud:
   - `CUBEJS_DB_TYPE=bigquery`
   - `CUBEJS_DB_BQ_PROJECT_ID=teamster-332318`
   - `CUBEJS_DB_BQ_CREDENTIALS` — service account JSON (base64-encoded)
   - `CUBEJS_API_SECRET` — generate a strong random secret
   - `GOOGLE_DIRECTORY_SA_KEY` — Admin Directory API service account
     (base64-encoded)
   - `GOOGLE_DIRECTORY_SA_SUBJECT` — email of the Workspace super-admin that
     granted the service account domain-wide delegation (e.g.
     `admin@apps.teamschools.org`)
   - `CUBEJS_SQL_SUPER_USER=cube-superset-service` — SQL API super-user for
     Superset user impersonation (follow-up integration)
6. The service account for BigQuery needs `roles/bigquery.dataViewer` and
   `roles/bigquery.jobUser` on the `teamster-332318` project
7. The Admin Directory API service account needs domain-wide delegation scoped
   to `https://www.googleapis.com/auth/admin.directory.group.readonly`

## Local Dev

1. `cp src/cube/.env.example src/cube/.env`
2. Fill in `CUBE_GROUP_MAP` with your email and the groups you want to simulate:
   ```bash
   CUBE_GROUP_MAP={"you@apps.teamschools.org":["cube-network-detail"]}
   ```
3. Run the **Cube: Dev Server** VS Code task (`Ctrl+Shift+P` → Tasks: Run Task)
4. Playground opens at `http://localhost:4000`

ADC is used for BigQuery auth locally — run the **GCloud: Application Default
Login** VS Code task first if you haven't already.

## Warnings

Do **not** set `CUBE_GROUP_MAP` in Cube Cloud — it bypasses the Directory API
entirely and must only be used for local dev. The `cube.js` guard relies on
`NODE_ENV !== "production"` as a second line of defense, but the variable should
never be configured in Cube Cloud in the first place.

`CUBE_TESTING_USERS` is a pre-Directory-API testing allowlist — set it in Cube
Cloud env vars only on testing/staging deployments, never on production. Remove
it from all deployments once Directory API is live and group membership is
resolved from Google Workspace.

Do **not** use the Cube Playground **Models** tab in dev mode. It overwrites
YAML files in `model/cubes/` and `model/views/` with auto-generated content,
discarding hand-authored definitions.
