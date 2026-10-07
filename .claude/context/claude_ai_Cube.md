# Cube MCP gotchas

**`cube` MCP path**: The `cube` MCP is served from Cloud Run (`teamster-mcp`
project) and reached as a `claude.ai` Custom Connector (and by data-team
Codespaces via `npx mcp-remote`) — there is no `cube` entry in the repo
`.mcp.json`. OAuth identity is verified by WorkOS AuthKit federating to Google
Workspace; no `CUBE_USER_EMAIL` env var is needed. First use opens a browser tab
for the OAuth flow; subsequent sessions use the refresh token silently.

Stdio dev mode (`scripts/cube-rest-mcp-launch.sh`) is retained for iterating on
`src/cube/mcp/server.py` itself. Dev-mode email resolution: `CUBE_USER_EMAIL`
environment variable → `~/.config/teamster/cube-user-email` cache file →
`ctx.elicit()` prompt. The VS Code extension swallows elicit prompts; in dev
mode, set `CUBE_USER_EMAIL` before launching or write the cache file with the
`# userEmail` system-context value.
