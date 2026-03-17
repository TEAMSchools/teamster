# CLAUDE.md Lean Router + Subdirectory Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents available) or superpowers:executing-plans to implement this
> plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce always-loaded CLAUDE.md context from ~4,000 to ~1,425 tokens
and eliminate ~3,700 tokens of redundancy across 58 CLAUDE.md files.

**Architecture:** Three changes applied in order — (1) restructure the top-level
CLAUDE.md into a lean router, (2) deduplicate content between 4 subdirectory
file pairs, (3) strip boilerplate headers from 57 files. All changes are
documentation-only (no code, no tests).

**Tech Stack:** Markdown files only. Validation via `wc`, `grep`, `find`.

**Spec:** `docs/superpowers/specs/2026-03-17-claude-md-lean-router-design.md`

---

## Tasks

### Task 1: Restructure top-level CLAUDE.md into lean router

This is the highest-impact change — removes ~199 lines and ~2,550 tokens from
the always-loaded context.

**Files:**

- Modify: `CLAUDE.md` (top-level, 323 lines currently)

- [ ] **Step 1: Remove the Skills section (lines 13-67)**

Delete everything from `## Skills` through the end of the
`### CLAUDE.md Maintenance` subsection (the blank line before
`## Working Conventions`). This is 55 lines that duplicate the system prompt
plugin catalog.

- [ ] **Step 2: Remove the Architecture section (lines 176-323)**

Delete everything from `## Architecture` through the end of file. This removes:

- Repository Structure tree (lines 178-250, 73 lines)
- Key Architectural Patterns (lines 252-303, 52 lines)
- dbt Project Conventions + Exposures (lines 305-323, 19 lines)

All of this content already exists in `src/teamster/CLAUDE.md`,
`src/dbt/CLAUDE.md`, and `src/dbt/kipptaf/CLAUDE.md`.

- [ ] **Step 3: Compress the Linting subsection**

Current content (lines 131-148):

````markdown
### Linting

