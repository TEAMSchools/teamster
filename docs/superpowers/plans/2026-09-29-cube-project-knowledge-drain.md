# Cube Project-Knowledge Drain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the assessment facts from the claude.ai Project markdown into
Cube member text, MCP tool docstrings and one server behavior, prove the move
with tests and an eval, and trim the markdown to process and policy.

**Architecture:** Each Cube member gets a `description:` (what it is, kept equal
to its dbt twin when it reads one column) and, where needed, a
`meta.ai_context:` (how to use it). Two view-level overrides carry view-specific
guidance on shared members. `server.py` gains 5 docstring sentences and an
empty-result note on `load`. Schema tests pin the text; eval family 4 measures
whether it changes model behavior.

**Tech Stack:** Cube 1.7.43 YAML models, dbt properties YAML, Python 3.13 (MCP
server, pytest, eval harness on `claude-agent-sdk`), Node (Cube's schema
compiler), `uv`, `trunk`.

**Spec:**
`docs/superpowers/specs/2026-09-10-cube-project-knowledge-drain-design.md` (read
it with this plan; every member's wording lives in its _Per-member drafts_
tables, and this plan points at those rows instead of repeating them).

## Global Constraints

- Work only in the worktree
  `/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-project-knowledge-drain`,
  branch `cristinabaldor/feat/claude-cube-project-knowledge-drain`. Use
  `git -C <worktree>` and absolute worktree paths on every call. In this plan,
  `<worktree>` means that path and `<scratchpad>` means the session scratchpad
  directory from the system prompt.
- Always `uv run` for Python, dbt and pytest; never bare `python` or `dbt`.
  Never bare `uv run pytest`: run only `tests/cube/`.
- Member wording is copied **verbatim** from the spec's _Per-member drafts_
  tables (the `description:` and `meta.ai_context:` columns). If a draft reads
  wrong while you implement it, stop and ask; do not reword silently.
- No point-in-time numbers in YAML: no score volumes, percentages or year
  ranges. Qualitative wording only ("a small share", "about a third").
- Never write a bare "vendor" in member text. Write "vendor diagnostic (i-Ready,
  DIBELS, STAR)" on first use in a string, or name the sources.
