# Academic-year eval

Measures whether the academic-year crosswalk in the `load` tool description
keeps the **wrong-year rate** near zero on Sonnet/Haiku, on top of the
`academic_year_label` dimension.

The unit tests in `tests/cube/test_mcp_server.py` cover the dimensions and view
wiring in isolation. This eval covers the part they can't: **model-in-the-loop
behavior** — does the model land on the right academic year end-to-end.

## History: the dropped resolver

An earlier version of this harness compared a third arm (`C_tool`) that added a
deterministic `resolve_academic_year` MCP tool the model was instructed to call
before any year-based query. Across 720 conversations (2 models × 24 prompts × 5
reps × 3 arms) the tool **never beat arm B**, and on the Family-2 trap it
produced the off-by-one it existed to prevent — fed the bare end-year integer
`2026`, it returned `SY27 (2026-2027)`, and only the model overriding the tool
avoided a wrong answer. The tool was dropped (issue #4084 proposal #4, PR
#4125). The crosswalk lived inline in `instructions=` until #4473 moved it into
the `load` tool description — a channel that reaches the model on every surface,
where `instructions=` is dropped by the claude.ai connector and truncated in
Claude Code. This harness is retained as the A-vs-B regression guard for that
crosswalk.

## What it compares

Two arms, holding the `meta` catalog (and its dimension descriptions) and the
slim `instructions` string constant; only the academic-year crosswalk paragraph
in the `load` tool description changes. The tool descriptions are read from the
real [`server.py`](../server.py), so the eval measures the shipped surface.

| Arm              | `load` description                          | isolates                   |
| ---------------- | ------------------------------------------- | -------------------------- |
| `A_baseline`     | shipped, minus the crosswalk paragraph      | floor — descriptions alone |
| `B_descriptions` | the shipped branch as-is (inline crosswalk) | does the crosswalk help?   |

`A` vs `B` shows whether the crosswalk paragraph buys correctness over the
dimension descriptions alone.

Every Cube tool is stubbed (`harness.py`): `meta` returns a fixed catalog,
`load`/`sql` record the query the model built and return a dummy result. No
warehouse, no auth, no PII.

### Family 4 — assessment traps (#5236)

Does the drained Cube text change how the model queries the assessment view? Run
with `--prompts prompts_assessment.yaml`. Each prompt names one trap from
`traps.py`; a trap fires when the captured `load` query on
`student_assessment_scores_view` shows the mistake. The one exception,
`paterson_zero_as_failure`, checks the answer text for a coverage statement.

| Arm        | Catalog and docstrings                                                   | Isolates                          |
| ---------- | ------------------------------------------------------------------------ | --------------------------------- |
| `A4_pre`   | `fixtures/meta_pre_drain.json` (origin/main), docstrings minus the drain | the floor                         |
| `B4_post`  | the working tree, compiled by `src/cube/compile-meta.js`                 | the drain                         |
| `C4_skill` | `B4_post` plus the orchestrator's policy and recipe sections             | what an org-level skill would add |

The `load` stub returns 0 rows for a Paterson query, with the server's
empty-result note on `B4_post` and `C4_skill` only. Every record also carries
tokens (input, cache read, cache write, output), `cost_usd`, `num_turns` and
`duration_ms`, and the run prints a median cost table per arm.

Pass rule, from the knowledge-drain spec: `B4_post`'s pooled trap rate is below
`A4_pre`'s, with at most 2 revision rounds. `C4_skill` and a Sonnet run report
but do not gate.

## Prompts (`prompts.yaml`)

- **Family 1** (16): determinate intent, 4 phrasings (`SY26`, `2025-2026`,
  `2025-26`, `AY2025`) × 4 question stems. Correct AY = 2025-26.
- **Family 2** (4): the observed bug — an SY-thinker supplies the bare end-year
  integer `2026` with context establishing `SY26` intent. Correct AY = 2025-26;
  the trap is filtering numeric `2026` (→ 2026-27).
- **Family 3** (4): genuinely ambiguous bare integer, no correct year — scored
  on whether the model surfaces its interpretation, not on the value.

## Metrics (`scorer.py`)

Determinate prompts: `wrong_rate`, `silent_wrong_rate` (wrong **and** no
interpretation echoed), `correct_rate`, `no_query_rate`. Ambiguous prompts:
`disambig_rate`. Family 4: `trap_rate`.

Every rate is reported with a 95% Wilson interval clustered on prompt id. Reps
of one prompt are correlated, so the independent unit is the prompt, not the
rep, and adding reps does not narrow the interval the way adding prompts does.
The interval uses the Korn-Graubard effective sample size and a Student-t
critical value with `prompts - 1` degrees of freedom, ported from Inspect AI's
`ci_wilson(cluster=...)`. The summary table prints `n/k` (records / prompts)
beside each family.

With 7 trap prompts the intervals are rough, and they are wide: expect 40 to 70
points across at mid-range rates. At a rate of exactly 0% or 100% the method
cannot estimate the correlation between reps, so the interval reflects only the
small prompt count and is likely too narrow. The pass rule compares point rates,
so the intervals inform the reading of a result but do not gate it.

## Two runners

Both sweep the same arms/prompts and share `scorer.py`; they differ only in how
they drive the model.

| Runner           | Auth                                                 | Model environment                                                                                                                            |
| ---------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_eval.py`    | `ANTHROPIC_API_KEY` (metered)                        | bare Messages API — model + cube instructions + only the cube tools                                                                          |
| `run_eval_cc.py` | Claude Code subscription (logged-in `claude` binary) | Claude Agent SDK, run **hermetic** — cube instructions as the full system prompt, `tools=[]`, `strict_mcp_config=True`, `setting_sources=[]` |

The two runners are methodologically equivalent (same clean "model + cube
instructions + only cube tools" surface); they differ only in auth. The
academic-year crosswalk under test rides in the `load` tool description (not the
slim `instructions` system prompt), so both runners vary it per arm via the tool
schema — the CC runner builds one in-process SDK server per arm for this. The CC
runner **must** be hermetic: an earlier append-to-`claude_code`-preset version
leaked into Bash, `ToolSearch`, sub-agents, and the **live claude.ai Cube
connector** (it queried production Cube and returned pre-rename member names),
because `allowed_tools` is permission pre-approval, not an availability gate.
Neither runner reproduces the claude.ai connector's own host prompt — that would
need the deployed connector + a real claude.ai session.

Deps are not in `pyproject.toml` — bring them in per
[CLAUDE.md transient-deps guidance](../../../../CLAUDE.md).

```bash
# --- API runner (needs ANTHROPIC_API_KEY) ---
uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --dry-run
uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --smoke
uv run --with anthropic --with pyyaml python src/cube/mcp/eval/run_eval.py --reps 5

# --- Claude Code runner (uses your subscription; run in your own terminal,
#     where the `claude` binary is on PATH and logged in) ---
unset ANTHROPIC_API_KEY   # so a metered key doesn't shadow the subscription
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py --dry-run
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py --smoke
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py --reps 5
```

Flags (both): `--models`, `--arms`, `--reps`, `--concurrency`, `--limit`,
`--out`. The API runner takes full model ids (`claude-sonnet-4-6`,
`claude-haiku-4-5`, add `claude-opus-4-8` for a ceiling); the CC runner takes
Claude Code aliases (`sonnet`, `haiku`). Results stream to `out/` (gitignored)
and a summary table prints to stdout. From 2026-06-15, subscription Agent-SDK
usage draws from a separate monthly Agent-SDK credit pool.

## Decision rules (pre-register before running)

1. **`B` near-zero wrong-rate on both models** → the shipped crosswalk holds; no
   regression.
2. **`B` wrong-rate climbs above `A` on any family** → a crosswalk edit made
   things worse → revert it.
3. **`A` already near-zero wrong-rate on Family 1** → filtering the label is
   unambiguous by construction → the label dimension carries the floor; the
   crosswalk is the Family-2 (SY-notation trap) safety margin.

> Earlier runs also pre-registered a rule keyed on the dropped resolver's
> call-rate and its `C`-vs-`B` win; see _History: the dropped resolver_ above.

## Fidelity caveats

- Drives the in-process tool descriptions + instructions from `server.py`, not
  the live Cloud Run connector. They share `server.py`, so behavior should
  match, but the MCP transport itself is not exercised.
- The human Superset path (no model in the loop) is out of scope by construction
  — that is a data-model question, not an MCP one.
