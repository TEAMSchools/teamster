# CLAUDE.md Lean Router + Subdirectory Cleanup

**Date**: 2026-03-17 **Status**: Draft **Goal**: Reduce always-loaded context
overhead by ~60% (4,000 → ~1,425 tokens) and eliminate redundancy across 58
CLAUDE.md files, optimizing for Sonnet's 200K context window while maintaining
clarity for Opus 1M.

## Problem

The top-level `CLAUDE.md` (323 lines, ~4K tokens) is loaded on every
conversation regardless of task. It contains:

- A Skills section (lines 13-67, 55 lines) that duplicates the system prompt
  skill catalog injected by plugins
- A Repository Structure tree (lines 178-250, 73 lines) that duplicates
  `src/teamster/CLAUDE.md`
- Key Architectural Patterns (lines 252-303, 52 lines) that duplicate content
  already in `src/teamster/CLAUDE.md` and `src/dbt/CLAUDE.md`
- dbt Project Conventions + Exposures (lines 305-323, 19 lines) that duplicate
  `src/dbt/CLAUDE.md` and `src/dbt/kipptaf/CLAUDE.md`
- A Linting subsection documenting `trunk fmt` which is already automated by a
  PostToolUse hook

Additionally, subdirectory CLAUDE.md files have cross-file redundancy and 55 of
58 total CLAUDE.md files carry a 4-line boilerplate header that provides no
information (the remaining 3 — top-level, `src/teamster/CLAUDE.md`, and
`src/dbt/CLAUDE.md` — already use the clean `# CLAUDE.md — <path>` format,
though the latter two still have a description line to remove).

On Sonnet (200K window), total instruction overhead at session start is ~30K
tokens (15%). This design reduces it to ~26.5K tokens (13.3%), reclaiming ~1.7%
of the context window.

## Approach

Three coordinated changes, in priority order:

### Change 1: Top-Level Becomes a Lean Router

The top-level `CLAUDE.md` keeps only what every conversation needs — project
identity, working conventions, commands, and documentation guidance — and
delegates architecture to subdirectory files.

**Removes:**

| Section                                             | Lines (actual) | Tokens     | Reason                                                             |
| --------------------------------------------------- | -------------- | ---------- | ------------------------------------------------------------------ |
| Skills (lines 13-67)                                | 55             | ~600       | 100% duplicate of system prompt plugin catalog                     |
| Repository Structure tree (lines 178-250)           | 73             | ~1,000     | Duplicated in `src/teamster/CLAUDE.md`                             |
| Key Architectural Patterns (lines 252-303)          | 52             | ~700       | Duplicated across `src/teamster/CLAUDE.md` and `src/dbt/CLAUDE.md` |
| dbt Project Conventions + Exposures (lines 305-323) | 19             | ~250       | Already in `src/dbt/CLAUDE.md` and `src/dbt/kipptaf/CLAUDE.md`     |
| **Subtotal removed**                                | **199**        | **~2,550** |                                                                    |

**Compresses:**

- Linting subsection (lines 131-148): Remove the `trunk check` / `trunk fmt`
  code block (lines 137-143) and the introductory sentence referencing Trunk
  (line 133). **Keep**: the `.trunk/trunk.yaml` and `.trunk/config/` reference
  (lines 134-135) and the SQL style paragraph (lines 145-148). This preserves
  discoverability of linter config while removing commands that are automated.
  Saves ~8 lines, ~75 tokens.

**Adds:**