- Name the population a member covers ("Illuminate only; null for every other
  source"), not what it excludes.
- Every `ai_context` value, including view overrides, is 2,000 characters or
  less.
- When a Cube member reads one column directly (`sql: <column>` or
  ``sql: "{CUBE}.`<column>`"``), its dbt `description:` is identical text. Where
  the current dbt text holds a true fact the Cube draft lacks, stop and ask
  whether to add it to both; never drop a dbt-only fact silently.
- One home per fact: a fact moved into Cube or `server.py` is deleted from the
  project-knowledge markdown in the same PR (Task 12).
- Never write PII values (student names, `student_number`, other school-facing
  ids) into commits, PR text, prompts or fixtures. `.claude/rules/ferpa-pii.md`
  governs.
- Stage with `git add -u` plus explicit paths for new files; never `git add -A`.
- Before pushing SQL, YAML or markdown, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.
- Commit messages follow conventional commits and end with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. If a
  hook blocks `git commit -m`, write the message to the session scratchpad and
  use `git commit -F <file>`.

## Review Focus

1. **A dbt twin loses a fact.** Several dbt descriptions (for example
   `enrollment_resolution`, `response_type_code`) say more than their Cube
   twins. Overwriting dbt with the shorter Cube draft would delete true
   documentation. Task 2 to Task 5 each include a step that diffs the old dbt
   text against the draft and stops on any fact the draft lacks.
2. **YAML that loads but compiles differently.** A folded scalar with a stray
   `:` or `#`, or an include written as an object with the wrong key, passes
   `yaml.safe_load` and breaks Cube's compiler, which would break the prod
   deploy on merge. Task 1 adds a compile test through Cube's own schema
   compiler.
3. **An override on the wrong include.** `staff_lead_teacher_full_name` is
   exposed through a `prefix: true` join; an override written on the wrong
   `join_path` block lands on nothing, with no error. Task 6's test resolves
   each override to its view member name, and Task 14's REST check reads it
   back.
4. **The empty-result note on a response that is not a result.** `load` can
   return an error payload or a payload with no `data` key. The note must leave
   those untouched rather than raise. Task 9 tests both.
5. **The Paterson stub matching the wrong query.** The eval returns 0 rows only
   for a Paterson query; a match on too wide a string would empty other prompts'
   results and corrupt their scores. Task 11 tests the matcher on a non-Paterson
   query.

---

## File Structure

| File                                                                                                                                                                                                                             | Change | Responsibility                                                                                      |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------- |
| `src/cube/compile-meta.js`                                                                                                                                                                                                       | create | Compile a Cube model directory with Cube's schema compiler and print the views' `/meta`-shaped JSON |
| `tests/cube/test_cube_schema.py`                                                                                                                                                                                                 | modify | 4 new schema tests (phrases, dbt twins, `ai_context` length, override hiding) and a compile test    |
| `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`                                                                                                                                                         | modify | Scores cube member text; new `count_assessments` measure                                            |
| `src/cube/model/cubes/student_assessments/student_assessments.yml`                                                                                                                                                               | modify | Assessments cube member text                                                                        |
| `src/cube/model/cubes/student_assessments/student_assessment_administrations.yml`                                                                                                                                                | modify | Administrations cube member text                                                                    |
| `src/cube/model/cubes/conformed/locations.yml`, `src/cube/model/cubes/courses/courses.yml`                                                                                                                                       | modify | Shared cube member text                                                                             |
| `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`                                                                                                                                                    | modify | View text, view `ai_context`, 2 overrides, `count_assessments` include                              |
| `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`, `src/dbt/kipptaf/models/marts/dimensions/properties/{dim_assessments,dim_assessment_administrations,dim_locations,dim_courses}.yml` | modify | dbt twins                                                                                           |
| `.claude/rules/cube-authoring.md`                                                                                                                                                                                                | modify | Replace the `meta.folders` rule; add twin rule, placement procedure, override rule                  |
| `src/cube/mcp/server.py`                                                                                                                                                                                                         | modify | 5 docstring sentences; `_with_empty_result_note`                                                    |
| `tests/cube/test_mcp_server.py`                                                                                                                                                                                                  | modify | Docstring anchors; empty-result note                                                                |
| `src/cube/mcp/eval/traps.py`                                                                                                                                                                                                     | create | Family 4 trap predicates, importable                                                                |
| `src/cube/mcp/eval/prompts_assessment.yaml`                                                                                                                                                                                      | create | Family 4 prompts                                                                                    |
| `src/cube/mcp/eval/arms.py`, `run_eval_cc.py`, `scorer.py`, `README.md`                                                                                                                                                          | modify | Family 4 arms, stub, metrics, scoring                                                               |
| `src/cube/mcp/eval/fixtures/meta_pre_drain.json`                                                                                                                                                                                 | create | Arm A catalog, compiled from `origin/main`                                                          |
| `tests/cube/test_eval_traps.py`                                                                                                                                                                                                  | create | Unit tests for the trap predicates and the Paterson matcher                                         |
| `src/cube/mcp/project_knowledge/{assessment-cube-reference,assessment-cube-orchestrator,README}.md`                                                                                                                              | modify | The trim                                                                                            |

---

### Task 1: Schema-test scaffolding and the compile check

**Files:**

- Create: `src/cube/compile-meta.js`
- Modify: `tests/cube/test_cube_schema.py` (append)

**Interfaces:**

- Produces: `node src/cube/compile-meta.js <modelDir>` prints
  `{"cubes": [<view>...]}` to stdout, each view shaped like a REST `/meta` cube
  entry (`name`, `type`, `description`, `meta`, `measures`, `dimensions`, each
  member with `name`, `description`, `meta`). Exits non-zero on a compile error.
- Produces, in `tests/cube/test_cube_schema.py`: the registries
  `TWINS: dict[tuple[str, str], tuple[str, str]]` (cube, member) → (dbt model,
  column) and `PHRASES: dict[str, list[str]]` keyed `"<cube>.<member>"` or
  `"<view>"`, both empty after this task; later tasks add entries.

- [ ] **Step 1: Install Cube's node modules in the worktree**

The worktree has no `src/cube/node_modules`.

Run:
`cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-project-knowledge-drain/src/cube && npm ci 2>&1 | tail -n 3`
Expected: `added ... packages`, no errors. Then
`node -e "console.log(require('./node_modules/@cubejs-backend/schema-compiler/package.json').version)"`
prints `1.7.43`.

- [ ] **Step 2: Write `src/cube/compile-meta.js`**

```js
// Compile a Cube model directory with Cube's own schema compiler and print the
// views as REST /meta-shaped JSON. Used by the schema compile test and by the
// eval's catalog builder. Usage: node compile-meta.js <modelDir>
const fs = require("fs");
const path = require("path");
const { prepareCompiler } = require(
  path.join(__dirname, "node_modules", "@cubejs-backend", "schema-compiler"),
);

function walk(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) =>
      e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
    );
}

async function main() {
  const modelDir = path.resolve(process.argv[2] || "model");
  const files = walk(modelDir)
    .filter((f) => /\.(yml|yaml|js)$/.test(f))
    .map((f) => ({
      fileName: path.relative(modelDir, f),
      content: fs.readFileSync(f, "utf8"),
    }));
  const repo = {
    localPath: () => modelDir,
    dataSchemaFiles: async () => files,
  };
  const { compiler, metaTransformer } = prepareCompiler(repo, {});
  await compiler.compile();
  const visible = (m) => m.isVisible !== false && m.public !== false;
  const member = (m) => ({
    name: m.name,
    title: m.title,
    type: m.type,
    description: m.description,
    meta: m.meta,
  });
  const cubes = metaTransformer.cubes
    .map((c) => c.config)
    .filter((c) => c.type === "view")
    .map((c) => ({
      name: c.name,
      title: c.title,
      type: c.type,
      description: c.description,
      meta: c.meta,
      measures: c.measures.filter(visible).map(member),
      dimensions: c.dimensions.filter(visible).map(member),
      segments: [],
    }));
  process.stdout.write(JSON.stringify({ cubes }));
}

main().catch((e) => {
  process.stderr.write(`compile failed: ${e.message}\n`);
  process.exit(1);
});
```

- [ ] **Step 3: Append the tests to `tests/cube/test_cube_schema.py`**

Add at the end of the file:

```python
import json
import re
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).parents[2]
DBT_MODELS_DIR = REPO_ROOT / "src" / "dbt" / "kipptaf" / "models"
AI_CONTEXT_MAX = 2000

# (cube, member) -> (dbt model, column). A Cube member that reads one column
# directly carries the same description as that column in dbt. Tasks 2-5 add
# entries as they rewrite each member.
TWINS: dict[tuple[str, str], tuple[str, str]] = {}

# "<cube>.<member>" or "<view>" -> phrases that must appear in that member's
# description or ai_context (case-insensitive, whitespace-collapsed), so a later
# edit cannot drop a moved fact silently. Tasks 2-6 add entries.
PHRASES: dict[str, list[str]] = {}


def _norm(text: str | None) -> str:
    return " ".join((text or "").split())


def _cube_docs() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in (CUBE_MODEL_DIR / "cubes").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for cube in doc.get("cubes", []):
            docs[cube["name"]] = cube
    return docs


def _view_docs() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in (CUBE_MODEL_DIR / "views").rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for view in doc.get("views", []):
            docs[view["name"]] = view
    return docs


def _members(cube: dict) -> dict[str, dict]:
    return {m["name"]: m for m in cube.get("dimensions", []) + cube.get("measures", [])}


def _resolve_member(cubes: dict[str, dict], cube_name: str, member: str) -> dict | None:
    """Find a member on a cube, following `extends` (staff_lead_teacher)."""
    cube = cubes.get(cube_name)
    while cube is not None:
        found = _members(cube).get(member)
        if found is not None:
            return found
        parent = cube.get("extends")
        cube = cubes.get(parent) if parent else None
    return None


def _dbt_column(model: str, column: str) -> dict:
    for path in DBT_MODELS_DIR.rglob("*.yml"):
        doc = yaml.safe_load(path.read_text()) or {}
        for m in doc.get("models", []) or []:
            if m.get("name") == model:
                for c in m.get("columns", []):
                    if c.get("name") == column:
                        return c
    raise AssertionError(f"dbt column {model}.{column} not found")


def _ai_contexts() -> list[tuple[str, str]]:
    """Every ai_context in the model: cube members, views, view overrides."""
    out: list[tuple[str, str]] = []
    for name, cube in _cube_docs().items():
        for m in _members(cube).values():
            text = (m.get("meta") or {}).get("ai_context")
            if text:
                out.append((f"{name}.{m['name']}", text))
    for name, view in _view_docs().items():
        text = (view.get("meta") or {}).get("ai_context")
        if text:
            out.append((name, text))
        for block in view.get("cubes", []):
            for inc in block.get("includes", []) or []:
                if isinstance(inc, dict):
                    text = (inc.get("meta") or {}).get("ai_context")
                    if text:
                        out.append((f"{name}:{inc['name']}", text))
    return out


def test_moved_facts_keep_their_key_phrases() -> None:
    cubes, views = _cube_docs(), _view_docs()
    missing: list[str] = []
    for key, phrases in PHRASES.items():
        if key in views:
            view = views[key]
            text = _norm(view.get("description")) + " " + _norm(
                (view.get("meta") or {}).get("ai_context")
            )
            for block in view.get("cubes", []):
                for inc in block.get("includes", []) or []:
                    if isinstance(inc, dict):
                        text += " " + _norm((inc.get("meta") or {}).get("ai_context"))
        else:
            cube_name, member_name = key.split(".", 1)
            member = _resolve_member(cubes, cube_name, member_name)
            assert member is not None, f"{key}: member not found"
            text = _norm(member.get("description")) + " " + _norm(
                (member.get("meta") or {}).get("ai_context")
            )
        for phrase in phrases:
            if _norm(phrase).lower() not in text.lower():
                missing.append(f"{key}: {phrase!r}")
    assert not missing, "moved facts missing:\n" + "\n".join(missing)


_ONE_COLUMN = re.compile(r"^\s*(?:\{CUBE\}\.)?`?(\w+)`?\s*$")


def test_twinned_members_match_their_dbt_description() -> None:
    cubes = _cube_docs()
    mismatches: list[str] = []
    for (cube_name, member_name), (model, column) in TWINS.items():
        member = _members(cubes[cube_name])[member_name]
        read = _ONE_COLUMN.match(str(member.get("sql", "")))
        assert read and read.group(1) == column, (
            f"{cube_name}.{member_name} does not read {column} directly"
        )
        cube_text = _norm(member.get("description"))
        dbt_text = _norm(_dbt_column(model, column).get("description"))
        if cube_text != dbt_text:
            mismatches.append(
                f"{cube_name}.{member_name} vs {model}.{column}:\n"
                f"  cube: {cube_text}\n  dbt:  {dbt_text}"
            )
    assert not mismatches, "\n".join(mismatches)


def test_ai_context_fits_the_cap() -> None:
    too_long = [
        f"{key}: {len(text)} chars"
        for key, text in _ai_contexts()
        if len(text) > AI_CONTEXT_MAX
    ]
    assert not too_long, (
        f"ai_context over {AI_CONTEXT_MAX} chars (Cube truncates silently):\n"
        + "\n".join(too_long)
    )


def test_view_overrides_do_not_hide_cube_ai_context() -> None:
    """An include-level override replaces the member's whole meta in that view,
    so it must restate any ai_context the cube member already carries."""
    cubes = _cube_docs()
    hidden: list[str] = []
    for view_name, view in _view_docs().items():
        for block in view.get("cubes", []):
            cube_name = str(block["join_path"]).split(".")[-1].strip()
            for inc in block.get("includes", []) or []:
                if not isinstance(inc, dict) or "meta" not in inc:
                    continue
                member = _resolve_member(cubes, cube_name, inc["name"])
                assert member is not None, (
                    f"{view_name}: override on {cube_name}.{inc['name']} "
                    "matches no member"
                )
                base = _norm((member.get("meta") or {}).get("ai_context"))
                override = _norm((inc.get("meta") or {}).get("ai_context"))
                if base and base not in override:
                    hidden.append(f"{view_name}: {cube_name}.{inc['name']}")
    assert not hidden, "overrides hide a cube-level ai_context:\n" + "\n".join(hidden)


_COMPILER = REPO_ROOT / "src" / "cube" / "node_modules" / "@cubejs-backend" / "schema-compiler"


@pytest.mark.skipif(
    not _COMPILER.exists() or shutil.which("node") is None,
    reason="Cube node_modules not installed (npm ci in src/cube)",
)
def test_model_compiles_with_cube() -> None:
    out = subprocess.run(
        ["node", str(REPO_ROOT / "src" / "cube" / "compile-meta.js"), str(CUBE_MODEL_DIR)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert out.returncode == 0, out.stderr[-2000:]
    names = {c["name"] for c in json.loads(out.stdout)["cubes"]}
    assert "student_assessment_scores_view" in names
```

- [ ] **Step 4: Run the new tests**

Run:
`cd <worktree> && uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15`
Expected: all PASS. The registries are empty, no `ai_context` exists yet, and
the compile test compiles the current model.

- [ ] **Step 5: Prove the compile test catches a broken model**

Temporarily add a line `      - name: broken` with no `sql:` under `dimensions:`
in `student_assessment_scores.yml`, rerun
`uv run pytest tests/cube/test_cube_schema.py::test_model_compiles_with_cube -v`,
confirm it FAILS with a compile error, then revert the line
(`git -C <worktree> diff --stat` shows only the 2 new files and the test file).

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/compile-meta.js tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add src/cube/compile-meta.js tests/cube/test_cube_schema.py
git -C <worktree> commit -m "test(cube): add schema tests for moved facts, dbt twins and ai_context"
```

---

### Task 2: Scores cube dimensions and their dbt twins

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`
- Modify: `tests/cube/test_cube_schema.py` (`TWINS`, `PHRASES`)

**Interfaces:**

- Consumes: `TWINS`, `PHRASES`, `_norm` from Task 1.
- Produces: `meta.ai_context` on the scores-cube dimensions that the spec drafts
  one for.

Members, all in the spec's _Scores cube (`student_assessment_scores`)_ table:
`response_type`, `response_type_code`, `response_type_description`,
`response_type_root_description`, `performance_band_label_number`,
`proficiency_level`, `is_mastery`, `scale_score`, `enrollment_resolution`,
`date_taken`. `date_taken` reads a `CAST`, so it has no twin.

- [ ] **Step 1: Add the registry entries (the failing test)**

In `tests/cube/test_cube_schema.py`, set:

```python
TWINS.update({
    ("student_assessment_scores", c): ("fct_assessment_scores_enrollment_scoped", c)
    for c in [
        "response_type",
        "response_type_code",
        "response_type_description",
        "response_type_root_description",
        "performance_band_label_number",
        "proficiency_level",
        "is_mastery",
        "scale_score",
        "enrollment_resolution",
    ]
})

PHRASES.update({
    "student_assessment_scores.response_type": ["not_taken", "Not additive across values", "default to overall"],
    "student_assessment_scores.response_type_code": ["8.EE.C.8b", "an empty string, not null", "never average", "group on response_type_description"],
    "student_assessment_scores.response_type_description": ["whitespace variants"],
    "student_assessment_scores.response_type_root_description": ["Florida's own standards", "Illuminate standard rows only"],
    "student_assessment_scores.performance_band_label_number": ["Illuminate only; null for every other source", "Not comparable across assessments", "across response types"],
    "student_assessment_scores.proficiency_level": ["Tested Out", "Graduation Ready", "Tier-movement rates are not comparable"],
    "student_assessment_scores.is_mastery": ["Early On is a looser bar", "Illuminate rate mixes different bars", "Mid or Above Grade Level instead"],
    "student_assessment_scores.scale_score": ["compresses at higher grades", "not a percent of the BOY score"],
    "student_assessment_scores.enrollment_resolution": ["Filter to subject_section"],
    "student_assessment_scores.date_taken": ["dates_date_day and academic_year"],
})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 20`
Expected: `test_moved_facts_keep_their_key_phrases` and
`test_twinned_members_match_their_dbt_description` FAIL, listing these members.

- [ ] **Step 3: Check each dbt description for facts the draft lacks**

For each twinned member, print both texts side by side:

```bash
cd <worktree> && uv run python - <<'PY'
import yaml
fct = yaml.safe_load(open("src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml"))
cols = {c["name"]: c.get("description", "") for m in fct["models"] for c in m.get("columns", [])}
for c in ["response_type","response_type_code","response_type_description","response_type_root_description","performance_band_label_number","proficiency_level","is_mastery","scale_score","enrollment_resolution"]:
    print(f"--- {c}\n{' '.join(cols[c].split())}\n")
PY
```

Compare each against the spec's `description:` draft. If the dbt text states a
true fact the draft omits (for example `enrollment_resolution` explaining what
`subject_section` and `homeroom` mean), stop and ask the user whether to add it
to both. Do not continue with a member until that is settled.

- [ ] **Step 4: Write the Cube text**

For each member, replace its `description:` with the spec's `description:` cell,
and add `meta.ai_context:` with the spec's `meta.ai_context:` cell when that
cell is not `—`. Use folded scalars. Example for `response_type`:

```yaml
- name: response_type
  description: >-
    Response-type breakdown. Never null; overall (every source), group
    (Illuminate, i-Ready and DIBELS), standard and not_taken (Illuminate only).
    not_taken marks an assessment a student was assigned and never sat. Not
    additive across values.
  sql: response_type
  type: string
  public: true
  meta:
    ai_context: >-
      Filter it on every query; default to overall unless a standard or group
      breakdown is asked for.
```

Keep `sql:`, `type:` and `public:` unchanged on every member.

- [ ] **Step 5: Write the dbt twins**

In `fct_assessment_scores_enrollment_scoped.yml`, set each twinned column's
`description:` to the exact Cube `description:` text from Step 4 (folded
scalar). Change nothing else in that file.

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 20`
Expected: all PASS, including `test_model_compiles_with_cube`.

- [ ] **Step 7: Validate the dbt YAML**

Invoke the `dbt-local-dev` skill, then run
`uv run dbt parse --project-dir src/dbt/kipptaf 2>&1 | tail -n 5`. Expected:
completes with no YAML or property errors.

- [ ] **Step 8: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessment_scores.yml src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): split scores-cube dimension text into description and ai_context"
```

---

### Task 3: Scores cube measures, including `count_assessments`

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml:20-45`
  (the `student_assessment_scores` includes)
- Modify: `tests/cube/test_cube_schema.py` (`PHRASES`)

**Interfaces:**

- Produces: measure `student_assessment_scores.count_assessments`, exposed on
  the view as `student_assessment_scores_view.count_assessments`. Task 11's
  traps and prompts do not reference it; Task 14 queries it.

Members, from the spec's _Scores cube_ table: `count_assigned`, `count_taken`,
`count_scored`, `pct_taken`, `pct_proficient`, `count_students`,
`count_assessments` (new), `pct_proficient_formative`. `avg_scale_score` and
`avg_percent_correct` are "Present" and unchanged. Measures have no dbt twin.

- [ ] **Step 1: Add the phrase entries (the failing test)**

```python
PHRASES.update({
    "student_assessment_scores.count_assigned": ["widest of 3 nested counts", "use count_taken"],
    "student_assessment_scores.count_taken": ["DIBELS Tested Out subtests", "how many assessments were taken"],
    "student_assessment_scores.count_scored": ["denominator of pct_proficient", "the n the rate rests on"],
    "student_assessment_scores.pct_taken": ["meaningful only within Illuminate", "Filter assessment_type to illuminate"],
    "student_assessment_scores.pct_proficient": ["comparable across sources", "never multiply it by count_assigned"],
    "student_assessment_scores.count_students": ["has timed out at standard grain", "count_taken"],
    "student_assessment_scores.count_assessments": ["not sittings", "Illuminate only", "thin base"],
    "student_assessment_scores.pct_proficient_formative": ["about a third of module-coded Illuminate scores", "Not \"all internal checkpoints\""],
})
```

- [ ] **Step 2: Run the tests to see them fail**

Run:
`uv run pytest tests/cube/test_cube_schema.py::test_moved_facts_keep_their_key_phrases -v 2>&1 | tail -n 15`
Expected: FAIL, including `count_assessments: member not found`.

- [ ] **Step 3: Rewrite the measure text**

For each measure, set `description:` and `meta.ai_context:` from the spec rows.
Move each "COUNT(*) over the unique PK … additive, so pre-aggregations roll it
up" sentence out of `description:` into a YAML comment above the measure. For
`count_students`, move the "switch to count_distinct_approx (HLL)…" sentence
into a YAML comment the same way. Leave `sql:`, `type:`, `filters:` and
`public:` unchanged.

- [ ] **Step 4: Add `count_assessments`**

Insert after `count_students`:

```yaml
- name: count_assessments
  description: >-
    Distinct Illuminate assessments in the filtered set — not sittings, not
    scored responses. Illuminate only: every other source has no
    source_assessment_id, so it reads 0 there.
  sql: "{student_assessment_administrations.source_assessment_id}"
  type: count_distinct
  public: true
  # Same join-forcing filters as the other counts, so every measure
  # shares one CTE (see count_assigned).
  filters:
    - sql: "{student_assessments.assessment_key} IS NOT NULL"
    - sql: "{regions.region_key} IS NOT NULL"
  meta:
    ai_context: >-
      Use this for "how many times was this assessed". A standard resting on 1
      assessment is a thin base for a trend; say so rather than trending it.
```

In the view, add `- count_assessments` to the `student_assessment_scores`
includes, directly after `- count_students`. Do not add it to
`proficiency_rollup`.

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15`
Expected: all PASS, including the compile test.

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessment_scores.yml src/cube/model/views/student_assessments/student_assessment_scores_view.yml tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): add count_assessments and move measure guidance to ai_context"
```

---

### Task 4: Assessments cube and `dim_assessments` twins

**Files:**

- Modify: `src/cube/model/cubes/student_assessments/student_assessments.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml`
- Modify: `tests/cube/test_cube_schema.py`

Members, from the spec's _Assessments cube (`student_assessments`)_ table:
`assessment_type` (reads `` {CUBE}.`type` ``), `is_internal_assessment`,
`module_type`, `module_code`, `academic_subject`, `grade_level_tested`. All 6
are twins.

- [ ] **Step 1: Add the registry entries (the failing test)**

```python
TWINS.update({
    ("student_assessments", "assessment_type"): ("dim_assessments", "type"),
    **{("student_assessments", c): ("dim_assessments", c) for c in [
        "is_internal_assessment", "module_type", "module_code",
        "academic_subject", "grade_level_tested",
    ]},
})
PHRASES.update({
    "student_assessments.assessment_type": ["computer-adaptive", "select a source"],
    "student_assessments.is_internal_assessment": ["Illuminate (KIPP-authored interims) only", "Filter assessment_type instead"],
    "student_assessments.module_type": ["UA (Unit Assessment)", "not documented", "Do not expand TP, ET or WPP"],
    "student_assessments.module_code": ["DIBELS: Composite", "Always pair it with academic_subject", "median date_taken"],
    "student_assessments.academic_subject": ["Math and Reading", "Text Study", "open decision"],
    "student_assessments.grade_level_tested": ["0 is kindergarten", "end-of-course", "filter grade_level instead"],
})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 20`
Expected: the phrase and twin tests FAIL for these 6 members.

- [ ] **Step 3: Check the dbt descriptions for missing facts**

Print the 6 current dbt descriptions from `dim_assessments.yml` (same script
shape as Task 2 Step 3, reading `type` for `assessment_type`). Stop and ask on
any true fact the drafts lack.

- [ ] **Step 4: Write the Cube text**

Set each member's `description:` and `meta.ai_context:` from the spec rows. For
`assessment_type`, the description is the shipped value list plus the spec's
added sentences, in one paragraph.

- [ ] **Step 5: Write the dbt twins**

Set each column's `description:` in `dim_assessments.yml` to the exact Cube
text, including `type` for `assessment_type`.

- [ ] **Step 6: Run the tests, parse dbt, lint and commit**

```bash
uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15   # all PASS
uv run dbt parse --project-dir src/dbt/kipptaf 2>&1 | tail -n 5      # no errors
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessments.yml src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessments.yml tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): rewrite assessments-cube text and its dbt twins"
```

---

### Task 5: Administrations and shared cubes, and their twins

**Files:**

- Modify:
  `src/cube/model/cubes/student_assessments/student_assessment_administrations.yml`
- Modify: `src/cube/model/cubes/conformed/locations.yml`
- Modify: `src/cube/model/cubes/courses/courses.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/{dim_assessment_administrations,dim_locations,dim_courses}.yml`
- Modify: `tests/cube/test_cube_schema.py`

Members, from the spec's _Administrations cube_ and _Shared cubes_ tables:
`administration_period`, `source_assessment_id`, `locations.grade_band`,
`courses.is_foundations`. `courses.discipline`, the `students` identifiers and
`staff.full_name` are "Present" and unchanged. `locations` and `courses` are
shared cubes: their text reaches every view that includes them, so it must hold
on every view.

- [ ] **Step 1: Add the registry entries (the failing test)**

```python
TWINS.update({
    ("student_assessment_administrations", "administration_period"): ("dim_assessment_administrations", "administration_period"),
    ("student_assessment_administrations", "source_assessment_id"): ("dim_assessment_administrations", "source_assessment_id"),
    ("locations", "grade_band"): ("dim_locations", "grade_band"),
    ("courses", "is_foundations"): ("dim_courses", "is_foundations"),
})
PHRASES.update({
    "student_assessment_administrations.administration_period": ["Outside Round", "FL end-of-course and science: PM3", "not the max date_taken", "use MOY"],
    "student_assessment_administrations.source_assessment_id": ["Illuminate only; null for every other source", "count_assessments"],
    "locations.grade_band": ["a school attribute, not a student's grade", "use grade_level"],
    "courses.is_foundations": ["not a record of intervention services delivered"],
})
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15`
Expected: the phrase and twin tests FAIL for these 4 members.

- [ ] **Step 3: Check the dbt descriptions for missing facts**

Print the 4 current dbt descriptions and compare. Stop and ask on any true fact
the drafts lack.

- [ ] **Step 4: Write the Cube text and the dbt twins**

Set `description:` and `meta.ai_context:` from the spec rows; set each dbt
column's `description:` to the same text.

- [ ] **Step 5: Run the tests, parse dbt, lint and commit**

```bash
uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15
uv run dbt parse --project-dir src/dbt/kipptaf 2>&1 | tail -n 5
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/cubes/student_assessments/student_assessment_administrations.yml src/cube/model/cubes/conformed/locations.yml src/cube/model/cubes/courses/courses.yml src/dbt/kipptaf/models/marts/dimensions/properties/dim_assessment_administrations.yml src/dbt/kipptaf/models/marts/dimensions/properties/dim_locations.yml src/dbt/kipptaf/models/marts/dimensions/properties/dim_courses.yml tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): rewrite administrations and shared-cube text and their dbt twins"
```

---

### Task 6: The view — description, `ai_context` and 2 overrides

**Files:**

- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
- Modify: `tests/cube/test_cube_schema.py`

**Interfaces:**

- Consumes: `courses.is_foundations`'s cube-level `ai_context` from Task 5,
  which the override must restate.
- Produces: view members `staff_lead_teacher_full_name` and `is_foundations`
  whose REST `meta` is `{"aiContext": ...}`, checked in Task 14.

Text, all from the spec's _The view (`student_assessment_scores_view`)_ section
and its override table: the view `description:` (863 characters), the view
`ai_context:` (1,050 characters), and the 2 override values.

- [ ] **Step 1: Add the phrase entry (the failing test)**

```python
PHRASES.update({
    "student_assessment_scores_view": [
        "Enrollment-scoped",
        "group covers Illuminate, i-Ready and DIBELS",
        "There is no growth measure",
        "calibration difference",
        "which sitting counts is an open decision",
        "release lag",
        "spiral review",
        "resolve a name against staff_directory",
        "the only intervention signal on this view",
    ],
})
```

- [ ] **Step 2: Run the test to see it fail**

Run:
`uv run pytest tests/cube/test_cube_schema.py::test_moved_facts_keep_their_key_phrases -v 2>&1 | tail -n 15`
Expected: FAIL listing the view phrases.

- [ ] **Step 3: Write the view text**

Replace the view's `description:` (lines 3-17) with the spec's `description:`
text. Add `ai_context:` as the first key under the existing `meta:` block (line
159), before `folders:`:

```yaml
meta:
  ai_context: >-
    Totals will not reconcile to vendor-diagnostic or state reports, ...
  folders:
