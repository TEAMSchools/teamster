# Goal-Setting Generator PR 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the rollout mode of the goal-setting generator: a rules-driven
Python package that produces one group's school goals and student buckets from
the warehouse, with input archive, freshness gate, invariants, diff and plan
mode, a committed manifest, and the `verify-crosswalk` and `show` commands.

**Architecture:** Adapters fetch flat student rows from BigQuery and archive
them. Pure rule functions over dataclass records classify students, derive
school goals with the bubble parameter, and assign buckets. A pipeline module
assembles a `Proposal`, invariants and a diff run against it, and a single
`write_run` call at the end writes every file. Rules live in
`config/goal_setting/ay2026.yaml`; the PowerSchool program crosswalk in
`config/goal_setting/ps_programs.yaml`.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, google-cloud-bigquery (all
already installed transitively), pytest. No pandas.

**Spec:** `docs/superpowers/specs/2026-09-16-goal-setting-generator-design.md`

## Global Constraints

- Every command runs as `uv run python -m teamster.goal_setting ...` from the
  worktree root. Never bare `python`.
- Worktree:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-goal-setting-generator`.
  Every path below is relative to it. Every git call is `git -C <worktree>`.
  Stage files by name.
- No student identifiers in anything committed: no student rows in fixtures, no
  per-student hashes in manifests. Fixtures are synthetic 5 to 10 student
  rosters or the SY27 school-by-grade aggregates.
- No module under `src/teamster/goal_setting/rules/` imports
  `google.cloud.bigquery` or reads the warehouse.
- Pydantic models use `model_config = ConfigDict(extra="forbid")`.
- Crosswalk uniqueness is on `(region, programid)`, never `programid` alone.
- Every invariant and gate message names region, school, grade, and subject.
- Bucket labels are the strings `Bucket 1` through `Bucket 4`. Bucket 4 rows
  also carry `bucket4_outcome` of `below` or `untested`.
- Bubble parameter math, verbatim from the spec: per region and group
  `bp = round((sum tested * target - sum proficient) / sum approaching, 2)`; per
  school and grade `n_to_move = ceil(n_approaching * bp)`;
  `goal = round((n_proficient + n_to_move) / n_tested, 2)`.
- Run `uv run pytest tests/goal_setting -q` before every commit. Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  on YAML and markdown before the final push.

---

## File structure

```text
config/goal_setting/
  ay2026.yaml                          Task 1
  ps_programs.yaml                     Task 1
  manifests/.gitkeep                   Task 8
src/teamster/goal_setting/
  __init__.py                          Task 1
  __main__.py                          Task 12
  records.py                           Task 2   dataclasses shared by every module
  config.py                            Task 1   Pydantic models, registry, loaders
  rules/__init__.py                    Task 2
  rules/classify.py                    Task 2
  rules/aggregate.py                   Task 3   counts per school and grade
  rules/school_goal.py                 Task 3
  rules/bucket2.py                     Task 4
  rules/bucket3.py                     Task 5
  rules/assign.py                      Task 5   bucket 1 and 4, reason strings
  rules/invariants.py                  Task 6
  rules/freshness.py                   Task 7
  pipeline.py                          Task 8   run_group -> Proposal
  manifest.py                          Task 8
  outputs.py                           Task 8
  diff.py                              Task 9
  adapters/__init__.py                 Task 10
  adapters/archive.py                  Task 10
  adapters/roster_sql.py               Task 10
  adapters/iready_boy.py               Task 10
  adapters/goals_sheet.py              Task 10
  verify_crosswalk.py                  Task 11
  show.py                              Task 11
tests/goal_setting/
  __init__.py                          Task 1
  fixtures/nj_math_1_2_ay2026_school_goals.csv    Task 3
  fixtures/nj_math_1_2_ay2026_region_rollup.csv   Task 3
  fixtures/roster_small.py             Task 2   synthetic roster builders
  test_config.py                       Task 1
  test_classify.py                     Task 2
  test_school_goal.py                  Task 3
  test_bucket2.py                      Task 4
  test_bucket3.py                      Task 5
  test_assign.py                       Task 5
  test_invariants.py                   Task 6
  test_freshness.py                    Task 7
  test_pipeline_outputs.py             Task 8
  test_diff.py                         Task 9
  test_adapters.py                     Task 10
  test_verify_crosswalk.py             Task 11
  test_cli.py                          Task 12
  test_purity.py                       Task 12
```

`.gitignore` gains `runs/` in Task 8.

---

### Task 1: Config models, strategy registry, crosswalk, and the SY27 rules file

**Files:**

- Create: `src/teamster/goal_setting/__init__.py` (empty)
- Create: `src/teamster/goal_setting/config.py`
- Create: `config/goal_setting/ay2026.yaml`
- Create: `config/goal_setting/ps_programs.yaml`
- Create: `tests/goal_setting/__init__.py` (empty)
- Test: `tests/goal_setting/test_config.py`

**Interfaces:**

- Produces: `load_rules(path: Path) -> RulesFile`,
  `load_crosswalk(path: Path) -> Crosswalk`,
  `Crosswalk.program_id(region: str, subject: str, bucket: str) -> int`,
  `RulesFile.group(name: str) -> Group`, `Group` fields:
  `name, regions, grades, subject, rollout_date, source, levels, target, school_goal, bucket2, bucket3, amendments, freshness`,
  `STRATEGIES: dict[str, dict[str, str | None]]` mapping slot to strategy name
  to either an implementing dotted path or `None` for not-yet-implemented,
  `ConfigError(ValueError)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_config.py
from datetime import date
from pathlib import Path

import pytest

from teamster.goal_setting.config import (
    ConfigError,
    load_crosswalk,
    load_rules,
)

REPO = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO / "config" / "goal_setting"


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(text)
    return p


GOOD = """
academic_year: 2026
groups:
  - name: nj_math_1_2
    regions: [Newark, Camden, Paterson]
    grades: [1, 2]
    subject: Math
    rollout_date: 2026-10-15
    source: iready_boy
    levels: {proficient: [5], approaching: [4]}
    target: {from: goals_sheet, column: grade_band_goal}
    school_goal: bubble_parameter
    bucket2: {strategy: top_approaching_to_move, ties: admit}
    bucket3: {strategy: remaining_approaching_or_stretch}
    amendments: {max_per_school_grade_subject: 3, to_buckets: [2]}
    freshness: {min_tested_share: 0.85, roster_tolerance: 0.15}
"""


def test_good_rules_file_loads(tmp_path):
    rules = load_rules(write(tmp_path, GOOD))
    g = rules.group("nj_math_1_2")
    assert rules.academic_year == 2026
    assert g.rollout_date == date(2026, 10, 15)
    assert g.levels.proficient == [5]
    assert g.bucket2.ties == "admit"


def test_unknown_strategy_lists_valid_names(tmp_path):
    bad = GOOD.replace("remaining_approaching_or_stretch", "remaining_aproaching")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, bad))
    msg = str(e.value)
    assert "remaining_aproaching" in msg
    assert "remaining_approaching_or_stretch" in msg
    assert "stretch_reachers" in msg


def test_unknown_parameter_is_rejected(tmp_path):
    bad = GOOD.replace("ties: admit", "ties: admit, tie: strict")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, bad))
    assert "tie" in str(e.value)


def test_overlapping_grades_same_region_subject_rejected(tmp_path):
    dup = GOOD + GOOD.split("groups:\n")[1].replace(
        "name: nj_math_1_2", "name: nj_math_2_only"
    ).replace("grades: [1, 2]", "grades: [2]")
    with pytest.raises(ConfigError) as e:
        load_rules(write(tmp_path, dup))
    assert "Newark" in str(e.value) and "grade 2" in str(e.value)


def test_group_missing_raises(tmp_path):
    rules = load_rules(write(tmp_path, GOOD))
    with pytest.raises(ConfigError):
        rules.group("nope")


CROSSWALK = """
programs:
  - {region: Camden, subject: Math, bucket: "Bucket 3", programid: 7374}
  - {region: Newark, subject: Reading, bucket: "Bucket 2", programid: 7374}
"""


