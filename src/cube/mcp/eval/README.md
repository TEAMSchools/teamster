# Academic-year resolver eval

Measures whether the `resolve_academic_year` MCP tool actually lowers the
**wrong-year rate** for the claude.ai connector path on Sonnet/Haiku — i.e.
whether the tool earns its round-trip over plain instructions plus the
`academic_year_label` dimension.

The unit tests in `tests/cube/test_mcp_server.py` already prove the parser is
correct in isolation. This eval covers the part they can't: **model-in-the-loop
behavior** — does the model land on the right academic year end-to-end, and does
it bother to call the resolver when told to.

## What it compares

Three arms, holding the `meta` catalog (and its dimension descriptions)
constant; only the FastMCP `instructions` string and the presence of the
resolver tool change. Tool schemas and instructions are read from the real
[`server.py`](../server.py), so the eval measures the shipped surface.

| Arm              | instructions                                                        | resolver tool | isolates                    |
| ---------------- | ------------------------------------------------------------------- | ------------- | --------------------------- |
| `A_baseline`     | current, minus the "REQUIRED: call resolve_academic_year" paragraph | no            | floor — descriptions alone  |
| `B_instructions` | same, plus an inline crosswalk + worked examples                    | no            | can prompting alone fix it? |
| `C_tool`         | branch as-is (REQUIRED paragraph)                                   | yes           | does the tool beat B?       |

`B` vs `C` is the money comparison: if `C` doesn't beat `B`, the tool is
overengineering. `A` vs `B` shows whether strengthening instructions helps at
all.

Every Cube tool is stubbed (`harness.py`): `meta` returns a fixed catalog,
`load`/`sql` record the query the model built and return a dummy result, and
`resolve_academic_year` (arm C only) calls the real parser. No warehouse, no
auth, no PII.

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
`disambig_rate`. All arms: `resolver_rate` — fraction of reps that called the
tool (only meaningful for arm C; it quantifies how reliable the soft "REQUIRED"
gate is on each model). Rates are reported with Wilson 95% intervals.

## Two runners

Both sweep the same arms/prompts and share `scorer.py`; they differ only in how
they drive the model.

| Runner           | Auth                                                 | Model environment                                                                                                                            |
| ---------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `run_eval.py`    | `ANTHROPIC_API_KEY` (metered)                        | bare Messages API — model + cube instructions + only the cube tools                                                                          |
| `run_eval_cc.py` | Claude Code subscription (logged-in `claude` binary) | Claude Agent SDK, run **hermetic** — cube instructions as the full system prompt, `tools=[]`, `strict_mcp_config=True`, `setting_sources=[]` |

The two runners are methodologically equivalent (same clean "model + cube
instructions + only cube tools" surface); they differ only in auth. The CC
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

1. **Resolver call-rate on Haiku (arm C) < ~85%** → the "REQUIRED" gate is
   unreliable on the target model → don't make the resolver the safety
   mechanism; make the label self-sufficient.
2. **`C` does not beat `B` on wrong-rate (both models)** → the deterministic
   tool isn't buying correctness over good instructions → slim or drop it.
3. **`B` already near-zero wrong-rate on Family 1** → filtering the label is
   unambiguous by construction → the label dimension is the real fix.
4. **`C` beats `B` specifically on Family 2 / SY-notation** → the end-year flip
   is where determinism pays → keep a thin resolver scoped to that transform.

## Fidelity caveats

- Drives the in-process tool schemas + instructions from `server.py`, not the
  live Cloud Run connector. They share `server.py`, so behavior should match,
  but the MCP transport itself is not exercised.
- The human Superset path (no model in the loop) is out of scope by construction
  — that is a data-model question, not an MCP one.