```

using the spec's full `ai_context:` text.

- [ ] **Step 4: Write the 2 overrides**

In the include block
`join_path: student_assessment_scores.student_section_enrollments.staff_lead_teacher`
(line 95), replace `- full_name` with:

```yaml
- name: full_name
  meta:
    ai_context: >-
      Stored Last, First. Resolve a name against staff_directory before
      filtering; a zero-row result is not proof the teacher has no students.
```

In the include block
`join_path: student_assessment_scores.student_section_enrollments.course_sections.courses`
(line 72), replace `- is_foundations` with:

```yaml
- name: is_foundations
  meta:
    ai_context: >-
      The only intervention signal on this view; there is no program- or
      MTSS-tracking dimension. Treat it as course enrollment, not a record of
      intervention services delivered.
```

- [ ] **Step 5: Prove the override guard works**

Temporarily delete the sentence "Treat it as course enrollment, not a record of
intervention services delivered." from the `is_foundations` override, run
`uv run pytest tests/cube/test_cube_schema.py::test_view_overrides_do_not_hide_cube_ai_context -v`,
confirm it FAILS naming `courses.is_foundations`, then restore the sentence.

- [ ] **Step 6: Run the tests, lint and commit**

```bash
uv run pytest tests/cube/test_cube_schema.py -v 2>&1 | tail -n 15   # all PASS
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/model/views/student_assessments/student_assessment_scores_view.yml tests/cube/test_cube_schema.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): add the assessment view's ai_context and 2 view overrides"
```

---

### Task 7: The authoring rule

**Files:**

- Modify: `.claude/rules/cube-authoring.md`

Open it with the Read tool (it carries conventions for this edit).

- [ ] **Step 1: Replace the `meta.folders` bullet**

Replace the bullet that starts **"`meta.folders` is the only Cube-rendered
`meta.*` key."** with:

```markdown
- **`description:` says what a member is; `meta.ai_context:` says how to use
  it.** `meta.folders` is the only key Cube Cloud renders, but every `meta.*`
  key reaches the model, because our MCP server returns each cube's `/meta`
  entry unchanged. Use `ai_context` for usage guidance, including synonyms and
  acronyms; do not invent other keys. It is capped at 2,000 characters and
  truncated silently past that (`tests/cube/test_cube_schema.py` enforces the
  cap). Only our MCP server and REST clients see `ai_context`; the SQL API
  serves `description` alone, as Postgres column comments.
