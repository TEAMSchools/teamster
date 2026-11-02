# WorkOS MCP gotchas

- Staging is the live AuthKit environment; production is not activated. Which
  environment to use, the session-token issuer, and the sign-in restriction are
  in [src/cube/mcp/CLAUDE.md](../../src/cube/mcp/CLAUDE.md) _WorkOS quirks_.
  Read it before verifying a token or changing a setting.
- `whoami` lists environment ids. Pass `environment_id` on every `query` and
  `mutate`: without it, an operation that takes no environment runs against a
  default sandbox environment.
- Every `mutate` changes a shared environment that live staff apps sign in
  through, and the auto-mode classifier denies it without consent. Get the
  user's explicit go-ahead for the specific change, restate it in the message
  before the call, and read the result back with a `query`.
- `createAuthkitApplication` takes no redirect URIs. Follow it with
  `setAuthkitApplicationRedirectUris`, which replaces the app's whole list.
- Reads that answer most setup questions: `dashboardSession` (AuthKit domain,
  custom domain, whether production is active), `authkitSettings` (enabled
  sign-in methods), `connectionsByType` with `GoogleOAuth` (the Google client),
  `jwtTemplateContent`, and `authkitApplications`.
- `users` returns staff names and emails. Count domains or sign-in methods from
  it; never copy rows to GitHub, commits, or any Slack channel other than
  `#data_team`.
