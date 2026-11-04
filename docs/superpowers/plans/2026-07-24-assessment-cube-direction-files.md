# Assessment Cube Direction Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce two version-controlled Markdown direction files that fill the
gap between the Cube semantic-layer YAML and correct use of assessment data,
ready to sync into the achievement-director claude.ai Project.

**Architecture:** Two files under `docs/guides/`, wired into the MkDocs nav
beside the existing Cube guides. An **orchestrator** carries the session
protocol, routing, and log template; an **assessment reference** carries settled
data-usage conventions with sections for shared conventions, internal
(Illuminate), NJ state, and FL state. Content is distilled from the spec, which
itself is distilled from four working-group session logs.

**Tech Stack:** Markdown; MkDocs Material (explicit `nav` in `mkdocs.yml`);
trunk markdownlint; the Cube MCP connector (`mcp__claude_ai_Cube__*`) for
factual verification.

**Source of truth:** the spec at
[docs/superpowers/specs/2026-07-24-assessment-cube-direction-files-design.md](../specs/2026-07-24-assessment-cube-direction-files-design.md).
Every content task reads the spec section it implements; the spec holds the full
prose, this plan holds structure, rules, and verification.

## Global Constraints

- **Audience/voice.** These files are claude.ai Project knowledge. The
  orchestrator is written as instructions _to Claude_ (imperative protocol),
  readable by humans; the reference is a lookup document. Do not write them as
  MkDocs-reader-only prose.
- **Governing principle (verbatim from spec §3):** document what fields actually
  mean and how the cube behaves (settled mechanics); do not invent the
  organization's policy defaults — where a default is needed but unratified,
  flag it as an inference and log it, never answer it.
- **Undecided policy defaults MUST NOT appear as rules.** Minimum-n suppression,
  intervention tier cut-scores, pool-vs-per-instrument, which subjects count as
  "math", and `grade_level_tested` prior-grade behavior appear only as "flag and
  log", never as a stated value.
- **Upstream Cube defects are out of these files.** Do not document
  `assessment_type` description drift, null `academic_year` on state rows,
  standard-code duplication, `proficiency_level` label drift, or the missing
  schema-version signal as director workarounds. They are separate `src/cube/`
  issues.
- **PII:** no student names or identifiers and no staff names anywhere in either
  file.
- **Markdown lint:** every fenced block gets a language (MD040; use `text` when
  none applies); headings increment by one level (MD001); ordered lists broken
  by fences use `1.` for every item (MD029); backtick every
  model/table/column/field identifier so trunk-fmt does not mangle `snake_case`.
- **Worktree:** all paths are in
  `/workspaces/teamster/.worktrees/cube-assessment-directions`. Use
  `git -C <worktree>` for git, and Read/Edit/Write the worktree paths — never
  the main checkout.

## File Structure

- Create: `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md` —
  session protocol (spec §5.1), routing (§5.2), session-log template (§5.3).
  Cross-references the reference file by its Project filename.
- Create: `src/cube/mcp/project_knowledge/assessment-cube-reference.md` — shared
  conventions (§6.1), internal/Illuminate (§6.2), NJ state (§6.3), FL state
  (§6.4).
- Modify: `mkdocs.yml` — add an "Assessment Cube Project" subsection under
  `Guides`.

---

### Task 1: Orchestrator file

**Files:**

- Create: `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`

**Interfaces:**

- Produces: the file other directors upload as the Project's protocol. Must name
  the reference file (`assessment-cube-reference.md`) in its routing section so
  cross-file references resolve after upload.

- [ ] **Step 1: Read the spec sections this implements**

Read spec §5.1 (standing protocol), §5.2 (routing), §5.3 (session-log template),
plus §3 (governing principle) and §1 "Confirmed environment facts".

- [ ] **Step 2: Write the file**

Structure (H1 title, then H2 sections):

```text
# Assessment Cube — Session Orchestrator

<1-2 sentence intro: what this file is, that Claude follows it every session,
 and that data-usage conventions live in assessment-cube-reference.md>

## How to use this file
## The standing protocol        (the 6 ordered steps from spec §5.1, imperative voice)
## Flag, don't invent           (spec §3 governing principle, stated as a rule)
## Routing                      (spec §5.2; name assessment-cube-reference.md and its sections)
## Session-log template         (spec §5.3, as a fill-in template the user can copy)
```

Requirements:

- The protocol's six steps stay ordered and keep the "hard gate" framing on
  calibration.
- The routing section names `assessment-cube-reference.md` and its four sections
  (shared, internal, NJ, FL) explicitly.
