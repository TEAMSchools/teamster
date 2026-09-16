# Cube description correctness and payload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct every Cube assessment member description that contradicts the
data, add a regression test that catches the next drift, and make view-scoped
`meta` the documented default so a session stops paying 161,663 bytes for a
catalog it does not need.

**Architecture:** Three independent changes under `src/cube/`. Descriptions are
corrected against `assessment-cube-reference.md`, which is the verified source
of truth and is currently _fresher_ than the YAML. A pytest guard asserts the
known-false strings stay absent. The `meta` tool already accepts `views` and
`force_refresh`; only its docstring fails to steer the model toward scoping, so
that is a docstring change, not a code change.

**Tech Stack:** Cube YAML data models, Python 3.13, pytest, `uv`, Cube Cloud
(auto-redeploys on merge to `main`).

**Spec:** `docs/superpowers/specs/2026-09-16-cube-guidance-packaging-design.md`

## Global Constraints

- Cubes carry `public: false` at the cube level; dimensions and measures use
  `public: true` only when exposed via a view. Never flip a cube to
  `public: true`.
- Put guidance in `description:`. `meta.folders` is the only Cube-rendered
  `meta.*` key — `meta.usage` and `meta.synonyms` land in `/v1/meta` but Cube
  Cloud and the chat agent do not read them.
- Field descriptions cap at about 400 characters. No dated numbers, no tables,
  no inventories — those belong in the bundled reference file with an "as of"
  date.
