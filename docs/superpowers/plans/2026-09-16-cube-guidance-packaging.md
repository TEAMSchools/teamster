# Cube guidance hardening and packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the session protocol so the four recorded failures are hard to
repeat, then package it as two skills in a required plugin so it works outside
one claude.ai Project.

**Architecture:** Hardening first, because the four failures all happened at
maximum delivery strength, so packaging alone would move a leaky protocol onto a
weaker mount. The rewrite shortens the file: defining an undefined criterion
deletes the prose that hedged around it, and converting an incident narrative
into a red flag is the same edit as compressing it. Then four layers —
organization instructions carry the trigger, `cube-data-session` carries the
protocol once, one conventions skill per domain carries routing, and Cube YAML
plus MCP docstrings carry field semantics.

**Tech Stack:** Markdown skills with YAML frontmatter, Python 3.13 with `uv` for
the generator and hash guard, a Claude plugin distributed from a private GitHub
marketplace repository, claude.ai organization instructions, the existing
`src/cube/mcp/eval` harness.

**Spec:** `docs/superpowers/specs/2026-09-16-cube-guidance-packaging-design.md`

## Global Constraints

- `SKILL.md` body stays under 500 lines; target under 800 words for
  `cube-data-session`. The "5k tokens" figure is a descriptive table cell, not a
  limit.
- A skill `description` caps at 1,024 characters and must keep a consistent
  third-person point of view. It is injected into the system prompt, so an
  inconsistent voice degrades discovery.
- Organization instructions cap at 3,000 characters and take up to 1 hour to
  propagate.
- The calibration procedure appears in exactly ONE file. Everything else points
  at it.
- Skills in a plugin reference MCP tools by fully qualified name
  (`ServerName:tool_name`). A bare `meta` fails to resolve when several servers
  are present.
- Never write a deliberately broad skill description. The root `CLAUDE.md`
  already carries a permanent countermand against
  `dbt:answering-natural-language-questions-with-dbt` for exactly that reason.
- Generated artifacts are never hand-edited. The generator is the only writer.
- A domain lives in exactly one target at a time. Assessment goes to the skill;
  grades and later domains stay in the Project format.
- No student names or identifiers in any committed file, any issue, any pull
  request, or any generated artifact.
- All Python runs through `uv run`. Never bare `python` or `pytest`.
- Every path is
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging/<path>`.
  Every git call is `git -C <worktree>`.
- Before pushing markdown, YAML, or Python:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.

---

## File Structure

| File                                                             | Responsibility                                                                                                                                           |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/cube/skills/cube-data-session/SKILL.md`                     | Create. The protocol, domain-agnostic. Sole home of the calibration gate, confidence and inference flags, the PII gate, and the session record procedure |
| `src/cube/skills/cube-data-session/session-record-template.md`   | Create. Disclosed reference, read only when writing a record                                                                                             |
| `src/cube/skills/assessment-cube-conventions/SKILL.md`           | Create. Instrument-family routing. Opens with a pointer step to the protocol                                                                             |
| `src/cube/skills/assessment-cube-conventions/reference.md`       | Create. Moved from `project_knowledge/assessment-cube-reference.md`, minus what drained to Cube YAML                                                     |
| `src/cube/skills/assessment-cube-conventions/open-decisions.md`  | Create. The 17 unratified items, disclosed                                                                                                               |
| `src/cube/skills/organization-instructions.md`                   | Create. The 3,000-character text an organization owner pastes. Version-controlled because it is load-bearing and pasted by hand                          |
| `src/cube/skills/build_targets.py`                               | Create. Generator emitting the Project-format artifacts and the hash lock                                                                                |
| `src/cube/skills/generated-lock.json`                            | Create. Path-to-sha256 map, mirroring `skills-lock.json`'s `computedHash` pattern                                                                        |
| `tests/cube/test_skill_contracts.py`                             | Create. Frontmatter limits, single-source gate check, generated-artifact hash check                                                                      |
| `src/cube/mcp/server.py`                                         | Modify. One pointer sentence in the `load` docstring; a guidance version in the `load` response payload                                                  |
| `.github/CODEOWNERS`                                             | Modify. Name an individual reviewer for `src/cube/skills/`                                                                                               |
| `.github/pull_request_template.md`                               | Modify. Add a "Skill and guidance content" section                                                                                                       |
| `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md` | Delete at graduation, in the same commit that adds the covered domain                                                                                    |
| `src/cube/mcp/project_knowledge/assessment-cube-reference.md`    | Delete at graduation                                                                                                                                     |
| `src/cube/mcp/project_knowledge/README.md`                       | Modify. Becomes the Project-format runbook for domains that have not graduated                                                                           |

`src/cube/skills/` rather than `src/cube/mcp/skills/` on purpose:
`.github/workflows/deploy-cube-mcp.yaml` fires on `src/cube/mcp/**`, so skill
edits under that path would trigger a pointless Cloud Run deploy on every
guidance change.

---

## Task 1: Define the four undefined terms

**Files:**

- Create: `src/cube/skills/definitions-draft.md` (temporary, deleted in Task 2)

**Interfaces:**

- Consumes: nothing.
- Produces: four definitions that Task 2 inlines into `SKILL.md`. Exact names:
  `CALIBRATION_PASS`, `TRIP_FLAG`, `OUT_OF_SCOPE`, `RECONSTRUCTED`.

The session record requires four judgments the protocol never defines:
`Trip flag` (4 uses, 0 definitions), `Out-of-scope` (3 uses, 0 definitions),
what counts as a calibration `[match / mismatch]`, and which reference figure to
check against. Three sessions read one attendance record three different ways,
which is an unstated criterion rather than a delivery failure.

