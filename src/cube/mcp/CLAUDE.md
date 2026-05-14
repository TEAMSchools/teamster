# CLAUDE.md — `src/cube/mcp/`

Custom MCP server wrapping Cube Cloud's REST API. Deployed to Cloud Run
(`teamster-mcp` GCP project) and reached by `claude.ai` Custom Connectors and by
data-team Codespaces via `npx mcp-remote`.

## Files

- `server.py` — FastMCP server (PEP 723 inline deps). Tools: `meta`, `load`,
  `sql`, `set_user_email`.
- `Dockerfile` — Python 3.13-slim, `uv run` entrypoint.

## Transport modes

- `TRANSPORT=stdio` (default) — for dev iteration via
  `scripts/cube-rest-mcp-launch.sh`. Email resolution: `CUBE_USER_EMAIL` env var
  → cache file → `ctx.elicit()` → `set_user_email` tool fallback.
- `TRANSPORT=http` — Cloud Run runtime. Requires `AUTHKIT_DOMAIN` and
  `PUBLIC_URL`. Email resolution: verified `email` claim on the
  `CubeAccessToken` returned by `JWKSTokenVerifier`.

## When to edit

- Tool descriptions or the FastMCP `instructions=` string: edit `server.py`.
  Redeploy is required for changes to reach `claude.ai` users.
- Tool surface changes (add/remove tools): edit `server.py` and add tests in
  `tests/cube/test_mcp_server.py`.
- Container changes (Python version, system deps): edit `Dockerfile`.

## Local testing

Run the test suite:

```bash
uv run pytest tests/cube/ -v
```

Stdio mode (uses `CUBE_USER_EMAIL`):

```bash
bash scripts/cube-rest-mcp-launch.sh
```

HTTP mode local smoke (no real OAuth — just verifies the server boots):

```bash
docker build -t cube-mcp-local:dev -f src/cube/mcp/Dockerfile src/cube/mcp/
docker run --rm -p 8080:8080 \
  -e TRANSPORT=http \
  -e CUBE_REST_URL=... \
  -e CUBE_API_SECRET=... \
  -e AUTHKIT_DOMAIN=... \
  -e PUBLIC_URL=http://localhost:8080 \
  cube-mcp-local:dev
```

## Deploy

GitHub Actions workflow `.github/workflows/deploy-cube-mcp.yaml` builds and
deploys on push to `main` when `src/cube/mcp/**` changes. Target project:
`teamster-mcp`. Secrets: `cube-api-secret` in Secret Manager (referenced by the
Cloud Run service via `--set-secrets`).

## MCP SDK gotchas

- **Verified bearer-token claims** live behind `get_access_token()` from
  `mcp.server.auth.middleware.auth_context`. `ctx.request_context.user` does not
  exist on `Context`.
- **`host` / `port` are FastMCP constructor kwargs**, not `run()` kwargs; stored
  at `mcp.settings.host` / `mcp.settings.port`. `run()` accepts only `transport`
  and `mount_path`.

## WorkOS quirks

- Access tokens omit `email` by default. Add a JWT template at Authentication →
  Sessions → JWT template: `{"email": "{{ user.email }}"}`.
- DCR/CIMD lives at Connect → Configuration → MCP Auth (tenant-wide toggle), not
  per-application. The advertised `registration_endpoint` returns
  `dynamic_client_registration_disabled` until the toggle is on.
- Google OAuth provider is under Authentication → Providers (Authentication →
  Connections is enterprise SSO).

## PII reminder

Tools return Cube query results. `*_detail` views carry row-level student
identifiers (see the FastMCP `instructions=` block in `server.py`). Never emit
detail-view values to PR comments, issues, or scheduled-agent outputs — only to
the local conversation. See project CLAUDE.md PII reference.
