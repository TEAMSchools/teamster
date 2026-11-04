---
name: gh-token-scopes
description:
  'Use when a git push or PR to a different org repo, `gh run rerun`, `gh
  workflow run`, or a ProjectV2 mutation fails with "Resource not accessible by
  integration" or an auth error from the Codespace: which GitHub token each
  command uses, the scopes it lacks, and the fallback that works.'
---

# GitHub token scopes in the Codespace

The Codespace `GITHUB_TOKEN` (`ghu_*`) only has access to the repo it was
provisioned for. Pushing to other org repos requires bypassing it:
`GITHUB_TOKEN= git -c credential.helper='!gh auth git-credential' push`

Opening the PR on that repo still fails: `mcp__github__create_pull_request`
returns 403 "Resource not accessible by integration", and `gh pr create` is in
`permissions.deny`. Hand the user the compare URL
(`https://github.com/<owner>/<repo>/compare/main...<branch>?expand=1`) and the
PR body as a file in the session scratchpad.

The Codespace token also lacks `project` and org-admin scopes. `gh` calls that
mutate ProjectV2 items/fields fail with "Resource not accessible by integration"
— prefix with `GITHUB_TOKEN=` to fall back to the user's OAuth token (`gho_*`)
which has full scopes.

`gh run rerun` needs that same `GITHUB_TOKEN=` prefix, and with it, it works —
so rerun a transiently failed CI job yourself instead of handing it over. Plain
`gh run rerun <id> --failed` fails with "Resource not accessible by integration"
because the `ghu_*` token lacks `workflow` scope; prefixing `GITHUB_TOKEN=`
reruns it. Success prints NOTHING, so confirm it took by re-reading the run
status rather than by the empty output. Only the `--failed` form has been
tested.

`gh workflow run` (`workflow_dispatch`) can't be done from the Codespace: the
`ghu_*` token lacks the `workflow` scope (403 "Resource not accessible by
integration"), and emptying it via `GITHUB_TOKEN=` leaves `gh` API calls
unauthenticated. No `mcp__github__*` tool dispatches workflows either — hand it
to the user or the Actions UI. (Pushing a commit that edits a
`deploy-prod-<loc>.yaml` also triggers that location's deploy, since the file is
in its own push-paths.)