- Scope-bound measures carry a leading
  `Grain: ... meaningful only within {scope} ... silent-failure trap` clause
  (#4476). This is a review-checked convention with no schema enforcement.
- A description's "non-additive" note is a pre-aggregation rollup property, not
  a query-time-grain hazard. Do not let it read as "unsafe to drop a dimension."
- Never run `bq cp` of a dev-schema table into `kipptaf_marts`.
- Never commit a `zz_<username>_kipptaf_marts` dev-schema redirect. Verify with
  `grep -r "zz_" src/cube/` before pushing.
- Open files under `src/cube/` with the Read tool, never `cat` —
  `.claude/rules/cube-authoring.md` loads on a Read path match and never on a
  Bash command string.
- All Python runs through `uv run`. Never bare `python` or `pytest`.
- Every path is
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging/<path>`.
  Every git call is `git -C <worktree>`.
- Before pushing YAML, Python, or markdown:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.

---

## File Structure

| File                                                                              | Responsibility                                                                               | Change                                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/cube/model/cubes/student_assessments/student_assessments.yml`                | Assessment-level dimensions                                                                  | Modify 3 descriptions: `module_type`, `is_internal_assessment`, `category`                                                                                                                                                       |
| `src/cube/model/cubes/student_assessments/student_assessment_administrations.yml` | Administration-level dimensions                                                              | Modify 1 description: `administration_period`                                                                                                                                                                                    |
| `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`          | Score-level dimensions and measures                                                          | Modify 8 descriptions: `response_type`, `response_type_code`, `response_type_description`, `response_type_root_description`, `percent_correct`, `proficiency_level`, `performance_band_label_number`, `pct_proficient_formative` |
| `tests/cube/test_assessment_descriptions.py`                                      | Create. Regression guard asserting the known-false strings stay absent from the shipped YAML | Create                                                                                                                                                                                                                           |
| `src/cube/mcp/server.py`                                                          | MCP tool surface                                                                             | Modify the `meta` docstring only                                                                                                                                                                                                 |

Twelve descriptions across three cube files. The reviews that produced this plan
said "about 9 member descriptions" and did not split by file; the true count is
12, and `module_type` lives in `student_assessments.yml`, not in the scores
cube.

---

## Task 1: Regression guard for the false description strings

**Files:**

- Create: `tests/cube/test_assessment_descriptions.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `FALSE_STRINGS` — a `dict[str, tuple[str, ...]]` mapping a YAML
  filename to the substrings that must not appear in it. Task 2 makes this test
  pass; no later task imports from it.

- [ ] **Step 1: Write the failing test**

```python
"""Guard against known-false assessment description strings.

Each entry is a substring that shipped in a Cube `description:` and
contradicted `src/cube/mcp/project_knowledge/assessment-cube-reference.md`.
The reference file is the verified source of truth for field semantics.
"""

from pathlib import Path

import pytest

CUBE_MODEL = Path("src/cube/model/cubes/student_assessments")

FALSE_STRINGS: dict[str, tuple[str, ...]] = {
    "student_assessments.yml": (
        # module_type has 7 values: QA, TP, MQQ, CRQ, UA, ET, WPP. `CR` is not one.
        "QA, CR)",
        # is_internal_assessment is FALSE for i-Ready, DIBELS and STAR too,
        # not only for state and college.
        "FALSE for state and college.",
    ),
    "student_assessment_administrations.yml": (
        # administration_period is populated for every source except Illuminate.
        # i-Ready/DIBELS use BOY/MOY/EOY and STAR uses Fall/Winter/Spring.
        "Null for Illuminate and AP.",
    ),
    "student_assessment_scores.yml": (
        # response_type values are overall / standard / group / null.
        # `strand` is not a value.
        "strand",
        # Both strings are false, for two different reasons. On
        # percent_correct and performance_band_label_number the claim is too
        # narrow — they are null for the vendor diagnostics as well as state.
        # On response_type_code and response_type_description it is the wrong
        # shape entirely: i-Ready domain rows and DIBELS sub-measure rows now
        # POPULATE them.
        "Null for state assessments.",
        "Null for state.",
        # pct_proficient_formative covers QA, MQQ and CRQ only. Whether TP, UA,
        # ET and WPP are formative is unratified, so "all" asserts a policy
        # answer nobody made.
        "across all formative module types",
    ),
}


@pytest.mark.parametrize("filename", sorted(FALSE_STRINGS))
def test_no_false_description_strings(filename: str) -> None:
    # `description: >-` folds across lines, and prettier reflows the YAML, so a
    # raw substring match would break on rewrap. Collapse all whitespace first
    # and write every expected string on one line.
    text = " ".join((CUBE_MODEL / filename).read_text().split())
    found = [s for s in FALSE_STRINGS[filename] if s in text]
    assert not found, f"{filename} still ships false description text: {found}"
```

Every string in `FALSE_STRINGS` must be written whitespace-collapsed, on one
line, or it will never match.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_assessment_descriptions.py -v
```

Expected: 3 FAILED, one per file. Each failure names the false strings still
present. `student_assessment_scores.yml` should report 4 of them.

If a string reports as absent, the YAML changed since 2026-09-16. Re-read the
member with the Read tool, confirm against the reference file, and update
`FALSE_STRINGS` to match what actually ships before continuing.

- [ ] **Step 3: Commit the failing test**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add tests/cube/test_assessment_descriptions.py && git commit -m "test(cube): guard against known-false assessment description strings

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Correct the 12 descriptions

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessments.yml:44-47,60-63,84-87`
- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_administrations.yml:31-35`
- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml:73-76,81-84,104-105,110-113,118-119,124-125,130-132,278-283`
- Test: `tests/cube/test_assessment_descriptions.py`

**Interfaces:**

- Consumes: `FALSE_STRINGS` from Task 1 as the pass condition.
- Produces: no new members, no renames, no signature changes. Description text
  only. `pct_proficient_formative` keeps its name and its filter.

Line numbers are as of 2026-09-16. Read each member before editing; do not edit
by line number alone.

**The four `response_type*` replacements were revised once already.** They
originally said only Illuminate populates these fields, which was true when the
reviews behind this plan ran and is false now:
`fct_assessment_scores_enrollment_scoped` unions i-Ready domain rows
(`response_type = 'group'`, `response_type_code = domain_name`) and DIBELS
sub-measure rows (`'group'` for any `measure_standard` other than `Composite`).
Re-read those two branches of the model before writing the descriptions — this
area is moving, and a "correction" that restates a stale claim is worse than the
wrong description it replaces. The domain and sub-measure value lists are dated
empirical inventories, so they stay in `assessment-cube-reference.md` and never
go in a field description.

- [ ] **Step 1: Correct `student_assessments.yml`**

`module_type`, replacing "Module type for internal Illuminate assessments (e.g.,
QA, CR). Null for state and college.":

```yaml
- name: module_type
  description: >-
    Module type for internal Illuminate assessments. Seven values: QA, TP, MQQ,
    CRQ, UA, ET, WPP. Null for every non-Illuminate source. What TP, UA, ET and
    WPP stand for is an open question for the model owner — do not invent an
    expansion.
```

`is_internal_assessment`, replacing "TRUE for KIPP-created internal assessments
via Illuminate; FALSE for state and college.":

```yaml
- name: is_internal_assessment
  description: >-
    TRUE only for Illuminate (KIPP-authored interims). FALSE for state, college,
    AND the i-Ready, DIBELS and STAR vendor diagnostics despite those being used
    internally. To select a source, filter assessment_type, not this field.
```

`category`, replacing "Assessment category by format/content (e.g., CMA, CGI,
NJSLA, FAST, SAT).":

```yaml
- name: category
  description: >-
    Assessment category by format or content for Illuminate, state and college
    sources (for example CMA, CGI, NJSLA, FAST, SAT). For the i-Ready, DIBELS
    and STAR vendor diagnostics this field carries the subject instead, not a
    format.
```

- [ ] **Step 2: Correct `student_assessment_administrations.yml`**

`administration_period`, replacing the NJ/FL/College-only text. The reference
file already flags this description as covering the state and college windows
only:

```yaml
- name: administration_period
  description: >-
    Scheduling period distinguishing administrations within an academic year.
    Populated for every source except Illuminate, but the vocabulary differs by
    source, so never filter it without also scoping assessment_type. i-Ready and
    DIBELS use BOY/MOY/EOY; STAR and NJ state use Fall/Winter/Spring; FL state
    uses the FLDOE window (PM1/PM2/PM3). Null only for illuminate.
```

- [ ] **Step 3: Correct the four null-coverage descriptions in
      `student_assessment_scores.yml`**

Each of these claims null for state only. All four are null for every
non-Illuminate source.

```yaml
- name: percent_correct
  description: >-
    Percent correct. Null for state and for the i-Ready, DIBELS and STAR vendor
    diagnostics. Scope-bound — comparable only within one source, subject and
    grade.
```

```yaml
- name: response_type_code
  description: >-
    Short code identifying the response type. Populated for Illuminate
    standards, i-Ready domain names, and DIBELS measure standards. Null on the
    overall or Composite row of each source, and for STAR and every state
    source.
```

```yaml
- name: response_type_description
  description: >-
    Human-readable response-type description. Populated alongside
    response_type_code for Illuminate, for i-Ready domains (title-cased by
    initcap, so "Number And Operations"), and for DIBELS measure names. Null on
    overall rows, and for STAR and state sources.
```

```yaml
- name: response_type_root_description
  description: >-
    Description of the root (top-level) response type. Illuminate only — null
    for STAR, for state sources, and for the i-Ready and DIBELS group rows.
```

- [ ] **Step 4: Correct `response_type` in `student_assessment_scores.yml`**

This is the one the protocol tells every session to filter explicitly, so it
carries the filter-operator trap. Replacing "Response-type breakdown (e.g.,
overall, strand, standard). Null for state assessments.":

```yaml
- name: response_type
  description: >-
    Response-type breakdown. Values: overall, standard, group, null (singular,
    not standards/groups). Not additive — always filter explicitly and default
    to overall. Illuminate owns standard. i-Ready emits group per domain and
    DIBELS per sub-measure, and for i-Ready those outnumber the overall rows
    about 4.7 to 1. STAR and state are overall only. Filter nulls with operator
    notSet, never equals "null", which matches the literal string and returns
    zero rows.
```

- [ ] **Step 5: Correct the two band descriptions in
      `student_assessment_scores.yml`**

`performance_band_label_number`, replacing "Numeric ordering of the performance
band label within the band scale. Null for state assessments.":

```yaml
- name: performance_band_label_number
  description: >-
    Grain: a band number is meaningful only within its own band set — pooling
    band numbers across assessments is a silent-failure trap. Illuminate-only;
    null for state and for i-Ready, DIBELS and STAR. Not a 1-5 scale: band
    counts and cut points differ per band set, and where mastery starts differs
    too. Confirm two assessments share a band set before comparing.
```

`proficiency_level`, replacing "Proficiency band label (performance band for
internal, achievement level for state).":

```yaml
- name: proficiency_level
  description: >-
    Proficiency band label — performance band for Illuminate, achievement level
    for state, and each vendor diagnostic's own scale for i-Ready, DIBELS and
    STAR. The label strings carry many variants per band, so prefer
    performance_band_label_number within a single band set.
```

- [ ] **Step 6: Correct `pct_proficient_formative` in
      `student_assessment_scores.yml`**

Keep the name and the `module_type IN ('QA', 'MQQ', 'CRQ')` filter. Only the
word "all" is false. Do not widen the filter: whether TP, UA, ET and WPP are
formative is unratified, and widening it would invent a policy answer.

```yaml
- name: pct_proficient_formative
  description: >-
    Proficiency rate across the QA, MQQ and CRQ module types. Does NOT include
    TP, UA, ET or WPP — whether those are formative is an open question routed
    to instructional leadership, so this rate covers part of module-coded work,
    not all of it. CRQ is also available standalone as pct_proficient_crq. Built
    from additive primitives so pre-aggregations roll it up.
```

- [ ] **Step 7: Run the guard to verify it passes**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_assessment_descriptions.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Run the existing cube suite for regressions**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/ -v
```

Expected: all pass. These are YAML description changes, so nothing should move.
A failure here means a description edit broke YAML parsing.

- [ ] **Step 9: Confirm each description stays under the 400-character cap**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python -c "
import pathlib, re, sys
d = pathlib.Path('src/cube/model/cubes/student_assessments')
over = []
for f in sorted(d.glob('*.yml')):
    for m in re.finditer(r'- name: (\S+)\n\s+description: >-\n((?:\s{10}.*\n)+)', f.read_text()):
        body = ' '.join(l.strip() for l in m.group(2).splitlines())
        if len(body) > 400:
            over.append((f.name, m.group(1), len(body)))
for row in over:
    print(row)
sys.exit(0)
"
```

Expected: no output. Any row printed names a description to shorten by moving
dated detail to the reference file.

- [ ] **Step 10: Lint**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessments.yml src/cube/model/cubes/student_assessments/student_assessment_administrations.yml src/cube/model/cubes/student_assessments/student_assessment_scores.yml tests/cube/test_assessment_descriptions.py </dev/null
```

Expected: no findings.

- [ ] **Step 11: Confirm no dev-schema redirect leaked in**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && grep -r "zz_" src/cube/ ; echo "exit=$?"
```

Expected: no matches, `exit=1`.

- [ ] **Step 12: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add -u && git commit -m "fix(cube): correct 12 assessment descriptions that contradict the data

Two named values that do not exist (module_type CR, response_type strand)
and ten null-coverage or scope claims that omit the vendor diagnostics.
Corrected against assessment-cube-reference.md, which is the verified
source of truth and was fresher than the YAML.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Make view-scoped `meta` the documented default

**Files:**

- Modify: `src/cube/mcp/server.py` — the `meta` docstring only, at the function
  defined near line 364

**Interfaces:**

- Consumes: the existing
  `meta(views: list[str] | None = None, force_refresh: bool = False)` signature.
  No signature change.
- Produces: no code change. Docstring only, so no caller is affected.

The capability already exists. A full `meta` call returns 161,663 bytes and
overflows the tool-result budget; `student_assessment_scores_view` alone is
42,730 bytes. The docstring is the right home for this because
query-construction mechanics that apply to any subject belong there, and because
the connector caches the tool list at connect time, so this change reaches
existing sessions only when they reconnect.

- [ ] **Step 1: Read the current `meta` docstring**

Use the Read tool on `src/cube/mcp/server.py`, offset 360, limit 45. Do not use
`cat` — `.claude/rules/cube-authoring.md` does not cover `src/cube/mcp/`, but
the root convention for this tree still applies.

- [ ] **Step 2: Add the scoping guidance to the docstring**

Insert this as the paragraph immediately before the existing
`force_refresh=True` sentence. Keep the existing text; this adds to it.

```text
    Always pass `views` when you know which view the question needs. An
    unscoped call returns every view and overflows the tool-result budget,
    so it spills to a file instead of reaching you. One view is roughly a
    quarter of that. Only omit `views` when you genuinely need to discover
    what views exist.
```

- [ ] **Step 3: Verify the docstring renders in the tool schema**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run pytest tests/cube/test_mcp_server.py -v
```

Expected: all pass. This suite covers the tool surface, so a malformed docstring
or broken import fails here.

- [ ] **Step 4: Confirm the guidance text is actually in the built schema**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && uv run python -c "
import pathlib
t = pathlib.Path('src/cube/mcp/server.py').read_text()
i = t.find('async def meta(')
doc = t[i:i+2600]
print('HAS GUIDANCE:', 'Always pass \`views\`' in doc)
print('HAS FORCE_REFRESH NOTE:', 'force_refresh=True' in doc)
"
```

Expected: both `True`. A `False` on the first means the paragraph landed outside
the docstring.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/server.py </dev/null
```

Expected: no findings.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && git add -u && git commit -m "docs(cube): steer the meta tool toward view-scoped calls

An unscoped meta call returns 161,663 bytes and overflows the tool-result
budget, so it spills to a file instead of reaching the model. The views
parameter already exists; only the docstring failed to steer toward it.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Verify whether a member-level `title:` shortens the payload

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml` — one
  member, provisionally

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: either a `title:` convention applied across high-cost members, or a
  recorded finding that it does not work. No interface other tasks depend on.

Auto-generated `title` and `shortTitle` keys account for 19,446 bytes, about 12
percent of the payload, on strings like "Student Assessment Scores View
Performance Band Label Number". **Whether a member-level `title:` removes the
view-name prefix is unverified.** Cube may prepend the view name regardless, in
which case an override saves little and this task stops after step 3. Do not
apply overrides across the model before step 3 answers this.

Zero `title:` overrides exist in these three files today, so this is net-new.

- [ ] **Step 1: Capture the baseline payload size**

Start the dev server as a backgrounded call and poll its log, per the `cube-ops`
skill. A foreground call never exits and hangs to timeout.

```bash
cd /workspaces/teamster && mkdir -p .claude/scratch && npm --prefix src/cube run dev > .claude/scratch/cube-dev.txt 2>&1 &
```

Then poll until ready:

```bash
grep -c "is listening on 4000" /workspaces/teamster/.claude/scratch/cube-dev.txt
```

The dev server always serves the MAIN checkout, so check this branch out in the
main checkout before running it, or the branch's YAML is never exercised.

- [ ] **Step 2: Measure the current title cost**

```bash
cd /workspaces/teamster && curl -s http://localhost:4000/cubejs-api/v1/meta | uv run python -c "
import json, sys
p = json.load(sys.stdin)
total = len(json.dumps(p))
titles = 0
for c in p.get('cubes', []):
    for k in ('dimensions', 'measures'):
        for m in c.get(k, []):
            titles += len(m.get('title', '')) + len(m.get('shortTitle', ''))
print(f'total={total} title_chars={titles} pct={100*titles/total:.1f}')
"
```

Record both numbers. Expected shape: total near 161,663 and `pct` near 12.

- [ ] **Step 3: Add one override and re-measure**

Add `title:` to `performance_band_label_number`, the longest auto-generated
name:

```yaml
- name: performance_band_label_number
  title: Band number
```

Save, let the dev server hot-reload, and re-run the step 2 command. Then check
the specific member:

```bash
cd /workspaces/teamster && curl -s http://localhost:4000/cubejs-api/v1/meta | uv run python -c "
import json, sys
p = json.load(sys.stdin)
for c in p.get('cubes', []):
    for m in c.get('dimensions', []):
        if m['name'].endswith('performance_band_label_number'):
            print(m['name'], '|', m.get('title'), '|', m.get('shortTitle'))
"
```

Expected if the override works: `title` reads `Band number` with no view-name
prefix. Expected if it does not: the view name is still prepended.

- [ ] **Step 4: Decide, and record the decision**

If `title` is now short and the total dropped: keep the override, apply the same
pattern to every member whose auto-generated title exceeds 40 characters,
re-measure, and continue to step 5.

If the view name is still prepended or the total did not move: revert the one
override, and add a note to the design doc's Evidence section recording that
member-level `title:` does not reduce the payload and that the 12 percent is not
recoverable this way. Then stop — steps 5 and 6 do not apply.

```bash
cd /workspaces/teamster && git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging diff --stat
```

- [ ] **Step 5: Stop the dev server**

```bash
pkill -f 'cubejs[-]server'
```

The bracket is required, or the pattern matches the killing shell and terminates
it instead.

- [ ] **Step 6: Lint and commit, only if step 4 kept the overrides**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cube-guidance-packaging && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessment_scores.yml </dev/null && git add -u && git commit -m "perf(cube): override auto-generated titles on long assessment members

Auto-generated title and shortTitle keys cost the byte count measured in
step 2; the reduction is the step 2 figure minus the step 3 figure. Paste
both numbers into this message body before committing.

Refs #5348

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Acceptance criteria

1. `uv run pytest tests/cube/ -v` passes, including the new
   `test_assessment_descriptions.py`.
2. No description in `src/cube/model/cubes/student_assessments/` exceeds 400
   characters.
3. `grep -r "zz_" src/cube/` returns no matches.
4. The `meta` docstring directs the model to pass `views`, and
   `tests/cube/test_mcp_server.py` passes.
5. Task 4 ends with either applied `title:` overrides and a recorded byte
   reduction, or a recorded finding in the design doc that the approach does not
   work. Not with an open question.
6. `pct_proficient_formative` keeps its name and its filter. Only its
   description changed.

## After merge

Cube Cloud auto-redeploys on merge to `main`, and the next `meta` call sees the
corrected descriptions — effective staleness is zero for the YAML half.

The `server.py` docstring change is different.
`.github/workflows/deploy-cube-mcp.yaml` deploys on push to `main` when
`src/cube/mcp/**` changes, but claude.ai Custom Connector sessions cache the
tool list and keep serving the old schema indefinitely. **Tell the three pilot
users to refresh the connector** in their claude.ai connector settings. Until
they do, they keep the old docstring and no version indicator reveals it. That
gap is what the `load`-response version stamp in the packaging plan exists to
expose.

## Out of scope

- The scoped-`meta` instruction in the session protocol. That is guidance
  markdown and belongs to
  `docs/superpowers/plans/2026-09-16-cube-guidance-packaging.md`, which rewrites
  that file wholesale. This plan changes the tool's own steer only, so the two
  plans never touch the same file.
- Widening `pct_proficient_formative`'s filter. Unratified; routes to Topline
  and instructional leadership.
- Standards-code fragmentation,
  [#5349](https://github.com/TEAMSchools/teamster/issues/5349). Upstream dbt.