- ~8-line Architecture section with **directive pointers** (~75 tokens). Uses
  imperative language ("you MUST read") rather than informational pointers ("see
  X for details") to reduce the risk of Sonnet skipping the read, especially on
  tasks that seem straightforward. Example:

  > **Before working on Dagster code**, read `src/teamster/CLAUDE.md` for
  > architecture, library patterns, and code location structure.
  >
  > **Before working on dbt models**, read `src/dbt/CLAUDE.md` for project
  > structure, model conventions, and SQL standards.
  >
  > Each subdirectory has its own CLAUDE.md — read it before modifying code in
  > that directory.

**Regarding Exposures** (lines 320-323): This content is adequately covered by
`src/dbt/kipptaf/CLAUDE.md` (lines 88-136, full exposure YAML reference) and
`src/dbt/CLAUDE.md` does not need it. Removing it from the top-level is safe.

**Result**: 323 lines -> ~125 lines. ~4,000 -> ~1,425 tokens always-loaded.

#### Target structure of the top-level CLAUDE.md

```
# CLAUDE.md
## Project Overview           (3 lines -- who, what, tech stack)
## Working Conventions         (unchanged -- uv run, git, branches, PRs, issues)
## Commands
### Development               (unchanged)
### Testing                   (unchanged)
### Linting                   (compressed -- Trunk config refs + SQL style note)
### BigQuery MCP Queries      (unchanged)
## Documentation              (unchanged -- dbt YAML vs MkDocs)
## Architecture               (NEW -- ~5 pointer lines replacing ~199 lines)
```

### Change 2: Subdirectory Deduplication

Five files have content duplicated with their parent CLAUDE.md. Each
deduplication keeps the more detailed version and replaces the other with a
pointer.

#### `src/dbt/kipptaf/CLAUDE.md` and `src/dbt/CLAUDE.md`

| Content                        | Keep in                                                                               | Remove from                                 | Action                                                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------- | ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `base_` to `int_` legacy note  | `src/dbt/CLAUDE.md` (lines 144-148)                                                   | `src/dbt/kipptaf/CLAUDE.md` (lines 138-145) | Remove from kipptaf (already has "See `src/dbt/CLAUDE.md`" pointer at line 149)                                      |
| `star()` / `SELECT *` guidance | `src/dbt/kipptaf/CLAUDE.md` (lines 188-219, expanded with INFORMATION_SCHEMA example) | `src/dbt/CLAUDE.md` (lines 109-116)         | Compress dbt root version to 1-line pointer: "See `src/dbt/kipptaf/CLAUDE.md` for full `dbt_utils.star()` guidance." |

#### `src/teamster/CLAUDE.md` and `src/teamster/core/CLAUDE.md`

| Content                            | Keep in                                                                    | Remove from                              | Action                                                                                                                                                                                               |
| ---------------------------------- | -------------------------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automation conditions (3 builders) | `core/CLAUDE.md` (lines 70-91, detailed, includes unsynced badge behavior) | `src/teamster/CLAUDE.md` (lines 87-101)  | Replace lines 87-101 with: "See `core/CLAUDE.md` for automation condition builders (`dbt_view_automation_condition`, `dbt_union_relations_automation_condition`, `dbt_table_automation_condition`)." |
| IO managers (3 modes)              | `core/CLAUDE.md` (lines 41-57, detailed, includes Hive path format)        | `src/teamster/CLAUDE.md` (lines 103-114) | Replace lines 103-114 with: "See `core/CLAUDE.md` for IO manager details (three modes: default, avro, file)."                                                                                        |

**Savings**: ~40 lines, ~1,500 bytes, ~375 tokens.

### Change 3: Boilerplate Stripping

**55 files** have the full 4-line boilerplate header:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.
```

**Replace with**: `# CLAUDE.md — <module path>` (single line, using em-dash `—`
to match the existing convention in `src/teamster/CLAUDE.md` and
`src/dbt/CLAUDE.md`).

