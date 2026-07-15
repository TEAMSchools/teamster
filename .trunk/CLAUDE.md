# CLAUDE.md — `.trunk/`

Trunk.io configuration for linting and formatting. Config: `trunk.yaml` (this
directory). Per-linter config: `.trunk/config/`.

## Linter Ignores

Suppression syntax (`# trunk-ignore(<linter>/<rule>): reason` on the line
immediately before; never linter-native disables): see root CLAUDE.md →
_Linter_.

`trunk-ignore-all` is a comment directive — it cannot suppress findings in JSON
(no comment syntax); drop/relocate the file or add a `lint.ignore` path rule in
`trunk.yaml`. A directive naming a rule that wouldn't have fired trips
`trunk/ignore-does-nothing`.

## Enabled Linters

| Category | Linters                                      |
| -------- | -------------------------------------------- |
| Python   | ruff, pyright, bandit, isort                 |
| SQL      | sqlfluff, sqlfmt                             |
| Shell    | shellcheck, shfmt                            |
| YAML     | yamllint                                     |
| Markdown | markdownlint                                 |
| CI       | actionlint                                   |
| Docker   | hadolint                                     |
| Security | grype, gitleaks, git-diff-check, osv-scanner |
| Config   | prettier, taplo                              |
| Images   | oxipng, svgo                                 |

## Ignore Rules

- `src/teamster/**` — sqlfluff, sqlfmt ignored (SQL linting is dbt-only)
- `src/teamster/libraries/dlt_sources/**` — pyright additionally ignored
  (third-party library wrappers)
- `src/dbt/**` — all linters except sqlfluff, sqlfmt, and prettier ignored
- `.k8s/**/values.yaml` — all linters ignored (generated Helm values)

## Hooks

Pre-commit runs `fmt` only; pre-push runs `check` — details (and the worktree
binary-path gotcha) in root CLAUDE.md → _Trunk linting/formatting_. Never use
`--no-verify` — fix reported issues instead.

## Shell Style

`shfmt` enforces tabs (not spaces) in shell scripts.

## Protected Config

`.trunk/config/` is read-only under hooks — present changes as manual
application blocks, not diffs.