def test_same_program_id_two_regions_loads(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(CROSSWALK)
    xw = load_crosswalk(p)
    assert xw.program_id("Camden", "Math", "Bucket 3") == 7374
    assert xw.program_id("Newark", "Reading", "Bucket 2") == 7374


def test_same_program_id_twice_one_region_fails_naming_both(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(
        CROSSWALK.replace("region: Newark", "region: Camden").replace(
            "subject: Reading", "subject: Math"
        ).replace('bucket: "Bucket 2"', 'bucket: "Bucket 2"')
    )
    with pytest.raises(ConfigError) as e:
        load_crosswalk(p)
    assert str(e.value).count("7374") >= 2 and "Camden" in str(e.value)


def test_bucket4_has_no_program(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text(CROSSWALK)
    xw = load_crosswalk(p)
    with pytest.raises(ConfigError):
        xw.program_id("Camden", "Math", "Bucket 4")


def test_committed_config_files_validate():
    rules = load_rules(CONFIG_DIR / "ay2026.yaml")
    xw = load_crosswalk(CONFIG_DIR / "ps_programs.yaml")
    assert rules.academic_year == 2026
    assert {g.name for g in rules.groups} >= {"nj_math_1_2", "nj_math_k"}
    for region in ("Camden", "Newark", "Paterson"):
        for bucket in ("Bucket 1", "Bucket 2", "Bucket 3"):
            for subject in ("Math", "Reading"):
                assert xw.program_id(region, subject, bucket) > 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_config.py -q` Expected: FAIL with
`ModuleNotFoundError: teamster.goal_setting`

- [ ] **Step 3: Write `config.py`**

```python
# src/teamster/goal_setting/config.py
"""Rules file and crosswalk loading.

Every strategy name is checked against STRATEGIES at load time. A None value
means the strategy is a known name that a later PR implements; the pipeline
raises NotImplementedError when it is selected.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


class ConfigError(ValueError):
    """A rules or crosswalk file is invalid. The message says what and where."""


STRATEGIES: dict[str, dict[str, str | None]] = {
    "source": {
        "iready_boy": "teamster.goal_setting.adapters.iready_boy",
        "njsla_prior_year": None,
        "fast_pm3_prior_year": None,
        "fast_pm1": None,
        "star_boy": None,
        "star_spring_prior": None,
        "psat": None,
    },
    "school_goal": {
        "bubble_parameter": "teamster.goal_setting.rules.school_goal:bubble_parameter",
        "blanket": "teamster.goal_setting.rules.school_goal:blanket",
        "flat": None,
    },
    "bucket2": {
        "top_approaching_to_move": "teamster.goal_setting.rules.bucket2:top_approaching_to_move",
        "none": "teamster.goal_setting.rules.bucket2:none",
    },
    "bucket3": {
        "remaining_approaching": "teamster.goal_setting.rules.bucket3:remaining_approaching",
        "stretch_reachers": "teamster.goal_setting.rules.bucket3:stretch_reachers",
        "remaining_approaching_or_stretch": "teamster.goal_setting.rules.bucket3:remaining_approaching_or_stretch",
        "bottom_pct_rank": None,
        "none": "teamster.goal_setting.rules.bucket3:none",
    },
}


def _check_strategy(slot: str, name: str) -> None:
    valid = sorted(STRATEGIES[slot])
    if name not in valid:
        raise ConfigError(
            f"{slot}: unknown strategy '{name}'. Valid names: {', '.join(valid)}"
        )


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Levels(Strict):
    proficient: list[int]
    approaching: list[int]


class Target(Strict):
    from_: Literal["goals_sheet", "inline"]
    column: str | None = None
    values: dict[str, dict[int, float]] | None = None  # region -> grade -> target

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _alias_from(cls, data):
        if isinstance(data, dict) and "from" in data:
            data = {**data, "from_": data.pop("from")}
        return data

    @model_validator(mode="after")
    def _shape(self):
        if self.from_ == "goals_sheet" and not self.column:
            raise ValueError("target.from goals_sheet needs column")
        if self.from_ == "inline" and not self.values:
            raise ValueError("target.from inline needs values")
        return self


class Bucket2(Strict):
    strategy: str
    ties: Literal["admit", "strict"] = "admit"

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("bucket2", self.strategy)
        return self


class Bucket3(Strict):
    strategy: str

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("bucket3", self.strategy)
        return self


class Amendments(Strict):
    max_per_school_grade_subject: int
    to_buckets: list[int]


class Freshness(Strict):
    min_tested_share: float
    roster_tolerance: float


class Group(Strict):
    name: str
    regions: list[str]
    grades: list[int]
    subject: Literal["Math", "Reading"]
    rollout_date: date
    source: str
    levels: Levels
    target: Target
    school_goal: str
    bucket2: Bucket2
    bucket3: Bucket3
    amendments: Amendments
    freshness: Freshness

    @model_validator(mode="after")
    def _known(self):
        _check_strategy("source", self.source)
        _check_strategy("school_goal", self.school_goal)
        return self


class RulesFile(Strict):
    academic_year: int
    groups: list[Group]

    @model_validator(mode="after")
    def _no_overlap(self):
        seen: dict[tuple[str, str, int], str] = {}
        for g in self.groups:
            for region in g.regions:
                for grade in g.grades:
                    key = (region, g.subject, grade)
                    if key in seen:
                        raise ValueError(
                            f"{region} {g.subject} grade {grade} appears in both "
                            f"'{seen[key]}' and '{g.name}'"
                        )
                    seen[key] = g.name
        return self

    def group(self, name: str) -> Group:
        for g in self.groups:
            if g.name == name:
                return g
        raise ConfigError(
            f"no group named '{name}'. Groups: {', '.join(g.name for g in self.groups)}"
        )


class Program(Strict):
    region: str
    subject: Literal["Math", "Reading"]
    bucket: Literal["Bucket 1", "Bucket 2", "Bucket 3"]
    programid: int


class Crosswalk(Strict):
    programs: list[Program]

    @model_validator(mode="after")
    def _unique(self):
        by_id: dict[tuple[str, int], list[Program]] = {}
        by_key: dict[tuple[str, str, str], Program] = {}
        for p in self.programs:
            by_id.setdefault((p.region, p.programid), []).append(p)
            key = (p.region, p.subject, p.bucket)
            if key in by_key:
                raise ValueError(f"duplicate crosswalk row for {key}")
            by_key[key] = p
        for (region, pid), rows in by_id.items():
            if len(rows) > 1:
                names = "; ".join(f"{r.subject} {r.bucket}" for r in rows)
                raise ValueError(
                    f"{region}: program id {pid} appears {len(rows)} times ({names})"
                )
        return self

    def program_id(self, region: str, subject: str, bucket: str) -> int:
        for p in self.programs:
            if (p.region, p.subject, p.bucket) == (region, subject, bucket):
                return p.programid
        raise ConfigError(f"no program id for {region} {subject} {bucket}")


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def _validate(model: type[BaseModel], data: dict, path: Path):
    try:
        return model.model_validate(data)
    except ValidationError as e:
        lines = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            lines.append(f"  {loc}: {err['msg']}")
        raise ConfigError(f"{path}:\n" + "\n".join(lines)) from e


def load_rules(path: Path) -> RulesFile:
    return _validate(RulesFile, _load_yaml(path), path)


def load_crosswalk(path: Path) -> Crosswalk:
    return _validate(Crosswalk, _load_yaml(path), path)
```

- [ ] **Step 4: Write the two config files**

```yaml
# config/goal_setting/ay2026.yaml
# Rules for academic_year 2026 (SY27). One entry per region x grade range x
# subject group. Strategy names are validated against
# teamster.goal_setting.config.STRATEGIES at load time.
academic_year: 2026
groups:
  - name: nj_math_1_2
    regions: [Newark, Camden, Paterson]
    grades: [1, 2]
    subject: Math
    rollout_date: 2026-10-15
    source: iready_boy
    levels:
      proficient: [5] # Mid or Above after typical growth
      approaching: [4] # Early On after typical growth
    target: { from: goals_sheet, column: grade_band_goal }
    school_goal: bubble_parameter
    bucket2: { strategy: top_approaching_to_move, ties: admit }
    bucket3: { strategy: remaining_approaching_or_stretch }
    # Open item: the methodology doc says both "to Bucket 2 only" and
    # "to Buckets 2 and 3". Change to_buckets when T&L confirms.
    amendments: { max_per_school_grade_subject: 3, to_buckets: [2] }
    freshness: { min_tested_share: 0.85, roster_tolerance: 0.15 }

  - name: nj_math_k
    regions: [Newark, Camden, Paterson]
    grades: [0]
    subject: Math
    rollout_date: 2026-10-15
    source: iready_boy
    levels:
      proficient: [5]
      approaching: [4]
    target: { from: goals_sheet, column: grade_band_goal }
    school_goal: blanket
    bucket2: { strategy: top_approaching_to_move, ties: admit }
    # Open item: the K row of the doc defines Bucket 3 as stretch-reachers
    # only; production used remaining approaching. Set to the doc's reading
    # until T&L confirms.
    bucket3: { strategy: stretch_reachers }
    amendments: { max_per_school_grade_subject: 3, to_buckets: [2] }
    freshness: { min_tested_share: 0.85, roster_tolerance: 0.15 }
```

```yaml
# config/goal_setting/ps_programs.yaml
# PowerSchool special program ids for bucket programs, verified against
# int_powerschool__spenrollments on 2026-09-16. Ids are scoped to each
# region's PowerSchool instance, so the same number may appear under two
# regions. Uniqueness is enforced on (region, programid). Bucket 4 has no
# program. Miami is absent pending confirmation of where its buckets live.
programs:
  - { region: Camden, subject: Reading, bucket: Bucket 1, programid: 7376 }
  - { region: Camden, subject: Math, bucket: Bucket 1, programid: 7375 }
  - { region: Camden, subject: Reading, bucket: Bucket 2, programid: 7173 }
  - { region: Camden, subject: Math, bucket: Bucket 2, programid: 7174 }
  - { region: Camden, subject: Reading, bucket: Bucket 3, programid: 7373 }
  - { region: Camden, subject: Math, bucket: Bucket 3, programid: 7374 }
  - { region: Newark, subject: Reading, bucket: Bucket 1, programid: 7578 }
  - { region: Newark, subject: Math, bucket: Bucket 1, programid: 7577 }
  - { region: Newark, subject: Reading, bucket: Bucket 2, programid: 7374 }
  - { region: Newark, subject: Math, bucket: Bucket 2, programid: 7375 }
  - { region: Newark, subject: Reading, bucket: Bucket 3, programid: 7573 }
  - { region: Newark, subject: Math, bucket: Bucket 3, programid: 7574 }
  - { region: Paterson, subject: Reading, bucket: Bucket 1, programid: 1633 }
  - { region: Paterson, subject: Math, bucket: Bucket 1, programid: 1634 }
  - { region: Paterson, subject: Reading, bucket: Bucket 2, programid: 1635 }
  - { region: Paterson, subject: Math, bucket: Bucket 2, programid: 1636 }
  - { region: Paterson, subject: Reading, bucket: Bucket 3, programid: 1637 }
  - { region: Paterson, subject: Math, bucket: Bucket 3, programid: 1638 }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_config.py -q` Expected: 9 passed

- [ ] **Step 6: Lint the YAML and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix config/goal_setting/ay2026.yaml config/goal_setting/ps_programs.yaml </dev/null
git -C <worktree> add src/teamster/goal_setting/__init__.py src/teamster/goal_setting/config.py config/goal_setting/ay2026.yaml config/goal_setting/ps_programs.yaml tests/goal_setting/__init__.py tests/goal_setting/test_config.py
git -C <worktree> commit -m "feat(goal-setting): rules file, strategy registry, and program crosswalk

Refs #5335"
```

---

### Task 2: Records and classification

**Files:**

- Create: `src/teamster/goal_setting/records.py`
- Create: `src/teamster/goal_setting/rules/__init__.py` (empty)
- Create: `src/teamster/goal_setting/rules/classify.py`
- Create: `tests/goal_setting/fixtures/roster_small.py`
- Test: `tests/goal_setting/test_classify.py`

**Interfaces:**

- Produces: `StudentRecord` dataclass, `SchoolGoal` dataclass,
  `classify(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]`
  (returns new records, does not mutate), and the fixture helper
  `student(**overrides) -> StudentRecord`.

- [ ] **Step 1: Write the failing test and fixture helper**

```python
# tests/goal_setting/fixtures/roster_small.py
"""Synthetic student rows for rule tests. No real students."""

from teamster.goal_setting.records import StudentRecord

_NEXT = iter(range(100001, 200000))


def student(**overrides) -> StudentRecord:
    base = dict(
        region="Newark",
        student_number=next(_NEXT),
        school="TEAM",
        school_id=133570965,
        grade_level=1,
        subject="Math",
        is_tested=True,
        projected_level=4,
        projected_score=405.0,
        stretch_level=4,
        assessment="i-Ready BOY",
    )
    base.update(overrides)
    return StudentRecord(**base)


def untested(**overrides) -> StudentRecord:
    return student(
        is_tested=False,
        projected_level=None,
        projected_score=None,
        stretch_level=None,
        **overrides,
    )
```

```python
# tests/goal_setting/test_classify.py
from teamster.goal_setting.config import Levels
from teamster.goal_setting.rules.classify import classify

from .fixtures.roster_small import student, untested

LEVELS = Levels(proficient=[5], approaching=[4])


def test_level_5_is_proficient():
    (r,) = classify([student(projected_level=5)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (True, False, False)


def test_level_4_is_approaching():
    (r,) = classify([student(projected_level=4)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, True, False)


def test_level_3_is_below():
    (r,) = classify([student(projected_level=3)], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, False, True)


def test_untested_is_none_of_the_three():
    (r,) = classify([untested()], LEVELS)
    assert (r.is_proficient, r.is_approaching, r.is_below) == (False, False, False)


def test_classify_does_not_mutate_input():
    src = student(projected_level=5)
    classify([src], LEVELS)
    assert src.is_proficient is False


def test_old_early_on_or_better_rule_is_just_different_levels():
    old = Levels(proficient=[4, 5], approaching=[3])
    (r,) = classify([student(projected_level=4)], old)
    assert r.is_proficient is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/goal_setting/test_classify.py -q` Expected: FAIL with
`ModuleNotFoundError: teamster.goal_setting.records`

- [ ] **Step 3: Write `records.py` and `classify.py`**

```python
# src/teamster/goal_setting/records.py
"""Dataclasses shared by adapters, rules, and outputs.

A StudentRecord starts as what an adapter fetched and gains classification,
rank, bucket, and reason as it moves through the rules. Rules return new
records rather than mutating, so a test can compare before and after.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class StudentRecord:
    region: str
    student_number: int
    school: str
    school_id: int
    grade_level: int
    subject: str
    is_tested: bool
    projected_level: int | None
    projected_score: float | None
    stretch_level: int | None
    assessment: str
    is_proficient: bool = False
    is_approaching: bool = False
    is_below: bool = False
    rank: int | None = None
    bucket: str | None = None
    bucket4_outcome: str | None = None  # "below" | "untested"
    reason: str = ""

    def with_(self, **changes) -> StudentRecord:
        return replace(self, **changes)

    @property
    def group_key(self) -> tuple[str, str, int]:
        """Partition key for ranking and goals: school, subject, grade."""
        return (self.school, self.subject, self.grade_level)


@dataclass(frozen=True)
class SchoolGoal:
    region: str
    school: str
    school_id: int
    grade_level: int
    subject: str
    n_roster: int
    n_tested: int
    n_proficient: int
    n_approaching: int
    n_below: int
    target: float
    bubble_parameter: float | None
    n_to_move: int
    goal: float

    @property
    def group_key(self) -> tuple[str, str, int]:
        return (self.school, self.subject, self.grade_level)
```

```python
# src/teamster/goal_setting/rules/classify.py
"""Proficient / approaching / below from the projected level."""

from __future__ import annotations

from teamster.goal_setting.config import Levels
from teamster.goal_setting.records import StudentRecord


def classify(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    out = []
    for r in records:
        if not r.is_tested or r.projected_level is None:
            out.append(r.with_(is_proficient=False, is_approaching=False, is_below=False))
            continue
        proficient = r.projected_level in levels.proficient
        approaching = r.projected_level in levels.approaching
        out.append(
            r.with_(
                is_proficient=proficient,
                is_approaching=approaching,
                is_below=not proficient and not approaching,
            )
        )
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_classify.py -q` Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/records.py src/teamster/goal_setting/rules/__init__.py src/teamster/goal_setting/rules/classify.py tests/goal_setting/fixtures/roster_small.py tests/goal_setting/test_classify.py
git -C <worktree> commit -m "feat(goal-setting): student records and level classification

Refs #5335"
```

---

### Task 3: Aggregates, school goals, and the SY27 regression fixture

**Files:**

- Create: `src/teamster/goal_setting/rules/aggregate.py`
- Create: `src/teamster/goal_setting/rules/school_goal.py`
- Create: `tests/goal_setting/fixtures/nj_math_1_2_ay2026_school_goals.csv`
- Create: `tests/goal_setting/fixtures/nj_math_1_2_ay2026_region_rollup.csv`
- Test: `tests/goal_setting/test_school_goal.py`

**Interfaces:**

- Consumes: `StudentRecord`, `SchoolGoal` from Task 2.
- Produces: `SchoolCounts` dataclass with fields
  `region, school, school_id, grade_level, subject, n_roster, n_tested, n_proficient, n_approaching, n_below`;
  `count_by_school(records) -> list[SchoolCounts]`;
  `bubble_parameter(counts: list[SchoolCounts], targets: dict[tuple[str, int], float]) -> list[SchoolGoal]`;
  `blanket(counts, targets) -> list[SchoolGoal]`;
  `region_parameters(counts, targets) -> dict[tuple[str, int], float]` (region,
  grade to bp). `targets` is keyed by `(region, grade_level)`.

- [ ] **Step 1: Copy the two aggregate CSVs from the one-off into fixtures**

Source files are in the main checkout's scratch folder, which holds no student
rows in these two files:

```bash
cp /workspaces/teamster/.claude/scratch/2026-09-15-iready-k2-goals/nj_k2_math_school_goals_ay2026.csv <worktree>/tests/goal_setting/fixtures/nj_math_1_2_ay2026_school_goals.csv
cp /workspaces/teamster/.claude/scratch/2026-09-15-iready-k2-goals/nj_k2_math_region_rollup_ay2026.csv <worktree>/tests/goal_setting/fixtures/nj_math_1_2_ay2026_region_rollup.csv
head -2 <worktree>/tests/goal_setting/fixtures/nj_math_1_2_ay2026_school_goals.csv
```

Expected header:
`region,school,grade_level,n_roster,n_tested,pct_mid_above_now,pct_projected_proficient,n_projected_proficient,n_early_on,bubble_parameter,n_bubble_to_move,region_goal,school_goal,bucket_1,bucket_2,bucket_3,bucket_4`
and 16 data rows. Confirm no column is a student identifier before committing.

- [ ] **Step 2: Write the failing tests**

```python
# tests/goal_setting/test_school_goal.py
import csv
from pathlib import Path

from teamster.goal_setting.rules.aggregate import SchoolCounts, count_by_school
from teamster.goal_setting.rules.school_goal import (
    blanket,
    bubble_parameter,
    region_parameters,
)

from .fixtures.roster_small import student, untested

FIX = Path(__file__).parent / "fixtures"

SY27_TARGETS = {
    ("Newark", 1): 0.35, ("Camden", 1): 0.35, ("Paterson", 1): 0.25,
    ("Newark", 2): 0.24, ("Camden", 2): 0.22, ("Paterson", 2): 0.24,
}


def _fixture_counts() -> list[SchoolCounts]:
    rows = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_school_goals.csv").open()))
    out = []
    for r in rows:
        n_tested = int(r["n_tested"])
        n_prof = int(r["n_projected_proficient"])
        n_appr = int(r["n_early_on"])
        out.append(
            SchoolCounts(
                region=r["region"], school=r["school"], school_id=0,
                grade_level=int(r["grade_level"]), subject="Math",
                n_roster=int(r["n_roster"]), n_tested=n_tested,
                n_proficient=n_prof, n_approaching=n_appr,
                n_below=n_tested - n_prof - n_appr,
            )
        )
    return out


def test_count_by_school_groups_by_school_subject_grade():
    recs = [
        student(is_proficient=True), student(is_approaching=True),
        student(is_below=True), untested(),
        student(school="Rise", is_proficient=True),
    ]
    counts = {c.school: c for c in count_by_school(recs)}
    assert counts["TEAM"].n_roster == 4
    assert counts["TEAM"].n_tested == 3
    assert (counts["TEAM"].n_proficient, counts["TEAM"].n_approaching, counts["TEAM"].n_below) == (1, 1, 1)
    assert counts["Rise"].n_roster == 1


def test_region_parameters_reproduce_sy27():
    params = region_parameters(_fixture_counts(), SY27_TARGETS)
    rollup = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_region_rollup.csv").open()))
    for r in rollup:
        assert params[(r["region"], int(r["grade_level"]))] == float(r["bubble_parameter"]), r


def test_bubble_parameter_reproduces_sy27_school_goals_to_the_cent():
    goals = {(g.school, g.grade_level): g for g in bubble_parameter(_fixture_counts(), SY27_TARGETS)}
    rows = list(csv.DictReader((FIX / "nj_math_1_2_ay2026_school_goals.csv").open()))
    assert len(goals) == len(rows) == 16
    for r in rows:
        g = goals[(r["school"], int(r["grade_level"]))]
        assert g.bubble_parameter == float(r["bubble_parameter"]), r
        assert g.n_to_move == int(r["n_bubble_to_move"]), r
        assert g.goal == float(r["school_goal"]), r
        assert g.target == float(r["region_goal"]), r


def test_region_rollup_lands_within_a_point_of_target():
    goals = bubble_parameter(_fixture_counts(), SY27_TARGETS)
    by_region: dict[tuple[str, int], list] = {}
    for g in goals:
        by_region.setdefault((g.region, g.grade_level), []).append(g)
    for key, gs in by_region.items():
        implied = sum(g.n_proficient + g.n_to_move for g in gs) / sum(g.n_tested for g in gs)
        assert implied >= SY27_TARGETS[key] - 0.01
        assert implied <= SY27_TARGETS[key] + 0.03  # per-school ceiling overshoots


def test_bubble_parameter_zero_approaching_gives_none_and_zero_to_move():
    counts = [SchoolCounts("Newark", "TEAM", 1, 1, "Math", 10, 10, 2, 0, 8)]
    (g,) = bubble_parameter(counts, {("Newark", 1): 0.5})
    assert g.bubble_parameter is None and g.n_to_move == 0 and g.goal == 0.2


def test_blanket_sets_every_school_to_the_region_target():
    counts = [
        SchoolCounts("Newark", "TEAM", 1, 0, "Math", 20, 20, 6, 8, 6),
        SchoolCounts("Newark", "Rise", 2, 0, "Math", 10, 10, 8, 1, 1),
    ]
    goals = {g.school: g for g in blanket(counts, {("Newark", 0): 0.55})}
    # 0.55 * 20 - 6 is 5.000000000000002 in float64; the answer is 5, not 6
    assert goals["TEAM"].goal == 0.55 and goals["TEAM"].n_to_move == 5
    assert goals["Rise"].goal == 0.55 and goals["Rise"].n_to_move == 0
    assert goals["TEAM"].bubble_parameter is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_school_goal.py -q` Expected: FAIL
with `ModuleNotFoundError: teamster.goal_setting.rules.aggregate`

- [ ] **Step 4: Write `aggregate.py` and `school_goal.py`**

```python
# src/teamster/goal_setting/rules/aggregate.py
"""Counts per school, subject, and grade. The input to school goals."""

from __future__ import annotations

from dataclasses import dataclass

from teamster.goal_setting.records import StudentRecord


@dataclass(frozen=True)
class SchoolCounts:
    region: str
    school: str
    school_id: int
    grade_level: int
    subject: str
    n_roster: int
    n_tested: int
    n_proficient: int
    n_approaching: int
    n_below: int

    @property
    def group_key(self) -> tuple[str, str, int]:
        return (self.school, self.subject, self.grade_level)


def count_by_school(records: list[StudentRecord]) -> list[SchoolCounts]:
    acc: dict[tuple[str, str, int], dict] = {}
    for r in records:
        a = acc.setdefault(
            r.group_key,
            dict(region=r.region, school=r.school, school_id=r.school_id,
                 grade_level=r.grade_level, subject=r.subject,
                 n_roster=0, n_tested=0, n_proficient=0, n_approaching=0, n_below=0),
        )
        a["n_roster"] += 1
        a["n_tested"] += int(r.is_tested)
        a["n_proficient"] += int(r.is_proficient)
        a["n_approaching"] += int(r.is_approaching)
        a["n_below"] += int(r.is_below)
    return [SchoolCounts(**a) for a in acc.values()]
```

```python
# src/teamster/goal_setting/rules/school_goal.py
"""School goal strategies.

bubble_parameter: the production method. One parameter per region and grade
spreads the region target across schools in proportion to each school's
approaching students. blanket: every school gets the region target.
"""

from __future__ import annotations

import math

from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.aggregate import SchoolCounts

Targets = dict[tuple[str, int], float]  # (region, grade_level) -> proportion


class MissingTarget(ValueError):
    pass


def _target(targets: Targets, c: SchoolCounts) -> float:
    try:
        return targets[(c.region, c.grade_level)]
    except KeyError as e:
        raise MissingTarget(
            f"no target for {c.region} grade {c.grade_level} {c.subject}"
        ) from e


def region_parameters(counts: list[SchoolCounts], targets: Targets) -> dict[tuple[str, int], float | None]:
    acc: dict[tuple[str, int], list[int]] = {}
    for c in counts:
        t = acc.setdefault((c.region, c.grade_level), [0, 0, 0])
        t[0] += c.n_tested
        t[1] += c.n_proficient
        t[2] += c.n_approaching
    out: dict[tuple[str, int], float | None] = {}
    for key, (tested, prof, appr) in acc.items():
        target = targets.get(key)
        if target is None:
            raise MissingTarget(f"no target for {key[0]} grade {key[1]}")
        out[key] = None if appr == 0 else round((tested * target - prof) / appr, 2)
    return out


def _goal(c: SchoolCounts, n_to_move: int) -> float:
    return 0.0 if c.n_tested == 0 else round((c.n_proficient + n_to_move) / c.n_tested, 2)


def bubble_parameter(counts: list[SchoolCounts], targets: Targets) -> list[SchoolGoal]:
    params = region_parameters(counts, targets)
    out = []
    for c in counts:
        bp = params[(c.region, c.grade_level)]
        # round before ceil: 25 * 0.36 is 9.000000000000002 in float64
        n_to_move = 0 if bp is None else max(0, math.ceil(round(c.n_approaching * bp, 6)))
        out.append(
            SchoolGoal(
                region=c.region, school=c.school, school_id=c.school_id,
                grade_level=c.grade_level, subject=c.subject,
                n_roster=c.n_roster, n_tested=c.n_tested, n_proficient=c.n_proficient,
                n_approaching=c.n_approaching, n_below=c.n_below,
                target=_target(targets, c), bubble_parameter=bp,
                n_to_move=n_to_move, goal=_goal(c, n_to_move),
            )
        )
    return out


def blanket(counts: list[SchoolCounts], targets: Targets) -> list[SchoolGoal]:
    out = []
    for c in counts:
        target = _target(targets, c)
        # round before ceil: 0.55 * 20 is 11.000000000000002 in float64
        n_to_move = max(0, math.ceil(round(target * c.n_tested - c.n_proficient, 6)))
        out.append(
            SchoolGoal(
                region=c.region, school=c.school, school_id=c.school_id,
                grade_level=c.grade_level, subject=c.subject,
                n_roster=c.n_roster, n_tested=c.n_tested, n_proficient=c.n_proficient,
                n_approaching=c.n_approaching, n_below=c.n_below,
                target=target, bubble_parameter=None,
                n_to_move=n_to_move, goal=target,
            )
        )
    return out
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_school_goal.py -q` Expected: 6
passed. If the regression test fails on a rounding cent, the fixture is the
authority: compare `round()` behavior on the failing row and fix the
implementation, not the fixture.

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/rules/aggregate.py src/teamster/goal_setting/rules/school_goal.py tests/goal_setting/fixtures/nj_math_1_2_ay2026_school_goals.csv tests/goal_setting/fixtures/nj_math_1_2_ay2026_region_rollup.csv tests/goal_setting/test_school_goal.py
git -C <worktree> commit -m "feat(goal-setting): school goals via bubble parameter, SY27 regression fixture

Refs #5335"
```

---

### Task 4: Bucket 2

**Files:**

- Create: `src/teamster/goal_setting/rules/bucket2.py`
- Test: `tests/goal_setting/test_bucket2.py`

**Interfaces:**

- Consumes: `StudentRecord`, `SchoolGoal`.
- Produces:
  `top_approaching_to_move(records, goals: list[SchoolGoal], ties: str) -> list[StudentRecord]`
  which sets `rank` on every approaching student and `bucket="Bucket 2"` on
  those admitted; `none(records, goals, ties) -> list[StudentRecord]` which
  returns records unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_bucket2.py
from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.bucket2 import none, top_approaching_to_move

from .fixtures.roster_small import student


def goal(n_to_move: int, school="TEAM", grade=1) -> SchoolGoal:
    return SchoolGoal(
        region="Newark", school=school, school_id=1, grade_level=grade, subject="Math",
        n_roster=0, n_tested=0, n_proficient=0, n_approaching=0, n_below=0,
        target=0.35, bubble_parameter=0.5, n_to_move=n_to_move, goal=0.4,
    )


def appr(score: float, **kw):
    return student(is_approaching=True, projected_score=score, **kw)


def test_top_n_by_projected_score_enter_bucket_2():
    recs = [appr(410), appr(405), appr(400), appr(395)]
    out = top_approaching_to_move(recs, [goal(2)], "admit")
    buckets = [r.bucket for r in sorted(out, key=lambda r: -r.projected_score)]
    assert buckets == ["Bucket 2", "Bucket 2", None, None]


def test_ties_at_cutoff_all_admitted():
    recs = [appr(410), appr(405), appr(405), appr(395)]
    out = top_approaching_to_move(recs, [goal(2)], "admit")
    assert sum(r.bucket == "Bucket 2" for r in out) == 3
    ranks = sorted(r.rank for r in out)
    assert ranks == [1, 2, 2, 4]


def test_ties_strict_breaks_by_student_number():
    a = appr(405, student_number=5)
    b = appr(405, student_number=3)
    out = {r.student_number: r for r in top_approaching_to_move([a, b], [goal(1)], "strict")}
    assert out[3].bucket == "Bucket 2" and out[5].bucket is None
    assert (out[3].rank, out[5].rank) == (1, 2)


def test_ranking_is_per_school_and_grade():
    recs = [appr(410), appr(400, school="Rise"), appr(390, grade_level=2)]
    goals = [goal(1), goal(1, school="Rise"), goal(1, grade=2)]
    out = top_approaching_to_move(recs, goals, "admit")
    assert all(r.bucket == "Bucket 2" for r in out)
    assert all(r.rank == 1 for r in out)


def test_non_approaching_students_get_no_rank():
    recs = [student(is_proficient=True, projected_score=430), appr(400)]
    out = {r.student_number: r for r in top_approaching_to_move(recs, [goal(5)], "admit")}
    prof = next(r for r in out.values() if r.is_proficient)
    assert prof.rank is None and prof.bucket is None


def test_zero_to_move_admits_nobody_but_still_ranks():
    out = top_approaching_to_move([appr(410), appr(400)], [goal(0)], "admit")
    assert all(r.bucket is None for r in out) and sorted(r.rank for r in out) == [1, 2]


def test_reason_names_rank_and_n_to_move():
    (r,) = top_approaching_to_move([appr(409)], [goal(12)], "admit")
    assert r.reason == "approaching, projected 409, rank 1 of 12 to move"


def test_none_strategy_is_identity():
    recs = [appr(410)]
    assert none(recs, [goal(3)], "admit") == recs
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_bucket2.py -q` Expected: FAIL with
`ModuleNotFoundError`

- [ ] **Step 3: Write `bucket2.py`**

```python
# src/teamster/goal_setting/rules/bucket2.py
"""Bucket 2: the approaching students a school must move to reach its goal."""

from __future__ import annotations

from teamster.goal_setting.records import SchoolGoal, StudentRecord


def _fmt(score: float | None) -> str:
    return "untested" if score is None else f"{score:g}"


def top_approaching_to_move(
    records: list[StudentRecord], goals: list[SchoolGoal], ties: str
) -> list[StudentRecord]:
    to_move = {g.group_key: g.n_to_move for g in goals}
    by_group: dict[tuple[str, str, int], list[StudentRecord]] = {}
    for r in records:
        if r.is_approaching:
            by_group.setdefault(r.group_key, []).append(r)

    ranked: dict[int, tuple[int, str]] = {}  # student_number -> (rank, reason)
    for key, group in by_group.items():
        n = to_move.get(key, 0)
        ordered = sorted(group, key=lambda r: (-(r.projected_score or 0), r.student_number))
        prev_score, prev_rank = None, 0
        for i, r in enumerate(ordered, start=1):
            if ties == "admit" and r.projected_score == prev_score:
                rank = prev_rank
            else:
                rank = i
            prev_score, prev_rank = r.projected_score, rank
            reason = f"approaching, projected {_fmt(r.projected_score)}, rank {rank} of {n} to move"
            ranked[r.student_number] = (rank, reason)

    out = []
    for r in records:
        if r.student_number in ranked and r.is_approaching:
            rank, reason = ranked[r.student_number]
            admitted = rank <= to_move.get(r.group_key, 0)
            out.append(r.with_(rank=rank, reason=reason, bucket="Bucket 2" if admitted else None))
        else:
            out.append(r)
    return out


def none(records: list[StudentRecord], goals: list[SchoolGoal], ties: str) -> list[StudentRecord]:
    return records
```

Note: the tie-break key includes `student_number` so `strict` is deterministic;
under `admit`, equal scores share the higher rank so the `rank <= n_to_move`
test admits every tie at the cutoff, matching `rank()` in the production SQL.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_bucket2.py -q` Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/rules/bucket2.py tests/goal_setting/test_bucket2.py
git -C <worktree> commit -m "feat(goal-setting): bucket 2 ranking with admit and strict ties

Refs #5335"
```

---

### Task 5: Bucket 3 strategies and final assignment

**Files:**

- Create: `src/teamster/goal_setting/rules/bucket3.py`
- Create: `src/teamster/goal_setting/rules/assign.py`
- Test: `tests/goal_setting/test_bucket3.py`
- Test: `tests/goal_setting/test_assign.py`

**Interfaces:**

- Consumes: records after `classify` and `bucket2`.
- Produces: in `bucket3.py`, four functions with the same signature
  `(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]`:
  `remaining_approaching`, `stretch_reachers`,
  `remaining_approaching_or_stretch`, `none`. Each sets `bucket="Bucket 3"` and
  a reason on records it selects and leaves others unchanged. In `assign.py`,
  `finalize(records) -> list[StudentRecord]` which sets Bucket 1 on proficient
  students, Bucket 4 with `bucket4_outcome` on everyone still unassigned, and
  fills reasons.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_bucket3.py
from teamster.goal_setting.config import Levels
from teamster.goal_setting.rules.bucket3 import (
    none,
    remaining_approaching,
    remaining_approaching_or_stretch,
    stretch_reachers,
)

from .fixtures.roster_small import student, untested

LEVELS = Levels(proficient=[5], approaching=[4])


def appr_left_out(**kw):
    return student(is_approaching=True, rank=9, bucket=None, **kw)


def appr_in_b2(**kw):
    return student(is_approaching=True, rank=1, bucket="Bucket 2", **kw)


def below(stretch: int, **kw):
    return student(is_below=True, projected_level=3, stretch_level=stretch, **kw)


def test_remaining_approaching_takes_only_left_out_approaching():
    out = remaining_approaching([appr_left_out(), appr_in_b2(), below(5)], LEVELS)
    assert [r.bucket for r in out] == ["Bucket 3", "Bucket 2", None]


def test_stretch_reachers_takes_anyone_unplaced_whose_stretch_level_is_proficient():
    out = stretch_reachers([appr_left_out(stretch_level=5), appr_left_out(stretch_level=4), below(5), below(4)], LEVELS)
    assert [r.bucket for r in out] == ["Bucket 3", None, "Bucket 3", None]


def test_stretch_reacher_below_approaching_enters():
    (r,) = stretch_reachers([below(5)], LEVELS)
    assert r.bucket == "Bucket 3" and "stretch" in r.reason


def test_remaining_or_stretch_is_the_union():
    recs = [appr_left_out(stretch_level=4), below(5), below(4), appr_in_b2()]
    out = remaining_approaching_or_stretch(recs, LEVELS)
    assert [r.bucket for r in out] == ["Bucket 3", "Bucket 3", None, "Bucket 2"]


def test_untested_never_enters_bucket_3():
    for fn in (remaining_approaching, stretch_reachers, remaining_approaching_or_stretch):
        (r,) = fn([untested()], LEVELS)
        assert r.bucket is None


def test_none_is_identity():
    recs = [appr_left_out()]
    assert none(recs, LEVELS) == recs
```

```python
# tests/goal_setting/test_assign.py
from teamster.goal_setting.rules.assign import finalize

from .fixtures.roster_small import student, untested


def test_proficient_becomes_bucket_1_with_reason():
    (r,) = finalize([student(is_proficient=True, projected_level=5, projected_score=420)])
    assert r.bucket == "Bucket 1" and r.reason == "proficient, projected 420 at level 5"


def test_unassigned_tested_becomes_bucket_4_below():
    (r,) = finalize([student(is_below=True, projected_level=2)])
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "below")


def test_untested_becomes_bucket_4_untested():
    (r,) = finalize([untested()])
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "untested")
    assert r.reason == "untested"


def test_existing_bucket_2_and_3_are_kept():
    recs = [student(bucket="Bucket 2", reason="x"), student(bucket="Bucket 3", reason="y")]
    out = finalize(recs)
    assert [r.bucket for r in out] == ["Bucket 2", "Bucket 3"]
    assert [r.bucket4_outcome for r in out] == [None, None]


def test_left_out_approaching_becomes_bucket_4_below_with_rank_reason():
    (r,) = finalize([student(is_approaching=True, rank=9, reason="approaching, projected 400, rank 9 of 5 to move")])
    assert (r.bucket, r.bucket4_outcome) == ("Bucket 4", "below")
    assert r.reason.startswith("approaching, projected 400, rank 9 of 5")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/goal_setting/test_bucket3.py tests/goal_setting/test_assign.py -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `bucket3.py` and `assign.py`**

```python
# src/teamster/goal_setting/rules/bucket3.py
"""Bucket 3 strategies. Each takes records after Bucket 2 has been assigned."""

from __future__ import annotations

from teamster.goal_setting.config import Levels
from teamster.goal_setting.records import StudentRecord


def _unplaced_tested(r: StudentRecord) -> bool:
    return r.is_tested and r.bucket is None and not r.is_proficient


def _is_stretch_reacher(r: StudentRecord, levels: Levels) -> bool:
    return r.stretch_level is not None and r.stretch_level in levels.proficient


def remaining_approaching(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    return [
        r.with_(bucket="Bucket 3", reason=f"{r.reason}; remaining approaching")
        if _unplaced_tested(r) and r.is_approaching
        else r
        for r in records
    ]


def stretch_reachers(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    out = []
    for r in records:
        if _unplaced_tested(r) and _is_stretch_reacher(r, levels):
            base = r.reason or f"projected level {r.projected_level}"
            out.append(r.with_(bucket="Bucket 3", reason=f"{base}; reaches level {r.stretch_level} with stretch growth"))
        else:
            out.append(r)
    return out


def remaining_approaching_or_stretch(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    return stretch_reachers(remaining_approaching(records, levels), levels)


def none(records: list[StudentRecord], levels: Levels) -> list[StudentRecord]:
    return records
```

```python
# src/teamster/goal_setting/rules/assign.py
"""Bucket 1 and Bucket 4. Runs last."""

from __future__ import annotations

from teamster.goal_setting.records import StudentRecord


def _fmt(score: float | None) -> str:
    return "untested" if score is None else f"{score:g}"


def finalize(records: list[StudentRecord]) -> list[StudentRecord]:
    out = []
    for r in records:
        if r.is_proficient:
            out.append(r.with_(bucket="Bucket 1", reason=f"proficient, projected {_fmt(r.projected_score)} at level {r.projected_level}"))
        elif r.bucket in ("Bucket 2", "Bucket 3"):
            out.append(r)
        elif not r.is_tested:
            out.append(r.with_(bucket="Bucket 4", bucket4_outcome="untested", reason="untested"))
        else:
            reason = r.reason or f"projected level {r.projected_level}, below approaching"
            out.append(r.with_(bucket="Bucket 4", bucket4_outcome="below", reason=reason))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
`uv run pytest tests/goal_setting/test_bucket3.py tests/goal_setting/test_assign.py -q`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/rules/bucket3.py src/teamster/goal_setting/rules/assign.py tests/goal_setting/test_bucket3.py tests/goal_setting/test_assign.py
git -C <worktree> commit -m "feat(goal-setting): bucket 3 strategies and final bucket assignment

Refs #5335"
```

---

### Task 6: Invariants

**Files:**

- Create: `src/teamster/goal_setting/rules/invariants.py`
- Test: `tests/goal_setting/test_invariants.py`

**Interfaces:**

- Consumes: finalized records and `SchoolGoal` list.
- Produces: `InvariantError(Exception)` with `.failures: list[str]`;
  `check(records, goals, targets, school_goal_strategy: str) -> None` which
  raises `InvariantError` listing every failure, each naming region, school,
  grade, and subject.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_invariants.py
import pytest

from teamster.goal_setting.records import SchoolGoal
from teamster.goal_setting.rules.invariants import InvariantError, check

from .fixtures.roster_small import student


def goal(**kw) -> SchoolGoal:
    base = dict(
        region="Newark", school="TEAM", school_id=1, grade_level=1, subject="Math",
        n_roster=2, n_tested=2, n_proficient=1, n_approaching=1, n_below=0,
        target=0.5, bubble_parameter=0.0, n_to_move=0, goal=0.5,
    )
    base.update(kw)
    return SchoolGoal(**base)


def test_clean_proposal_passes():
    recs = [student(bucket="Bucket 1"), student(bucket="Bucket 4", bucket4_outcome="below")]
    check(recs, [goal()], {("Newark", 1): 0.5}, "bubble_parameter")


def test_duplicate_student_year_subject_aborts_naming_school():
    a = student(bucket="Bucket 1", student_number=7)
    b = a.with_(bucket="Bucket 2")
    with pytest.raises(InvariantError) as e:
        check([a, b], [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    msg = str(e.value)
    assert "Newark" in msg and "TEAM" in msg and "grade 1" in msg and "Math" in msg
    assert "2 buckets" in msg


def test_student_without_bucket_fails():
    with pytest.raises(InvariantError) as e:
        check([student(bucket=None)], [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    assert "no bucket" in str(e.value)


def test_missing_goal_row_for_a_school_grade_fails():
    recs = [student(bucket="Bucket 1"), student(bucket="Bucket 1", school="Rise")]
    with pytest.raises(InvariantError) as e:
        check(recs, [goal()], {("Newark", 1): 0.5}, "bubble_parameter")
    assert "Rise" in str(e.value) and "no goal row" in str(e.value)


def test_region_rollup_far_from_target_fails_for_bubble_parameter():
    recs = [student(bucket="Bucket 1"), student(bucket="Bucket 4", bucket4_outcome="below")]
    g = goal(n_proficient=1, n_to_move=0, n_tested=2)  # implied 0.50 vs target 0.80
    with pytest.raises(InvariantError) as e:
        check(recs, [g], {("Newark", 1): 0.80}, "bubble_parameter")
    assert "roll-up" in str(e.value) and "Newark" in str(e.value)


def test_region_rollup_check_skipped_for_blanket():
    recs = [student(bucket="Bucket 1"), student(bucket="Bucket 4", bucket4_outcome="below")]
    g = goal(n_proficient=1, n_to_move=0, n_tested=2)
    check(recs, [g], {("Newark", 1): 0.80}, "blanket")


def test_all_failures_are_reported_together():
    a = student(bucket=None, student_number=7)
    b = a.with_(bucket="Bucket 2")
    with pytest.raises(InvariantError) as e:
        check([a, b], [], {("Newark", 1): 0.5}, "blanket")
    assert len(e.value.failures) >= 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_invariants.py -q` Expected: FAIL
with `ModuleNotFoundError`

- [ ] **Step 3: Write `invariants.py`**

```python
# src/teamster/goal_setting/rules/invariants.py
"""Checks on an assembled proposal. Run before any file is written."""

from __future__ import annotations

from teamster.goal_setting.records import SchoolGoal, StudentRecord

ROLLUP_TOLERANCE = 0.01


class InvariantError(Exception):
    def __init__(self, failures: list[str]):
        self.failures = failures
        super().__init__("\n".join(failures))


def _where(r: StudentRecord | SchoolGoal) -> str:
    return f"{r.region} {r.school} grade {r.grade_level} {r.subject}"


def check(
    records: list[StudentRecord],
    goals: list[SchoolGoal],
    targets: dict[tuple[str, int], float],
    school_goal_strategy: str,
) -> None:
    failures: list[str] = []

    seen: dict[tuple[str, int, str], list[StudentRecord]] = {}
    for r in records:
        seen.setdefault((r.region, r.student_number, r.subject), []).append(r)
        if r.bucket is None:
            failures.append(f"{_where(r)}: a student has no bucket")
    for key, rows in seen.items():
        buckets = {x.bucket for x in rows}
        if len(rows) > 1:
            failures.append(
                f"{_where(rows[0])}: one student holds {len(buckets)} buckets "
                f"({', '.join(sorted(str(b) for b in buckets))}) across {len(rows)} rows"
            )

    goal_keys = {g.group_key for g in goals}
    for key in sorted({r.group_key for r in records}):
        if key not in goal_keys:
            sample = next(r for r in records if r.group_key == key)
            failures.append(f"{_where(sample)}: no goal row")

    if school_goal_strategy == "bubble_parameter":
        acc: dict[tuple[str, int], list[int]] = {}
        for g in goals:
            t = acc.setdefault((g.region, g.grade_level), [0, 0])
            t[0] += g.n_proficient + g.n_to_move
            t[1] += g.n_tested
        for (region, grade), (num, den) in acc.items():
            target = targets.get((region, grade))
            if target is None or den == 0:
                continue
            implied = num / den
            if implied < target - ROLLUP_TOLERANCE:
                failures.append(
                    f"{region} grade {grade}: region roll-up {implied:.3f} is below target {target:.2f}"
                )

    if failures:
        raise InvariantError(failures)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_invariants.py -q` Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/rules/invariants.py tests/goal_setting/test_invariants.py
git -C <worktree> commit -m "feat(goal-setting): proposal invariants with located failure messages

Refs #5335"
```

---

### Task 7: Freshness gate

**Files:**

- Create: `src/teamster/goal_setting/rules/freshness.py`
- Test: `tests/goal_setting/test_freshness.py`

**Interfaces:**

- Consumes: `SchoolCounts` (from `count_by_school` run on the raw fetched
  records, before classification) and `Freshness` config.
- Produces: `GateResult` dataclass with `errors: list[str]`,
  `warnings: list[str]`, and `.ok` property;
  `Baseline = dict[tuple[str, str, int], int]` keyed by
  `(region, school, grade_level)` giving a roster count;
  `check(counts: list[SchoolCounts], cfg: Freshness, baseline: Baseline | None) -> GateResult`.
  Rule: tested share below `min_tested_share` is an error. With a baseline,
  roster count below `baseline * (1 - roster_tolerance)` is an error and above
  `baseline * (1 + roster_tolerance)` is a warning. Without a baseline, a
  warning says no baseline was available.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_freshness.py
from teamster.goal_setting.config import Freshness
from teamster.goal_setting.rules.aggregate import SchoolCounts
from teamster.goal_setting.rules.freshness import check

CFG = Freshness(min_tested_share=0.85, roster_tolerance=0.15)


def counts(n_roster=100, n_tested=95, school="TEAM", grade=1) -> SchoolCounts:
    return SchoolCounts("Newark", school, 1, grade, "Math", n_roster, n_tested, 0, 0, 0)


def test_clean_pass_with_baseline():
    res = check([counts()], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok and res.errors == [] and res.warnings == []


def test_low_tested_share_is_an_error_naming_school_and_numbers():
    res = check([counts(n_tested=60)], CFG, {("Newark", "TEAM", 1): 100})
    assert not res.ok
    assert "Newark TEAM grade 1 Math" in res.errors[0]
    assert "0.60" in res.errors[0] and "0.85" in res.errors[0]


def test_roster_far_below_baseline_is_an_error():
    res = check([counts(n_roster=50, n_tested=50)], CFG, {("Newark", "TEAM", 1): 100})
    assert not res.ok and "50" in res.errors[0] and "100" in res.errors[0]


def test_roster_above_baseline_is_a_warning_not_an_error():
    res = check([counts(n_roster=130, n_tested=125)], CFG, {("Newark", "TEAM", 1): 100})
    assert res.ok and res.warnings and "130" in res.warnings[0]


def test_school_missing_from_roster_but_in_baseline_is_an_error():
    res = check([counts()], CFG, {("Newark", "TEAM", 1): 100, ("Newark", "Rise", 1): 80})
    assert not res.ok and "Rise" in res.errors[0] and "0 students" in res.errors[0]


def test_no_baseline_is_a_single_warning():
    res = check([counts()], CFG, None)
    assert res.ok and len(res.warnings) == 1 and "no baseline" in res.warnings[0]


def test_empty_roster_is_an_error():
    res = check([], CFG, None)
    assert not res.ok and "0 rows" in res.errors[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_freshness.py -q` Expected: FAIL with
`ModuleNotFoundError`

- [ ] **Step 3: Write `freshness.py`**

```python
# src/teamster/goal_setting/rules/freshness.py
"""Completeness gate. Runs between fetch and compute.

A half-loaded upstream and a small group look identical to the rules and both
land every student in Bucket 4. This gate compares what was fetched against a
baseline and a tested-share floor before any rule runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from teamster.goal_setting.config import Freshness
from teamster.goal_setting.rules.aggregate import SchoolCounts

Baseline = dict[tuple[str, str, int], int]  # (region, school, grade) -> roster count


@dataclass
class GateResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check(counts: list[SchoolCounts], cfg: Freshness, baseline: Baseline | None) -> GateResult:
    res = GateResult()
    if not counts:
        res.errors.append("roster fetch returned 0 rows")
        return res

    for c in counts:
        where = f"{c.region} {c.school} grade {c.grade_level} {c.subject}"
        share = 0.0 if c.n_roster == 0 else c.n_tested / c.n_roster
        if share < cfg.min_tested_share:
            res.errors.append(
                f"{where}: tested share {share:.2f} is below floor {cfg.min_tested_share:.2f} "
                f"({c.n_tested} of {c.n_roster})"
            )
        if baseline is not None:
            base = baseline.get((c.region, c.school, c.grade_level))
            if base is None:
                res.warnings.append(f"{where}: no baseline row; {c.n_roster} students fetched")
                continue
            low = base * (1 - cfg.roster_tolerance)
            high = base * (1 + cfg.roster_tolerance)
            if c.n_roster < low:
                res.errors.append(f"{where}: roster {c.n_roster} is below baseline {base} minus {cfg.roster_tolerance:.0%}")
            elif c.n_roster > high:
                res.warnings.append(f"{where}: roster {c.n_roster} is above baseline {base} plus {cfg.roster_tolerance:.0%}")

    if baseline is None:
        res.warnings.append("no baseline available; roster counts were not compared to a prior run")
    else:
        fetched = {(c.region, c.school, c.grade_level) for c in counts}
        for (region, school, grade), base in sorted(baseline.items()):
            if (region, school, grade) not in fetched:
                res.errors.append(f"{region} {school} grade {grade}: 0 students fetched, baseline {base}")
    return res
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_freshness.py -q` Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/rules/freshness.py tests/goal_setting/test_freshness.py
git -C <worktree> commit -m "feat(goal-setting): freshness gate with error and warn severities

Refs #5335"
```

---

### Task 8: Pipeline, manifest, and outputs

**Files:**

- Create: `src/teamster/goal_setting/pipeline.py`
- Create: `src/teamster/goal_setting/manifest.py`
- Create: `src/teamster/goal_setting/outputs.py`
- Create: `config/goal_setting/manifests/.gitkeep`
- Modify: `.gitignore` (add `runs/`)
- Test: `tests/goal_setting/test_pipeline_outputs.py`

**Interfaces:**

- Consumes: everything from Tasks 1 to 7.
- Produces:
  - `pipeline.Proposal` dataclass: `group: Group`, `academic_year: int`,
    `records: list[StudentRecord]`, `goals: list[SchoolGoal]`,
    `targets: dict[tuple[str, int], float]`, `gate: GateResult`.
  - `pipeline.run_group(group, academic_year, records, targets, baseline) -> Proposal`.
    Order: raw counts, freshness gate (raises `FreshnessError` on errors unless
    `force_stale=True`), classify, counts, school goal strategy, bucket2,
    bucket3, finalize, invariants. Strategy functions are resolved from
    `STRATEGIES` by dotted path; a `None` path raises `NotImplementedError`
    naming the strategy.
  - `manifest.build(proposal, rules_sha, crosswalk_sha, inputs: list[dict], diff: dict | None, force_stale: bool) -> dict`
    with keys
    `academic_year, group, rollout_date, run_at, rules_sha, crosswalk_sha, inputs, gate_warnings, gate_overridden, bubble_parameters, school_goals, bucket_counts, diff`.
    `bucket_counts` is a list of
    `{region, school, grade_level, subject, bucket, bucket4_outcome, n}`.
  - `outputs.write_run(out_dir: Path, proposal, manifest: dict, crosswalk: Crosswalk) -> list[Path]`
    writing `school_goals.csv`, `ps_programs.csv`, `student_buckets.csv`,
    `explain.csv`, `manifest.json`, in one call at the end.
  - `outputs.summary_tables(proposal) -> str` for the terminal.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_pipeline_outputs.py
import csv
import json
from datetime import date
from pathlib import Path

import pytest

from teamster.goal_setting.config import load_crosswalk, load_rules
from teamster.goal_setting.manifest import build
from teamster.goal_setting.outputs import summary_tables, write_run
from teamster.goal_setting.pipeline import FreshnessError, run_group

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]
RULES = load_rules(REPO / "config/goal_setting/ay2026.yaml")
XW = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")
GROUP = RULES.group("nj_math_1_2")
TARGETS = {("Newark", 1): 0.50}


def roster():
    # 10 students, one school, grade 1: 3 proficient, 4 approaching, 2 below, 1 untested
    return (
        [student(projected_level=5, projected_score=430 + i) for i in range(3)]
        + [student(projected_level=4, projected_score=400 + i, stretch_level=5 if i == 0 else 4) for i in range(4)]
        + [student(projected_level=3, projected_score=380, stretch_level=5), student(projected_level=2, projected_score=350, stretch_level=3)]
        + [untested()]
    )


def test_run_group_assigns_every_student_once():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    assert len(p.records) == 10
    assert all(r.bucket for r in p.records)
    # target 0.50 of 9 tested = 4.5 -> bp = (4.5 - 3) / 4 = 0.38 -> ceil(4 * 0.38) = 2
    assert sum(r.bucket == "Bucket 1" for r in p.records) == 3
    assert sum(r.bucket == "Bucket 2" for r in p.records) == 2
    # remaining approaching (2) + below stretch reacher (1)
    assert sum(r.bucket == "Bucket 3" for r in p.records) == 3
    assert sum(r.bucket == "Bucket 4" for r in p.records) == 2
    assert {r.bucket4_outcome for r in p.records if r.bucket == "Bucket 4"} == {"below", "untested"}
    (g,) = p.goals
    assert g.bubble_parameter == 0.38 and g.n_to_move == 2 and g.goal == 0.56


def test_freshness_error_stops_before_compute():
    recs = [untested() for _ in range(10)]
    with pytest.raises(FreshnessError) as e:
        run_group(GROUP, 2026, recs, TARGETS, baseline=None)
    assert "tested share 0.00" in str(e.value)


def test_force_stale_records_override():
    recs = [untested() for _ in range(10)]
    p = run_group(GROUP, 2026, recs, TARGETS, baseline=None, force_stale=True)
    assert p.gate.errors and all(r.bucket == "Bucket 4" for r in p.records)


def test_unimplemented_strategy_raises_naming_it():
    g = GROUP.model_copy(update={"school_goal": "flat"})
    with pytest.raises(NotImplementedError) as e:
        run_group(g, 2026, roster(), TARGETS, baseline=None)
    assert "flat" in str(e.value)


def test_manifest_has_no_student_identifiers_and_counts_bucket4_outcomes():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    m = build(p, rules_sha="r" * 40, crosswalk_sha="c" * 40, inputs=[], diff=None, force_stale=False)
    text = json.dumps(m)
    for r in p.records:
        assert str(r.student_number) not in text
    outcomes = {(b["bucket"], b["bucket4_outcome"]): b["n"] for b in m["bucket_counts"]}
    assert outcomes[("Bucket 4", "untested")] == 1 and outcomes[("Bucket 4", "below")] == 1
    assert m["bubble_parameters"] == [{"region": "Newark", "grade_level": 1, "bubble_parameter": 0.38}]
    assert m["group"] == "nj_math_1_2" and m["rollout_date"] == "2026-10-15"


def test_write_run_writes_five_files_in_expected_shapes(tmp_path):
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    m = build(p, "r" * 40, "c" * 40, [], None, False)
    written = write_run(tmp_path, p, m, XW)
    names = sorted(f.name for f in written)
    assert names == ["explain.csv", "manifest.json", "ps_programs.csv", "school_goals.csv", "student_buckets.csv"]

    goals = list(csv.DictReader((tmp_path / "school_goals.csv").open()))
    assert list(goals[0]) == ["Academic_Year", "School_ID", "Grade_Level", "Illuminate_Subject_Area", "School_Goal", "Grade_Band_Goal"]
    assert goals[0]["Illuminate_Subject_Area"] == "Mathematics" and goals[0]["School_Goal"] == "0.56"

    programs = list(csv.DictReader((tmp_path / "ps_programs.csv").open()))
    assert list(programs[0]) == ["region", "student_number", "programid", "enter_date", "exit_date"]
    assert len(programs) == 8  # buckets 1-3 only
    assert {p_["programid"] for p_ in programs} == {"7577", "7375", "7574"}
    assert programs[0]["enter_date"] == "2026-07-01" and programs[0]["exit_date"] == "2027-06-30"

    explain = list(csv.DictReader((tmp_path / "explain.csv").open()))
    assert list(explain[0]) == ["region", "student_number", "subject", "bucket", "reason"]
    assert all(e["reason"] for e in explain)

    sb = list(csv.DictReader((tmp_path / "student_buckets.csv").open()))
    assert "bucket4_outcome" in sb[0] and "rank" in sb[0] and "projected_score" in sb[0]


def test_summary_tables_mention_school_and_untested_count():
    p = run_group(GROUP, 2026, roster(), TARGETS, baseline=None)
    text = summary_tables(p)
    assert "TEAM" in text and "untested" in text and "0.38" in text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_pipeline_outputs.py -q` Expected:
FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `pipeline.py`**

```python
# src/teamster/goal_setting/pipeline.py
"""Assemble one group's proposal. Pure: takes records, returns a Proposal."""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from teamster.goal_setting.config import STRATEGIES, Group
from teamster.goal_setting.records import SchoolGoal, StudentRecord
from teamster.goal_setting.rules import assign, classify, freshness, invariants
from teamster.goal_setting.rules.aggregate import count_by_school
from teamster.goal_setting.rules.freshness import Baseline, GateResult

Targets = dict[tuple[str, int], float]


class FreshnessError(Exception):
    pass


@dataclass
class Proposal:
    group: Group
    academic_year: int
    records: list[StudentRecord]
    goals: list[SchoolGoal]
    targets: Targets
    gate: GateResult


def resolve(slot: str, name: str):
    path = STRATEGIES[slot][name]
    if path is None:
        raise NotImplementedError(f"{slot} strategy '{name}' is not implemented yet")
    module, _, attr = path.partition(":")
    return getattr(importlib.import_module(module), attr)


def run_group(
    group: Group,
    academic_year: int,
    records: list[StudentRecord],
    targets: Targets,
    baseline: Baseline | None,
    force_stale: bool = False,
) -> Proposal:
    gate = freshness.check(count_by_school(records), group.freshness, baseline)
    if gate.errors and not force_stale:
        raise FreshnessError("\n".join(gate.errors))

    recs = classify.classify(records, group.levels)
    counts = count_by_school(recs)
    goals = resolve("school_goal", group.school_goal)(counts, targets)
    recs = resolve("bucket2", group.bucket2.strategy)(recs, goals, group.bucket2.ties)
    recs = resolve("bucket3", group.bucket3.strategy)(recs, group.levels)
    recs = assign.finalize(recs)
    invariants.check(recs, goals, targets, group.school_goal)
    return Proposal(group, academic_year, recs, goals, targets, gate)
```

- [ ] **Step 4: Write `manifest.py`**

```python
# src/teamster/goal_setting/manifest.py
"""The committed, non-PII record of a run."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from teamster.goal_setting.pipeline import Proposal


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bucket_counts(p: Proposal) -> list[dict]:
    acc: dict[tuple, int] = {}
    for r in p.records:
        key = (r.region, r.school, r.grade_level, r.subject, r.bucket, r.bucket4_outcome)
        acc[key] = acc.get(key, 0) + 1
    return [
        dict(region=k[0], school=k[1], grade_level=k[2], subject=k[3], bucket=k[4], bucket4_outcome=k[5], n=n)
        for k, n in sorted(acc.items(), key=lambda kv: tuple(str(x) for x in kv[0]))
    ]


def build(
    p: Proposal,
    rules_sha: str,
    crosswalk_sha: str,
    inputs: list[dict],
    diff: dict | None,
    force_stale: bool,
) -> dict:
    params = sorted(
        {(g.region, g.grade_level, g.bubble_parameter) for g in p.goals},
        key=lambda t: (t[0], t[1]),
    )
    return {
        "academic_year": p.academic_year,
        "group": p.group.name,
        "rollout_date": p.group.rollout_date.isoformat(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rules_sha": rules_sha,
        "crosswalk_sha": crosswalk_sha,
        "inputs": inputs,
        "gate_warnings": p.gate.warnings,
        "gate_errors": p.gate.errors,
        "gate_overridden": bool(p.gate.errors) and force_stale,
        "bubble_parameters": [
            {"region": r, "grade_level": g, "bubble_parameter": bp} for r, g, bp in params
        ],
        "school_goals": [
            {
                "region": g.region, "school": g.school, "school_id": g.school_id,
                "grade_level": g.grade_level, "subject": g.subject,
                "n_roster": g.n_roster, "n_tested": g.n_tested,
                "n_proficient": g.n_proficient, "n_approaching": g.n_approaching,
                "n_below": g.n_below, "target": g.target,
                "bubble_parameter": g.bubble_parameter, "n_to_move": g.n_to_move,
                "goal": g.goal,
            }
            for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level))
        ],
        "bucket_counts": bucket_counts(p),
        "diff": diff,
    }
```

- [ ] **Step 5: Write `outputs.py`**

```python
# src/teamster/goal_setting/outputs.py
"""Every file a run writes, in one call, after invariants have passed."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from teamster.goal_setting.config import Crosswalk
from teamster.goal_setting.pipeline import Proposal

ILLUMINATE_SUBJECT = {"Math": "Mathematics", "Reading": "Text Study"}
PROGRAM_BUCKETS = ("Bucket 1", "Bucket 2", "Bucket 3")


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> Path:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def school_goal_rows(p: Proposal) -> list[dict]:
    return [
        {
            "Academic_Year": p.academic_year,
            "School_ID": g.school_id,
            "Grade_Level": g.grade_level,
            "Illuminate_Subject_Area": ILLUMINATE_SUBJECT[g.subject],
            "School_Goal": f"{g.goal:.2f}",
            "Grade_Band_Goal": f"{g.target:.2f}",
        }
        for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level))
    ]


def program_rows(p: Proposal, xw: Crosswalk) -> list[dict]:
    enter = date(p.academic_year, 7, 1).isoformat()
    exit_ = date(p.academic_year + 1, 6, 30).isoformat()
    rows = []
    for r in sorted(p.records, key=lambda r: (r.region, r.school, r.grade_level, r.student_number)):
        if r.bucket in PROGRAM_BUCKETS:
            rows.append(
                {
                    "region": r.region,
                    "student_number": r.student_number,
                    "programid": xw.program_id(r.region, r.subject, r.bucket),
                    "enter_date": enter,
                    "exit_date": exit_,
                }
            )
    return rows


def write_run(out_dir: Path, p: Proposal, manifest: dict, xw: Crosswalk) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    student_rows = [asdict(r) for r in sorted(p.records, key=lambda r: (r.region, r.school, r.grade_level, r.bucket or "", r.student_number))]
    student_cols = list(student_rows[0]) if student_rows else []
    written = [
        _write_csv(out_dir / "school_goals.csv", school_goal_rows(p), ["Academic_Year", "School_ID", "Grade_Level", "Illuminate_Subject_Area", "School_Goal", "Grade_Band_Goal"]),
        _write_csv(out_dir / "ps_programs.csv", program_rows(p, xw), ["region", "student_number", "programid", "enter_date", "exit_date"]),
        _write_csv(out_dir / "student_buckets.csv", student_rows, student_cols),
        _write_csv(out_dir / "explain.csv", student_rows, ["region", "student_number", "subject", "bucket", "reason"]),
    ]
    mpath = out_dir / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    written.append(mpath)
    return written


def summary_tables(p: Proposal) -> str:
    lines = ["region | school | gr | roster | tested | untested | prof | appr | bp | to_move | target | goal | B1 | B2 | B3 | B4"]
    by_key: dict[tuple, dict[str, int]] = {}
    for r in p.records:
        d = by_key.setdefault(r.group_key, {"B1": 0, "B2": 0, "B3": 0, "B4": 0, "untested": 0})
        d["B" + r.bucket[-1]] += 1
        d["untested"] += int(r.bucket4_outcome == "untested")
    for g in sorted(p.goals, key=lambda g: (g.region, g.school, g.grade_level)):
        d = by_key.get(g.group_key, {})
        bp = "" if g.bubble_parameter is None else f"{g.bubble_parameter:.2f}"
        lines.append(
            f"{g.region} | {g.school} | {g.grade_level} | {g.n_roster} | {g.n_tested} | {d.get('untested', 0)} | "
            f"{g.n_proficient} | {g.n_approaching} | {bp} | {g.n_to_move} | {g.target:.2f} | {g.goal:.2f} | "
            f"{d.get('B1', 0)} | {d.get('B2', 0)} | {d.get('B3', 0)} | {d.get('B4', 0)}"
        )
    lines.append("")
    lines.append("region | gr | tested | prof + to_move | implied | target")
    acc: dict[tuple[str, int], list[int]] = {}
    for g in p.goals:
        t = acc.setdefault((g.region, g.grade_level), [0, 0])
        t[0] += g.n_tested
        t[1] += g.n_proficient + g.n_to_move
    for (region, grade), (tested, num) in sorted(acc.items()):
        implied = 0 if tested == 0 else num / tested
        lines.append(f"{region} | {grade} | {tested} | {num} | {implied:.3f} | {p.targets.get((region, grade), float('nan')):.2f}")
    if p.gate.warnings:
        lines += ["", "gate warnings:"] + [f"  {w}" for w in p.gate.warnings]
    return "\n".join(lines)
```

- [ ] **Step 6: Add `runs/` to `.gitignore` and the manifests folder**

Append to `.gitignore` after the `.claude/scratch/` line:

```text
runs/
```

```bash
mkdir -p <worktree>/config/goal_setting/manifests && touch <worktree>/config/goal_setting/manifests/.gitkeep
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting -q` Expected: all passed (46 so far)

- [ ] **Step 8: Commit**

```bash
git -C <worktree> add .gitignore config/goal_setting/manifests/.gitkeep src/teamster/goal_setting/pipeline.py src/teamster/goal_setting/manifest.py src/teamster/goal_setting/outputs.py tests/goal_setting/test_pipeline_outputs.py
git -C <worktree> commit -m "feat(goal-setting): pipeline, manifest, and single-call outputs

Refs #5335"
```

---

### Task 9: Diff against the prior run

**Files:**

- Create: `src/teamster/goal_setting/diff.py`
- Test: `tests/goal_setting/test_diff.py`

**Interfaces:**

- Consumes: manifest dicts from Task 8; optional prior `student_buckets.csv`.
- Produces: `DiffReport` dataclass with `goal_changes: list[dict]`,
  `count_changes: list[dict]`, `transitions: list[dict] | None`,
  `roster_churn: dict | None`, `verdict: str` in
  `{"no prior run", "no change", "changed counts", "additive only", "reclassifies"}`
  (`changed counts` is the manifest-depth verdict when goals or counts moved but
  no student file was supplied to say who), `n_reclassified: int`, and
  `render() -> str`;
  `diff_manifests(prior: dict | None, current: dict) -> DiffReport`;
  `add_student_depth(report, prior_rows: list[dict], current_records) -> DiffReport`;
  `load_prior_manifest(path: Path) -> dict | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_diff.py
import copy

from teamster.goal_setting.diff import add_student_depth, diff_manifests

from .fixtures.roster_small import student

BASE = {
    "group": "nj_math_1_2",
    "school_goals": [
        {"region": "Newark", "school": "TEAM", "school_id": 1, "grade_level": 1, "subject": "Math",
         "bubble_parameter": 0.52, "n_to_move": 12, "goal": 0.41},
    ],
    "bucket_counts": [
        {"region": "Newark", "school": "TEAM", "grade_level": 1, "subject": "Math", "bucket": "Bucket 1", "bucket4_outcome": None, "n": 20},
        {"region": "Newark", "school": "TEAM", "grade_level": 1, "subject": "Math", "bucket": "Bucket 2", "bucket4_outcome": None, "n": 12},
    ],
}


def test_no_prior_run():
    rep = diff_manifests(None, BASE)
    assert rep.verdict == "no prior run" and "no prior" in rep.render()


def test_identical_manifests_is_no_change():
    rep = diff_manifests(BASE, copy.deepcopy(BASE))
    assert rep.verdict == "no change" and rep.goal_changes == [] and rep.count_changes == []


def test_goal_and_count_changes_are_listed():
    cur = copy.deepcopy(BASE)
    cur["school_goals"][0].update(bubble_parameter=0.48, n_to_move=11, goal=0.40)
    cur["bucket_counts"][1]["n"] = 11
    rep = diff_manifests(BASE, cur)
    assert rep.goal_changes[0]["school"] == "TEAM"
    assert rep.goal_changes[0]["old"]["bubble_parameter"] == 0.52 and rep.goal_changes[0]["new"]["bubble_parameter"] == 0.48
    assert rep.count_changes[0] == {"region": "Newark", "school": "TEAM", "grade_level": 1, "subject": "Math", "bucket": "Bucket 2", "bucket4_outcome": None, "old": 12, "new": 11}
    text = rep.render()
    assert "0.52" in text and "0.48" in text and "Bucket 2" in text


def test_student_depth_additive_only():
    prior = [{"region": "Newark", "student_number": "1", "subject": "Math", "bucket": "Bucket 1"}]
    cur = [student(student_number=1, bucket="Bucket 1"), student(student_number=2, bucket="Bucket 4", bucket4_outcome="untested")]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.verdict == "additive only" and rep.roster_churn == {"new": 1, "gone": 0}
    assert rep.transitions == []


def test_student_depth_reclassification_is_named_and_counted():
    prior = [
        {"region": "Newark", "student_number": "1", "subject": "Math", "bucket": "Bucket 2"},
        {"region": "Newark", "student_number": "2", "subject": "Math", "bucket": "Bucket 2"},
    ]
    cur = [student(student_number=1, bucket="Bucket 4", bucket4_outcome="below"), student(student_number=2, bucket="Bucket 2")]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.verdict == "reclassifies" and rep.n_reclassified == 1
    assert rep.transitions == [{"region": "Newark", "school": "TEAM", "grade_level": 1, "subject": "Math", "from": "Bucket 2", "to": "Bucket 4", "n": 1}]
    assert "RECLASSIFIES 1" in rep.render()


def test_student_depth_keys_on_region_and_student_number():
    prior = [{"region": "Camden", "student_number": "1", "subject": "Math", "bucket": "Bucket 2"}]
    cur = [student(student_number=1, region="Newark", bucket="Bucket 4", bucket4_outcome="below")]
    rep = add_student_depth(diff_manifests(BASE, copy.deepcopy(BASE)), prior, cur)
    assert rep.transitions == [] and rep.roster_churn == {"new": 1, "gone": 1}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_diff.py -q` Expected: FAIL with
`ModuleNotFoundError`

- [ ] **Step 3: Write `diff.py`**

```python
# src/teamster/goal_setting/diff.py
"""Compare a proposal to the prior run for the same group and year.

Manifest depth always works because manifests are committed. Student depth
needs the prior run's student_buckets.csv, which lives only on the operator's
disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from teamster.goal_setting.records import StudentRecord

GOAL_FIELDS = ("bubble_parameter", "n_to_move", "goal")


@dataclass
class DiffReport:
    verdict: str
    goal_changes: list[dict] = field(default_factory=list)
    count_changes: list[dict] = field(default_factory=list)
    transitions: list[dict] | None = None
    roster_churn: dict | None = None
    n_reclassified: int = 0
    depth: str = "manifest"

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict, "depth": self.depth, "n_reclassified": self.n_reclassified,
            "goal_changes": self.goal_changes, "count_changes": self.count_changes,
            "transitions": self.transitions, "roster_churn": self.roster_churn,
        }

    def render(self) -> str:
        if self.verdict == "no prior run":
            return "diff: no prior run for this group and year"
        lines = [f"diff vs prior run ({self.depth} depth)"]
        if self.goal_changes:
            lines.append("goal changes: region | school | gr | field | old | new")
            for c in self.goal_changes:
                for f in GOAL_FIELDS:
                    if c["old"][f] != c["new"][f]:
                        lines.append(f"  {c['region']} | {c['school']} | {c['grade_level']} | {f} | {c['old'][f]} | {c['new'][f]}")
        if self.count_changes:
            lines.append("bucket count changes: region | school | gr | bucket | old | new")
            for c in self.count_changes:
                tag = c["bucket"] + (f" ({c['bucket4_outcome']})" if c["bucket4_outcome"] else "")
                lines.append(f"  {c['region']} | {c['school']} | {c['grade_level']} | {tag} | {c['old']} | {c['new']}")
        if self.transitions is not None:
            lines.append(f"roster churn: {self.roster_churn['new']} new, {self.roster_churn['gone']} gone")
            if self.transitions:
                lines.append("transitions: region | school | gr | from | to | n")
                for t in self.transitions:
                    lines.append(f"  {t['region']} | {t['school']} | {t['grade_level']} | {t['from']} | {t['to']} | {t['n']}")
        verdict = self.verdict.upper() if self.verdict == "reclassifies" else self.verdict
        suffix = f" {self.n_reclassified} students already proposed" if self.verdict == "reclassifies" else ""
        lines.append(f"verdict: {verdict}{suffix}")
        return "\n".join(lines)


def load_prior_manifest(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def _goal_key(g: dict) -> tuple:
    return (g["region"], g["school"], g["grade_level"], g["subject"])


def _count_key(c: dict) -> tuple:
    return (c["region"], c["school"], c["grade_level"], c["subject"], c["bucket"], c["bucket4_outcome"])


def diff_manifests(prior: dict | None, current: dict) -> DiffReport:
    if prior is None:
        return DiffReport(verdict="no prior run")
    rep = DiffReport(verdict="no change")

    old_goals = {_goal_key(g): g for g in prior["school_goals"]}
    for g in current["school_goals"]:
        o = old_goals.get(_goal_key(g))
        if o is None or any(o[f] != g[f] for f in GOAL_FIELDS):
            rep.goal_changes.append({
                "region": g["region"], "school": g["school"], "grade_level": g["grade_level"], "subject": g["subject"],
                "old": {f: (o or {}).get(f) for f in GOAL_FIELDS}, "new": {f: g[f] for f in GOAL_FIELDS},
            })

    old_counts = {_count_key(c): c["n"] for c in prior["bucket_counts"]}
    new_counts = {_count_key(c): c["n"] for c in current["bucket_counts"]}
    for key in sorted(set(old_counts) | set(new_counts), key=lambda k: tuple(str(x) for x in k)):
        o, n = old_counts.get(key, 0), new_counts.get(key, 0)
        if o != n:
            rep.count_changes.append({
                "region": key[0], "school": key[1], "grade_level": key[2], "subject": key[3],
                "bucket": key[4], "bucket4_outcome": key[5], "old": o, "new": n,
            })

    if rep.goal_changes or rep.count_changes:
        rep.verdict = "changed counts"
    return rep


def add_student_depth(rep: DiffReport, prior_rows: list[dict], current: list[StudentRecord]) -> DiffReport:
    rep.depth = "student"
    prior = {(r["region"], int(r["student_number"]), r["subject"]): r["bucket"] for r in prior_rows}
    now = {(r.region, r.student_number, r.subject): r for r in current}
    new = len(set(now) - set(prior))
    gone = len(set(prior) - set(now))
    acc: dict[tuple, int] = {}
    for key, r in now.items():
        old = prior.get(key)
        if old is not None and old != r.bucket:
            k = (r.region, r.school, r.grade_level, r.subject, old, r.bucket)
            acc[k] = acc.get(k, 0) + 1
    rep.transitions = [
        {"region": k[0], "school": k[1], "grade_level": k[2], "subject": k[3], "from": k[4], "to": k[5], "n": n}
        for k, n in sorted(acc.items())
    ]
    rep.roster_churn = {"new": new, "gone": gone}
    rep.n_reclassified = sum(acc.values())
    if rep.n_reclassified:
        rep.verdict = "reclassifies"
    elif new or gone:
        rep.verdict = "additive only"
    elif not rep.goal_changes and not rep.count_changes:
        rep.verdict = "no change"
    return rep
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_diff.py -q` Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/diff.py tests/goal_setting/test_diff.py
git -C <worktree> commit -m "feat(goal-setting): diff a proposal against the prior run

Refs #5335"
```

---

### Task 10: Adapters, input archive, and targets

**Files:**

- Create: `src/teamster/goal_setting/adapters/__init__.py`
- Create: `src/teamster/goal_setting/adapters/archive.py`
- Create: `src/teamster/goal_setting/adapters/roster_sql.py`
- Create: `src/teamster/goal_setting/adapters/iready_boy.py`
- Create: `src/teamster/goal_setting/adapters/goals_sheet.py`
- Test: `tests/goal_setting/test_adapters.py`

**Interfaces:**

- Produces:
  - `archive.write_input(rows: list[dict], path: Path) -> dict` returning
    `{"file", "sha256", "row_count", "counts_by_school_grade", "tested_share_by_school_grade"}`;
    `archive.read_input(path: Path, expected_sha: str) -> list[dict]` raising
    `ArchiveMismatch` on hash mismatch;
    `archive.rows_to_records(rows) -> list[StudentRecord]` and
    `archive.records_to_rows(records) -> list[dict]` (the input CSV shape is
    exactly the `StudentRecord` adapter fields).
  - `iready_boy.sql(group, academic_year) -> str` (pure; testable) and
    `iready_boy.fetch(client, group, academic_year) -> list[StudentRecord]`.
  - `goals_sheet.sql(group, academic_year) -> str` and
    `goals_sheet.fetch_targets(client, group, academic_year) -> dict[tuple[str, int], float]`
    raising `MissingTargets` listing every `(region, grade)` with no row;
    `goals_sheet.inline_targets(group) -> dict` for `target.from: inline`.
  - `roster_sql.baseline_sql(group, academic_year, as_of: date) -> str` and
    `roster_sql.fetch_baseline(client, group, academic_year, as_of) -> Baseline`.
  - `adapters.client() -> bigquery.Client` for project `teamster-332318`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_adapters.py
from datetime import date
from pathlib import Path

import pytest

from teamster.goal_setting.adapters import archive, goals_sheet, iready_boy, roster_sql
from teamster.goal_setting.config import load_rules

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]
GROUP = load_rules(REPO / "config/goal_setting/ay2026.yaml").group("nj_math_1_2")


def test_archive_round_trip_is_lossless(tmp_path):
    recs = [student(projected_score=405.0), untested()]
    meta = archive.write_input(archive.records_to_rows(recs), tmp_path / "in.csv")
    back = archive.rows_to_records(archive.read_input(tmp_path / "in.csv", meta["sha256"]))
    assert back == recs
    assert meta["row_count"] == 2 and len(meta["sha256"]) == 64
    assert meta["counts_by_school_grade"] == [{"region": "Newark", "school": "TEAM", "grade_level": 1, "n": 2}]
    assert meta["tested_share_by_school_grade"] == [{"region": "Newark", "school": "TEAM", "grade_level": 1, "share": 0.5}]


def test_archive_hash_mismatch_aborts(tmp_path):
    archive.write_input(archive.records_to_rows([student()]), tmp_path / "in.csv")
    with pytest.raises(archive.ArchiveMismatch):
        archive.read_input(tmp_path / "in.csv", "0" * 64)


def test_iready_sql_names_group_filters():
    q = iready_boy.sql(GROUP, 2026)
    assert "academic_year = 2026" in q
    assert "grade_level in (1, 2)" in q
    assert "region in ('Newark', 'Camden', 'Paterson')" in q
    assert "iready_subject = 'Math'" in q
    assert "test_round = 'BOY'" in q
    assert "annual_typical_growth_measure" in q and "annual_stretch_growth_measure" in q
    assert "stg_google_sheets__iready__crosswalk" in q
    assert "TODO(#5317)" in q


def test_goals_sql_maps_subject_to_illuminate_area():
    q = goals_sheet.sql(GROUP, 2026)
    assert "'Mathematics'" in q and "grade_band_goal" in q and "academic_year = 2026" in q


def test_inline_targets_from_config():
    g = GROUP.model_copy(update={"target": GROUP.target.model_copy(update={"from_": "inline", "column": None, "values": {"Newark": {1: 0.35, 2: 0.24}}})})
    assert goals_sheet.inline_targets(g) == {("Newark", 1): 0.35, ("Newark", 2): 0.24}


def test_targets_from_rows_reports_every_missing_pair():
    rows = [{"region": "Newark", "grade_level": 1, "target": 0.35}]
    with pytest.raises(goals_sheet.MissingTargets) as e:
        goals_sheet.targets_from_rows(rows, GROUP)
    msg = str(e.value)
    assert "Camden grade 1" in msg and "Paterson grade 2" in msg and "Newark grade 1" not in msg


def test_baseline_sql_pins_a_date():
    q = roster_sql.baseline_sql(GROUP, 2026, date(2026, 9, 1))
    assert "'2026-09-01'" in q and "grade_level in (1, 2)" in q
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_adapters.py -q` Expected: FAIL with
`ModuleNotFoundError`

- [ ] **Step 3: Write the adapter modules**

```python
# src/teamster/goal_setting/adapters/__init__.py
"""Warehouse adapters. The only modules that import a BigQuery client."""

from __future__ import annotations

PROJECT = "teamster-332318"


def client():
    from google.cloud import bigquery

    return bigquery.Client(project=PROJECT)


def sql_list(values) -> str:
    return ", ".join(repr(v) if isinstance(v, str) else str(v) for v in values)
```

```python
# src/teamster/goal_setting/adapters/archive.py
"""Save fetched rows next to the run so a run can be replayed without the warehouse."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from teamster.goal_setting.records import StudentRecord

INPUT_COLUMNS = [
    "region", "student_number", "school", "school_id", "grade_level", "subject",
    "is_tested", "projected_level", "projected_score", "stretch_level", "assessment",
]


class ArchiveMismatch(Exception):
    pass


def records_to_rows(records: list[StudentRecord]) -> list[dict]:
    return [{c: getattr(r, c) for c in INPUT_COLUMNS} for r in records]


def _opt_int(v: str) -> int | None:
    return None if v in ("", "None") else int(v)


def _opt_float(v: str) -> float | None:
    return None if v in ("", "None") else float(v)


def rows_to_records(rows: list[dict]) -> list[StudentRecord]:
    return [
        StudentRecord(
            region=r["region"], student_number=int(r["student_number"]), school=r["school"],
            school_id=int(r["school_id"]), grade_level=int(r["grade_level"]), subject=r["subject"],
            is_tested=str(r["is_tested"]) == "True",
            projected_level=_opt_int(str(r["projected_level"])),
            projected_score=_opt_float(str(r["projected_score"])),
            stretch_level=_opt_int(str(r["stretch_level"])),
            assessment=r["assessment"],
        )
        for r in rows
    ]


def _per_school(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    acc: dict[tuple, list[int]] = {}
    for r in rows:
        t = acc.setdefault((r["region"], r["school"], int(r["grade_level"])), [0, 0])
        t[0] += 1
        t[1] += int(str(r["is_tested"]) == "True")
    keys = sorted(acc)
    counts = [{"region": k[0], "school": k[1], "grade_level": k[2], "n": acc[k][0]} for k in keys]
    shares = [{"region": k[0], "school": k[1], "grade_level": k[2], "share": round(acc[k][1] / acc[k][0], 3)} for k in keys]
    return counts, shares


def write_input(rows: list[dict], path: Path) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=INPUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    counts, shares = _per_school(rows)
    return {
        "file": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "row_count": len(rows),
        "counts_by_school_grade": counts,
        "tested_share_by_school_grade": shares,
    }


def read_input(path: Path, expected_sha: str) -> list[dict]:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha:
        raise ArchiveMismatch(f"{path}: sha256 {actual} does not match manifest {expected_sha}")
    with path.open() as fh:
        return list(csv.DictReader(fh))
```

```python
# src/teamster/goal_setting/adapters/roster_sql.py
"""Roster and baseline queries shared by source adapters."""

from __future__ import annotations

from datetime import date

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.config import Group
from teamster.goal_setting.rules.freshness import Baseline

ROSTER = "`teamster-332318.kipptaf_extracts.int_extracts__student_enrollments_subjects`"
SNAPSHOT = "`teamster-332318.kipptaf_students.int_extracts__student_enrollments_subjects_weeks`"


def roster_where(group: Group, academic_year: int) -> str:
    return f"""
        co.academic_year = {academic_year}
        and co.rn_year = 1
        and co.enroll_status = 0
        and not co.is_exempt_state_testing
        and co.grade_level in ({sql_list(group.grades)})
        and co.region in ({sql_list(group.regions)})
        and co.iready_subject = '{group.subject}'
    """


def baseline_sql(group: Group, academic_year: int, as_of: date) -> str:
    """Roster count per school and grade as of a pinned week, for the year-one gate."""
    return f"""
    select co.region, co.school, co.grade_level, count(distinct co.student_number) as n
    from {SNAPSHOT} as co
    where {roster_where(group, academic_year)}
      and co.week_start_monday <= '{as_of.isoformat()}'
      and co.week_end_sunday >= '{as_of.isoformat()}'
    group by co.region, co.school, co.grade_level
    """


def fetch_baseline(client, group: Group, academic_year: int, as_of: date) -> Baseline:
    rows = client.query(baseline_sql(group, academic_year, as_of)).result()
    return {(r["region"], r["school"], int(r["grade_level"])): int(r["n"]) for r in rows}
```

Before implementing, confirm the weekly snapshot model's week columns by reading
`src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects_weeks.yml`
with the Read tool and adjust the two column names in `baseline_sql` to match.
If that model does not carry a per-week enrollment row, fall back to the prior
manifest as the only baseline and make `--baseline-date` print "not available"
instead of querying.

```python
# src/teamster/goal_setting/adapters/iready_boy.py
"""i-Ready BOY diagnostic, projected with typical and stretch growth.

Adds annual_typical_growth_measure directly to the BOY scale score. That is
exact for a baseline diagnostic (gain is 0 by definition) and sidesteps the
null diagnostic_gain in staging for AY2026.
"""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.adapters.roster_sql import ROSTER, roster_where
from teamster.goal_setting.config import Group
from teamster.goal_setting.records import StudentRecord

IREADY = "`teamster-332318.kipptaf_iready.int_iready__diagnostic_results`"
CROSSWALK = "`teamster-332318.kipptaf_google_sheets.stg_google_sheets__iready__crosswalk`"
ASSESSMENT = "i-Ready BOY"


def sql(group: Group, academic_year: int) -> str:
    return f"""
    with
        xw as (
            select grade_level, `level`, scale_low, scale_high
            from {CROSSWALK}
            where destination_system = 'i-Ready'
              and test_name = '{group.subject}'
              and grade_level in ({sql_list(group.grades)})
        ),
        ir as (
            select
                student_id as student_number,
                student_grade_int as grade_level,
                overall_scale_score,
                -- TODO(#5317): switch to level_number_with_typical once typical growth is non-null in staging
                overall_scale_score + annual_typical_growth_measure as scale_plus_typical,
                overall_scale_score + annual_stretch_growth_measure as scale_plus_stretch
            from {IREADY}
            where academic_year_int = {academic_year}
              and subject = '{group.subject}'
              and test_round = 'BOY'
              and rn_subj_round = 1
              and student_grade_int in ({sql_list(group.grades)})
        ),
        ir_lvl as (
            select
                ir.student_number,
                ir.scale_plus_typical,
                xt.`level` as level_typical,
                xs.`level` as level_stretch
            from ir
            left join xw as xt
                on ir.grade_level = xt.grade_level
                and ir.scale_plus_typical between xt.scale_low and xt.scale_high
            left join xw as xs
                on ir.grade_level = xs.grade_level
                and ir.scale_plus_stretch between xs.scale_low and xs.scale_high
        )
    select
        co.region,
        co.student_number,
        co.school,
        co.schoolid as school_id,
        co.grade_level,
        co.iready_subject as subject,
        ir.scale_plus_typical is not null as is_tested,
        ir.level_typical as projected_level,
        ir.scale_plus_typical as projected_score,
        ir.level_stretch as stretch_level
    from {ROSTER} as co
    left join ir_lvl as ir on co.student_number = ir.student_number
    where {roster_where(group, academic_year)}
    """


def fetch(client, group: Group, academic_year: int) -> list[StudentRecord]:
    rows = client.query(sql(group, academic_year)).result()
    return [
        StudentRecord(
            region=r["region"], student_number=int(r["student_number"]), school=r["school"],
            school_id=int(r["school_id"]), grade_level=int(r["grade_level"]), subject=r["subject"],
            is_tested=bool(r["is_tested"]),
            projected_level=None if r["projected_level"] is None else int(r["projected_level"]),
            projected_score=None if r["projected_score"] is None else float(r["projected_score"]),
            stretch_level=None if r["stretch_level"] is None else int(r["stretch_level"]),
            assessment=ASSESSMENT,
        )
        for r in rows
    ]
```

```python
# src/teamster/goal_setting/adapters/goals_sheet.py
"""Region targets from the academic goals sheet, or inline from the rules file."""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.config import Group

GOALS = "`teamster-332318.kipptaf_assessments.int_assessments__academic_goals`"
ILLUMINATE_AREAS = {"Math": ["Mathematics"], "Reading": ["Text Study", "English Language Arts"]}
Targets = dict[tuple[str, int], float]


class MissingTargets(Exception):
    pass


def sql(group: Group, academic_year: int) -> str:
    return f"""
    select region, grade_level, max({group.target.column}) as target
    from {GOALS}
    where academic_year = {academic_year}
      and region in ({sql_list(group.regions)})
      and grade_level in ({sql_list(group.grades)})
      and illuminate_subject_area in ({sql_list(ILLUMINATE_AREAS[group.subject])})
    group by region, grade_level
    """


def targets_from_rows(rows: list[dict], group: Group) -> Targets:
    targets = {(r["region"], int(r["grade_level"])): float(r["target"]) for r in rows if r["target"] is not None}
    missing = [f"{region} grade {grade}" for region in group.regions for grade in group.grades if (region, grade) not in targets]
    if missing:
        raise MissingTargets(
            f"goals sheet has no {group.target.column} for {group.subject} in academic_year rows: "
            + ", ".join(missing)
            + ". Enter the region targets in the goals sheet, or set target.from: inline in the rules file."
        )
    return targets


def fetch_targets(client, group: Group, academic_year: int) -> Targets:
    rows = [dict(r) for r in client.query(sql(group, academic_year)).result()]
    return targets_from_rows(rows, group)


def inline_targets(group: Group) -> Targets:
    assert group.target.values is not None
    return {(region, int(grade)): float(v) for region, grades in group.target.values.items() for grade, v in grades.items()}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_adapters.py -q` Expected: 7 passed

- [ ] **Step 5: Smoke the two SQL strings against BigQuery with a dry run**

Write the SQL to scratch and dry-run it with the BigQuery MCP tool
(`mcp__bigquery__execute_sql` with `dry_run: true`) or, in a terminal with ADC,
`uv run python -c` printing `iready_boy.sql(group, 2026)` and pasting it into
`bq query --dry_run`. Both must validate. Fix column names against the model
properties files if either fails. Do not run the real query yet.

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/adapters/__init__.py src/teamster/goal_setting/adapters/archive.py src/teamster/goal_setting/adapters/roster_sql.py src/teamster/goal_setting/adapters/iready_boy.py src/teamster/goal_setting/adapters/goals_sheet.py tests/goal_setting/test_adapters.py
git -C <worktree> commit -m "feat(goal-setting): i-Ready BOY adapter, input archive, targets, baseline

Refs #5335"
```

---

### Task 11: verify-crosswalk and show

**Files:**

- Create: `src/teamster/goal_setting/verify_crosswalk.py`
- Create: `src/teamster/goal_setting/show.py`
- Test: `tests/goal_setting/test_verify_crosswalk.py`

**Interfaces:**

- Produces:
  - `verify_crosswalk.sql(regions: list[str]) -> str`;
    `verify_crosswalk.compare(xw: Crosswalk, live_rows: list[dict]) -> list[str]`
    returning one line per problem (crosswalk id absent from live, live bucket
    program absent from crosswalk, name disagreeing with bucket or subject);
    `verify_crosswalk.run(client, xw) -> list[str]`.
  - `show.explain(run_dir: Path, student_number: int, region: str | None) -> list[str]`
    reading `explain.csv` from a run folder.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_verify_crosswalk.py
from pathlib import Path

from teamster.goal_setting.config import load_crosswalk
from teamster.goal_setting.verify_crosswalk import compare, sql

REPO = Path(__file__).resolve().parents[2]
XW = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")


def live(region, pid, name):
    return {"region": region, "programid": pid, "specprog_name": name}


def full_live():
    rows = []
    for p in XW.programs:
        disc = "ELA" if p.subject == "Reading" else "Math"
        rows.append(live(p.region, p.programid, f"{p.bucket} - {disc}"))
    return rows


def test_clean_crosswalk_has_no_problems():
    assert compare(XW, full_live()) == []


def test_missing_live_program_is_reported_with_region():
    rows = [r for r in full_live() if r["programid"] != 1638]
    (problem,) = compare(XW, rows)
    assert "Paterson" in problem and "1638" in problem and "not found" in problem


def test_live_bucket_program_absent_from_crosswalk_is_reported():
    rows = full_live() + [live("Newark", 9999, "Bucket 2 - Math")]
    (problem,) = compare(XW, rows)
    assert "9999" in problem and "not in crosswalk" in problem


def test_name_mismatch_is_reported():
    rows = full_live()
    rows[0]["specprog_name"] = "Bucket 3 - Math"  # Camden 7376 should be Bucket 1 - ELA
    problems = compare(XW, rows)
    assert any("7376" in p and "Bucket 1 - ELA" in p and "Bucket 3 - Math" in p for p in problems)


def test_sql_scopes_regions_and_bucket_names():
    q = sql(["Camden", "Newark"])
    assert "like 'Bucket%'" in q and "kippcamden" in q and "kippnewark" in q
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/goal_setting/test_verify_crosswalk.py -q` Expected:
FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `verify_crosswalk.py` and `show.py`**

```python
# src/teamster/goal_setting/verify_crosswalk.py
"""Check ps_programs.yaml against the live special programs view."""

from __future__ import annotations

from teamster.goal_setting.adapters import sql_list
from teamster.goal_setting.config import Crosswalk

SPENROLLMENTS = "`teamster-332318.kipptaf_powerschool.int_powerschool__spenrollments`"
REGION_TO_PROJECT = {"Camden": "kippcamden", "Newark": "kippnewark", "Paterson": "kipppaterson", "Miami": "kippmiami"}
PROJECT_TO_REGION = {v: k for k, v in REGION_TO_PROJECT.items()}
DISCIPLINE = {"Reading": "ELA", "Math": "Math"}


def sql(regions: list[str]) -> str:
    projects = [REGION_TO_PROJECT[r] for r in regions]
    return f"""
    select
        regexp_extract(_dbt_source_relation, r'(kipp\\w+)_') as project,
        programid,
        specprog_name
    from {SPENROLLMENTS}
    where specprog_name like 'Bucket%'
      and regexp_extract(_dbt_source_relation, r'(kipp\\w+)_') in ({sql_list(projects)})
    group by project, programid, specprog_name
    """


def expected_name(subject: str, bucket: str) -> str:
    return f"{bucket} - {DISCIPLINE[subject]}"


def compare(xw: Crosswalk, live_rows: list[dict]) -> list[str]:
    problems = []
    live = {(r["region"], int(r["programid"])): r["specprog_name"] for r in live_rows}
    for p in xw.programs:
        name = live.get((p.region, p.programid))
        want = expected_name(p.subject, p.bucket)
        if name is None:
            problems.append(f"{p.region}: crosswalk program id {p.programid} ({want}) not found in PowerSchool")
        elif name != want:
            problems.append(f"{p.region}: program id {p.programid} is '{name}' in PowerSchool but '{want}' in crosswalk")
    known = {(p.region, p.programid) for p in xw.programs}
    for (region, pid), name in sorted(live.items()):
        if (region, pid) not in known:
            problems.append(f"{region}: PowerSchool bucket program {pid} '{name}' is not in crosswalk")
    return problems


def run(client, xw: Crosswalk) -> list[str]:
    regions = sorted({p.region for p in xw.programs})
    rows = [
        {"region": PROJECT_TO_REGION[r["project"]], "programid": r["programid"], "specprog_name": r["specprog_name"]}
        for r in client.query(sql(regions)).result()
    ]
    return compare(xw, rows)
```

```python
# src/teamster/goal_setting/show.py
"""Replay one student's explanation from a saved run folder."""

from __future__ import annotations

import csv
from pathlib import Path


def explain(run_dir: Path, student_number: int, region: str | None = None) -> list[str]:
    path = run_dir / "explain.csv"
    if not path.exists():
        return [f"{path} not found; is {run_dir} a run folder?"]
    with path.open() as fh:
        rows = [r for r in csv.DictReader(fh) if int(r["student_number"]) == student_number and (region is None or r["region"] == region)]
    if not rows:
        return [f"student {student_number} is not in this run"]
    return [f"{r['region']} {r['subject']}: {r['bucket']} because {r['reason']}" for r in rows]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/goal_setting/test_verify_crosswalk.py -q` Expected: 5
passed

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/teamster/goal_setting/verify_crosswalk.py src/teamster/goal_setting/show.py tests/goal_setting/test_verify_crosswalk.py
git -C <worktree> commit -m "feat(goal-setting): verify-crosswalk and show commands

Refs #5335"
```

---

### Task 12: CLI, purity test, and end-to-end plan run

**Files:**

- Create: `src/teamster/goal_setting/__main__.py`
- Test: `tests/goal_setting/test_cli.py`
- Test: `tests/goal_setting/test_purity.py`

**Interfaces:**

- Produces the commands:
  - `rollout --year 2026 --group nj_math_1_2 --out <dir> [--plan] [--input <dir>] [--against <dir>] [--baseline-date YYYY-MM-DD] [--force-stale] [--allow-reclassification] [--rules <path>] [--crosswalk <path>]`
  - `verify-crosswalk [--crosswalk <path>]`
  - `show --run <dir> --student <n> [--region <r>]`
  - `main(argv: list[str] | None = None, client_factory=adapters.client) -> int`
    so tests can inject a fake client.

- [ ] **Step 1: Write the failing tests**

```python
# tests/goal_setting/test_purity.py
"""Rules must be pure: no warehouse client anywhere under rules/."""

import ast
from pathlib import Path

RULES = Path(__file__).resolve().parents[2] / "src/teamster/goal_setting/rules"
BANNED = ("google.cloud", "bigquery", "teamster.goal_setting.adapters")


def test_rules_modules_import_no_warehouse_client():
    offenders = []
    for path in RULES.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.startswith(BANNED):
                    offenders.append(f"{path.name}: {n}")
    assert offenders == []
```

```python
# tests/goal_setting/test_cli.py
import csv
import json
from pathlib import Path

from teamster.goal_setting.__main__ import main

from .fixtures.roster_small import student, untested

REPO = Path(__file__).resolve().parents[2]


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    """Answers the three queries the rollout makes by matching a table name."""

    def __init__(self, roster_rows, target_rows, live_programs):
        self.roster_rows, self.target_rows, self.live_programs = roster_rows, target_rows, live_programs

    def query(self, sql: str):
        if "int_iready__diagnostic_results" in sql:
            return FakeResult(self.roster_rows)
        if "int_assessments__academic_goals" in sql:
            return FakeResult(self.target_rows)
        if "int_powerschool__spenrollments" in sql:
            return FakeResult(self.live_programs)
        raise AssertionError(f"unexpected query: {sql[:80]}")


def roster_rows():
    recs = (
        [student(projected_level=5, projected_score=430 + i) for i in range(3)]
        + [student(projected_level=4, projected_score=400 + i, stretch_level=4) for i in range(4)]
        + [student(projected_level=3, projected_score=380, stretch_level=5), student(projected_level=2, projected_score=350, stretch_level=3)]
        + [untested()]
    )
    return [
        dict(region=r.region, student_number=r.student_number, school=r.school, school_id=r.school_id,
             grade_level=r.grade_level, subject=r.subject, is_tested=r.is_tested,
             projected_level=r.projected_level, projected_score=r.projected_score, stretch_level=r.stretch_level)
        for r in recs
    ]


def targets():
    return [{"region": r, "grade_level": g, "target": 0.5} for r in ("Newark", "Camden", "Paterson") for g in (1, 2)]


def live_programs():
    rows = []
    for region, proj in (("Camden", "kippcamden"), ("Newark", "kippnewark"), ("Paterson", "kipppaterson")):
        for bucket in ("Bucket 1", "Bucket 2", "Bucket 3"):
            for disc in ("ELA", "Math"):
                rows.append({"project": proj, "programid": 1, "specprog_name": f"{bucket} - {disc}"})
    return rows


def run(argv, tmp_path, live=None):
    client = FakeClient(roster_rows(), targets(), live if live is not None else _live_matching_crosswalk())
    return main(argv, client_factory=lambda: client)


def _live_matching_crosswalk():
    from teamster.goal_setting.config import load_crosswalk
    from teamster.goal_setting.verify_crosswalk import REGION_TO_PROJECT, expected_name

    xw = load_crosswalk(REPO / "config/goal_setting/ps_programs.yaml")
    return [{"project": REGION_TO_PROJECT[p.region], "programid": p.programid, "specprog_name": expected_name(p.subject, p.bucket)} for p in xw.programs]


def test_plan_mode_writes_no_files(tmp_path, capsys):
    out = tmp_path / "run"
    rc = run(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(out), "--plan", "--manifest-dir", str(tmp_path / "m")], tmp_path)
    assert rc == 0
    assert not out.exists() or list(out.iterdir()) == []
    text = capsys.readouterr().out
    assert "TEAM" in text and "no prior run" in text


def test_rollout_writes_run_and_commits_manifest_copy(tmp_path, monkeypatch):
    out = tmp_path / "run"
    manifests = tmp_path / "manifests"
    rc = main(
        ["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(out), "--manifest-dir", str(manifests)],
        client_factory=lambda: FakeClient(roster_rows(), targets(), _live_matching_crosswalk()),
    )
    assert rc == 0
    assert (out / "inputs" / "iready_boy_nj_math_1_2.csv").exists()
    assert (out / "manifest.json").exists()
    committed = json.loads((manifests / "ay2026" / "nj_math_1_2.json").read_text())
    assert committed["inputs"][0]["row_count"] == 10
    assert committed["diff"]["verdict"] == "no prior run"


def test_replay_from_inputs_is_byte_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    manifests = tmp_path / "manifests"
    factory = lambda: FakeClient(roster_rows(), targets(), _live_matching_crosswalk())  # noqa: E731
    assert main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(first), "--manifest-dir", str(manifests)], client_factory=factory) == 0
    assert main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(second), "--manifest-dir", str(manifests), "--input", str(first)], client_factory=factory) == 0
    for name in ("school_goals.csv", "ps_programs.csv", "explain.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_second_run_diffs_against_committed_manifest(tmp_path, capsys):
    first, second, manifests = tmp_path / "a", tmp_path / "b", tmp_path / "m"
    factory = lambda: FakeClient(roster_rows(), targets(), _live_matching_crosswalk())  # noqa: E731
    main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(first), "--manifest-dir", str(manifests)], client_factory=factory)
    capsys.readouterr()
    rc = main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(second), "--manifest-dir", str(manifests), "--against", str(first)], client_factory=factory)
    assert rc == 0
    assert "verdict: no change" in capsys.readouterr().out


def test_reclassification_exits_nonzero_without_flag(tmp_path, capsys):
    first, second, manifests = tmp_path / "a", tmp_path / "b", tmp_path / "m"
    rows = roster_rows()
    main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(first), "--manifest-dir", str(manifests)],
         client_factory=lambda: FakeClient(rows, targets(), _live_matching_crosswalk()))
    # add a new top approaching student: tested 10, bp = (5 - 3) / 5 = 0.4,
    # n_to_move = 2, so Bucket 2 becomes {404, 403} and 402 moves to Bucket 3
    newcomer = student(projected_level=4, projected_score=404.0, stretch_level=4)
    changed = rows + [
        dict(region=newcomer.region, student_number=newcomer.student_number, school=newcomer.school,
             school_id=newcomer.school_id, grade_level=newcomer.grade_level, subject=newcomer.subject,
             is_tested=True, projected_level=4, projected_score=404.0, stretch_level=4)
    ]
    rc = main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(second), "--manifest-dir", str(manifests), "--against", str(first)],
              client_factory=lambda: FakeClient(changed, targets(), _live_matching_crosswalk()))
    out = capsys.readouterr().out
    assert rc == 2 and "RECLASSIFIES" in out
    assert not (second / "manifest.json").exists()


def test_missing_targets_is_a_clear_error(tmp_path, capsys):
    rc = main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(tmp_path / "r"), "--plan"],
              client_factory=lambda: FakeClient(roster_rows(), [], _live_matching_crosswalk()))
    assert rc == 1 and "Camden grade 1" in capsys.readouterr().err


def test_crosswalk_problem_aborts_rollout(tmp_path, capsys):
    live = _live_matching_crosswalk()[1:]
    rc = main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(tmp_path / "r"), "--plan"],
              client_factory=lambda: FakeClient(roster_rows(), targets(), live))
    assert rc == 1 and "not found in PowerSchool" in capsys.readouterr().err


def test_show_replays_a_student(tmp_path, capsys):
    out = tmp_path / "run"
    main(["rollout", "--year", "2026", "--group", "nj_math_1_2", "--out", str(out), "--manifest-dir", str(tmp_path / "m")],
         client_factory=lambda: FakeClient(roster_rows(), targets(), _live_matching_crosswalk()))
    sn = list(csv.DictReader((out / "explain.csv").open()))[0]["student_number"]
    capsys.readouterr()
    assert main(["show", "--run", str(out), "--student", sn]) == 0
    assert "because" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/goal_setting/test_cli.py tests/goal_setting/test_purity.py -q`
Expected: purity passes; CLI fails with
`ModuleNotFoundError: teamster.goal_setting.__main__`

- [ ] **Step 3: Write `__main__.py`**

```python
# src/teamster/goal_setting/__main__.py
"""Command line entry point.

    uv run python -m teamster.goal_setting rollout --year 2026 --group nj_math_1_2 --out runs/ay2026/nj_math_1_2/$(date +%FT%H%M)
    uv run python -m teamster.goal_setting rollout ... --plan
    uv run python -m teamster.goal_setting verify-crosswalk
    uv run python -m teamster.goal_setting show --run <folder> --student <n>
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from datetime import date
from pathlib import Path

from teamster.goal_setting import adapters, diff, manifest, outputs, show, verify_crosswalk
from teamster.goal_setting.adapters import archive, goals_sheet, iready_boy, roster_sql
from teamster.goal_setting.config import ConfigError, load_crosswalk, load_rules
from teamster.goal_setting.pipeline import FreshnessError, run_group
from teamster.goal_setting.rules.invariants import InvariantError

REPO = Path(__file__).resolve().parents[3]
DEFAULT_RULES_DIR = REPO / "config" / "goal_setting"
SOURCES = {"iready_boy": iready_boy}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="teamster.goal_setting")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rollout", help="propose school goals and buckets for one group")
    r.add_argument("--year", type=int, required=True)
    r.add_argument("--group", required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--plan", action="store_true", help="compute, diff, check; write nothing")
    r.add_argument("--input", type=Path, help="replay from a prior run folder's inputs/")
    r.add_argument("--against", type=Path, help="prior run folder for student-depth diff")
    r.add_argument("--baseline-date", type=date.fromisoformat, help="pin a roster date for the freshness baseline")
    r.add_argument("--force-stale", action="store_true")
    r.add_argument("--allow-reclassification", action="store_true")
    r.add_argument("--rules", type=Path)
    r.add_argument("--crosswalk", type=Path)
    r.add_argument("--manifest-dir", type=Path, default=DEFAULT_RULES_DIR / "manifests")

    v = sub.add_parser("verify-crosswalk", help="check ps_programs.yaml against PowerSchool")
    v.add_argument("--crosswalk", type=Path)

    s = sub.add_parser("show", help="replay one student's explanation from a run folder")
    s.add_argument("--run", type=Path, required=True)
    s.add_argument("--student", type=int, required=True)
    s.add_argument("--region")
    return p


def _err(msg: str) -> int:
    print(msg, file=sys.stderr)
    return 1


def _rollout(a: argparse.Namespace, client_factory) -> int:
    rules_path = a.rules or DEFAULT_RULES_DIR / f"ay{a.year}.yaml"
    xw_path = a.crosswalk or DEFAULT_RULES_DIR / "ps_programs.yaml"
    rules = load_rules(rules_path)
    xw = load_crosswalk(xw_path)
    group = rules.group(a.group)
    if rules.academic_year != a.year:
        return _err(f"{rules_path} is for academic_year {rules.academic_year}, not {a.year}")

    client = client_factory()
    problems = verify_crosswalk.run(client, xw)
    if problems:
        return _err("crosswalk check failed:\n  " + "\n  ".join(problems))

    input_name = f"{group.source}_{group.name}.csv"
    if a.input:
        prior_manifest = diff.load_prior_manifest(a.input / "manifest.json")
        if prior_manifest is None:
            return _err(f"{a.input} has no manifest.json")
        expected = next(i for i in prior_manifest["inputs"] if i["file"] == input_name)
        rows = archive.read_input(a.input / "inputs" / input_name, expected["sha256"])
        records = archive.rows_to_records(rows)
    else:
        records = SOURCES[group.source].fetch(client, group, a.year)
        rows = archive.records_to_rows(records)

    targets = goals_sheet.inline_targets(group) if group.target.from_ == "inline" else goals_sheet.fetch_targets(client, group, a.year)

    manifest_path = a.manifest_dir / f"ay{a.year}" / f"{group.name}.json"
    prior = diff.load_prior_manifest(manifest_path)
    baseline = None
    if prior is not None:
        baseline = {(c["region"], c["school"], c["grade_level"]): c["n"] for i in prior["inputs"] for c in i["counts_by_school_grade"]}
    elif a.baseline_date:
        baseline = roster_sql.fetch_baseline(client, group, a.year, a.baseline_date)

    proposal = run_group(group, a.year, records, targets, baseline, force_stale=a.force_stale)

    report = diff.diff_manifests(prior, manifest.build(proposal, "", "", [], None, a.force_stale))
    if a.against and (a.against / "student_buckets.csv").exists():
        with (a.against / "student_buckets.csv").open() as fh:
            report = diff.add_student_depth(report, list(csv.DictReader(fh)), proposal.records)

    print(report.render())
    print()
    print(outputs.summary_tables(proposal))

    if report.verdict == "reclassifies" and not a.allow_reclassification:
        print("\nrefusing to write: pass --allow-reclassification to accept the transitions above", file=sys.stderr)
        return 2
    if a.plan:
        print("\n--plan: nothing written")
        return 0

    a.out.mkdir(parents=True, exist_ok=True)
    input_meta = archive.write_input(rows, a.out / "inputs" / input_name)
    m = manifest.build(
        proposal,
        rules_sha=manifest.sha256_file(rules_path),
        crosswalk_sha=manifest.sha256_file(xw_path),
        inputs=[input_meta],
        diff=report.as_dict(),
        force_stale=a.force_stale,
    )
    written = outputs.write_run(a.out, proposal, m, xw)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.out / "manifest.json", manifest_path)
    print("\nwrote:")
    for w in written:
        print(f"  {w}")
    print(f"  {manifest_path}  (commit this one)")
    return 0


def main(argv: list[str] | None = None, client_factory=adapters.client) -> int:
    a = _parser().parse_args(argv)
    try:
        if a.cmd == "rollout":
            return _rollout(a, client_factory)
        if a.cmd == "verify-crosswalk":
            xw = load_crosswalk(a.crosswalk or DEFAULT_RULES_DIR / "ps_programs.yaml")
            problems = verify_crosswalk.run(client_factory(), xw)
            for p in problems:
                print(p)
            print("crosswalk OK" if not problems else f"{len(problems)} problems")
            return 1 if problems else 0
        if a.cmd == "show":
            for line in show.explain(a.run, a.student, a.region):
                print(line)
            return 0
    except (ConfigError, FreshnessError, InvariantError, goals_sheet.MissingTargets, archive.ArchiveMismatch, NotImplementedError) as e:
        return _err(f"{type(e).__name__}: {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest tests/goal_setting -q` Expected: all passed. If
`test_reclassification_exits_nonzero_without_flag` fails because the count diff
already reads `changed counts`, that is fine: the assertion is on `RECLASSIFIES`
and exit code 2, which come from student depth.

- [ ] **Step 5: Run the real plan against the warehouse, from your terminal**

This step needs ADC and reads production tables. It writes nothing. Run in the
worktree:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-goal-setting-generator
uv run python -m teamster.goal_setting verify-crosswalk
uv run python -m teamster.goal_setting rollout --year 2026 --group nj_math_1_2 --out runs/ay2026/nj_math_1_2/plan --plan --baseline-date 2026-09-01
```

Expected: `crosswalk OK`; then either the school summary table, or
`MissingTargets` naming every region and grade, because the goals sheet has no
SY27 rows yet. If targets are missing, temporarily switch the group to
`target: { from: inline, values: { Newark: { 1: 0.35, 2: 0.24 }, Camden: { 1: 0.35, 2: 0.22 }, Paterson: { 1: 0.25, 2: 0.24 } } }`
in a scratch copy of the rules file passed with `--rules`, re-run, and compare
the school table against
`tests/goal_setting/fixtures/nj_math_1_2_ay2026_school_goals.csv`. The bubble
parameters and goals must match to the cent; bucket counts may differ only where
the roster changed since 2026-09-15. Record the comparison in the PR body. Do
not commit the scratch rules file.

- [ ] **Step 5b: Concordance with the old rollup, SY26 Newark grades 1 to 2
      math**

The spec asks for one group where the old rollup and the new rules agree by
design. Write a second scratch rules file with `academic_year: 2025`, a single
group `regions: [Newark]`, `grades: [1, 2]`, `subject: Math`,
`levels: {proficient: [4, 5], approaching: [3]}`,
`bucket3: {strategy: remaining_approaching}`,
`target: {from: goals_sheet, column: grade_band_goal}`, and run:

```bash
uv run python -m teamster.goal_setting rollout --year 2025 --group newark_math_1_2_sy26 --out runs/ay2025/concordance --plan --rules /workspaces/teamster/.claude/scratch/concordance_ay2025.yaml --manifest-dir /tmp/claude-1000/concordance-manifests
```

Then, with the BigQuery MCP tool, count the rollup's buckets for the same
population:

```sql
select school, grade_level, student_tier_calculated, count(*) as n
from `teamster-332318.kipptaf_tableau.rpt_tableau__academic_goals_rollup`
where academic_year = 2025 and region = 'Newark' and subject = 'Math'
  and grade_level in (1, 2)
group by school, grade_level, student_tier_calculated
order by school, grade_level, student_tier_calculated
```

Expected: Bucket 1 and Bucket 2 counts match the plan's school table exactly,
and Bucket 3 matches because SY26 Newark math used remaining approaching. Known
difference: the rollup reads `level_number_with_typical`, which is correct for
AY2025 (the staging defect is AY2026 only), while the adapter adds typical
growth directly; both give the same level for a baseline diagnostic. Any other
difference is a bug in the adapter or the rules. Record the aggregate comparison
in the PR body.

- [ ] **Step 6: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/teamster/goal_setting tests/goal_setting config/goal_setting </dev/null
git -C <worktree> add src/teamster/goal_setting/__main__.py tests/goal_setting/test_cli.py tests/goal_setting/test_purity.py
git -C <worktree> commit -m "feat(goal-setting): rollout CLI with plan mode, replay, and diff

Refs #5335"
```

Fix any ruff or pyright findings before committing. Expected findings: line
length in the SQL strings (wrap them), unused `date` import in `__main__.py` if
`--baseline-date` parsing is moved.

---

### Task 13: Reading order and PR

**Files:**

- Create:
  `docs/superpowers/plans/2026-09-16-goal-setting-generator-pr1-reading-order.md`

- [ ] **Step 1: Write the reading order**

```markdown
# PR 1 reading order

Read in this order. Each file says what to check. Every test name says which
methodology rule or failure it covers; read the test before the module.

1. `config/goal_setting/ay2026.yaml` and `ps_programs.yaml`. Check: the two
   groups match the SY27 decisions in the handoff. The K group's Bucket 3
   strategy and both groups' `to_buckets` are open items marked in comments.
2. `tests/goal_setting/test_school_goal.py` then
   `src/teamster/goal_setting/rules/school_goal.py`. Check: the regression test
   reproduces the SY27 one-off to the cent. The formula is in the Global
   Constraints of the plan.
3. `tests/goal_setting/test_bucket2.py` then `rules/bucket2.py`. Check: ties at
   the cutoff are all admitted under `admit`.
4. `tests/goal_setting/test_bucket3.py`, `test_assign.py`, then
   `rules/bucket3.py` and `rules/assign.py`. Check: a below student whose
   stretch level is proficient enters Bucket 3; untested never does.
5. `tests/goal_setting/test_invariants.py` then `rules/invariants.py`. Check:
   every message names region, school, grade, subject.
6. `tests/goal_setting/test_freshness.py` then `rules/freshness.py`. Check:
   error versus warning split.
7. `adapters/iready_boy.py`. Check the SQL against
   `rpt_tableau__academic_goals_rollup.sql` roster filters and the crosswalk
   join. This is the one file where a wrong column name would be silent.
8. `pipeline.py`. Check the order: gate, classify, goals, bucket 2, bucket 3,
   finalize, invariants.
9. `__main__.py`. Check that nothing is written before the invariants and the
   diff verdict.

Skip on first read: `archive.py`, `manifest.py`, `outputs.py`, `diff.py`,
`show.py`. They move data; their tests describe the file shapes.
```

- [ ] **Step 2: Lint, commit, push, open the PR**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/superpowers/plans/2026-09-16-goal-setting-generator-pr1-reading-order.md </dev/null
git -C <worktree> add docs/superpowers/plans/2026-09-16-goal-setting-generator-pr1-reading-order.md
git -C <worktree> commit -m "docs(goal-setting): PR 1 reading order

Refs #5335"
git -C <worktree> push -u origin anthonygwalters/feat/claude-goal-setting-generator
```

Open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md`, title
`feat(goal-setting): rules-driven goal and bucket generator, rollout mode`, body
ending `Refs #5335` (not `Closes`; PRs 2 to 4 remain), and the attribution line.
Include the plan-run comparison from Task 12 Step 5 as aggregate numbers only.