The calibration definition below **eliminates the unknown reference figure**
rather than asking for it. That is why it also deletes about 250 words of the
Camden summer-cohort carve-out, whose own text concedes interpretation is not
that step's job.

- [ ] **Step 1: Write the four definitions**

```markdown
# Definitions (draft — inlined into SKILL.md in Task 2)

**CALIBRATION_PASS.** The calibration check confirms connectivity and data
currency. Nothing else. It passes when the query returns one or more rows.
Report three things together: the rate, the student count, and which regions are
present. A small single-region cohort with a high rate still passes — it
confirms connectivity, which is all this step is for. Zero rows during a period
with no active school week also passes; say so and continue. Never label the
result "match" or "mismatch" against a remembered figure.

**TRIP_FLAG.** A trip is any point where following this protocol changed the
answer: a filter you would have omitted, a default you would have assumed, a
field you would have read the wrong way. Record what would have gone wrong, not
that a rule exists. No trips in a session is a normal result — do not
manufacture one.

**OUT_OF_SCOPE.** A question is out of scope when it needs a data domain with no
ratified conventions loaded — that is, no `*-cube-conventions` skill covers it.
Out of scope does NOT mean refused. Answer it, label the answer exploratory with
no vetted conventions, name who owns ratifying them, and record it.

**RECONSTRUCTED.** Any per-query record written for a turn that happened before
this protocol loaded. Mark it `reconstructed — unverified` and say so in the
session summary. Do not present a reconstructed record as observed.
```

- [ ] **Step 2: Confirm the calibration definition removes the need for a named
      figure**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && grep -n "known figure\|match / mismatch\|sanity-check" src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md
```

Expected: matches in the current file. Each one is a line Task 2 deletes. If a
match survives Task 2, the definition did not actually replace it.

- [ ] **Step 3: Commit the draft**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add src/cube/skills/definitions-draft.md && git commit -m "docs(cube): define the four undefined session-record terms

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Harden the orchestrator into `cube-data-session`

**Files:**

- Create: `src/cube/skills/cube-data-session/SKILL.md`
- Create: `src/cube/skills/cube-data-session/session-record-template.md`
- Delete: `src/cube/skills/definitions-draft.md`
- Test: `tests/cube/test_skill_contracts.py`

**Interfaces:**

- Consumes: the four definitions from Task 1.
- Produces: skill name `cube-data-session`. Task 3's conventions skill points at
  that exact string. The protocol's steps are referenced nowhere else — this
  file is the only copy.

The source is 367 lines, 3,115 words. The target is under 800 words, reached by
four moves:

| Move                                                                                  | Words      |
| ------------------------------------------------------------------------------------- | ---------- |
| Delete "How to use this file" — it describes a deployment surface that stops existing | −117       |
| Delete the summer-cohort carve-out, superseded by `CALIBRATION_PASS`                  | −250       |
| Disclose the session-record template to a bundled file                                | −450       |
| Convert 4 incident narratives to red flags and a rationalization table                | −300, +250 |

- [ ] **Step 1: Write the failing contract test**

```python
"""Contracts for the Cube guidance skills."""

import re
from pathlib import Path

import pytest
import yaml

SKILLS = Path("src/cube/skills")
SKILL_NAMES = ("cube-data-session", "assessment-cube-conventions")