- **A member that reads one column has a dbt twin.** When its `sql:` is
  `<column>` or `` {CUBE}.`<column>` ``, its `description:` equals that dbt
  column's `description:`, and the pair is registered in `TWINS` in
  `tests/cube/test_cube_schema.py`, which fails on any difference. Edit both
  sides together.
- **Where a new fact goes.** Work down the list and stop at the first match: (1)
  a point-in-time number: delete it or say it qualitatively; (2) process or
  unratified policy: the project-knowledge markdown, and Cube may say only that
  the decision is open; (3) derivable live (coverage): delete the specifics; (4)
  holds for every view (query mechanics): the `load` or `meta` docstring; (5)
  about reading the answer and not tied to one member: the view's `ai_context`;
  (6) a definition: the member's `description:`; (7) an instruction: the
  member's `ai_context`. When 6 and 7 both fit, ask whether the sentence is true
  and useful against the raw dbt column: if so, `description:`; if it depends on
  Cube or tells the agent what to do, `ai_context`.
- **View-specific guidance on a shared member goes in a view override.** Give
  the include an object form (`- name: <member>` with a `meta:` block). The
  override replaces the member's whole `meta` in that view only, and REST
  `/meta` returns it as `aiContext`, not `ai_context`. If the cube member also
  carries an `ai_context`, the override must restate it; a schema test fails
  otherwise.
