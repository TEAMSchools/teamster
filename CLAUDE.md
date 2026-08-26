# CLAUDE.md

## Layout

**Read the relevant subdirectory CLAUDE.md before any work there** (reading,
explaining, reviewing, or modifying). Project-wide conventions live in this
file; domain specifics live in the nearest subdirectory CLAUDE.md.

## CLAUDE.md Editing Rules

- **Before adding to any CLAUDE.md file**: beyond the skill's
  brevity/avoid-list, apply the necessity test — name the specific decision or
  action Claude will make differently because of the line. If you can't name
  one, cut it, even when the line is concise and non-obvious.

- **Where a new line goes**: if it is specific to one MCP server's behavior, put
  it in `.claude/context/<server>.md` (auto-injected on first use of that
  server). If it is specific to one directory, put it in that directory's
  CLAUDE.md. Keep it in this file only when it must be known BEFORE any tool
  runs — safety prohibitions, branch/PR etiquette, and rules whose violation
  produces a silently wrong answer rather than a loud error.

## Working Conventions

### Privacy

- **PII stays local.** Never emit PII values (or screenshots/logs containing
  them) to PR comments, commits, issues, Slack, Asana, scheduled-agent outputs,
  or any other external surface. Local artifacts (`.claude/scratch/`,
  `.worktrees/`, terminal) are fine. Before any external write that touched
  values from local validation, replace PII with redacted labels (`Student A`,
  `a sample student`) or column-name references. Aggregates / deidentified ≠
  PII. See _PII reference_ below for what counts.

### Issues and specs

- **Before writing any spec or plan**: STOP and explicitly ask the user whether
  to open a GitHub issue first. Required for specs/plans; not required for quick
  fixes. Do not write anything until the user answers. If opening: use
  `mcp__github__issue_write`; label with conventional commit type, related
  source systems, and `dagster`/`dbt` when applicable.

- **Opening any GitHub issue** (via `mcp__github__issue_write`, whether for a
  spec/plan or a quick-fix bug/feature report): `issue_write` does NOT apply a
  repo issue template — that's a GitHub web-UI-only convenience (the "New issue"
  picker), invisible to the API. Read the matching template under
  `.github/ISSUE_TEMPLATE/` yourself (`bug_report.md` or `feature_request.md`)
  and structure the body to match it — plain-language sections first, a "For
  Claude" fold-out last — rather than writing free-form. Because no template is
  applied, its front-matter label never lands either: add `enhancement`
  (feature_request) or `bug` (bug_report) alongside the conventional-commit-type
  and source-system labels.

- **Keep the "For Claude" fold-out on every issue Claude opens.** The template's
  "Delete if you're not looping Claude in" applies only when the issue carries
  no technical detail at all. `PLAIN_LANGUAGE.md` names the fold-out as the one
  section exempt from plain-language rules, so its job is structural, not
  audience-based — it is where model paths, column names, row counts,
  constraints, and acceptance criteria go. Reaching for a heading the template
  does not have (a "what blocks what" section, say) is the tell that detail is
  escaping into the body; put it below the fold instead.

### Branches and worktrees

- **Before creating a branch**: ask the user — worktree or branch switch? Do not
  choose for them. When an issue isn't already required (i.e. quick fixes, not
  specs/plans), also ask whether to anchor the branch with one, and honor a
  decline — create the branch without an issue via the paths below.

- **Before writing any file (spec, code, config)**: be on the feature branch.

- **Worktree**: with an issue, `gh issue develop <number> --name <branch>` (no
  `--checkout`), then `git worktree add .worktrees/<branch> <branch>`. If the
  user explicitly declined an issue, skip `gh issue develop` and create the
  branch directly: `git worktree add -b <branch> <abs-path> origin/main` (name
  the base — local `main` is often behind).

- **Stacked branch** (build on an unmerged branch):
  `gh issue develop <num> --name <branch> --base <parent-branch>` links a branch
  off a non-`main` base; then `git worktree add`. Gives a clean diff + enforced
  merge-after-parent — but base ≠ main skips `claude-review` (dbt Cloud CI still
  runs; it is not base-gated — see `.github/CLAUDE.md`).

- **A stacked `git worktree add -b <new> <abs-path> <parent-branch>` sets the
  new branch's upstream to the PARENT** — a bare `git push` then pushes your
  commits onto that branch, which is usually someone else's. Run
  `git -C <worktree> branch --unset-upstream` immediately after creating it,
  then `git -C <worktree> push -u origin <new-branch>`.

- **Linking an existing remote branch to an issue**:
  `mcp__github__create_branch` and GraphQL `createLinkedBranch` both no-op when
  the branch already exists. Delete the remote branch, then
  `gh issue develop <num> --name <branch>`, then re-push local commits.
  `git push origin --delete <branch>` is classifier-blocked as a destructive git
  action even with consent — if the delete is refused, create the branch under a
  NEW name and `gh issue develop --name <new-name>` instead of deleting.

