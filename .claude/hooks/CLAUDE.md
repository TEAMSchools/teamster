# Hook regression tests and editing gotchas

Loads when working under `.claude/hooks/`. Protocol and block list:
`.claude/CLAUDE.md`.

## Regression tests

```bash
bash tests/hooks/run_all.sh
```

Individual suites are in `tests/hooks/test_*.sh`. Test files contain sensitive
fixture strings (gitleaks ignores are required). The `expect_deny_exit0` helper
in `helpers.sh` guards against the exit-code and stderr regressions described
above.

**Ad-hoc rule probing:** a Bash command that names `.claude/hooks/*.sh` is
blocked (Rule 2), and trigger tokens placed in the command self-block. To test a
rule, `Write` a harness into `.claude/scratch/` (Write `content` is exempt from
scanning) that pipes fixtures into the hook by absolute path, then run
`bash .claude/scratch/<name>.sh` (the command string carries no triggers).

The same trick `cp`s or `diff`s the protected hooks (Bash can't name
`.claude/hooks/*.sh`): put the hook paths inside the scratch script (snapshot a
hook into scratch for patching, or `diff` scratch-vs-committed before hand-off)
and run it by its scratch path.

## Editing the hooks — recurring gotchas

- **The CI `claude-review` bot recurringly reports a phantom unstaged
  "working-tree revert"** of an edited hook (e.g. ` M check-sensitive.sh`, with
  the new patterns "missing"). It's a CI-checkout artifact, not the PR — the
  committed blob is correct. Confirm `git status` is clean and dismiss; do NOT
  `git checkout` to "fix" a clean tree.
- **trunk's shellcheck enables `SC2312` (masked-return) on pipelines**:
  `echo`/`printf` are exempt, but `tr` / `base64` / `gunzip` / `jq` inside a
  `$(...)` are flagged. Prefer bash parameter expansion (`${v,,}`, `${v//x/y}`,
  `${v//$'\n'/ }`) over a `tr` subshell, or put a
  `# trunk-ignore(shellcheck/SC2312)` on the line immediately before the
  substitution. (Raw `shellcheck` won't show it; trunk's config does.)