```

- [ ] **Step 2: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/rules/cube-authoring.md </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "docs(cube): replace the meta.folders authoring rule with the ai_context split"
```

---

### Task 8: Docstring sentences on `load` and `meta`

**Files:**

- Modify: `src/cube/mcp/server.py:369-420` (`meta` docstring) and `:444-522`
  (`load` docstring)
- Test: `tests/cube/test_mcp_server.py` (append)

**Interfaces:**

- Produces: the 5 sentences below, as exact docstring text. Task 11's arm A
  removes them by exact match, so they must appear verbatim, each on lines that
  wrap only at spaces.

The 5 sentences, quoted in the spec's _Server changes → Docstrings_:

- `load`, filter-operators paragraph: `equals "null"` matches the literal string
  and returns zero rows; filter a null with `notSet`.
- `load`, Grain paragraph: A query with no measure groups by its dimensions, so
  identical rows collapse into one; add a count or the primary key to see every
  row.
- `load`, PII paragraph: Student views return only the schools the user can
  access; before describing a result as network-wide, check which regions or
  schools it covers.
- `meta`: Refresh before concluding a member is missing.
- `meta`: Members may carry `meta.ai_context` (`aiContext` on some view-specific
  members): usage rules written for you. Read and follow a member's `ai_context`
  before building a query that uses it.

- [ ] **Step 1: Write the failing test**

Append to `tests/cube/test_mcp_server.py`:

```python
LOAD_DOC_SENTENCES = [
    '`equals "null"` matches the literal string and returns zero rows; filter a null with `notSet`.',
    "A query with no measure groups by its dimensions, so identical rows collapse into one; add a count or the primary key to see every row.",
    "Student views return only the schools the user can access; before describing a result as network-wide, check which regions or schools it covers.",
]
META_DOC_SENTENCES = [
    "Refresh before concluding a member is missing.",
    "Members may carry `meta.ai_context` (`aiContext` on some view-specific members): usage rules written for you. Read and follow a member's `ai_context` before building a query that uses it.",
]


def _tool_descriptions(server: ModuleType) -> dict[str, str]:
    tools = asyncio.run(server.mcp.list_tools())
    return {t.name: " ".join((t.description or "").split()) for t in tools}


def test_load_and_meta_docstrings_carry_the_drained_mechanics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    desc = _tool_descriptions(server)
    for sentence in LOAD_DOC_SENTENCES:
        assert sentence in desc["load"], sentence
    for sentence in META_DOC_SENTENCES:
        assert sentence in desc["meta"], sentence
```

- [ ] **Step 2: Run it to see it fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py::test_load_and_meta_docstrings_carry_the_drained_mechanics -v 2>&1 | tail -n 8`
Expected: FAIL on the first sentence.

- [ ] **Step 3: Add the sentences**

In `load`'s docstring: append the first sentence to the paragraph that ends
"SQL-style `=`/`IN`/`LIKE` won't parse."; append the second to the paragraph
starting "Grain:", after "…refers to pre-aggregation rollup, not query-time
grain.)"; append the third to the PII paragraph after "…gated separately from
the open `staff_directory` roster." In `meta`'s docstring: append the fourth
sentence to the paragraph ending "Pass `force_refresh=True` after a model
deploy.", and add the fifth as a new paragraph after the "Grain/scope:"
paragraph. Keep the docstrings' existing 4-space indentation and wrap width.

- [ ] **Step 4: Run the whole server suite**

Run: `uv run pytest tests/cube/test_mcp_server.py -v 2>&1 | tail -n 8` Expected:
all PASS.

- [ ] **Step 5: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/server.py tests/cube/test_mcp_server.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): add the drained query mechanics to the load and meta docstrings"
```

---

### Task 9: The empty-result note on `load`

**Files:**

- Modify: `src/cube/mcp/server.py` (new helper beside `_with_default_timezone`;
  `load` body at `:523-530`)
- Test: `tests/cube/test_mcp_server.py` (append)

**Interfaces:**

- Produces: `EMPTY_RESULT_NOTE: str` and
  `_with_empty_result_note(payload: dict[str, Any]) -> dict[str, Any]`, a pure
  function. Task 11's eval stub imports both through `arms.load_server()`.

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_load_result_gets_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTHKIT_DOMAIN", raising=False)
    server = _load_server(monkeypatch)
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")

    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return {"data": [], "annotation": {}}

    monkeypatch.setattr(server, "_request", fake_request)
    out = asyncio.run(server.load(MagicMock(), {"measures": ["x.count"]}))
    assert out["note"] == server.EMPTY_RESULT_NOTE
    assert out["data"] == []


def test_non_empty_and_non_result_payloads_are_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    rows = {"data": [{"x.count": "3"}]}
    assert "note" not in server._with_empty_result_note(dict(rows))
    error = {"error": "Continue wait"}
    assert server._with_empty_result_note(dict(error)) == error
    assert server._with_empty_result_note({"data": None}) == {"data": None}
```

- [ ] **Step 2: Run them to see them fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -k "empty_load_result or non_empty_and" -v 2>&1 | tail -n 8`
Expected: FAIL with `AttributeError: ... EMPTY_RESULT_NOTE`.

- [ ] **Step 3: Implement**

Beside `_with_default_timezone` in `server.py`:

```python
EMPTY_RESULT_NOTE = (
    "0 rows. The data may not exist for this slice, or your access may not "
    "include it. Check which regions and schools come back before concluding "
    "the data does not exist."
)


def _with_empty_result_note(payload: dict[str, Any]) -> dict[str, Any]:
    """Add a note to a load result with an empty data array; leave any other
    payload (rows, errors, no data key) unchanged."""
    data = payload.get("data")
    if isinstance(data, list) and not data:
        return {**payload, "note": EMPTY_RESULT_NOTE}
    return payload
```

Change `load`'s body to wrap the result:

```python
    email = await _get_user_email(ctx)
    result = await _request(
        "POST",
        "/load",
        json={"query": _with_default_timezone(query)},
        email=email,
        poll=True,
    )
    return _with_empty_result_note(result)
```

- [ ] **Step 4: Check whether Cube says when access removed rows**

Before committing, check Cube's `/v1/load` response for an access-filter signal,
so the note can name the cause instead of offering both. Search the compiled SQL
of a default-denied query (`sql` tool output shows `rlsAccessDenied` for a full
deny, per the `cube-ops` skill) and the `load` response keys. If a reliable
signal exists only for a full deny, leave the note as written and record the
finding in the PR body; do not add branching the tests do not cover.

- [ ] **Step 5: Run the suite, lint and commit**

```bash
uv run pytest tests/cube/test_mcp_server.py -v 2>&1 | tail -n 8   # all PASS
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/server.py tests/cube/test_mcp_server.py </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "feat(cube): note empty load results so a zero is not read as no data"
```

---

### Task 10: Eval catalogs for arms A and B

**Files:**

- Create: `src/cube/mcp/eval/fixtures/meta_pre_drain.json`
- Modify: `src/cube/mcp/eval/arms.py`

**Interfaces:**

