# Cube Setup

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
6. The service account for BigQuery needs `roles/bigquery.dataViewer` and
   `roles/bigquery.jobUser` on the `teamster-332318` project
7. The Admin Directory API service account needs domain-wide delegation scoped
   to `https://www.googleapis.com/auth/admin.directory.group.member.readonly`

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

## Warning

Do **not** use the Cube Playground **Models** tab in dev mode. It overwrites
YAML files in `model/cubes/` and `model/views/` with auto-generated content,
discarding hand-authored definitions.
