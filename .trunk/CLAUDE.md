# CLAUDE.md — `.trunk/`

Trunk.io configuration for linting and formatting. Config: `trunk.yaml` (this
directory). Per-linter config: `.trunk/config/`.

## Linter Ignores

Use `# trunk-ignore(<linter>/<rule>)` with a reason comment. Do not use
linter-native disable syntax (`# shellcheck disable=`, `# noqa`, `-- noqa`):

```python
# trunk-ignore(bandit/B603): subprocess args are hardcoded, not user input
subprocess.run(["git", "status"])
```

## Enabled Linters

| Category | Linters                               |
| -------- | ------------------------------------- |
| Python   | ruff, pyright, bandit, isort          |
| SQL      | sqlfluff, sqlfmt                      |
| Shell    | shellcheck, shfmt                     |
| YAML     | yamllint                              |
| Markdown | markdownlint                          |
| CI       | actionlint                            |
| Docker   | hadolint                              |
| Security | gitleaks, git-diff-check, osv-scanner |
| Config   | prettier, taplo                       |
| Images   | oxipng, svgo                          |

## Ignore Rules

- `src/teamster/**` — sqlfluff, sqlfmt ignored (SQL linting is dbt-only)
- `src/teamster/libraries/dlt_sources/**` — pyright additionally ignored
  (third-party library wrappers)
- `src/dbt/**` — all linters except sqlfluff, sqlfmt, and prettier ignored
- `.k8s/**/values.yaml` — all linters ignored (generated Helm values)

## Hooks

- **Pre-commit**: `trunk-fmt-pre-commit` runs `trunk fmt` (auto-formats staged
  files)
- **Pre-push**: `trunk-check-pre-push` runs `trunk check` (blocks on lint
  failures). Never use `--no-verify` — fix reported issues instead.

## Shell Style

`shfmt` enforces tabs (not spaces) in shell scripts.

## Protected Config

`.trunk/config/` is read-only under hooks — present changes as manual
application blocks, not diffs.