- Consumes: `src/cube/compile-meta.js` from Task 1.
- Produces: `arms.load_assessment_meta(which: str) -> dict[str, Any]` where
  `which` is `"pre"` (reads the committed fixture) or `"post"` (compiles the
  working tree's `src/cube/model` by running `compile-meta.js`), each returning
  `{"cubes": [<student_assessment_scores_view>]}`.

- [ ] **Step 1: Build the arm A fixture from `origin/main`**

```bash
cd <worktree>
tmp=$(mktemp -d)
git archive origin/main src/cube/model | tar -x -C "$tmp"
mkdir -p src/cube/mcp/eval/fixtures
node src/cube/compile-meta.js "$tmp/src/cube/model" \
  | uv run python -c "import json,sys; d=json.load(sys.stdin); d['cubes']=[c for c in d['cubes'] if c['name']=='student_assessment_scores_view']; json.dump(d, sys.stdout, indent=1, sort_keys=True)" \
  > src/cube/mcp/eval/fixtures/meta_pre_drain.json
rm -rf "$tmp"
```

Expected: the file exists, holds exactly 1 view, and
`rg -c ai_context src/cube/mcp/eval/fixtures/meta_pre_drain.json` prints nothing
(no `ai_context` on `main`).

- [ ] **Step 2: Check the fixture for PII**

It holds member names and descriptions only. Confirm no student values:
`rg -n "[0-9]{6,}" src/cube/mcp/eval/fixtures/meta_pre_drain.json` returns
nothing.

- [ ] **Step 3: Add the loader to `arms.py`**

```python
_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ASSESSMENT_VIEW = "student_assessment_scores_view"


def load_assessment_meta(which: str) -> dict[str, Any]:
    """The assessment view's /meta entry: "pre" is the committed pre-drain
    fixture (origin/main before this PR); "post" compiles the working tree."""
    import json
    import subprocess

    if which == "pre":
        return json.loads((_FIXTURES / "meta_pre_drain.json").read_text())
    if which != "post":
        raise ValueError(f"which must be 'pre' or 'post', got {which!r}")
    out = subprocess.run(
        ["node", str(_REPO_ROOT / "src" / "cube" / "compile-meta.js"),
         str(_REPO_ROOT / "src" / "cube" / "model")],
        capture_output=True, text=True, timeout=180, check=True,
    )
    full = json.loads(out.stdout)
    return {"cubes": [c for c in full["cubes"] if c["name"] == _ASSESSMENT_VIEW]}
```

- [ ] **Step 4: Smoke-test both loaders**

```bash
cd <worktree> && uv run python -c "
import sys; sys.path.insert(0, 'src/cube/mcp/eval'); import arms
pre, post = arms.load_assessment_meta('pre'), arms.load_assessment_meta('post')
print(len(str(pre)), len(str(post)), 'ai_context' in str(post))"
```

Expected: two sizes, `post` larger, and `True`.

- [ ] **Step 5: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/eval/arms.py </dev/null
git -C <worktree> add src/cube/mcp/eval/fixtures/meta_pre_drain.json
git -C <worktree> add -u
git -C <worktree> commit -m "test(cube): build eval catalogs for the pre- and post-drain assessment view"
```

---

### Task 11: Eval family 4 — traps, prompts, arms, stub and metrics

**Files:**

- Create: `src/cube/mcp/eval/traps.py`
- Create: `src/cube/mcp/eval/prompts_assessment.yaml`
- Create: `tests/cube/test_eval_traps.py`
- Modify: `src/cube/mcp/eval/scorer.py`, `src/cube/mcp/eval/arms.py`,
  `src/cube/mcp/eval/run_eval_cc.py`, `src/cube/mcp/eval/README.md`

**Interfaces:**

- Consumes: `arms.load_assessment_meta` (Task 10); `EMPTY_RESULT_NOTE` and
  `_with_empty_result_note` (Task 9); `LOAD_DOC_SENTENCES`-equivalent text in
  the docstrings (Task 8).
- Produces: `traps.TRAPS: dict[str, Callable[[list[dict], str], bool]]` (each
  returns `True` when the trap **fired**);
  `traps.is_paterson_query(query: dict) -> bool`;
  `arms.build_assessment_arms(server) -> dict[str, dict]` with keys `A4_pre`,
  `B4_post`, `C4_skill`, each
  `{"instructions", "tools", "meta", "empty_note": bool}`; scorer records with
  `trap` and `trap_fired`.

- [ ] **Step 1: Write the failing trap tests**

Create `tests/cube/test_eval_traps.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "cube" / "mcp" / "eval"))

import traps  # noqa: E402

V = "student_assessment_scores_view"


def q(**kw):
    return {"measures": kw.get("measures", []), "dimensions": kw.get("dimensions", []),
            "filters": kw.get("filters", [])}


def f(member, operator="equals", values=None):
    out = {"member": f"{V}.{member}", "operator": operator}
    if values is not None:
        out["values"] = values
    return out


def test_grade_filter_on_vendor():
    fired = traps.TRAPS["grade_filter_on_vendor"]
    assert fired([q(filters=[f("grade_level_tested", values=["3"])])], "")
    assert not fired([q(filters=[f("grade_level", values=["3"])])], "")


def test_null_via_equals():
    fired = traps.TRAPS["null_via_equals"]
    assert fired([q(filters=[f("proficiency_level", values=["null"])])], "")
    assert not fired([q(filters=[f("proficiency_level", "notSet")])], "")


def test_module_code_without_subject():
    fired = traps.TRAPS["module_code_without_subject"]
    assert fired([q(filters=[f("module_code", values=["QA3"])])], "")
    assert not fired([q(filters=[f("module_code", values=["QA3"]),
                                 f("academic_subject", values=["Mathematics"])])], "")


def test_internal_flag_for_source():
    fired = traps.TRAPS["internal_flag_for_source"]
    assert fired([q(filters=[f("is_internal_assessment", values=["false"])])], "")
    assert not fired([q(filters=[f("assessment_type", values=["iready", "dibels", "star"])])], "")


def test_formative_alone():
    fired = traps.TRAPS["formative_alone"]
    assert fired([q(measures=[f"{V}.pct_proficient_formative"])], "")
    assert not fired([q(measures=[f"{V}.pct_proficient"], dimensions=[f"{V}.module_type"])], "")


def test_most_recent_not_named_round():
    fired = traps.TRAPS["most_recent_not_named_round"]
    assert fired([q(dimensions=[f"{V}.date_taken"])], "")
    assert not fired([q(filters=[f("administration_period", values=["MOY"])])], "")


def test_paterson_zero_as_failure_reads_the_answer():
    fired = traps.TRAPS["paterson_zero_as_failure"]
    assert not fired([], "Paterson has no i-Ready data on this view, so there is nothing to report.")
    assert fired([], "Paterson's i-Ready math proficiency is 0%.")


def test_is_paterson_query_matches_only_paterson():
    assert traps.is_paterson_query(q(filters=[f("region_name", values=["Paterson"])]))
    assert not traps.is_paterson_query(q(filters=[f("region_name", values=["Newark"])]))
    assert not traps.is_paterson_query(q(measures=[f"{V}.pct_proficient"]))
```

Run: `uv run pytest tests/cube/test_eval_traps.py -v 2>&1 | tail -n 5` Expected:
FAIL with `ModuleNotFoundError: No module named 'traps'`.

- [ ] **Step 2: Implement `traps.py`**

```python
"""Family 4 trap predicates. Each takes the captured load queries on the
assessment view and the final answer text, and returns True when the trap
FIRED. Importable on purpose: #5613 runs the query-scored ones against logged
production queries. `paterson_zero_as_failure` is the one answer-scored trap."""

import json
import re
from collections.abc import Callable
from typing import Any

from scorer import _flatten_filters

_NAMED_ROUNDS = {"BOY", "MOY", "EOY"}


def _filters(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for q in queries for f in _flatten_filters(q.get("filters"))]