def _frontmatter(name: str) -> dict:
    text = (SKILLS / name / "SKILL.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{name}/SKILL.md has no YAML frontmatter"
    return yaml.safe_load(m.group(1))


def _body(name: str) -> str:
    text = (SKILLS / name / "SKILL.md").read_text()
    return re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_description_within_limit(name: str) -> None:
    desc = _frontmatter(name)["description"]
    assert 0 < len(desc) <= 1024, f"{name} description is {len(desc)} chars"


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_name_matches_directory(name: str) -> None:
    assert _frontmatter(name)["name"] == name


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_body_under_500_lines(name: str) -> None:
    lines = len(_body(name).splitlines())
    assert lines < 500, f"{name} body is {lines} lines"


def test_protocol_body_under_800_words() -> None:
    words = len(_body("cube-data-session").split())
    assert words < 800, f"cube-data-session body is {words} words"


def test_calibration_procedure_has_one_home() -> None:
    """The gate procedure lives in cube-data-session and nowhere else.

    Other files may POINT at it. Only one may describe it. The marker is the
    attendance measure the check queries.
    """
    marker = "avg_daily_attendance"
    owners = [
        p
        for p in SKILLS.rglob("*.md")
        if marker in p.read_text()
    ]
    assert owners == [SKILLS / "cube-data-session" / "SKILL.md"], (
        f"calibration procedure appears in {[str(p) for p in owners]}"
    )


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_mcp_tools_are_fully_qualified(name: str) -> None:
    """A bare tool name fails to resolve when several MCP servers are present."""
    body = _body(name)
    for tool in ("meta", "load", "sql"):
        bare = re.findall(rf"(?<![:\w]) `{tool}\(", body)
        assert not bare, f"{name} references bare `{tool}(` — qualify it"


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_no_unresolved_connector_placeholder(name: str) -> None:
    """Task 2 writes <CubeConnector>; Task 4 step 1 resolves it.

    Without this test the placeholder ships silently and every tool
    reference in the skill fails to resolve at runtime.
    """
    assert "<CubeConnector>" not in _body(name), (
        f"{name} still contains the <CubeConnector> placeholder — "
        "resolve it per Task 4 step 1"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_skill_contracts.py -v
```

Expected: errors, because neither `SKILL.md` exists yet. Every test should fail
on a missing file, not on an assertion.

- [ ] **Step 3: Write `cube-data-session/SKILL.md`**

Frontmatter first. Four genuinely distinct trigger branches, one trigger each,
and no workflow summary — a description that narrates the workflow invites
following the description instead of reading the body.

```markdown
---
name: cube-data-session
description:
  Use when working KIPP TEAM and Family data through the Cube connector — before
  the first substantive data answer in a conversation, when recording a query in
  the working-group session record, when a session wraps or a participant asks
  to file the record, and when a request turns into a document, an export, or an
  identified student roster.
version: 2026-09-16
---
```

Body. Every temporal instruction is a conversation-state predicate, because this
file may load at turn 7 and "at the start of every session" is then
unsatisfiable.

```markdown
# Cube data session protocol

## Before your first data answer

1. **Ask the participant's name in one line and wait for the answer.** The
   session record filename depends on it.
2. **Run the calibration check.** Query `<CubeConnector>:load` for
   `student_attendance_view.avg_daily_attendance`, filtered
   `is_week_end_record = true`, most recent `dates_school_week_start_date`. It
   passes when one or more rows return. Report the rate, the student count, and
   which regions are present. Zero rows in a period with no active school week
   also passes — say so and continue.
3. **Refresh the catalog, scoped.** Call `<CubeConnector>:meta` with `views` set
   to the view the question needs and `force_refresh` true. An unscoped call
   returns every view, overflows the budget, and spills to a file.

If a data question was already answered in this conversation before this
protocol loaded, run steps 1 to 3 now, then record those earlier turns as
`reconstructed — unverified`.

## Every query

- **Filter `response_type` explicitly.** Never rely on the default blend.
- **State confidence** as High, Medium, or Low, and list every default you chose
  on the participant's behalf.
- **Flag, do not invent.** When an answer needs a convention instructional
  leadership has not ratified, say so and record it as an open decision. If a
  provisional choice is unavoidable, label it provisional.
- **Record the query as it happens.** Never batch records to the end.

## Red flags — stop when you notice these

- You are about to infer the participant's name from chat history, a commit
  author, or a signature. **Stop. Ask.**
- You are about to report a network rate from a record covering one region or a
  few hundred students. **Stop. Report the count and the regions.**
- You are about to print a student name or student ID into chat. **Stop.** Write
  a file instead.
- You are about to file a session record for a session you already filed.
  **Stop. Search the folder first.**
- You are about to state a cut score, a pooling rule, or which subjects count as
  a subject, as though it were settled. **Stop. Flag it.**

## What you will tell yourself

| The thought                                                 | What is true                                               |
| ----------------------------------------------------------- | ---------------------------------------------------------- |
| This request is urgent, so calibration can wait             | Urgency is when a stale catalog costs the most             |
| I can tell their name from the conversation                 | 3 of the first 4 sessions were wrong doing exactly this    |
| They authorized the roster, so chat is fine                 | Authorization covers the request, not the delivery surface |
| I filed this session already, so I will file the correction | The connector cannot delete. A second file is permanent    |
| A 99 percent network rate looks plausible                   | Check which regions are in the row before believing it     |

## Identified data

Hold any request pairing student names or IDs with performance or status until
the participant states explicit permission and a legitimate need. Once
authorized, deliver it as a downloadable file and nothing more — never into
chat, and never into the session record. Authorization covers the request you
asked about. Reformatting the same roster continues it; a new population,
subject, or grade band is a new request.

## Definitions

<!-- Inline CALIBRATION_PASS, TRIP_FLAG, OUT_OF_SCOPE and RECONSTRUCTED
     from Task 1 here, verbatim. -->

## Session record

Write it to a Markdown file as you go, without being asked, and file it when the
session wraps. Format, filename rules, and the Drive filing procedure: read
`session-record-template.md` beside this file.

Never write a student name or ID into it.
```

Replace `<CubeConnector>` with the connector's real name. Task 4 step 1 resolves
it; leave the placeholder until then and the contract test in step 1 will not
catch it, so do not skip Task 4.

- [ ] **Step 4: Write `session-record-template.md`**

Move the session-record and Drive-filing sections out of the orchestrator
verbatim, keeping every revision rule. Those rules were earned by an incident
that left 7 permanent files across 8 days and they are the most expensive lines
in the source. Preserve in particular: search the folder before writing;
unchanged content means do not write; changed content files as `_rev2` with the
supersession note inside the file's own header; a chat resumed on a later date
is a new session, not a revision.

- [ ] **Step 5: Delete the draft and run the contract test**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && rm src/cube/skills/definitions-draft.md && uv run pytest tests/cube/test_skill_contracts.py -v -k "cube_data_session or protocol or calibration"
```

Expected: the `cube-data-session` tests pass. `assessment-cube-conventions`
tests still error on the missing file until Task 3.

- [ ] **Step 6: Verify the word count and the negation count directly**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python -c "
import pathlib, re
p = pathlib.Path('src/cube/skills/cube-data-session/SKILL.md')
body = re.sub(r'^---\n.*?\n---\n', '', p.read_text(), flags=re.DOTALL)
print('words:', len(body.split()))
print('negations:', len(re.findall(r'\b(do not|don.t|never)\b', body, re.I)))
"
```

Expected: under 800 words. Negations well under the source's 24 — prohibition is
now concentrated in the red-flag list and the rationalization table, where it is
the prescribed form, rather than scattered through prose where it drags the
forbidden behavior into context.

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add src/cube/skills tests/cube/test_skill_contracts.py && git add -u && git commit -m "feat(cube): harden the session protocol into the cube-data-session skill

Defines the four terms the session record required and never defined,
converts four recorded incidents into red flags and a rationalization
table, and rewrites every session-start instruction as a conversation-state
predicate so the protocol still works when it loads mid-conversation.

3,115 words to under 800.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: The assessment conventions skill

**Files:**

- Create: `src/cube/skills/assessment-cube-conventions/SKILL.md`
- Create: `src/cube/skills/assessment-cube-conventions/reference.md`
- Create: `src/cube/skills/assessment-cube-conventions/open-decisions.md`
- Test: `tests/cube/test_skill_contracts.py`

**Interfaces:**

- Consumes: the skill name `cube-data-session` from Task 2, referenced as a
  literal string.
- Produces: skill name `assessment-cube-conventions`. Every later domain skill
  copies this file's first line verbatim, changing only the domain.

- [ ] **Step 1: Write the frontmatter**

Sharp and keyword-dense, so a grade point average question cannot pull it. The
instrument families are both the routing axis and the words participants
actually use.

```markdown
---
name: assessment-cube-conventions
description:
  Use when a question touches KIPP TEAM and Family assessment results —
  Illuminate QA, MQQ, or CRQ; i-Ready; DIBELS; STAR; NJSLA; NJGPA; FAST; EOC —
  including proficiency, mastery, cut scores, performance bands, benchmark
  windows, standards rollups, or grade-band and school comparisons across
  Newark, Camden, Paterson, and Miami.
version: 2026-09-16
---
```

- [ ] **Step 2: Write the body, opening with the pointer step**

The first line is a step, not a cross-reference. This is what keeps the gate
procedure in one file while still running before any conventions apply.

```markdown
# Assessment conventions

1. **If `cube-data-session` has not run in this conversation, load and run it
   before answering, then return here.**
2. Identify the assessment family, then read the matching section of
   `reference.md` beside this file.

## Routing

- **Region.** Newark, Camden, and Paterson are NJ. Miami is FL.
- **Family.** `QA`, `MQQ`, or `CRQ` means Illuminate. i-Ready, DIBELS, and STAR
  each have their own section. NJSLA or NJGPA means NJ state. FAST or EOC means
  FL state.
- Select a source with `assessment_type`, never with `is_internal_assessment`.
- If the family is ambiguous, ask before querying.

Read the shared conventions in `reference.md` first, then the family section.
Each family section assumes the shared mechanics and adds only what differs.

## Coverage

This skill covers assessment only. A question needing grades, grade point
average, attendance, enrollment, operations, or staff data is `OUT_OF_SCOPE` as
`cube-data-session` defines it: answer it, label it exploratory with no ratified
conventions, name instructional leadership as the owner, and record it. Do not
refuse it — every domain is queryable by anyone Cube admits, and a governed path
that refuses what the dashboards answer gets routed around.

Conventions instructional leadership has not ratified are listed in
`open-decisions.md`. Read it when a question turns on one.
```

- [ ] **Step 3: Move the reference and split out the open decisions**

Move `src/cube/mcp/project_knowledge/assessment-cube-reference.md` to
`reference.md`, minus anything Plan A drained into Cube YAML. Move the 17-item
open-decisions list to `open-decisions.md`. Stamp both with an "as of" date,
because both carry dated empirical inventories — band-set tables, module
volumes, coverage matrices, deduplication rates — and those are what go stale.

- [ ] **Step 4: Run the full contract test**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_skill_contracts.py -v
```

Expected: all pass. `test_calibration_procedure_has_one_home` is the important
one — it fails if `reference.md` or the conventions body describes the
calibration query rather than pointing at it.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add src/cube/skills && git add -u && git commit -m "feat(cube): add the assessment conventions skill

Routing plus disclosed reference files. Opens with a pointer step to
cube-data-session so the gate procedure keeps one home and a new domain
costs one skill and zero edits to the protocol.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: The `load` pointer and the version stamp

**Files:**

- Modify: `src/cube/mcp/server.py` — the `load` docstring, and the `load` return
  payload
- Modify: `src/cube/skills/cube-data-session/SKILL.md` — replace
  `<CubeConnector>`
- Test: `tests/cube/test_mcp_server.py`

**Interfaces:**

- Consumes: the skill name `cube-data-session`.
- Produces: a `guidance_version` string key on the `load` response.
  `session-record-template.md` records it in the record header.

The gate procedure does **not** go in the docstring. The gate says "call `load`
with an attendance query before answering," but the calibration call and the
answer call are the same tool, and the docstring arrives when the model has
already decided to call `load`. `stateless_http=True` leaves no session state to
enforce against. So `load` gets one pointer sentence, and the procedure stays in
Task 2's file.

The version goes in the **response payload**, not in `meta`. A stamp in `meta`
reports the deployed version while the model obeys the connect-time-cached
docstring, so it would read current while running stale — wrong exactly when it
matters.

- [ ] **Step 1: Resolve the connector's real name**

Open claude.ai, Customize, Connectors, and read the Cube connector's exact
display name. Then in a session with the connector attached, call any Cube tool
and read the qualified name back from the tool call. Record it, and replace
`<CubeConnector>` in `cube-data-session/SKILL.md` with it.

This is an in-product check with no documentation substitute. The name is
user-side and not guaranteed stable across reinstalls, which is itself worth
noting in the skill.

- [ ] **Step 2: Add the pointer sentence to the `load` docstring**

Read `src/cube/mcp/server.py` with the Read tool and locate the `load`
docstring. Add exactly this, and nothing more:

```text
    Session protocol governs this tool. If the cube-data-session skill has not
    loaded in this conversation, load it before answering.
```

- [ ] **Step 3: Add `guidance_version` to the `load` response**

Cloud Run injects a revision name into the runtime automatically, so derive the
value from it and fall back to `"local"` when unset. Never a hand-maintained
constant — a stamp someone forgets to bump reads as verified and is worse than
none.

```python
import os

GUIDANCE_VERSION = os.environ.get("K_REVISION", "local")
```

Then include it in the `load` return value alongside the existing payload, as a
sibling key named `guidance_version`.

- [ ] **Step 4: Run the server tests**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_mcp_server.py -v
```

Expected: all pass. Add a test asserting `guidance_version` is present in the
`load` response shape if one does not already cover the return keys.

- [ ] **Step 5: Verify the pointer landed and the procedure did not**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python -c "
import pathlib
t = pathlib.Path('src/cube/mcp/server.py').read_text()
print('pointer present:', 'cube-data-session skill has not' in t)
print('procedure leaked:', 'avg_daily_attendance' in t)
print('version key:', 'guidance_version' in t)
"
```

Expected: `pointer present: True`, `procedure leaked: False`,
`version key: True`. A `True` on the second means the calibration procedure was
copied into the docstring, which is the thing this task exists to avoid.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add -u && git commit -m "feat(cube): point the load tool at the session protocol and stamp its version

One pointer sentence, not the procedure: load's docstring arrives when the
model has already decided to call load, so it cannot gate that call. The
version goes in the response payload rather than meta, because meta would
report the deployed version while the model obeys a connect-time-cached
docstring.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: The generator and the hash guard

**Files:**

- Create: `src/cube/skills/build_targets.py`
- Create: `src/cube/skills/generated-lock.json`
- Modify: `tests/cube/test_skill_contracts.py`
- Modify: `src/cube/mcp/project_knowledge/README.md`

**Interfaces:**

- Consumes: the skill directories from Tasks 2 and 3.
- Produces: `build_targets(write: bool) -> dict[str, str]`, mapping a generated
  path to its sha256. Task 6 does not use it; the test does.

One source, two targets. Assessment graduates to the skill; grades and later
domains stay in the Project format, so the generator has to keep producing
Project artifacts from skill-shaped source for as long as any domain has not
graduated. The custom-instructions block is generated too, because it is pasted
by hand today and is therefore the piece most likely to drift.

The hash guard removes the "continuous integration when the second domain lands"
trigger, which had no owner watching for it.

- [ ] **Step 1: Write the generator**

```python
"""Emit claude.ai Project-format artifacts from skill-shaped source.

One source, two targets. A domain that has not graduated to a skill still
needs Project knowledge files and a custom-instructions block. Generated
artifacts are never hand-edited; this module is their only writer.
"""

import hashlib
import json
from pathlib import Path

SKILLS = Path("src/cube/skills")
OUT = Path("src/cube/skills/build")
LOCK = SKILLS / "generated-lock.json"

PROJECT_DOMAINS = ("assessment-cube-conventions",)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        return text.split("\n---\n", 1)[1].lstrip("\n")
    return text


def _render_knowledge(domain: str) -> str:
    """Concatenate the protocol and one domain's files into one flat document."""
    parts = [
        "<!-- GENERATED by src/cube/skills/build_targets.py. Do not edit. -->",
        _strip_frontmatter((SKILLS / "cube-data-session" / "SKILL.md").read_text()),
        (SKILLS / "cube-data-session" / "session-record-template.md").read_text(),
        _strip_frontmatter((SKILLS / domain / "SKILL.md").read_text()),
        (SKILLS / domain / "reference.md").read_text(),
        (SKILLS / domain / "open-decisions.md").read_text(),
    ]
    return "\n\n".join(p.strip() for p in parts) + "\n"


def _render_instructions() -> str:
    text = (SKILLS / "organization-instructions.md").read_text()
    return (
        "<!-- GENERATED by src/cube/skills/build_targets.py. Do not edit. -->\n"
        + _strip_frontmatter(text)
    )


def build_targets(write: bool = False) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for domain in PROJECT_DOMAINS:
        outputs[f"build/{domain}-project-knowledge.md"] = _render_knowledge(domain)
    outputs["build/project-custom-instructions.md"] = _render_instructions()

    hashes = {
        path: hashlib.sha256(body.encode()).hexdigest()
        for path, body in outputs.items()
    }

    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        for path, body in outputs.items():
            (SKILLS / path).write_text(body)
        LOCK.write_text(
            json.dumps({"version": 1, "generated": hashes}, indent=2, sort_keys=True)
            + "\n"
        )

    return hashes


if __name__ == "__main__":
    for path, digest in sorted(build_targets(write=True).items()):
        print(f"{digest[:12]}  {path}")
```

- [ ] **Step 2: Add the drift test**

Append to `tests/cube/test_skill_contracts.py`:

```python
def test_generated_artifacts_match_their_lock() -> None:
    """Re-run the generator and compare hashes without writing.

    A mismatch means either a source file changed without regenerating, or a
    generated artifact was hand-edited. Both are the drift this guards.
    """
    import json
    import sys

    sys.path.insert(0, str(SKILLS))
    from build_targets import build_targets  # noqa: PLC0415

    recorded = json.loads((SKILLS / "generated-lock.json").read_text())["generated"]
    assert build_targets(write=False) == recorded, (
        "generated artifacts are stale — run: "
        "uv run python src/cube/skills/build_targets.py"
    )
```

- [ ] **Step 3: Run it and verify the test fails first**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_skill_contracts.py::test_generated_artifacts_match_their_lock -v
```

Expected: FAIL on the missing `generated-lock.json`.

- [ ] **Step 4: Generate, then verify the test passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python src/cube/skills/build_targets.py && uv run pytest tests/cube/test_skill_contracts.py -v
```

Expected: hashes printed, then all tests pass.

- [ ] **Step 5: Prove the guard catches a hand edit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && printf '\nhand edit\n' >> src/cube/skills/build/project-custom-instructions.md && uv run pytest tests/cube/test_skill_contracts.py::test_generated_artifacts_match_their_lock -v ; git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging checkout -- src/cube/skills/build/project-custom-instructions.md
```

Expected: FAIL, naming the stale artifact, then the `git checkout` restores it.
This step proves the guard works; a passing test here means the guard is inert.

- [ ] **Step 6: Rewrite `project_knowledge/README.md` as the Project-format
      runbook**

It currently describes uploading two hand-maintained files. It becomes: which
domains have not graduated, that their artifacts are generated under
`src/cube/skills/build/`, that nothing there is hand-edited, and the upload
steps. Delete the six "non-negotiables" block entirely — it duplicates the
protocol steps, it has already drifted (it lists `what "progress" means` as an
open decision, which appears in the reference file and not in the orchestrator's
list), and its job moves to organization instructions in Task 9.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/skills/build_targets.py tests/cube/test_skill_contracts.py src/cube/mcp/project_knowledge/README.md </dev/null && git add src/cube/skills tests/cube/test_skill_contracts.py && git add -u && git commit -m "feat(cube): generate Project-format artifacts from skill source with a hash guard

One source, two targets. A domain that has not graduated still needs
Project knowledge and a custom-instructions block, and the block is the
piece most likely to drift because it is pasted by hand. The lock file
mirrors skills-lock.json's computedHash pattern, so drift fails a test
instead of waiting for someone to notice.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Plugin manifest and the private marketplace

**Files:**

- Create: `src/cube/skills/.claude-plugin/plugin.json`
- Create: `docs/superpowers/specs/2026-09-16-marketplace-repo-setup.md`

**Interfaces:**

- Consumes: the two skill directories.
- Produces: a plugin package layout the marketplace repository consumes. No
  Python interface.

`teamster` is public, and **organization marketplaces do not accept public
repositories.** So `teamster` authors and a separate private repository
publishes. The plugin also carries the Cube connector, so a new cohort member
installs once rather than adding a connector URL and completing an authorization
flow separately.

- [ ] **Step 1: Verify the manifest schema before writing it**

I have not verified the plugin manifest schema in this session, so do not write
it from memory. Read the current schema from the plugin documentation — the
Plugins page and the administrator extensions page — and note the required keys
and the expected directory layout. Record what you found at the top of
`docs/superpowers/specs/2026-09-16-marketplace-repo-setup.md`, with the source
URL and the date you read it.

Known limits to confirm while you are there: 50 MB per plugin archive and 100
plugins per manual marketplace on the organization path; 200 MB uncompressed and
500 plugins per marketplace on the user path. Nothing here comes close, so a
limit failure means the layout is wrong, not the size.

- [ ] **Step 2: Write the manifest to the verified schema**

Include the two skills and the Cube connector. Use the connector name resolved
in Task 4 step 1, and point the connector at the existing Cloud Run URL — the
same one the three pilot users already use manually.

- [ ] **Step 3: Grep the manifest for secret-shaped values before it goes
      anywhere**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && grep -nE '_SECRET|_KEY|_TOKEN|-----BEGIN|op://' src/cube/skills/.claude-plugin/plugin.json ; echo "exit=$?"
```

Expected: no matches, `exit=1`. This is the one genuinely new exposure the
public-repository split introduces: a manifest copied from a working local
configuration can carry a real credential into a public repo. The outbound hook
would also block a write containing one, but do not rely on that.

- [ ] **Step 4: Write the marketplace setup runbook**

`docs/superpowers/specs/2026-09-16-marketplace-repo-setup.md` records, for
whoever does this after you: create the private or internal repository, add it
as an organization marketplace, set the organization-wide preference to
`Not available`, then grant per group. The organization-wide default matters —
multi-group membership resolves to **most permissive**, so a group-level
`Not available` is defeated by any other group the person belongs to. In a
network with regional and functional groups, multi-group membership is the norm.

Also record that skill provisioning is Owner or Primary Owner only, while
group-level plugin access is Admin and above. Those are different role gates, so
confirm who holds Primary Owner before planning the rollout rather than during
it.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/superpowers/specs/2026-09-16-marketplace-repo-setup.md </dev/null && git add src/cube/skills docs/superpowers/specs && git commit -m "feat(cube): add the plugin manifest and marketplace setup runbook

Organization marketplaces reject public repositories, so teamster authors
and a private repo publishes.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: The review gate

**Files:**

- Modify: `.github/CODEOWNERS`
- Modify: `.github/pull_request_template.md`

**Interfaces:**

- Consumes: the `src/cube/skills/` path from Task 2.
- Produces: no code interface.

`claude-code-review.yaml` triggers on `src/`, `tests/`, `scripts/`, and
`.github/workflows/`, and this repo negates with `!**/*.md` rather than
`paths-ignore`. So guidance markdown gets no automated review wherever it lands.
`.github/CLAUDE.md` also records a markdown-excluded deploy path firing anyway,
so do not assume the negation behaves as designed either — check it.

`src/cube/` belongs to `@TEAMSchools/analytics-engineers`, who can catch "this
contradicts the data" but are not tasked with catching "this states an
unratified convention as settled."

- [ ] **Step 1: Add the CODEOWNERS line**

Name the individual, not a team. CODEOWNERS is last-match-wins, so this line
goes after the existing `src/cube/` line or it has no effect.

```text
/src/cube/skills/ @anthonygwalters
```

- [ ] **Step 2: Verify the rule resolves to the intended owner**

```bash
cd /workspaces/teamster && grep -n 'src/cube' .github/CODEOWNERS
```

Expected: the `src/cube/` team line first, then the `src/cube/skills/`
individual line. If the order is reversed, the team line wins and the gate does
nothing.

- [ ] **Step 3: Add the pull-request-template section**

Match the template's existing domain-gated pattern, which uses "skip if no X
changes" headings.

```markdown
### Skill and guidance content _(skip if unrelated)_

- [ ] A person with instructional-domain competence reviewed the substance, not
      only the diff. Automated review does not run on markdown.
- [ ] No convention is stated as settled unless instructional leadership
      ratified it. Unratified conventions belong in `open-decisions.md`.
- [ ] Generated artifacts under `src/cube/skills/build/` were regenerated, not
      hand-edited.
```

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .github/pull_request_template.md </dev/null && git add -u && git commit -m "chore(github): add a review gate for skill and guidance content

Automated review excludes markdown, and analytics-engineers are not tasked
with catching an unratified convention stated as settled.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Evaluate the gate and the triggers

**Files:**

- Create: `src/cube/mcp/eval/cases/gate_compliance.json`
- Create: `src/cube/mcp/eval/cases/trigger_matrix.json`

**Interfaces:**

- Consumes: the shipped skills and the `load` docstring pointer.
- Produces: two recorded result sets. These gate nothing else in this plan; they
  decide whether the design's central bet holds.

Everything about the gate so far is argument. These two runs turn it into a
number. The harness is already hermetic — `tools=[]`, `strict_mcp_config=True`,
`setting_sources=[]`, custom system prompt — and Cube is stubbed, so no
warehouse and no student data are touched. Read `src/cube/mcp/eval/README.md`
first; it records that neither runner reproduces the claude.ai connector's own
host prompt, which is the surface the pilot actually uses, so treat the result
as directional for that surface.

- [ ] **Step 1: Write the gate-compliance cases**

Three arms, 5 runs each, 15 total. Ask an assessment question cold, with no
prompt hinting at the protocol.

| Arm       | Condition                                               |
| --------- | ------------------------------------------------------- |
| `control` | No guidance at all                                      |
| `pointer` | The `load` docstring pointer sentence only              |
| `full`    | Pointer plus organization instructions naming the skill |

Measure: did calibration run before the first substantive answer. **Always
include the control.** If the control does not exhibit the failure, there is
nothing to fix and the whole gate design is solving a problem that is not there.

- [ ] **Step 2: Run it and record the counts**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest src/cube/mcp/eval -v -k gate_compliance
```

Read every flagged match manually. A pass rate is not evidence on its own at 5
runs per arm; the transcripts are.

- [ ] **Step 3: Write the trigger matrix**

Per skill, 3 to 5 queries covering should-fire, should-not-fire, and ambiguous.
The should-not-fire cases matter most, because trigger competition is the named
scaling limit on the roadmap and there is no built-in runner for this.

```json
{
  "assessment-cube-conventions": {
    "should_fire": [
      "How did Newark do on the last interim?",
      "What share of 6th graders hit proficient on i-Ready this fall?",
      "Compare NJSLA math proficiency across our three NJ regions."
    ],
    "should_not_fire": [
      "What is the average grade point average for 11th graders?",
      "How many staff vacancies are open in Camden?",
      "What was attendance last week?"
    ],
    "ambiguous": ["How are our students performing this year?"]
  }
}
```

- [ ] **Step 4: Record the results in the design doc**

Append a Results section to
`docs/superpowers/specs/2026-09-16-cube-guidance-packaging-design.md` with both
counts and the date. If `pointer` and `full` do not beat `control`, say so
plainly and reopen the gate design rather than shipping on the argument.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add src/cube/mcp/eval docs/superpowers/specs && git commit -m "test(cube): evaluate gate compliance and skill trigger accuracy

Three arms with a no-guidance control, plus should-fire and should-not-fire
queries per skill. Trigger competition is the named scaling limit on the
roadmap and has no built-in runner.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Roll out and graduate assessment

**Files:**

- Create: `src/cube/skills/organization-instructions.md`
- Delete: `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`
- Delete: `src/cube/mcp/project_knowledge/assessment-cube-reference.md`

**Interfaces:**

- Consumes: everything above.
- Produces: the shipped state.

Graduation is atomic. The Project source files for assessment are deleted in the
**same commit** that adds assessment to the skills, or there are two live copies
of one domain's conventions with different update paths, which is the collision
this design exists to prevent.

- [ ] **Step 1: Write the organization instructions**

Under 3,000 characters. It holds the trigger and nothing procedural, so it
cannot diverge from the skill.

```markdown
KIPP TEAM and Family internal data questions go through the governed path.

When a request touches internal student or staff data — assessment results,
attendance, enrollment, grades, staff roster — load and run the
`cube-data-session` skill before your first substantive answer. Do this however
simple or urgent the request looks.

Query internal data through the Cube connector, not through raw warehouse tools.
Cube enforces each person's row-level access; a raw query does not.

Never print a student name or student ID into chat. If an identified roster is
authorized, deliver it as a downloadable file and nothing more.
```

Keep it to those three ideas. Every sentence added here is a sentence that can
drift from the skill.

- [ ] **Step 2: Verify the character count**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python -c "
import pathlib, re
t = pathlib.Path('src/cube/skills/organization-instructions.md').read_text()
body = re.sub(r'^---\n.*?\n---\n', '', t, flags=re.DOTALL).strip()
print('chars:', len(body))
assert len(body) <= 3000, 'over the 3,000-character cap'
"
```

Expected: well under 3,000.

- [ ] **Step 3: Graduate assessment in one commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git rm src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md src/cube/mcp/project_knowledge/assessment-cube-reference.md && uv run python src/cube/skills/build_targets.py && uv run pytest tests/cube/ -v
```

Expected: all tests pass with the Project files gone. A failure here means
something still reads them.

- [ ] **Step 4: Commit the graduation**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add src/cube/skills && git add -u && git commit -m "feat(cube): graduate assessment from Project knowledge to skills

Deletes the Project source files in the same commit that ships the skills,
so one domain never has two live copies with different update paths.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Hand the organization owner their steps**

These are not commands anyone can run from here. The Claude CLI is not on the
path in this environment, and every one of these is a console action.

1. Organization settings, Capabilities: confirm **Code execution and file
   creation** and **Skills** are both on. Skills do not work without code
   execution.
2. Organization settings, Organization and access: paste the organization
   instructions from step 1. Allow up to 1 hour to propagate.
3. Create the private or internal marketplace repository and add it as an
   organization marketplace.
4. Set the plugin's organization-wide preference to **Not available**, then
   grant it to the pilot group. Not the reverse — most-permissive wins across
   groups.
5. Set the plugin to **Required** for that group, so it cannot be toggled off. A
   provisioned bare skill can be switched off by the user; only a required
   plugin cannot.

**Sequence security scanning after go-live, not before.** A skill that fails a
scan, or whose scan has not finished, is blocked from use — and a skill body
describing data-access procedure is plausible bait for a heuristic looking for
data leaving the organization. Ship first, then enable scanning, or budget time
for an appeal.

- [ ] **Step 6: Answer the two open in-product questions with the first
      install**

Have one **new** cohort member install the plugin, then check Customize,
Connectors and count the Cube rows. That answers whether a plugin-bundled
connector collides with a manually added one. In the same session, open the
required plugin and check whether the individual skill's toggle is live — that
answers whether the guidance is enforceable or merely advisory.

Record both answers in the design doc's Open questions section. Do this
**before** step 7, because step 7 depends on knowing the answer.

- [ ] **Step 7: Migrate the three pilot users**

Migrate them. Do not freeze them. Freezing looks cheaper and is a trap: once the
Project source files are deleted no pull request can reach them, but their live
Project is untouched and simply stops receiving corrections forever. The next
ratified decision would reach everyone except the three people who piloted it,
and nobody would remember in eighteen months that those three are frozen.

For each: confirm the plugin is installed and the skill is enabled, ask one
assessment question, and confirm the answer runs calibration and cites the
skill's protocol. Then archive their Project.

- [ ] **Step 8: Tell every connector user to refresh**

Plan A's `server.py` change and Task 4's both reach users only on reconnect.
claude.ai Custom Connector sessions cache the tool list and keep serving the old
schema indefinitely. Have each user open their claude.ai connector settings and
refresh the Cube connector. The `guidance_version` on the `load` response is how
you check afterward who is still stale.

- [ ] **Step 9: Name an owner and a cadence for reading the version stamps**

A detection mechanism with no reader is theater. The version lines land in
session records in the shared Drive folder, and nobody is currently named as
reading them. Assign one person a weekly check: read new session records,
extract the two version lines, and flag anyone more than one release behind.
This environment has scheduling primitives if you want it automated, but an
owner matters more than automation.

---

## Acceptance criteria

1. `uv run pytest tests/cube/ -v` passes, including every contract in
   `test_skill_contracts.py`.
2. `cube-data-session/SKILL.md` body is under 800 words and under 500 lines.
3. Both skill descriptions are 1,024 characters or fewer and read in a
   consistent third-person voice.
4. `test_calibration_procedure_has_one_home` passes, so the calibration
   procedure exists in exactly one file.
5. The four terms are defined where the session record asks for them:
   `CALIBRATION_PASS`, `TRIP_FLAG`, `OUT_OF_SCOPE`, `RECONSTRUCTED`.
6. No instruction in `cube-data-session/SKILL.md` assumes it loaded at the start
   of the conversation.
7. `src/cube/mcp/server.py` contains the pointer sentence, contains
   `guidance_version`, and does **not** contain `avg_daily_attendance`.
8. Regenerating with `build_targets.py` produces no diff against
   `generated-lock.json`, and hand-editing a generated file fails that test.
9. A new domain can be added by creating one skill directory and editing zero
   lines of `cube-data-session/SKILL.md`.
10. The gate-compliance run has recorded counts for all three arms including the
    control, and they are written into the design doc.
11. Assessment exists in exactly one target. `src/cube/mcp/project_knowledge/`
    holds no assessment files.
12. Both in-product open questions have recorded answers.

## Out of scope

- Grades, grade point average, and operations domains. They stay in the Project
  format, and the generator keeps emitting their artifacts.
- The wholesale move of reference content into Cube YAML. See the design doc.
- Whether `pct_proficient_formative` covers three module types or seven. A
  Topline definitional question for instructional leadership, not a defect.
- Standards-code fragmentation,
  [#5349](https://github.com/TEAMSchools/teamster/issues/5349).
- Small-cell suppression,
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237).
- **A Claude Code hook enforcing the gate deterministically for the data team.**
  Hooks are inert in chat but live in Cowork and Claude Code, so this is
  genuinely available and would give the data team the one thing a matched skill
  cannot promise — a gate that cannot be skipped. It is left out because the
  pilot audience is in chat, where it does nothing, and because Task 8 should
  first establish whether the gate needs that much help. Revisit once the data
  team is the audience.

## Risks this plan does not remove

**One person.** The plan describes parallel targets, not parallel people. Tasks
1 through 9 all route through the same person, who is also the named review gate
in Task 7. The mitigation inside the plan is that hardening cuts the document
nearly in half and the hash guard catches mechanical drift, so review is only
ever about substance. That reduces the load; it does not remove the dependency.

**The end-of-SY27 goal is a stretch, not a schedule.** Assessment took about ten
recorded sessions and four rounds of documentation pull requests, with Cube
views already built. Five or six domains remain against roughly nine to ten
months, and operations very likely needs new dbt marts and Cube modeling rather
than guidance iteration. Either cut the domain count, lower the maturity bar
below assessment's, or add people — but do not let anyone plan other work
against the date as a commitment.

**Rollout stays partly unverifiable.** The connector caches its tool list at
connect time with no push mechanism, so a user on a stale connector must
reconnect manually. The version stamps make that visible; nothing makes it
automatic.