Linting is managed via [Trunk](https://trunk.io) and enforced by a pre-commit
hook. See `.trunk/trunk.yaml` for the full list of enabled linters and
`.trunk/config/` for per-linter configuration files.

\```bash

# Check all files

trunk check

# Auto-format all files

trunk fmt \```

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.
````

Replace with:

```markdown
### Linting

See `.trunk/trunk.yaml` for the full list of enabled linters and
`.trunk/config/` for per-linter configuration files.

**SQL style**: Before writing, reviewing, or commenting on SQL, read
`.trunk/config/.sqlfluff`. Key enforced rules: BigQuery dialect, trailing commas
**required** in SELECT clauses, single quotes for literals, max line length 88.
Do not flag code that follows these rules.
```

This removes the `trunk check`/`trunk fmt` code block (automated by hooks) and
the introductory sentence about Trunk managing linting (redundant with the
config reference).

- [ ] **Step 4: Add the Architecture section with directive pointers**

After the Documentation section (which ends with "the documentation mechanism
for that work."), add:

```markdown
## Architecture

**Before working on Dagster code**, read `src/teamster/CLAUDE.md` for
architecture, library patterns, and code location structure.

**Before working on dbt models**, read `src/dbt/CLAUDE.md` for project
structure, model conventions, and SQL standards.

Each subdirectory has its own CLAUDE.md — read it before modifying code in that
directory.
```

- [ ] **Step 5: Validate the top-level file**

Run: `wc -l -c CLAUDE.md` Expected: ~120-130 lines, ~5-6KB

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: restructure top-level CLAUDE.md into lean router

Remove Skills section (duplicate of plugin catalog), Repository Structure
tree, Key Architectural Patterns, and dbt Project Conventions (all
duplicated in subdirectory CLAUDE.md files). Compress Linting subsection.
Add directive Architecture pointers to subdirectory files.

Reduces always-loaded context from ~4,000 to ~1,425 tokens (~60%)."
```

---

### Task 2: Deduplicate `src/teamster/CLAUDE.md` with `src/teamster/core/CLAUDE.md`

**Files:**

- Modify: `src/teamster/CLAUDE.md` (lines 87-114)

- [ ] **Step 1: Replace Automation Conditions section with pointer**

Replace `src/teamster/CLAUDE.md` lines 87-101 (the `## Automation Conditions`
section through "or sensor/schedule triggers.") with:

```markdown
## Automation Conditions

See `core/CLAUDE.md` for automation condition builders
(`dbt_view_automation_condition`, `dbt_union_relations_automation_condition`,
`dbt_table_automation_condition`). Non-dbt assets use
`AutomationCondition.eager()` or sensor/schedule triggers.
```

- [ ] **Step 2: Replace IO Managers section with pointer**

Replace `src/teamster/CLAUDE.md` lines 103-114 (the `## IO Managers` section
through "(`_dagster_partition_date=YYYY-MM-DD/data`).") with:

```markdown
## IO Managers

See `core/CLAUDE.md` for IO manager details (three modes: default, avro, file).
All use Hive-style partitioned GCS paths.
```

- [ ] **Step 3: Commit**

```bash
git add src/teamster/CLAUDE.md
git commit -m "docs: deduplicate teamster CLAUDE.md with core/CLAUDE.md

Replace inline automation conditions and IO managers documentation with
pointers to core/CLAUDE.md where the detailed versions live."
```

---

### Task 3: Deduplicate `src/dbt/CLAUDE.md` with `src/dbt/kipptaf/CLAUDE.md`

**Files:**

- Modify: `src/dbt/CLAUDE.md` (lines 109-116)
- Modify: `src/dbt/kipptaf/CLAUDE.md` (lines 138-145)

- [ ] **Step 1: Compress star() guidance in `src/dbt/CLAUDE.md`**

Replace `src/dbt/CLAUDE.md` lines 109-116 (the `SELECT *` from star() models
bullet point) with:

```markdown
- **`SELECT *` from models that use `dbt_utils.star()`**: See
  `src/dbt/kipptaf/CLAUDE.md` for the full guidance on selecting from
  star-generated models (includes `INFORMATION_SCHEMA.COLUMNS` query pattern).
```

- [ ] **Step 2: Remove `base_` legacy note from `src/dbt/kipptaf/CLAUDE.md`**

Remove `src/dbt/kipptaf/CLAUDE.md` lines 138-145 (the `## Legacy base_ Prefix`
section). The parent file `src/dbt/CLAUDE.md` already has this at lines 144-148,
and kipptaf line 149 already says "See `src/dbt/CLAUDE.md` for shared per-layer
requirements."

- [ ] **Step 3: Commit**

```bash
git add src/dbt/CLAUDE.md src/dbt/kipptaf/CLAUDE.md
git commit -m "docs: deduplicate dbt CLAUDE.md files

Compress star() guidance in dbt root to pointer to kipptaf (which has the
expanded version with INFORMATION_SCHEMA example). Remove base_-to-int_
legacy note from kipptaf (already in dbt root)."
```

---

### Task 4: Strip boilerplate from `src/teamster/` library CLAUDE.md files (34 files)

Batch 1 of boilerplate stripping — all files under `src/teamster/libraries/`.

**Files** (34 files):

- Modify: `src/teamster/libraries/adp/CLAUDE.md`
- Modify: `src/teamster/libraries/airbyte/CLAUDE.md`
- Modify: `src/teamster/libraries/alchemer/CLAUDE.md`
- Modify: `src/teamster/libraries/amplify/CLAUDE.md`
- Modify: `src/teamster/libraries/collegeboard/CLAUDE.md`
- Modify: `src/teamster/libraries/couchdrop/CLAUDE.md`
- Modify: `src/teamster/libraries/coupa/CLAUDE.md`
- Modify: `src/teamster/libraries/dayforce/CLAUDE.md`
- Modify: `src/teamster/libraries/dbt/CLAUDE.md`
- Modify: `src/teamster/libraries/deanslist/CLAUDE.md`
- Modify: `src/teamster/libraries/dlt/CLAUDE.md`
- Modify: `src/teamster/libraries/edplan/CLAUDE.md`
- Modify: `src/teamster/libraries/email/CLAUDE.md`
- Modify: `src/teamster/libraries/extracts/CLAUDE.md`
- Modify: `src/teamster/libraries/finalsite/CLAUDE.md`
- Modify: `src/teamster/libraries/fivetran/CLAUDE.md`
- Modify: `src/teamster/libraries/fldoe/CLAUDE.md`
- Modify: `src/teamster/libraries/google/CLAUDE.md`
- Modify: `src/teamster/libraries/iready/CLAUDE.md`
- Modify: `src/teamster/libraries/knowbe4/CLAUDE.md`
- Modify: `src/teamster/libraries/ldap/CLAUDE.md`
- Modify: `src/teamster/libraries/level_data/CLAUDE.md`
- Modify: `src/teamster/libraries/nsc/CLAUDE.md`
- Modify: `src/teamster/libraries/overgrad/CLAUDE.md`
- Modify: `src/teamster/libraries/pearson/CLAUDE.md`
- Modify: `src/teamster/libraries/performance_management/CLAUDE.md`
- Modify: `src/teamster/libraries/powerschool/CLAUDE.md`
- Modify: `src/teamster/libraries/renlearn/CLAUDE.md`
- Modify: `src/teamster/libraries/sftp/CLAUDE.md`
- Modify: `src/teamster/libraries/smartrecruiters/CLAUDE.md`
- Modify: `src/teamster/libraries/ssh/CLAUDE.md`
- Modify: `src/teamster/libraries/tableau/CLAUDE.md`
- Modify: `src/teamster/libraries/titan/CLAUDE.md`
- Modify: `src/teamster/libraries/zendesk/CLAUDE.md`

- [ ] **Step 1: For each file, apply the boilerplate replacement**

For each file, replace the header:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Purpose
```

With the clean format:

```markdown
# CLAUDE.md — `libraries/<name>/`
```

The `## Purpose` heading is removed. The content that was under `## Purpose`
follows the title directly (after one blank line).

**Special case — 6 files where `## Purpose` is the only heading**: For these
files (`collegeboard`, `nsc`, `pearson`, `dayforce`, `fldoe`,
`performance_management`), the `## Purpose` heading is removed and the
descriptive text follows the title directly. The remaining files have multiple
`##` headings — only the `## Purpose` heading is removed; other headings remain.

**Note**: Some files do not have a `## Purpose` heading (they jump to a
different heading like `## Identity` or `## Files`). For these, just replace the
4-line boilerplate with the clean title — do not remove any other headings.

- [ ] **Step 2: Commit**

```bash
git add src/teamster/libraries/*/CLAUDE.md
git commit -m "docs: strip boilerplate headers from library CLAUDE.md files

Replace 4-line boilerplate with clean title format across 34 library
CLAUDE.md files. Remove redundant Purpose headings."
```

---

### Task 5: Strip boilerplate from `src/teamster/code_locations/` and `src/teamster/core/` CLAUDE.md files (6 files)

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippnewark/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippcamden/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippmiami/CLAUDE.md`
- Modify: `src/teamster/code_locations/kipppaterson/CLAUDE.md`
- Modify: `src/teamster/core/CLAUDE.md`

- [ ] **Step 1: Apply boilerplate replacement to each file**

Same pattern as Task 4. Replace:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.
```

With the clean title:

- `# CLAUDE.md — `code_locations/kipptaf/``
- `# CLAUDE.md — `code_locations/kippnewark/``
- `# CLAUDE.md — `code_locations/kippcamden/``
- `# CLAUDE.md — `code_locations/kippmiami/``
- `# CLAUDE.md — `code_locations/kipppaterson/``
- `# CLAUDE.md — `core/``

These files use `## Identity` or `## Purpose` + other headings — remove
`## Purpose` heading where present, keep other headings intact.

- [ ] **Step 2: Commit**

```bash
git add src/teamster/code_locations/*/CLAUDE.md src/teamster/core/CLAUDE.md
git commit -m "docs: strip boilerplate headers from code location and core CLAUDE.md files"
```

---

### Task 6: Strip boilerplate from `src/dbt/` CLAUDE.md files (15 files) and description lines from 2 clean files

**Files:**

- Modify: `src/dbt/amplify/CLAUDE.md`
- Modify: `src/dbt/deanslist/CLAUDE.md`
- Modify: `src/dbt/edplan/CLAUDE.md`
- Modify: `src/dbt/finalsite/CLAUDE.md`
- Modify: `src/dbt/iready/CLAUDE.md`
- Modify: `src/dbt/kippcamden/CLAUDE.md`
- Modify: `src/dbt/kippmiami/CLAUDE.md`
- Modify: `src/dbt/kippnewark/CLAUDE.md`
- Modify: `src/dbt/kipppaterson/CLAUDE.md`
- Modify: `src/dbt/kipptaf/CLAUDE.md`
- Modify: `src/dbt/overgrad/CLAUDE.md`
- Modify: `src/dbt/pearson/CLAUDE.md`
- Modify: `src/dbt/powerschool/CLAUDE.md`
- Modify: `src/dbt/renlearn/CLAUDE.md`
- Modify: `src/dbt/titan/CLAUDE.md`
- Modify: `src/dbt/CLAUDE.md` (remove description line only)
- Modify: `src/teamster/CLAUDE.md` (remove description line only)

- [ ] **Step 1: Apply boilerplate replacement to 15 dbt project files**

Same pattern. Replace 4-line boilerplate with clean title:

- `# CLAUDE.md — `dbt/amplify/``
- `# CLAUDE.md — `dbt/deanslist/``
- etc.

Remove `## Purpose` heading where present. Keep other headings.

- [ ] **Step 2: Remove description lines from 2 already-clean files**

`src/dbt/CLAUDE.md` line 3-4 currently reads:

```markdown
This file provides guidance to Claude Code (claude.ai/code) when working with
dbt projects in this directory.
```

Delete these 2 lines (and the blank line after them if present).

`src/teamster/CLAUDE.md` line 3-4 currently reads:

```markdown
This file provides guidance to Claude Code (claude.ai/code) when working with
the Dagster Python package in this directory.
```

Delete these 2 lines (and the blank line after them if present).

- [ ] **Step 3: Commit**

```bash
git add src/dbt/*/CLAUDE.md src/dbt/CLAUDE.md src/teamster/CLAUDE.md
git commit -m "docs: strip boilerplate from dbt CLAUDE.md files and remove description lines

Replace 4-line boilerplate with clean title format across 15 dbt project
CLAUDE.md files. Remove residual description lines from src/dbt/CLAUDE.md
and src/teamster/CLAUDE.md."
```

---

### Task 7: Validation

- [ ] **Step 1: Verify top-level CLAUDE.md size**

Run: `wc -l -c CLAUDE.md` Expected: ~120-130 lines, ~5-6KB

- [ ] **Step 2: Verify no boilerplate headers remain**

Run: `grep -rl "This file provides guidance to Claude Code" src/` Expected: no
output (no matches)

- [ ] **Step 3: Verify all subdirectory CLAUDE.md files have clean title**

Run: `find src/ -name "CLAUDE.md" | xargs grep -L "^# CLAUDE.md —"` Expected: no
output (all files match)

- [ ] **Step 4: Verify total CLAUDE.md size reduction**

Run: `find . -name "CLAUDE.md" -not -path "./docs/*" -exec wc -c {} + | tail -1`
Expected: ~95KB total (down from ~109KB)