- **Worktree commands**: Path-flag-driven tools must name the worktree
  explicitly. Use `git -C <worktree>` on every git call (bare `git` from the
  main repo silently commits to `main`) and
  `uv run dbt ... --project-dir <worktree>/src/dbt/<project>` on every dbt call
  (do NOT use `uv --directory <worktree> run dbt ...` — that overrides cwd to
  the worktree root where `dbt_project.yml` doesn't exist). For Python execution
  from the main repo, prefix `VIRTUAL_ENV=` and use
  `uv --directory <worktree> run python ...` — bare `uv run --active` reads the
  main repo's `.venv` and misses worktree-only changes. `uv --directory` also
  resolves a relative _script_ path under the worktree, so a main-repo script
  path breaks — pass an absolute script path or run it from the main repo.
  Otherwise prefer absolute paths.

- **Bash cwd persistence is version-dependent — treat it as unknown.** Older
  builds reset every call to the main repo root; current builds carry a `cd`
  forward (the harness notes "Session cwd remains ..."). Rely on neither: prefix
  commands with `pwd &&`, and for worktree work include `cd <worktree> &&` in
  the SAME command (or use absolute paths) — tools that resolve relative paths
  from cwd (`trunk check`, `pytest`, `sed -i`) silently operate on the wrong
  checkout's copies and report a false "clean".

- **Worktree file operations must name the worktree path** —
  `/workspaces/teamster/.worktrees/<branch>/<path>`, never
  `/workspaces/teamster/<path>`. Editing the main path silently leaves the
  worktree unchanged and dirties `main`, and the worktree commit then reports
  "nothing to commit". IDE Pyright diagnostics on worktree files are
  false-positive-prone for the same reason: it resolves imports against the MAIN
  checkout, so worktree-only signature or symbol changes surface phantom
  `unknown import` / `no parameter named X` errors. Trust `uv run` executed
  inside the worktree, not the IDE.

- **Worktree Read/Edit and Bash `cd <worktree>` re-inject that worktree's
  CLAUDE.md files (~40KB each) on every call**; `git -C <worktree>` and
  `uv run dbt --project-dir <abs-worktree>` from the MAIN cwd, and `Write`
  (content-exempt), do NOT. For a large multi-file worktree refactor, delegate
  the edits to subagents — their context absorbs the injection — and verify via
  `git -C <worktree> diff` from the main repo. With no subagents available,
  `Write` a Python script to `.claude/scratch/` and run it by ABSOLUTE path from
  the main repo cwd (neither step re-injects); assert each anchor matches
  exactly once, abort otherwise, and verify the same way.

- **`git worktree add` with a RELATIVE path resolves against the shell cwd**,
  which drifts after a foreground `cd` into another worktree — pass an ABSOLUTE
  path (`git worktree add /workspaces/teamster/.worktrees/<branch> <branch>`) or
  it nests one worktree inside another.

- **Branch switch**: with an issue,
  `gh issue develop <number> --name <branch> --checkout`; if the user explicitly
  declined an issue, `git checkout -b <branch>`.

### Git basics

- **Git naming**: Commit messages and branch names use
  [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/). Branch
  naming: `<gh-username>/<commit-type>/claude-<brief-description>` (get username
  from `mcp__github__get_me`).

- **Git staging**: Prefer `git add -u` — naming protected paths triggers the
  hook, `git add -A` can stage unrelated files. Subagents must name specific
  files in `git add` — never `-u`, `-A`, or `.`.

- **`git merge-tree` reads the committed tip, not the index** — a staged-but-
  uncommitted conflict resolution still reports CONFLICT. Commit first, then
  verify with `git merge-tree --write-tree --name-only origin/main <branch>`.

- **A version-only dependency conflict resolves by taking main's blobs whole**:
  `git checkout origin/main -- <manifest> <lockfile>`, then run the installer
  and confirm it leaves the lockfile unchanged (proof main's pair is coherent).
  Both files end byte-identical to main, so the conflict cannot recur. Do NOT
  hand-merge a lockfile.

- **Git resuming**: Before resuming work on an existing branch, merge `main`:
  `git fetch origin main && git merge origin/main`.

- **A CI failure in a file your branch never touched usually means `main`
  moved** — run `git log <merge-base>..origin/main` before diagnosing. A clean
  prod baseline does NOT rule this out — CI builds `--full-refresh` against
  deferred upstreams, so prod passing and CI failing is the expected shape.
  Check git before the warehouse; it is one command and decisive.

- **A mid-session Codespace restart can delete `.worktrees/` and desync local
  git refs** (stale `main`, `git ls-remote <branch>` empty for a live branch, a
  HEAD that reads as the pre-session commit yet holds merged content). Trust
  GitHub over local git for ground truth: `gh api .../branches/main` and
  `gh api .../pulls/<n>` (`merged` / `merge_commit_sha`), then re-fetch and
  recreate any lost worktree off `origin/main`.

- **Reverting experimental code to a docs-only PR**:
  `git checkout origin/main -- <file>` restores main's CURRENT blob, which can
  differ from the branch's merge-base and leak main's advancement into the
  three-dot PR diff. Restore to the merge-base instead —
  `git checkout $(git merge-base origin/main HEAD) -- <file>` — then verify with
  `git diff --stat origin/main...HEAD`.

### Subagents and workflows

- **Dispatching subagents**: Subagents do not auto-invoke skills. In the
  dispatch prompt, name the exact `Skill` tool calls the subagent must run
  before starting work (e.g. `Skill` with
  skill=`dbt:using-dbt-for-analytics-engineering` for a dbt review). For
  negation goals (remove X, no Y), list anti-patterns explicitly — subagents
  otherwise re-introduce familiar idioms (`dbt_utils.deduplicate`,
  `select distinct`, `qualify row_number()=1`).

- **Subagents cannot Write report/findings files** — the harness refuses with
  "Subagents should return findings as text". Have them return the report as
  their final text; the coordinator persists it to scratchpad.

- **Edit-task dispatches must say "do the edits YOURSELF — do NOT dispatch
  sub-agents."** Without it an agent may re-delegate, stall waiting on its
  children, and self-report progress that `git status` disproves.

- **Subagent model/effort**: when a skill carries its own model-selection
  guidance (e.g. subagent-driven-development), follow the skill; this line only
  binds its tiers to models. Mechanical scoped tasks (1-2 files, precise brief)
  -> `haiku` (no effort parameter -- omit it); integration/debugging
  implementers -> `sonnet` at `high`; review and re-review dispatches ->
  `sonnet` at `xhigh`; design work -> `opus` at `high`; final whole-branch
  review -> `opus` at `xhigh`. When none of these clearly apply, omit both
  overrides. The `Agent` tool accepts only `model` — effort is settable on
  Workflow `agent()`, not `Agent`, so via `Agent` pass the model and drop the
  effort tier.

- **Subagent multi-step bail risk**: subagents can abandon multi-step tasks
  partway through. Scope dispatches to one file / one commit; inspect the file
  diff and `git log` before marking complete — don't trust the self-report.

- **Tell subagents to run builds in the FOREGROUND.** A subagent that
  backgrounds a long `dbt build` strands itself waiting on the notification and
  returns having written nothing. Also never run two dbt subagents concurrently
  against one worktree — they share `target/` and corrupt the partial-parse
  manifest.

- **A subagent's "pre-existing failure" baseline is the working tree AS
  DISPATCHED**, including your own uncommitted edits. "Already failing before I
  touched anything" can mean "failing because of the coordinator's change."
  Check whether your own work caused it before accepting that framing.

- **Subagent worktree dispatches must spell out the absolute worktree path**: a
  subagent starts in the MAIN checkout, so the dispatch prompt must give the
  worktree path and mandate `git -C <worktree>` + `uv run` from it (bare edits
  hit `main` silently), and state that IDE Pyright errors on worktree files
  (`reportMissingImports`, "not accessed", "not iterable") are expected false
  positives — trust `uv run` inside the worktree, not the IDE.

- **The `Workflow`-tool orchestrator is unreliable for long fan-outs in this
  Codespace** — runs stall mid-run, and a window reload can leave a prior run
  orphaned-but-alive, still spawning branches and worktrees. Prefer discrete
  main-loop `Agent` dispatches for multi-batch work (one unit lost on failure,
  resumable); if you must run a Workflow, check for and kill a leftover prior
  run after any reload BEFORE relaunching.

- **Workflow run hygiene**: a dead run = its journal
  (`~/.claude/projects/<proj>/subagents/workflows/wf_<id>/journal.jsonl`) stops
  growing for ~2min with no live `dbt`/agent procs. Its `isolation:'worktree'`
  dirs are `.claude/worktrees/wf_<id>-N` (NOT the repo `.worktrees/`; left
  `locked` when orphaned — `git worktree unlock` then `remove --force`).
  `TaskStop` only sees tasks launched in the CURRENT session — a Workflow from a
  prior (reloaded) session isn't in the registry; clean it at the
  process/worktree level. Concurrency cap = `min(16, cpu_cores-2)` (4-core
  Codespace → 2; raising it needs a larger machine, whose restart kills
  in-flight runs).

### Consent and the auto-classifier

- **Auto-classifier doesn't see verbal approval or `AskUserQuestion` answers** —
  only the assistant message immediately preceding the tool call. After
  out-of-band consent, re-confirm in plain text the same turn or the write will
  be denied. Common surfaces: `git worktree add -b` / `git checkout -b`,
  `git push origin main` (route through a PR or have the user push), bulk Asana
  `create_tasks`. If the user hasn't ruled an issue out, open a minimal one
  (title + 1-2 sentences) and use `gh issue develop`; if the user explicitly
  declined an issue, create the branch directly (`git worktree add -b` /
  `git checkout -b`) and re-confirm that consent in plain text the same turn so
  the classifier (which can't see `AskUserQuestion` answers) allows it.
  `gh issue develop --name <branch>` also fails when the branch contains trigger
  words like `log`, `auth`, `secret` — rename and retry.

- **Destructive SQL / shared-resource mutations need _named_ consent.** The
  auto-classifier ("Cloud Storage Mass Delete", "Shared Cluster Mutation")
  rejects a warehouse `DELETE`/`DROP` or a bulk `launch_multiple_runs` even
  after "yes"/"resume" and an agent plain-text re-confirm — the USER's message
  must name the specific operation + target ("delete rows where X from
  `dataset.table`"). Draft the exact statement and have them restate it, or hand
  it to their terminal. For `launch_multiple_runs` the block fires even at
  `confirm=False` (preview), and the dagster MCP has no `create_backfill` — hand
  a partition-range backfill to the user to launch from the Dagster UI
  (splitting into per-partition `launch_run`s to dodge the bulk classifier
  bypasses intent — don't).

- **Pushing to `main` is forbidden** (user policy, and the classifier
  hard-blocks it regardless of in-conversation consent) — hand any main push to
  the user; do not retry. Editing and committing on LOCAL `main` is allowed when
  the user asks; anything remote goes through a branch + PR.

### Pull requests and CI

- **Pull requests**: Squash merge. Use `.github/pull_request_template.md` as the
  PR body.

- **PR project linkage**: PRs auto-appear on project boards via issue refs
  (`Refs #N`, `Closes #N`) in the body. Do NOT `gh project item-add` a PR.

- **`not_planned` closure with a "Tracked in Asana: <url>" comment = handoff to
  Ops, not rejection.** The `TODO(#NNNN)` pointer is still live. Reopen the GH
  issue and apply the `ops-tracked` label; it stays open until the linked Asana
  task completes.

- **Check dbt Cloud CI state before pushing fixes**: pushing cancels an
  in-progress dbt run and restarts it. Before pushing a CI-fix commit, confirm
  dbt Cloud is in terminal state; if it's still running, wait or ask the user.
  Bundle multiple CI-fix commits into one push.

- **After dbt Cloud CI passes on a PR**: fetch warnings with
  `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before
  declaring done. Local relationships warnings absent from CI are stale-dev
  `--defer` drift; ignore. CI warnings unchanged from main are pre-existing —
  `gh search issues` for a tracker before filing.

- **The `claude-review` bot asserts repo conventions that may not be enforced.**
  Verify each convention claim against existing models before applying — its
  findings are advisory, and `git grep` settles it faster than complying.
  **Always invoke `superpowers:receiving-code-review` BEFORE processing
  `claude-review` findings** — verify each claim (including its file:line
  citations) against the code before relaying or replying, not after. Fixing a
  finding in code is not a reply — post a per-finding verdict as a PR comment
  (declines included, with reasons). A silent fix reads to a human reviewer as
  an unaddressed review.

- **A dispatched code-review subagent's "confirmed non-issue" dismissals aren't
  authoritative** — verify its convention claims (dismissals as much as flags)
  against the guide text + `git grep` before relaying.

- **A PR's CI lives on two disjoint surfaces**: dbt Cloud is a commit _status_
  (`pull_request_read get_status` / `gh api commits/<sha>/status`); Trunk /
  CodeQL / `claude` are _check runs_ (`get_check_runs` /
  `commits/<sha>/check-runs`). Check both before calling a PR green. Trunk's
  check-runs are RE-CREATED on each push, so a `gh pr checks` poll gating on
  "nothing pending" can sample the gap between them and report done prematurely
  — re-check after a delay. A PR with all checks green but
  `mergeable_state: blocked` (from `gh api repos/<owner>/<repo>/pulls/<n>`) is
  awaiting a required review approval (CODEOWNERS `src/dbt/` =
  analytics-engineers), not a CI failure.

- **`claude-review` fires only on PR `opened` / `ready_for_review`**, never on
  `synchronize` — it does NOT re-run when you push fixes, so don't wait or
  monitor for a re-review after a fix push. To get it onto code pushed after its
  pass, toggle draft state via GraphQL `convertPullRequestToDraft` then
  `markPullRequestReadyForReview`; REST
  `gh api -X PATCH .../pulls/<n> -f draft=true` silently no-ops (returns
  `draft: false`, no error).

- **Read `claude-review` findings by enumerating ALL issue comments**, newest
  and longest first. It posts as **`github-actions[bot]`**, not a `claude`-named
  user, so filtering by a "claude" login returns nothing. It may leave TWO
  comments (a "Reviewing…" stub plus a findings comment) or instead EDIT the
  stub in place minutes AFTER the check-run reports `success`, and a re-fired
  run creates a NEW comment even with `use_sticky_comment: true`. So gate a
  findings-poll on the body no longer matching "in progress" — never on a cached
  comment id, a length threshold, or the check-run conclusion.

- **A merged PR's CI status is not evidence the change was validated** — a PR
  merged mid-CI leaves a permanent `dbt Cloud: failure` that is a cancellation,
  not a build failure (mechanics in `.claude/context/dbt.md`).

- **`dagster-cloud-deploy / deploy` emits one same-named check-run per code
  location** (~5) — `get_check_runs` returns duplicates; wait for ALL to reach a
  terminal conclusion before calling the deploy green. A shared-library change
  (e.g. `libraries/dlt/`) redeploys every consuming location, not just the ones
  whose config you edited.

### Python

- **Python**: Always `uv run` — never bare `python`, `python3`, or
  venv-installed tools (`dbt`, `dagster`, etc.).

- **Transient Python deps**: Use `uv run --with <pkg> python script.py` for
  one-off scripts needing a package not in `pyproject.toml` — don't
  `uv add --dev` for throwaway tooling.

### Harness behavior

- **IDE selection arrives only via `<ide_selection>` tags**, not
  `<ide_opened_file>` (which only names the open path). When the user references
  "this" without an `<ide_selection>`, ask for the snippet — don't guess.

- **Arm the Monitor in the same turn you say you'll watch something.** A monitor
  that has exited is indistinguishable from one still waiting — both are silent.
  Stating an intention is not a mechanism.

- **Never assert remaining context as fact** — there is no token counter, the
  harness compacts automatically, and a felt sense of a long session is not
  evidence. Truncating analysis or handing off work on that basis costs more
  than finishing it.

- **Before claiming a harness artifact (rewritten output, phantom rendering,
  truncated literal), verify with a DERIVED value** — line length, `grep -c`, a
  checksum. A misread is far likelier than a rewriting pipeline, and a plausible
  substitute string survives eyeballing where a length does not.

- **Built-in tools over Bash**: Use dedicated tools for file I/O (Read, Grep,
  Glob, Edit, Write). Bash is only for commands with no dedicated tool (`git`,
  `uv run`, `gh`, `docker`, `trunk`, `ls`). On the VSCode-extension (native)
  build of Claude Code ≥2.1.117, Grep/Glob are folded into Bash and absent as
  standalone tools (`Grep` → "No such tool available") — search with `rg`/`grep`
  via Bash instead.

- **Don't pipe `Bash(run_in_background=true)` output through
  `head`/`tail`/`grep`**. The pipe truncates what reaches the output file —
  defeats the purpose. Pipe the raw stream; filter with Read/Bash after.

- **Verify tool-call results for resource creation/update**: syntax errors in
  structured tool-call parameters (malformed closing tags, misnested blocks) can
  silently produce corrupted values — the call succeeds without error, just with
  the wrong payload. After any call that creates or updates a resource with
  string fields (issue title, PR body, commit message, etc.), check the returned
  values match intent before moving on.

- **Smoke-test the runtime path, not just imports**: `hasattr(cls, "method")`
  and `python -c "import X"` pass even when a third-party SDK sub-resource (e.g.
  `googleapiclient` `.files()`, OpenAI sub-client) lacks the attribute at call
  time. Before claiming a fix is verified, call the method — minimally against a
  mock or `try` block — not just `hasattr`.

### Trunk and linting

- **Trunk linting/formatting**: Do not run `trunk fmt` or `trunk check` manually
  — `trunk-fmt-pre-commit` formats at commit time and `trunk-check-pre-push`
  blocks bad pushes, both in the main repo and in worktrees (`core.hooksPath` is
  shared). **Pre-commit hook runs `fmt` only**; sqlfluff/yamllint and other
  check-only linters fire at `pre-push` and in CI. If a session reports "trunk
  clean" on a SQL/YAML change based on commit hooks alone, run
  `.trunk/tools/trunk check --force <files>` to verify before claiming the
  change is lint-clean. A clean pre-PUSH `trunk-check-pre-push` is not
  sufficient either — it is git-diff-scoped (no `--force`) and can MISS a
  sqlfluff violation (e.g. ST06) on already-committed lines that CI's full check
  flags, so a push succeeds and CI still fails on lint; `trunk check --force`
  the changed SQL before pushing. Run from inside the worktree —
  `trunk check --force <abs-worktree-paths>` from the main repo silently returns
  "no applicable linters". The `trunk` binary lives only in the main repo
  (`.trunk/tools/` is gitignored, absent in worktrees) — invoke the absolute
  path `/workspaces/teamster/.trunk/tools/trunk` with cwd set to the worktree;
  relative paths run from the main repo check the main-repo copies, not your
  worktree edits. A `--force` check over
  `git diff --name-only origin/main...HEAD` hard-errors with
  `'<path>' does not exist` when the PR deletes files — filter to existing paths
  first.

- **A merge commit skips the pre-commit trunk hook** ("Merge detected. Skipping
  trunk"), so lint introduced while resolving conflicts goes straight to a red
  CI check. `trunk check --force` the conflicted files before committing a
  merge.

- **`.trunk/tools/` is gitignored and lazily populated** — the `trunk` symlink
  there does not exist until trunk has run once, so on a cold Codespace the
  documented path above fails with "No such file or directory". Fall back to
  `~/.cache/trunk/launcher/trunk`, which is always present; the first run
  creates the `.trunk/tools/trunk` symlink.

- **A `--force` check over ~10 files takes >2 minutes — background it.** Its
  progress spinner emits no result lines, so grepping interim output returns
  nothing and reads as a false "clean". Only interpret the output after the run
  exits.

- **Two concurrent trunk runs produce spurious `✖ N failures`.** A `FAILURES`
  block names a TOOL plus a `.trunk/out/*.yaml` and no rule — that is the linter
  crashing (e.g. `grype`), not a finding. Distinct from `✖ N unformatted files`
  (the pre-commit `fmt` hook fixes those) and from real lint issues, which name
  `file:line` + rule. Re-run single-instance before chasing one.

- **Linter**: Suppress with `trunk-ignore(linter/rule): reason` (e.g.
  `# trunk-ignore(bandit/B603): static argv, no shell`) on the line immediately
  before the flagged line — not linter-native disable syntax. Wrapping the
  reason onto extra comment lines silently breaks the suppression (trunk only
  honors the directive on the adjacent line), and CI also flags it with
  `trunk/ignore-does-nothing`. Binary:
  `/workspaces/teamster/.trunk/tools/trunk`.

### Markdown

- **Markdown**: Always specify a language on fenced code blocks (MD040). Use
  `text` only when no real language applies.

- **Markdown headings**: increment by one level (markdownlint MD001). `#` title
  goes directly to `##` — never jump to `###`.

- **Backtick identifiers in markdown prose**: trunk-fmt reads unbackticked
  `snake_case` / `glob_*` tokens as emphasis and mangles them (`attendance_day`
  → `attendance*day`). Wrap model/table/column names in backticks in docs,
  specs, and plans.

- **Nested triple-backticks in markdown**: when a fenced block contains a
  heredoc with its own ``` examples, promote the outer fence to 4-backticks so
  trunk-fmt doesn't mangle the structure.

- **Markdown ordered lists broken by code fences (MD029)**: a numbered list
  whose items are separated by fenced code blocks fails markdownlint MD029 —
  `trunk fmt` renumbers items sequentially (1, 2, 3), but each fence restarts
  the list so an item numbered >1 is invalid. Use `1.` for every item. Fires at
  CI only.

- **Widening a markdown table cell trips markdownlint MD060** (table column
  style) until `trunk fmt` re-pads the table. Commit and let the fmt hook fix it
  — don't hand-align.

- **Refactor regex sweeps include `*.md`**: a model/column rename's
  `grep -rl --include='*.sql' --include='*.yml'` misses CLAUDE.md
  hash-derivation examples, plan/spec docs, and inline doc cross-refs. Use
  `--include='*.{sql,yml,md}'` (or drop `--include` entirely) for any rename
  that changes a model or column name.

### Tooling and docs

- **Claude CLI**: Not on `$PATH` — user must run `claude` commands in their
  terminal, not via Bash tool.

- **Verify third-party tool behavior from source**: Before describing how an MCP
  server, dbt CLI flag, or `gh` subcommand behaves, open the source or run
  `--help` — do not extrapolate from general knowledge.

- **gcloud quota project**: Fresh `gcloud` writes (`projects create`,
  service-enable, etc.) hit 429 on Google's shared default project
  (`32555940559`) when no quota project is set. Pass
  `--billing-project=teamster-332318` per-command, or
  `gcloud config set billing/quota_project teamster-332318` once.
  `gcloud auth application-default set-quota-project` fails when ADC is a
  service-account credential — use the gcloud config form instead.

- **Cloud Build prereqs**: `gcloud builds submit` requires
  `cloudbuild.googleapis.com` enabled, and the Cloud Build SA
  (`<PROJECT_NUMBER>@cloudbuild.gserviceaccount.com`) needs
  `roles/artifactregistry.writer` on the target project to push the built image.

- **Docs**: "docs" means the `docs/` folder (MkDocs site), not CLAUDE.md files.
  "The docs", "the ref doc", or "the reference" means the **published** page in
  the `mkdocs.yml` nav (e.g. `docs/models/<dashboard>-data-model.md`) — NOT the
  design specs and implementation plans under `docs/superpowers/`, which are
  working documents excluded from the nav. When asked whether docs are stale,
  audit the published page against the shipped code first; a spec/plan
  describing a superseded design is expected, a wrong published page is a bug.

### PII reference

`config.meta.contains_pii: true` in model YAML is authoritative but
**incomplete**. Untagged columns are PII under FERPA's direct-identifier list
([34 CFR §99.3](https://www.ecfr.gov/current/title-34/part-99/section-99.3)):
name, SSN, student/employee ID, address, date/place of birth, mother's maiden
name, biometric record, plus "other information... linked or linkable to a
specific student." Schema mapping: IDs (`student_number`, `employee_number`,
`ssn`, `state_id`, `local_id`, kippadb `school_specific_id`), names (`*_name`),
contact (`email`, `phone`, `address`, `street`, `city`, `zip`),
`dob`/`birth_date`, guardian/parent fields, free-text `comment`/`note` on people
tables, credentials/tokens.

Indirect identifiers (combinations covered by FERPA's "linked or linkable"
standard): gender, birth date, geographic indicators (school, zip),
race/ethnicity, religion, place of birth, education info (grade level, EL
status, IEP/504/disability), financial info (FRL status), activities. Each field
alone may be safe; combinations may not. When unsure, consult the
[PTAC glossary](https://studentprivacy.ed.gov/glossary) or treat as PII.

PII-tagging precedent in staging (powerschool) is **narrower** than this list —
it omits gender, race/ethnicity, and internal/student ids. For a PII-heavy new
model, confirm scope (direct-only vs direct+indirect) with the user before
tagging.

## Superpowers skill overrides

- **Branch creation always goes through the issue-and-branch flow in _Working
  Conventions_** — no exceptions for `superpowers:brainstorming`'s "Write design
  doc" step, `superpowers:writing-plans`' "Save plans to:" step, or
  `superpowers:using-git-worktrees`' worktree-consent prompt. Pause those
  skills, run the flow, then write specs to `docs/superpowers/specs/...` or
  plans to `docs/superpowers/plans/...` on the new branch. Default to
  `gh issue develop` so the branch is linked to an issue; only create a branch
  standalone (`git worktree add -b` / `git checkout -b`) when the user
  explicitly declines an issue — re-confirm that consent in plain text the same
  turn.

- **`trunk check` the spec/plan `.md` you write before pushing** — markdownlint
  (MD040 fenced-block language, MD036, MD029 ordered lists) fires only at
  pre-push/CI, not the pre-commit `fmt` hook; checking only the code files
  misses a doc-only Trunk failure. Use `--force --no-fix </dev/null`: `--force`
  is REQUIRED (without it a committed file is git-diff-check-skipped and
  markdownlint under-reports — a false "No issues"), and `--no-fix </dev/null`
  avoids the interactive "Apply formatting?" hang.

- **`finishing-a-development-branch` / `using-git-worktrees` tests & setup**:
  this repo uses `uv`, not `poetry`/`pip`, and
  `uv run dbt build --select <model>+` should run alongside the skills' other
  tests.

- **Before brainstorming a fix for a GitHub issue**: verify the issue's claims
  (row counts, bucket sizes, reproduce queries, named files/columns) against
  current code and data. Issue bodies drift — code moves, data changes, prior
  PRs land. Re-run the diagnostic before designing.

- **Continuous execution exceptions**: `superpowers:subagent-driven-development`
  and `superpowers:executing-plans` push you to execute every task without
  pausing to check in. Pause anyway to ask the user before (a) opening a
  tracking issue, (b) creating a branch or worktree, (c) modifying protected
  files (hook scripts, `.devcontainer/scripts/`, `.claude/settings*.json`).

- **At the investigation→build pivot, ask about `superpowers:brainstorming`** —
  a design settled in conversation doesn't waive it on its own. Ask the user
  whether to run it; skip only when they say so.

## Compact Instructions

When summarizing the conversation, always preserve:

- The original task/request verbatim, plus constraints and scope decisions the
  user stated ("don't touch X", "we decided against Y" — and why).
- Worktree state: the absolute worktree path, branch name, and which checkout
  (main vs worktree) each pending change lives in; what is committed vs
  uncommitted; open PR/issue numbers.
- Verification state: which tests/builds/lints ran and their results; what is
  verified working vs not yet checked.
- Unresolved items: open questions awaiting the user, known failures not yet
  fixed, and the agreed next step.
- Exact identifiers over descriptions: file paths, model/column names, run IDs,
  verbatim error messages.
- Dead ends already tried, gotchas discovered, and workarounds applied this
  session.

Discard freely: full file contents already on disk, verbose tool output, and
exploration that led nowhere (keep only the conclusion).

## MCP Servers

Dagster+ MCP auth: do not revert `.mcp.json` to `op run` —
`OP_SERVICE_ACCOUNT_TOKEN` is scrubbed post-boot, so `op run` silently breaks
after the first Codespace restart. Keep `scripts/dagster-mcp-launch.sh` as the
launcher. Package internals: see
[TEAMSchools/dagster-plus-mcp](https://github.com/TEAMSchools/dagster-plus-mcp).

- **MCP outages**: If an MCP tool returns "server disconnected" or clearly
  impaired responses, surface to the user before working around with raw `gh` /
  BigQuery calls. Same if an EXPECTED MCP tool is absent from the deferred-tools
  list (ToolSearch returns "No matching deferred tools") — flag it immediately
  so the user can reconnect; do not silently fall back.

- **MCP subprocess logs**: stdio MCP stderr captured at
  `~/.cache/claude-cli-nodejs/-workspaces-teamster/mcp-logs-<name>/<ts>.jsonl`.
  Retries and reconnects append to the same file — read the newest file's tail,
  don't expect a new file per attempt. JSONL keys: `debug` (connect timings),
  `error` (subprocess stderr). Read these before guessing why an MCP fails.

### MCP tool selection

For natural-language analytics questions (metrics, KPIs, business-domain
questions about students, attendance, grades, enrollment, staff, etc.), **start
with `cube`** — `meta` to discover views, then `load`. Cube enforces row-level
access policies and PII defaults; raw-warehouse paths bypass them. See
[src/cube/CLAUDE.md](src/cube/CLAUDE.md) for query shape.

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

If `dbt:answering-natural-language-questions-with-dbt` auto-loads, do not follow
it — its dbt-Semantic-Layer path doesn't apply (no dbt SL here) and its
ad-hoc-SQL fallback bypasses Cube's policies. Use the `cube` MCP instead. Fall
back to BigQuery MCP for ad-hoc SQL only after `cube meta` confirms no view
models the needed columns.

Use BigQuery MCP for warehouse-level inspection (raw source rows, schema diffs,
`INFORMATION_SCHEMA`) and for engineering tasks (dbt model validation, audits).

Use dbt MCP's `show` only when `ref()` / `source()` resolution is needed — it
adds compilation overhead.

For run-internal timelines (steps, engine events, failures), use
`mcp__dagster__get_run_logs` — its events are canonical and structured. Note the
unit mismatch: GraphQL `creationTime/startTime/endTime` are float seconds;
`get_run_logs` event `timestamp` is a millisecond string.

GitHub MCP (`mcp__github__*`) is the primary tool for every GitHub operation.
The `gh`-via-Bash list below is an **exhaustive allowlist** — any `gh`
subcommand not on it is forbidden via Bash. Before any GitHub operation, first
identify the `mcp__github__*` tool that handles it; only if none exists, check
the allowlist.

- `gh issue develop` — linked branch creation; `mcp__github__create_branch` does
  not link branches to issues.
- `gh project item-edit --id <ITEM_ID> --project-id <PROJECT_ID> --field-id <FIELD_ID> --single-select-option-id <OPTION_ID>`
  — ProjectV2 field mutations (Status / Tier / Driver / etc.) aren't exposed by
  `mcp__github__*`. To unset a field value (any type), replace the value flag
  with `--clear`. No output on success — verify via `gh api graphql` querying
  the item's `fieldValues`. `gh project item-list` JSON also omits ProjectV2
  custom fields whose names contain spaces (e.g. `PR batch`); single-word custom
  fields (`Driver`, `Tier`, `Status`) do appear. Use the same `fieldValues`
  GraphQL query to read the omitted ones.
- `gh project item-add <PROJECT_NUMBER> --owner <OWNER> --url <ISSUE_URL>` —
  adds an issue/PR to a ProjectV2 board. No `mcp__github__*` equivalent. Combine
  with `gh project item-edit` to set fields after add.
- `gh api graphql` ProjectV2 `items(first: N)` is capped at 100. Paginate with
  `pageInfo.endCursor` for boards with >100 items.
- `gh pr checks <n> --json name,bucket,state` — combined commit statuses + check
  runs for CI poll loops (Monitor); no single `mcp__github__*` tool covers both
  surfaces.
- `gh run *` — Actions run inspection/control; no MCP coverage.
- `gh workflow *` — Actions workflow inspection/dispatch; no MCP coverage.
- `gh repo edit` — repo settings; `gh repo create/view/list` have MCP
  equivalents and are not on this list.
- Editing an existing comment — `mcp__github__add_issue_comment` only creates.
  Use `gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -f body='...'`.
  For large bodies (tables, multi-paragraph), write the body to a file and pass
  `-F body=@<file>` instead of inline `-f body='...'` (avoids shell-quoting on
  big markdown). Same `-F body=@<file>` trick applies to `create_pull_request` /
  comment creation via `gh api`.
- Editing a PR **body** — never round-trip a fetched body through
  `mcp__github__update_pull_request`; it double-encodes existing entities (see
  `.claude/context/github.md`). Edit cleanly via
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>` (raw, no
  re-encoding).
- Replying to a PR inline review comment in-thread —
  `mcp__github__add_issue_comment` posts top-level PR comments only, not thread
  replies. Use
  `gh api -X POST repos/<owner>/<repo>/pulls/<pr>/comments/<id>/replies -f body='...'`.
- `gh api repos/<owner>/<repo>/contents/<path>?ref=<sha> -H 'Accept: application/vnd.github.raw'`
  — read a third-party file at a pinned SHA (for the verify-behavior-from-source
  rule above). The `--jq .content | base64 -d` form is hook-blocked as an
  encoding bypass.
- `gh api -X POST repos/<owner>/<repo>/labels -f name=... -f color=... -f description=...`
  — no `mcp__github__*` label-create tool.
- `gh api -X POST repos/<owner>/<repo>/issues/<n>/labels -f 'labels[]=<name>'` —
  additive label add. `mcp__github__issue_write` with `labels` REPLACES the full
  set; passing one label drops the rest.
- GitHub Search API caps at 5 OR/AND/NOT operators per query (422 otherwise).
  Loop per-term via `gh api -X GET search/issues -f q='...'` for larger searches
  — without `-X GET`, `-f` turns the request into a POST and 404s.
  `search/issues` also requires `is:issue` or `is:pull-request` in `q` — 422
  "Query must include..." otherwise.
- `gh api` reporting `unexpected end of JSON input` means an empty response
  body, not a bad request — re-run with `-i` to see the HTTP status. A 500 on
  `POST /pulls` is usually a GitHub incident; check
  `githubstatus.com/api/v2/incidents/unresolved.json` before bisecting.

**Per-MCP gotchas load automatically.** The `tool-gotchas` PreToolUse hook
injects `.claude/context/<server>.md` the first time each MCP server is used in
a session (and again after a compaction), so this file no longer carries them.
The file name must match the server segment of the tool name
(`mcp__<server>__<tool>`). To add or change guidance for a server, edit that
file — no hook or settings change is needed.

**Warehouse writes stay with the user**: the BigQuery MCP is SELECT-only, and
the `bq` CLI runs on user credentials that expire mid-session, so warehouse
DML/DDL must be handed to the user's terminal — never worked around.