- The log template is copy-pasteable (use a fenced ```text block containing the
  header / per-query block / patterns / fix-backlog / handoff / guardrail
  skeleton).
- No undecided policy default stated as a value (Global Constraints).

- [ ] **Step 3: Lint the file**

Run:
`cd /workspaces/teamster/.worktrees/cube-assessment-directions && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md </dev/null`
Expected: `No issues` (or only auto-fixable formatting, which the pre-commit
`fmt` hook resolves).

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cube-assessment-directions add src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md
git -C /workspaces/teamster/.worktrees/cube-assessment-directions commit -m "docs: add assessment Cube session orchestrator" -m "Refs #4534"
```

---

### Task 2: Assessment reference file

**Files:**

- Create: `src/cube/mcp/project_knowledge/assessment-cube-reference.md`

**Interfaces:**

- Consumes: nothing from Task 1 (independent; the two files can be drafted in
  parallel).
- Produces: the four sections the orchestrator's routing points at.

- [ ] **Step 1: Read the spec sections this implements**

Read spec §6.1 (shared conventions), §6.2 (internal/Illuminate), §6.3 (NJ
state), §6.4 (FL state), plus §3 and §4 (to keep the settled/open line correct).

- [ ] **Step 2: Write the file**

Structure:

```text
# Assessment Cube — Data-Usage Reference

<1-2 sentence intro: settled mechanics only; open policy defaults are flagged,
 not answered here — see the orchestrator's "Flag, don't invent" rule>

## Shared conventions   (spec §6.1)
## Internal (Illuminate) (spec §6.2)
## NJ state             (spec §6.3)
## FL state             (spec §6.4)
```

Requirements:

- Every field/measure/value is backticked.
- Mark the three not-yet-verified facts inline with a literal `**[VERIFY]**` tag
  so Task 4 can find them: (a) the exact internal `assessment_type` enum value
  in §Internal; (b) the `performance_band_label_number` to abbreviation
  crosswalk in §Shared; (c) the canonical NJ student identifier in §NJ.
- State the FL `academic_year` 100%-null → `date_taken` school-year mapping as a
  hard rule; state `response_type_root_description` reliable for CCSS and
  unreliable for FL.
- Undecided defaults (pooling, min-n, subject scope) appear only as "flag and
  log", never a value.

- [ ] **Step 3: Lint the file**

Run:
`cd /workspaces/teamster/.worktrees/cube-assessment-directions && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/project_knowledge/assessment-cube-reference.md </dev/null`
Expected: `No issues`.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cube-assessment-directions add src/cube/mcp/project_knowledge/assessment-cube-reference.md
git -C /workspaces/teamster/.worktrees/cube-assessment-directions commit -m "docs: add assessment Cube data-usage reference" -m "Refs #4534"
```

---

### Task 3: Wire the files into the MkDocs nav

**Files:**

- Modify: `mkdocs.yml` (the `nav:` `Guides:` list, after the
  `Claude + Cube Connector` entry)

- [ ] **Step 1: Add the nav subsection**

Insert under `Guides:`, after the `Claude + Cube Connector` line:

```yaml
- Assessment Cube Project:
    - Orchestrator: guides/assessment-cube-orchestrator.md
    - Data-Usage Reference: guides/assessment-cube-reference.md
```

- [ ] **Step 2: Lint the config**

Run:
`cd /workspaces/teamster/.worktrees/cube-assessment-directions && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix mkdocs.yml </dev/null`
Expected: `No issues` (yamllint clean).

- [ ] **Step 3: Verify the build sees both pages with no nav warning**

Run:
`cd /workspaces/teamster/.worktrees/cube-assessment-directions && VIRTUAL_ENV= uv --directory /workspaces/teamster run mkdocs build --strict -f mkdocs.yml -d /tmp/claude-1000/mkdocs-build 2>&1 | tail -20`
Expected: build succeeds; no `is not included in the "nav"` warning for either
new file. If `mkdocs` is not available via `uv run`, skip this step and rely on
CI, noting the skip.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cube-assessment-directions add mkdocs.yml
git -C /workspaces/teamster/.worktrees/cube-assessment-directions commit -m "docs: add assessment Cube project pages to nav" -m "Refs #4534"
```

---

### Task 4: Verify the flagged facts against the live Cube connector

Main-loop only — the Cube connector authenticates per-user via claude.ai OAuth
and is not reliably available to subagents. Do not delegate this task.

**Files:**

- Modify: `src/cube/mcp/project_knowledge/assessment-cube-reference.md` (resolve
  the three `**[VERIFY]**` tags)

- [ ] **Step 1: Load the Cube tool schemas**

`ToolSearch` query `select:mcp__claude_ai_Cube__meta,mcp__claude_ai_Cube__load`.

- [ ] **Step 2: Confirm the three facts (aggregate/deidentified queries only —
      no student rows)**

- Internal `assessment_type` enum: `meta` on `student_assessment_scores_view`,
  then a `load` grouping `count_scores` by `assessment_type` to read the
  internal (Illuminate) value.
- Performance-band crosswalk: `load` grouping `count_scores` by
  `performance_band_label_number` and its label dimension to confirm band 1 =
  Far Below, band 2 = Below.
- NJ identifier: `load` for a NJ region counting non-null
  `lea_student_identifier` vs `district_student_identifier` at the aggregate
  level to confirm district is null / LEA populated.

- [ ] **Step 3: Resolve the tags**

Replace each `**[VERIFY]**` with the confirmed value. If any fact cannot be
confirmed, leave a one-line explicit flag
(`not confirmed as of 2026-07-24 — <reason>`) rather than guessing.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cube-assessment-directions && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/project_knowledge/assessment-cube-reference.md </dev/null
git -C /workspaces/teamster/.worktrees/cube-assessment-directions add src/cube/mcp/project_knowledge/assessment-cube-reference.md
git -C /workspaces/teamster/.worktrees/cube-assessment-directions commit -m "docs: confirm assessment reference facts against Cube" -m "Refs #4534"
```

---

### Task 5: Final coverage and lint sweep

**Files:**

- Read-only review of both new files + `mkdocs.yml`

- [ ] **Step 1: Spec-coverage check**

Confirm every item in spec §5 and §6 appears in a file, and that no undecided
policy default (spec §4 bucket 2 / §7) is stated as a rule. List any gap and fix
it in the owning file.

- [ ] **Step 2: Full lint sweep**

Run:
`cd /workspaces/teamster/.worktrees/cube-assessment-directions && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md src/cube/mcp/project_knowledge/assessment-cube-reference.md mkdocs.yml docs/superpowers/plans/2026-07-24-assessment-cube-direction-files.md </dev/null`
Expected: `No issues`.

- [ ] **Step 3: Commit any fixes**

```bash
git -C /workspaces/teamster/.worktrees/cube-assessment-directions add src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md src/cube/mcp/project_knowledge/assessment-cube-reference.md
git -C /workspaces/teamster/.worktrees/cube-assessment-directions commit -m "docs: coverage and lint fixes for assessment Cube files" -m "Refs #4534"
```

(Skip the commit if Step 1 and Step 2 found nothing to fix.)

---

## Self-Review

- **Spec coverage:** §5.1 → Task 1; §5.2 → Task 1; §5.3 → Task 1; §6.1 → Task 2;
  §6.2 → Task 2; §6.3 → Task 2; §6.4 → Task 2; §8 distribution/nav → Task 3; §9
  items 2-4 (factual confirmations) → Task 4; §9 item 1 (repo home) → resolved
  to `src/cube/mcp/project_knowledge/` (see Execution deviations); §10 success
  criteria → Task 5. Buckets 1 and 2 (spec §4) are deliberately out-of-file; the
  "flag and log" handling is enforced by Global Constraints and checked in Task
  5 Step 1.
- **Placeholder scan:** the only intentional in-file markers are the
  `**[VERIFY]**` tags, which Task 4 resolves; no `TODO`/`TBD` remain after
  Task 4.
- **Consistency:** the reference filename `assessment-cube-reference.md` is used
  identically in Task 1 (routing reference), Task 2 (create), Task 3 (nav), and
  Task 4 (modify).

## Execution deviations

Recorded after the fact. File-path references throughout the tasks above were
updated in place to the actual location; the following are the substantive
divergences from the original plan:

- **File location.** Both files were relocated to
  `src/cube/mcp/project_knowledge/` (decided by the data engineer) instead of
  `docs/guides/`. They are Cube MCP project knowledge synced into the shared
  claude.ai Project, not MkDocs-rendered pages.
- **Task 3 dropped.** The MkDocs nav wiring task did not happen — the files are
  not docs-site pages, so there is no `mkdocs.yml` nav entry for them.
- **Scope expansion.** The assessment reference gained three additional sections
  beyond the original spec's plan: i-Ready, DIBELS, and STAR, each its own
  vendor normed-diagnostic reference section alongside internal (Illuminate), NJ
  state, and FL state.
- **Verification.** All facts flagged `**[VERIFY]**` in the original plan
  (internal `assessment_type` enum value, performance-band crosswalk, canonical
  NJ student identifier) were confirmed against the live Cube connector per
  Task 4.