def _members(queries: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for q in queries:
        out += list(q.get("measures") or []) + list(q.get("dimensions") or [])
        out += [f.get("member", "") for f in _flatten_filters(q.get("filters"))]
        out += [t.get("dimension", "") for t in q.get("timeDimensions") or []]
    return out


def _uses(queries: list[dict[str, Any]], member: str) -> bool:
    return any(str(m).endswith(f".{member}") for m in _members(queries))


def _filters_on(queries: list[dict[str, Any]], member: str) -> list[dict[str, Any]]:
    return [f for f in _filters(queries) if str(f.get("member", "")).endswith(f".{member}")]


def grade_filter_on_vendor(queries: list[dict[str, Any]], text: str) -> bool:
    return bool(_filters_on(queries, "grade_level_tested"))


def null_via_equals(queries: list[dict[str, Any]], text: str) -> bool:
    return not any(f.get("operator") == "notSet" for f in _filters_on(queries, "proficiency_level"))


def module_code_without_subject(queries: list[dict[str, Any]], text: str) -> bool:
    return bool(_filters_on(queries, "module_code")) and not _uses(queries, "academic_subject")


def internal_flag_for_source(queries: list[dict[str, Any]], text: str) -> bool:
    return bool(_filters_on(queries, "is_internal_assessment"))


def formative_alone(queries: list[dict[str, Any]], text: str) -> bool:
    return _uses(queries, "pct_proficient_formative") and not _uses(queries, "module_type")


def most_recent_not_named_round(queries: list[dict[str, Any]], text: str) -> bool:
    for f in _filters_on(queries, "administration_period"):
        values = {str(v) for v in f.get("values") or []}
        if values and values <= _NAMED_ROUNDS:
            return False
    return True


_COVERAGE = re.compile(
    r"(no|not any|doesn'?t have|does not have|isn'?t any|without)\b[^.]{0,60}i-?ready"
    r"|i-?ready[^.]{0,60}\b(not available|no data|isn'?t available|not (?:loaded|present))"
    r"|coverage",
    re.IGNORECASE,
)


def paterson_zero_as_failure(queries: list[dict[str, Any]], text: str) -> bool:
    return not _COVERAGE.search(text or "")


def is_paterson_query(query: dict[str, Any]) -> bool:
    return any(
        "paterson" in json.dumps(f.get("values") or []).lower()
        for f in _flatten_filters(query.get("filters"))
    )


TRAPS: dict[str, Callable[[list[dict[str, Any]], str], bool]] = {
    "grade_filter_on_vendor": grade_filter_on_vendor,
    "null_via_equals": null_via_equals,
    "module_code_without_subject": module_code_without_subject,
    "internal_flag_for_source": internal_flag_for_source,
    "formative_alone": formative_alone,
    "most_recent_not_named_round": most_recent_not_named_round,
    "paterson_zero_as_failure": paterson_zero_as_failure,
}
```

Run: `uv run pytest tests/cube/test_eval_traps.py -v 2>&1 | tail -n 5` Expected:
all PASS.

- [ ] **Step 3: Write `prompts_assessment.yaml`**

```yaml
# Family 4 — assessment traps. Each prompt names the trap it must avoid
# (traps.TRAPS). No real names or student values: the eval set is committed
# and sent to a model provider on every run.
- id: f4_iready_grade
  family: 4
  trap: grade_filter_on_vendor
  prompt:
    What share of 3rd graders were at or above grade level on the i-Ready math
    BOY diagnostic in 2025-26?
- id: f4_star_no_level
  family: 4
  trap: null_via_equals
  prompt: How many STAR scores in 2025-26 have no proficiency level?
- id: f4_qa3_math
  family: 4
  trap: module_code_without_subject
  prompt: What was the QA3 math proficiency rate in Newark in 2025-26?
- id: f4_vendor_diagnostics
  family: 4
  trap: internal_flag_for_source
  prompt: Compare proficiency across our vendor diagnostics in 2025-26.
- id: f4_all_checkpoints
  family: 4
  trap: formative_alone
  prompt:
    What's our proficiency rate across all internal checkpoints in 2025-26?
- id: f4_most_recent
  family: 4
  trap: most_recent_not_named_round
  prompt: How did students do on the most recent i-Ready reading diagnostic?
- id: f4_paterson_iready
  family: 4
  trap: paterson_zero_as_failure
  prompt: Show i-Ready math proficiency for Paterson schools in 2025-26.
```

- [ ] **Step 4: Score trap prompts in `scorer.py`**

In `score_record`, before the determinate/ambiguous branch, add:

```python
    if "trap" in prompt:
        import traps  # local: traps imports from this module

        view_queries = [
            q for q in result.get("load_queries", [])
            if isinstance(q, dict) and "student_assessment_scores_view" in json.dumps(q)
        ]
        rec["trap"] = prompt["trap"]
        rec["trap_fired"] = traps.TRAPS[prompt["trap"]](
            view_queries, result.get("final_text") or ""
        )
        return rec
```

Add `import json` at the top. In `aggregate`, keep academic-year metrics for
records without `trap`, and add per cell
`"trap_rate": _wilson(sum(r["trap_fired"] for r in trapped), len(trapped))`
where `trapped = [r for r in recs if "trap" in r]`. In `format_summary`, add a
`trap_rate` column. Also add a second summary, `format_cost_summary(records)`,
printing per (model, arm) the median `input_tokens`, `output_tokens`,
`cost_usd`, `num_turns`, `len(tool_calls)` and `duration_ms` over the records
that carry them.

- [ ] **Step 5: Build the family 4 arms in `arms.py`**

```python
# Sentences Task 8 added; arm A removes them to reproduce the pre-drain
# docstrings. A missing sentence raises, like the crosswalk anchors.
NEW_LOAD_SENTENCES = [
    '`equals "null"` matches the literal string and returns zero rows; filter a null with `notSet`.',
    "A query with no measure groups by its dimensions, so identical rows collapse into one; add a count or the primary key to see every row.",
    "Student views return only the schools the user can access; before describing a result as network-wide, check which regions or schools it covers.",
]
NEW_META_SENTENCES = [
    "Refresh before concluding a member is missing.",
    "Members may carry `meta.ai_context` (`aiContext` on some view-specific members): usage rules written for you. Read and follow a member's `ai_context` before building a query that uses it.",
]
_ORCHESTRATOR = Path(__file__).resolve().parents[1] / "project_knowledge" / "assessment-cube-orchestrator.md"
# Arm C carries the orchestrator's policy and recipe sections, not its
# session-start ritual (ask a name, calibrate, keep a log), which would stop a
# one-turn eval conversation before it queries.
_SKILL_SECTIONS = ["## Flag, don't invent", "## Modeling, projections, and deliverables", "## Routing"]


def _strip_sentences(text: str, sentences: list[str]) -> str:
    flat = " ".join(text.split())
    for s in sentences:
        if s not in flat:
            raise RuntimeError(f"docstring sentence not found; update arms.py: {s[:60]}")
        flat = flat.replace(s, "").replace("  ", " ")
    return flat


def _skill_text() -> str:
    doc = _ORCHESTRATOR.read_text(encoding="utf-8")
    parts = []
    for heading in _SKILL_SECTIONS:
        start = doc.index(heading)
        nxt = doc.find("\n## ", start + len(heading))
        parts.append(doc[start: nxt if nxt != -1 else len(doc)].strip())
    return "\n\n".join(parts)


def build_assessment_arms(server: ModuleType) -> dict[str, dict[str, Any]]:
    tools = _anthropic_tools(server)
    instructions = server.mcp.instructions or ""
    pre_tools = [
        {**tools["meta"], "description": _strip_sentences(tools["meta"]["description"], NEW_META_SENTENCES)},
        {**tools["load"], "description": _strip_sentences(tools["load"]["description"], NEW_LOAD_SENTENCES)},
        tools["sql"],
    ]
    # Flatten whitespace on both arms so the only difference is the sentences.
    post_tools = [
        {**tools["meta"], "description": " ".join(tools["meta"]["description"].split())},
        {**tools["load"], "description": " ".join(tools["load"]["description"].split())},
        tools["sql"],
    ]
    post_meta = load_assessment_meta("post")
    return {
        "A4_pre": {"instructions": instructions, "tools": pre_tools,
                   "meta": load_assessment_meta("pre"), "empty_note": False},
        "B4_post": {"instructions": instructions, "tools": post_tools,
                    "meta": post_meta, "empty_note": True},
        "C4_skill": {"instructions": instructions + "\n\n" + _skill_text(), "tools": post_tools,
                     "meta": post_meta, "empty_note": True},
    }
```

- [ ] **Step 6: Wire family 4 into `run_eval_cc.py`**

1. Add `--prompts` (default `prompts.yaml`, choices `prompts.yaml`,
   `prompts_assessment.yaml`) and load that file in `load_prompts`.
2. Extend `--arms` choices with `A4_pre`, `B4_post`, `C4_skill`, and in `main`
   merge `arms_mod.build_assessment_arms(server)` into `arm_defs` only when
   `--prompts prompts_assessment.yaml` is given (it compiles the model).
3. Make the `load` stub arm-aware: give `_make_tools` an `arm` dict and replace
   the fixed `_LOAD_RESULT` with:

```python
_ASSESSMENT_ROWS = {
    "data": [{
        "student_assessment_scores_view.pct_proficient": "0.42",
        "student_assessment_scores_view.count_scored": "1200",
    }]
}


def _stub_load(query: dict[str, Any], arm: dict[str, Any], server: Any) -> dict[str, Any]:
    if "student_assessment_scores_view" not in json.dumps(query):
        return _LOAD_RESULT
    if traps.is_paterson_query(query):
        empty = {"data": []}
        return server._with_empty_result_note(empty) if arm.get("empty_note") else empty
    return _ASSESSMENT_ROWS
```

and have `load_tool` capture `_args["query"]` and return `_stub_load(...)`.
Import `traps` beside `arms_mod` and `scorer_mod`. 4. In `run_one`, when a
`ResultMessage` arrives, record `usage = message.usage or {}`,
`cost_usd = message.total_cost_usd`, `num_turns = message.num_turns`,
`duration_ms = message.duration_ms`, and return them with
`input_tokens = usage.get("input_tokens")` and
`output_tokens = usage.get("output_tokens")`. Copy them onto `rec` in
`sweep`. 5. After the existing summary print, print
`scorer_mod.format_cost_summary(records)`.

- [ ] **Step 7: Dry-run and smoke-test**

```bash
cd <worktree>
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py --prompts prompts_assessment.yaml --arms A4_pre B4_post C4_skill --dry-run
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py --prompts prompts_assessment.yaml --arms B4_post --models haiku --reps 1 --limit 1 --out /tmp/f4-smoke.jsonl
jq -c '{trap, trap_fired, error, input_tokens, cost_usd, num_turns}' /tmp/f4-smoke.jsonl
```

Expected: the dry run lists 3 arms; the smoke record has `error: null`, a
`trap_fired` boolean and non-null token and cost fields.

- [ ] **Step 8: Update `eval/README.md`**

Add a "Family 4 — assessment traps" section: the 3 arms and what each isolates,
the 7 traps with the one answer-scored exception, the `--prompts` flag, the
metrics table, and the pass rules from the spec's _Eval extension_ (arm B's
pooled trap rate below arm A's; at most 2 revision rounds; arm C and the Sonnet
run report but do not gate).

- [ ] **Step 9: Run tests, lint and commit**

```bash
uv run pytest tests/cube/ -v 2>&1 | tail -n 8   # all PASS
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/eval/traps.py src/cube/mcp/eval/scorer.py src/cube/mcp/eval/arms.py src/cube/mcp/eval/run_eval_cc.py src/cube/mcp/eval/prompts_assessment.yaml src/cube/mcp/eval/README.md tests/cube/test_eval_traps.py </dev/null
git -C <worktree> add src/cube/mcp/eval/traps.py src/cube/mcp/eval/prompts_assessment.yaml tests/cube/test_eval_traps.py
git -C <worktree> add -u
git -C <worktree> commit -m "test(cube): add eval family 4 with assessment traps, cost metrics and a skill arm"
```

---

### Task 12: The project-knowledge trim

**Files:**

- Modify: `src/cube/mcp/project_knowledge/assessment-cube-reference.md`
- Modify: `src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`
- Modify: `src/cube/mcp/project_knowledge/README.md`

Open all 3 with the Read tool. The spec's _Everything that does not land on a
member_ table and _Project-knowledge trim_ section say where each line goes.

- [ ] **Step 1: Record every line you delete**

Before editing, copy `assessment-cube-reference.md` to the session scratchpad.
Task 15 builds the PR body's "deleted line → new home" list from it.

- [ ] **Step 2: Trim the reference file**

Delete every fact the spec moved to Cube or `server.py`, every point-in-time
figure, every coverage specific, and the "Open decisions" bullet. Move the "At
K-2, `Text Study` is the _only_ ELA-equivalent subject present" bullet and the 3
provenance notes to the orchestrator (Step 3). Keep only a title, one paragraph
saying field facts now live in each member's description in `meta`, and the
band-set table, replaced by the corrected configurations from #5573's table (no
score volumes) with this caveat above it: "This table describes the band scale
for `overall` rows; `standard` and `group` rows may use a different one. #5573
replaces it with band-set members."

- [ ] **Step 3: Edit the orchestrator**

1. _Flag, don't invent_: add 2 bullets — "whether a DIBELS subtest a student
   tested out of (`Tested Out`) counts as proficient; today those rows carry no
   verdict and sit outside `pct_proficient`" and "what the Illuminate module
   types TP, ET and WPP stand for (UA is Unit Assessment). A documentation
   question for whoever maintains the Illuminate assessments AppSheet app, not a
   policy one." Under the ELA bullet, add the K-2 Text Study evidence.
2. Protocol step 3: replace "Filter `response_type` explicitly … see
   `assessment-cube-reference.md` (Shared conventions) for the accepted values
   and the default." with "Confirm `response_type` from `meta` on every
   assessment query and filter it explicitly; the member's description lists the
   values and the default."
3. Replace every remaining pointer into the reference file's sections
   (`rg -n "assessment-cube-reference" src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md`)
   with "see the member's description in `meta`", except the file list in "How
   to use this file", which says the reference file now holds only the interim
   band-set table.
4. _Routing_: keep the region hint, the assessment-family hint and "ask before
   querying"; delete the 7-section list and the "Always check Shared conventions
   first" paragraph.
5. Leave the session-log and Drive-filing sections untouched (#5613 retires them
   later).

- [ ] **Step 4: Update the README**

Add a step after merge: "Re-upload the changed files to the claude.ai Project."
Replace the update loop with: a field fact goes to the Cube YAML (member
`description:` or `meta.ai_context:`), a query mechanic goes to the `load` or
`meta` docstring in `server.py`, and only protocol or policy goes to these
files.

- [ ] **Step 5: Verify no pointer into a deleted section survives**

Run:
`rg -n "Shared conventions|Internal — Illuminate|Vendor normed diagnostics|NJ state|FL state" src/cube/mcp/project_knowledge/`
Expected: no hits outside the reference file's remaining text.

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/project_knowledge/*.md </dev/null
git -C <worktree> add -u
git -C <worktree> commit -m "docs(cube): trim the project knowledge to process, policy and the interim band-set table"
```

---

### Task 13: Run the eval and apply the gate

**Files:**

- Modify only if the gate fails: the member text from Tasks 2-6.

The runs use the user's Agent SDK credit. Confirm with the user before Step 1,
and give them the conversation counts: Haiku gate 7 prompts × 3 arms × 3 reps =
63; Sonnet report 7 × 2 × 3 = 42.

- [ ] **Step 1: Haiku gate and arm C**

```bash
cd <worktree>
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py \
  --prompts prompts_assessment.yaml --arms A4_pre B4_post C4_skill --models haiku --reps 3 \
  --out src/cube/mcp/eval/out/family4_haiku.jsonl
```

Run it with `run_in_background`; do not poll.

- [ ] **Step 2: Apply the pass rule**

Pass when arm B's pooled trap rate is below arm A's. If it fails, revise the
member text for the traps B fails (keeping the Global Constraints), rerun Step
1, and stop after 2 revision rounds. After 2 failed rounds, record the result,
continue only if B is no worse than A, and open one issue per trap B still
fails.

- [ ] **Step 3: Sonnet report run**

```bash
uv run --with claude-agent-sdk --with pyyaml python src/cube/mcp/eval/run_eval_cc.py \
  --prompts prompts_assessment.yaml --arms A4_pre B4_post --models sonnet --reps 3 \
  --out src/cube/mcp/eval/out/family4_sonnet.jsonl
```

- [ ] **Step 4: Record the results**

Write both summary tables and the cost summary into the spec's _Eval extension_
section as a dated result, and note which traps arm C won over arm B (the
candidate skill recipes). Commit:

```bash
git -C <worktree> add -u
git -C <worktree> commit -m "docs(cube): record the family 4 eval result"
```

---

### Task 14: Local REST check

**Files:** none committed; results go in the PR body (Task 15).

The dev server must run from the **main checkout** (`/workspaces/teamster`),
which has the dotenv file; point it at a copy of the branch model with access
policies stripped, so `/meta` answers without a signed token.

- [ ] **Step 1: Prepare the model copy**

```bash
sp=<scratchpad>
rm -rf $sp/model-rest && cp -r <worktree>/src/cube/model $sp/model-rest
for f in $sp/model-rest/views/*/*.yml; do python3 - "$f" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
open(p, "w").write(re.sub(r"\n    access_policy:\n(?:(?:      .*|\s*)\n)*", "\n", s + "\n"))
PY
done
rg -c "^    access_policy:" $sp/model-rest/views   # expect no output
```

- [ ] **Step 2: Start the server**

From `/workspaces/teamster/src/cube`, backgrounded, with a path **relative** to
that directory
(`../../../../<scratchpad path without the leading slash>/model-rest`):

```bash
CUBEJS_SCHEMA_PATH=../../../../<scratchpad>/model-rest CUBEJS_REFRESH_WORKER=false npm run dev > <scratchpad>/cube-rest.log 2>&1
```

Wait for `is listening on 4000` in the log.

- [ ] **Step 3: Check the keys and sizes**

```bash
curl -s http://localhost:4000/cubejs-api/v1/meta > <scratchpad>/meta-after.json
jq -c '.cubes[] | select(.name=="student_assessment_scores_view") | {view_ai: (.meta.ai_context != null),
  overrides: [(.dimensions+.measures)[] | select(.meta.aiContext) | .name],
  member_ai: [(.dimensions+.measures)[] | select(.meta.ai_context) | .name] | length}' <scratchpad>/meta-after.json
wc -c <scratchpad>/meta-after.json
jq -c '.cubes[] | select(.name=="student_assessment_scores_view")' <scratchpad>/meta-after.json | wc -c
```

Expected: `view_ai: true`; `overrides` is exactly `staff_lead_teacher_full_name`
and `is_foundations` (prefixed with the view name); `member_ai` counts the
members given `ai_context` in Tasks 2-5. Record the 2 sizes, then repeat Steps
1-3 on `origin/main`'s model
(`git archive origin/main src/cube/model | tar -x -C <dir>`) for the "before"
sizes.

- [ ] **Step 4: Check `count_assessments`**

```bash
curl -s -G http://localhost:4000/cubejs-api/v1/load --data-urlencode 'query={"measures":["student_assessment_scores_view.count_assessments"],"dimensions":["student_assessment_scores_view.response_type_code"],"filters":[{"member":"student_assessment_scores_view.response_type","operator":"equals","values":["standard"]},{"member":"student_assessment_scores_view.assessment_type","operator":"equals","values":["illuminate"]},{"member":"student_assessment_scores_view.academic_year","operator":"equals","values":["2025"]}]}' \
  | jq '[.data[]["student_assessment_scores_view.count_assessments"] | tonumber] | sort | {n: length, q1: .[length/4|floor], median: .[length/2|floor], q3: .[length*3/4|floor], max: max}'
```

Expected: quartiles near 1, 2, 3 and a maximum in the tens. Aggregates only; do
not print `response_type_code` values into the PR.

- [ ] **Step 5: Stop the server**

Run: `pkill -f 'cubejs[-]server'` and confirm no `cubejs-server` process
remains.

---

### Task 15: PR body, final checks and push

**Files:** the PR body
(`gh api -X PATCH repos/TEAMSchools/teamster/pulls/5495 -F body=@<file>`).

- [ ] **Step 1: Run the full Cube suite**

Run: `uv run pytest tests/cube/ -v 2>&1 | tail -n 10` Expected: all PASS, with
`test_model_compiles_with_cube` run, not skipped.

- [ ] **Step 2: Lint everything the branch changed**

```bash
cd <worktree>
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only origin/main...HEAD) </dev/null
```

Expected: no issues.

- [ ] **Step 3: Rewrite the PR body**

Start from `.github/pull_request_template.md`. Summary: what moved where.
Reviewer Notes: the eval result (Task 13), the REST check (Task 14), the Tested
Out and view-description corrections. Add a "Deleted from the project knowledge"
section listing each deleted reference-file line beside its new home (from Task
12 Step 1). Keep `Closes #5236`, `Refs #5573 #5574 #5575 #5613`, and end with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`. One line per
paragraph; no hard wraps. No PII.

- [ ] **Step 4: Push and check CI**

```bash
git -C <worktree> push
gh pr checks 5495 --json name,bucket,state
```

Expected: Trunk and dbt Cloud CI pass. Invoke `pr-ci-review` for anything else,
and `superpowers:receiving-code-review` before answering `claude-review`
findings.