**2 files** (`src/teamster/CLAUDE.md`, `src/dbt/CLAUDE.md`) already use the
`# CLAUDE.md -- <path>` title format but retain the description line ("This file
provides guidance to Claude Code..."). **Remove** the description line from
these two files as well.

**The top-level** `CLAUDE.md` gets its header updated as part of Change 1.

For small files where `## Purpose` is the only section heading, remove the
heading and let the content follow the title directly. Examples:
`libraries/collegeboard/`, `libraries/nsc/`, `libraries/pearson/`.

**Savings**: ~170 lines, ~3,000 bytes, ~750 tokens across 57 files.

## Files Modified

| File                            | Change type                                                                  |
| ------------------------------- | ---------------------------------------------------------------------------- |
| `CLAUDE.md` (top-level)         | Major restructure — remove 4 sections, compress linting, add pointers        |
| `src/teamster/CLAUDE.md`        | Remove automation conditions + IO managers detail, add pointers to `core/`   |
| `src/dbt/CLAUDE.md`             | Compress `star()` guidance to pointer to `kipptaf/`; remove description line |
| `src/dbt/kipptaf/CLAUDE.md`     | Remove `base_` to `int_` note (already covered by parent)                    |
| `src/teamster/CLAUDE.md`        | Remove description line                                                      |
| 55 subdirectory CLAUDE.md files | Strip boilerplate header, simplify `## Purpose` headings                     |

**Total files touched**: 59 (top-level + 2 dedup targets + 2 description-line
removals + 55 boilerplate strips; some overlap — actual unique files: ~58).

## Token Budget Impact

"Worst-case active path" = top-level + deepest subdirectory chain. The most
expensive path is: `CLAUDE.md` (always) + `src/dbt/CLAUDE.md` (~2,000 tokens) +
`src/dbt/kipptaf/CLAUDE.md` (~2,750 tokens).

| Metric                                                                | Before                 | After                  | Sonnet % of 200K |
| --------------------------------------------------------------------- | ---------------------- | ---------------------- | ---------------- |
| Always-loaded (top-level only)                                        | 4,000 tokens (2.0%)    | 1,425 tokens (0.7%)    | -1.3%            |
| Worst-case active path (top + `src/dbt/` + `src/dbt/kipptaf/`)        | ~8,750 tokens (4.4%)   | ~6,000 tokens (3.0%)   | -1.4%            |
| System + plugins + CLAUDE.md at session start (before any file reads) | ~30,000 tokens (15.0%) | ~27,425 tokens (13.7%) | -1.3%            |

**Token savings by change**:

| Change                               | Tokens saved                                      | Where                                     |
| ------------------------------------ | ------------------------------------------------- | ----------------------------------------- |
| Change 1: Top-level lean router      | ~2,575 (2,550 removed + 75 compressed - 50 added) | Always-loaded                             |
| Change 2: Subdirectory deduplication | ~375                                              | On-demand (when working in affected dirs) |
| Change 3: Boilerplate stripping      | ~750                                              | On-demand (spread across 57 files)        |
| **Total**                            | **~3,700**                                        |                                           |

The always-loaded reduction (~2,575 tokens) benefits every conversation. Changes
2 and 3 benefit conversations that read the affected subdirectory files.

## What Does NOT Change

- **Plugins**: All 8 enabled plugins are lean (~3K tokens total catalog). No
  removals.
- **MCP servers**: BigQuery and dbt MCP servers are both essential. dbt MCP is
  required by dbt plugin skills.
- **Subdirectory CLAUDE.md content**: Library, code location, and dbt project
  files are already well-scoped. Only boilerplate and cross-file duplication are
  touched.
- **Working Conventions, Commands, Documentation sections**: Kept in top-level
  (essential for every conversation).

## Risks

- **Claude may not read subdirectory CLAUDE.md early enough**: Sonnet is more
  eager than Opus and may start writing code before reading subdirectory
  context, especially for tasks that seem straightforward. Mitigated by three
  layers: (1) directive language in the top-level pointers ("you MUST
  read...before"), (2) Claude naturally loads subdirectory CLAUDE.md files when
  it opens files in those directories, and (3) Trunk linting hooks catch SQL
  convention violations that would otherwise be missed (PostToolUse
  `trunk fmt` + pre-commit `trunk check`).
- **Cross-domain tasks** (Dagster + dbt in one session): Claude needs to read 2
  subdirectory files. This is a ~3-second cost vs having the information
  always-loaded. Acceptable trade-off.

## Validation

After implementation, verify with:

```bash
# Top-level should be ~125 lines, ~5-6KB
wc -l -c CLAUDE.md

# No boilerplate headers should remain in subdirectory files
grep -rl "This file provides guidance to Claude Code" src/

# All subdirectory CLAUDE.md files should have the clean title format
# (top-level is excluded since it uses just "# CLAUDE.md")
find src/ -name "CLAUDE.md" | xargs grep -L "^# CLAUDE.md —"

# Total CLAUDE.md size should drop from ~109KB to ~95KB
find . -name "CLAUDE.md" -exec wc -c {} + | tail -1
```
