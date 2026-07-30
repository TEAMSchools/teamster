# CLAUDE.md — `src/cube/mcp/`

Custom MCP server wrapping Cube Cloud's REST API. Deployed to Cloud Run
(`teamster-mcp` GCP project) and reached by `claude.ai` Custom Connectors and by
data-team Codespaces via `npx mcp-remote`.

## Files

- `server.py` — `MCPServer` (mcp SDK's `mcp.server.mcpserver`, PEP 723 inline
  deps; the class was `FastMCP` under `mcp.server.fastmcp` before SDK 2.0).
  Tools: `meta`, `load`, `sql`.
- `Dockerfile` — Python 3.13-slim; bare `python` entrypoint (uv installs PEP 723
  deps at build time).

## Transport modes

- `TRANSPORT=stdio` (default) — for dev iteration via
  `scripts/cube-rest-mcp-launch.sh`. Email resolution: `CUBE_USER_EMAIL`
  environment variable → cache file at `~/.config/teamster/cube-user-email` →
  `ctx.elicit()` prompt.
- `TRANSPORT=http` — Cloud Run runtime. Requires `AUTHKIT_DOMAIN` and
  `PUBLIC_URL`. Email resolution: verified `email` claim on the
  `CubeAccessToken` returned by `JWKSTokenVerifier`.

## When to edit

- Tool descriptions or the `MCPServer` `instructions=` string: edit `server.py`.
  Redeploy is required for changes to reach `claude.ai` users. **Put
  load-bearing model guidance in the per-tool docstrings, not `instructions=`**
  — the `instructions=` block is dropped by the claude.ai connector and
  truncated in Claude Code, whereas tool descriptions reach the model on every
  surface (#4473). `instructions=` is now a slim orientation only.
- Tool surface changes (add/remove tools): edit `server.py` and add tests in
  `tests/cube/test_mcp_server.py`.
- Validate that an `instructions=`/tool change actually helps the model with the
  `eval/` harness (model-in-the-loop, scored). Its Claude-Agent-SDK runner
  (`run_eval_cc.py`, subscription auth) MUST be hermetic — `tools=[]`,
  `strict_mcp_config=True`, `setting_sources=[]`, custom `system_prompt`.
  Without these the agent leaks into Bash/ToolSearch and the live
  `mcp__claude_ai_Cube__*` connector (`allowed_tools` is permission-only, not an
  availability gate). See `eval/README.md`.
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

- **`--min-instances=0`** when the server is stateless. The `=1` pin only pays
  off when there's in-memory session state to preserve across idle periods.
- **Cloud Run request timeout defaults to 300s** (no `--timeout` set). Claude
  Code's 60s per-tool ceiling is tighter for tool wall-clock; Cloud Run's
  governs the underlying connection.
- **After a deploy that changes tool signatures or descriptions, refresh the
  connector's tool list on the client.** claude.ai Custom Connector sessions
  cache the tool list and keep serving the old schema indefinitely — a new
  parameter or an edited description is invisible to the model until the user
  reconnects / refreshes the connector (settings → the cube connector). The
  server has the change immediately; the client does not (#4473).

## MCP SDK gotchas

- **Verified bearer-token claims** live behind `get_access_token()` from
  `mcp.server.auth.middleware.auth_context`. `ctx.request_context.user` does not
  exist on `Context`.
- **SDK 2.0 (`mcp>=2.0`) renamed `FastMCP` → `MCPServer` and moved it from
  `mcp.server.fastmcp` to `mcp.server.mcpserver`.** `Context` moved with it.
  `mcp.server.auth.*` and `mcp.types` imports are unaffected by the rename.
- **`host` / `port` / `stateless_http` moved from constructor kwargs to `run()`
  kwargs** in SDK 2.0 (the reverse of SDK 1.x, where they were constructor-only
  and read back via `mcp.settings.host`/`.port`). `mcp.settings` no longer
  carries them at all — pass them to
  `mcp.run(transport="streamable-http", host=..., port=..., stateless_http=...)`
  and don't try to introspect them off the server object afterward.
- **Elicit capability check**:
  `ctx.session.check_client_capability(ClientCapabilities(elicitation=ElicitationCapability()))`.
  Don't use the `CapabilityNotSupported` try/except from build-mcp-server's
  `references/elicitation.md` — that's jlowin's `fastmcp`, not the official
  SDK's bundled `MCPServer`.
- **`lifespan=` + `stateless_http=True` is safe again as of SDK 2.0** — verified
  against `mcp/server/streamable_http_manager.py`: lifespan is now entered once
  for the manager's lifetime and that state is reused across every stateless
  request, not re-entered per request. (SDK 1.x re-entered it per request, which
  is why `server.py` used to keep the httpx client as a bare module-level global
  with no `aclose()` — `client.aclose()` in a `lifespan=` teardown would close
  the shared client after the first request and break every subsequent one.)
  `server.py` now creates/tears down the client in `_lifespan()`, passed via the
  `lifespan=` kwarg — still a constructor kwarg (unlike
  host/port/stateless_http, it did not move to `run()`).
- **`PyJWKClient` defaults are uncached** (`cache_keys=False`, `lifespan=300`).
  For hot-path verifiers pass `cache_keys=True, lifespan=3600`.
- **Total tool wall-clock must stay under 60s** (Claude Code default per-tool
  timeout). httpx timeout + polling-loop deadline both fit inside that budget.
- **`stateless_http=True`** on `mcp.run(transport="streamable-http", ...)` for
  any multi-instance Cloud Run deploy. `StreamableHTTPSessionManager` holds
  session state per-instance, so rollovers return 404 "Session not found".
  Stateless mode disables subscriptions, progress, sampling, and
  elicit-over-HTTP — this server uses none.

## Cube REST quirks

- **`/sql` is GET-only**; query goes in URL via
  `params={"query": json.dumps(query)}`. `/load` accepts POST with JSON body.

## WorkOS quirks

- Access tokens omit `email` by default. Add a JWT template at Authentication →
  Sessions → JWT template: `{"email": "{{ user.email }}"}`.
- DCR/CIMD lives at Connect → Configuration → MCP Auth (tenant-wide toggle), not
  per-application. The advertised `registration_endpoint` returns
  `dynamic_client_registration_disabled` until the toggle is on.
- Google OAuth provider is under Authentication → Providers (Authentication →
  Connections is enterprise SSO).
- MCP resource indicators (RFC 8707) live at Connect → Configuration → MCP
  resource indicators. Add each MCP server's public URL there to bind issued
  tokens to that resource.

## PII reminder

Tools return Cube query results. Student views carry row-level student
identifiers alongside aggregate-safe dimensions (see the PII note in the `load`
tool docstring in `server.py`). Never emit identifying values to PR comments,
issues, or scheduled-agent outputs — only to the local conversation. See project
CLAUDE.md PII reference.
