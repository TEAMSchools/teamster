# i-Ready FY27 Export Renames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore FY2027 i-Ready ingestion in all regions by translating the
partition subject to the vendor's renamed filename tokens at the SFTP boundary.

**Architecture:** The subject partition value stays `ela`. A new
`libraries/iready/subjects.py` module holds a fixed fiscal-year boundary and a
one-entry token map. The asset translates partition subject to filename token
when composing its regex; the sensor translates back when building a partition
key from a matched path. Everything else — partition space, GCS layout,
downstream models — is unchanged.

**Tech Stack:** Dagster, dbt (BigQuery), pytest, `uv`.

**Spec:**
`docs/superpowers/specs/2026-09-01-iready-fy27-export-renames-design.md`

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames`.
  Use `git -C <worktree>` for every git call and
  `uv run dbt ... --project-dir <worktree>/src/dbt/iready` for every dbt call.
- Always `uv run` — never bare `python`, `python3`, `pytest`, or `dbt`.
- Credentialed work (live SFTP, `materialize()`) runs under `uv run pytest`,
  which bootstraps 1Password via `tests/conftest.py`. A plain
  `uv run python script.py` gets no secrets.
- `RENAME_ACADEMIC_YEAR = 2026` — the partition key of FY2027, the first year
  the vendor used new export names.
- `REMOTE_SUBJECT_TOKENS = {"ela": "reading"}` — partition subject to
  current-era filename token.
- The dbt contract is enforced (`src/dbt/iready/dbt_project.yml:36-37`). Every
  column reaching model output must be declared in the properties YAML.
- Never emit PII to any external surface. SFTP filenames, sizes, and column
  names are not PII; data rows are.
- Do not run `trunk fmt` or `trunk check` manually except on markdown before
  pushing — the pre-commit hook formats.

## File Structure

| File                                                                          | Responsibility                                                                                                                           |
| ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `src/teamster/libraries/iready/subjects.py`                                   | **Create.** The era boundary and the token map. Single source of truth for both directions of translation.                               |
| `src/teamster/libraries/iready/assets.py`                                     | **Modify.** `build_iready_sftp_asset` accepts and forwards `legacy_remote_file_regex`.                                                   |
| `src/teamster/libraries/sftp/assets.py`                                       | **Modify.** Inside the existing `if group_name == "iready"` block only: pick the era's regex and translate the subject before composing. |
| `src/teamster/libraries/iready/sensors.py`                                    | **Modify.** Map the captured remote token back to the partition subject.                                                                 |
| `src/teamster/libraries/iready/schema.py`                                     | **Modify.** 4 new fields on `DiagnosticResults`.                                                                                         |
| `src/teamster/code_locations/kippmiami/iready/assets.py`                      | **Modify.** 4 current-era regexes plus 4 `legacy_remote_file_regex` values.                                                              |
| `src/teamster/code_locations/kippnewark/iready/assets.py`                     | **Modify.** Same 8 values.                                                                                                               |
| `src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql`            | **Modify.** Coalesce 3 renamed columns; translate the raw subject token in the final select.                                             |
| `src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml` | **Modify.** Declare `tactile_graphics`.                                                                                                  |
| `tests/libraries/test_iready_subjects.py`                                     | **Create.** Unit tests for the boundary and both translation directions.                                                                 |
| `tests/libraries/test_iready_remote_file_regex.py`                            | **Create.** The regression test for this outage: every asset's composed regex matches the real filename for its era.                     |

---

### Task 1: The subject translation module

**Files:**

- Create: `src/teamster/libraries/iready/subjects.py`
- Test: `tests/libraries/test_iready_subjects.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `RENAME_ACADEMIC_YEAR: int`,
  `REMOTE_SUBJECT_TOKENS: dict[str, str]`,
  `PARTITION_SUBJECTS_BY_REMOTE_TOKEN: dict[str, str]`,
  `is_legacy_year(academic_year: str) -> bool`,
  `remote_subject_token(subject: str, academic_year: str) -> str`,
  `partition_subject(remote_token: str, academic_year: str) -> str`. Tasks 2, 3
  and 5 depend on these exact names.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_iready_subjects.py`:

```python
import pytest

from teamster.libraries.iready.subjects import (
    is_legacy_year,
    partition_subject,
    remote_subject_token,
)


@pytest.mark.parametrize(
    ("academic_year", "expected"),
    [
        ("2020", True),
        ("2024", True),
        ("2025", True),
        ("2026", False),
        ("2027", False),
        ("Current_Year", False),
    ],
)
def test_is_legacy_year(academic_year, expected):
    assert is_legacy_year(academic_year) is expected


@pytest.mark.parametrize(
    ("subject", "academic_year", "expected"),
    [
        ("ela", "2025", "ela"),
        ("ela", "2026", "reading"),
        ("ela", "Current_Year", "reading"),
        ("math", "2025", "math"),
        ("math", "2026", "math"),
    ],
)
def test_remote_subject_token(subject, academic_year, expected):
    assert remote_subject_token(subject=subject, academic_year=academic_year) == expected


@pytest.mark.parametrize(
    ("remote_token", "academic_year", "expected"),
    [
        ("ela", "2025", "ela"),
        ("reading", "Current_Year", "ela"),
        ("reading", "2026", "ela"),
        ("math", "Current_Year", "math"),
        ("ela", "Current_Year", "ela"),
    ],
)
def test_partition_subject(remote_token, academic_year, expected):
    assert partition_subject(remote_token=remote_token, academic_year=academic_year) == expected


def test_round_trip_is_stable_for_current_era():
    token = remote_subject_token(subject="ela", academic_year="Current_Year")

    assert partition_subject(remote_token=token, academic_year="Current_Year") == "ela"
```

Note the last `partition_subject` case: a stale `_ela_` file sitting in
`Current_Year` must still map to partition `ela`, so it acts as a harmless
trigger rather than an error.

- [ ] **Step 2: Run test to verify it fails**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/libraries/test_iready_subjects.py -v`

Expected: FAIL with
`ModuleNotFoundError: No module named 'teamster.libraries.iready.subjects'`

- [ ] **Step 3: Write minimal implementation**

Create `src/teamster/libraries/iready/subjects.py`:

```python
"""Translation between i-Ready partition subjects and vendor filename tokens.

Curriculum Associates renamed the reading exports from `ela` to `reading` for
FY2027. The partition subject stays `ela` in every fiscal year, because the GCS
object path is derived from the partition key and `MultiPartitionsDefinition` is
a cartesian product that cannot vary its subject list by year. So the rename is
absorbed here, at the SFTP boundary, in both directions.
"""

# partition key of FY2027, the first year the vendor used the new export names
RENAME_ACADEMIC_YEAR = 2026

# partition subject -> filename token, for FY2027 and later
REMOTE_SUBJECT_TOKENS = {"ela": "reading"}

PARTITION_SUBJECTS_BY_REMOTE_TOKEN = {
    token: subject for subject, token in REMOTE_SUBJECT_TOKENS.items()
}


def is_legacy_year(academic_year: str) -> bool:
    """True when this partition's files still carry the pre-FY2027 names.

    `Current_Year` is the vendor's folder for the newest fiscal year, so it is
    never legacy.
    """
    if academic_year == "Current_Year":
        return False

    return int(academic_year) < RENAME_ACADEMIC_YEAR


def remote_subject_token(subject: str, academic_year: str) -> str:
    """Partition subject -> the token that appears in the filename."""
    if is_legacy_year(academic_year):
        return subject

    return REMOTE_SUBJECT_TOKENS.get(subject, subject)


def partition_subject(remote_token: str, academic_year: str) -> str:
    """Filename token -> the partition subject it belongs to.

    A stale pre-rename file left behind in `Current_Year` still maps to its
    original partition, so it can trigger a run but never becomes the payload.
    """
    if is_legacy_year(academic_year):
        return remote_token

    return PARTITION_SUBJECTS_BY_REMOTE_TOKEN.get(remote_token, remote_token)
```

- [ ] **Step 4: Run test to verify it passes**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/libraries/test_iready_subjects.py -v`

Expected: PASS, 17 tests.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/teamster/libraries/iready/subjects.py tests/libraries/test_iready_subjects.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "feat(dagster): add i-Ready subject token translation

Refs #4949"
```

---

### Task 2: Era-aware file regex in the asset builder

**Files:**

- Modify: `src/teamster/libraries/sftp/assets.py:95-139`
- Modify: `src/teamster/libraries/iready/assets.py`
- Test: `tests/libraries/test_iready_remote_file_regex.py`

**Interfaces:**

- Consumes: `is_legacy_year`, `remote_subject_token` from Task 1.
- Produces:
  `build_sftp_file_asset(..., legacy_remote_file_regex: str | None = None)` and
  `build_iready_sftp_asset(..., legacy_remote_file_regex: str | None = None)`.
  Task 5 passes this parameter.

- [ ] **Step 1: Write the failing test**

Create `tests/libraries/test_iready_remote_file_regex.py`. This is the
regression test for the FY27 outage: it asserts the composed regex matches the
real filename for each era, using filenames verified on the SFTP on 2026-09-01.

```python
import re

import pytest
from dagster import MultiPartitionKey

from teamster.libraries.sftp.assets import compose_regex

CURRENT_REGEXES = {
    "personalized_instruction_summary": (
        r"personalized_instruction_summary_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    "personalized_instruction_by_lesson": (
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math|reading)(_CONFIDENTIAL)?\.csv"
    ),
    "instruction_by_lesson": (
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    "diagnostic_results": (
        r"i-ready_inform_results_(?P<subject>ela|math|reading)"
        r"(_english)?_CONFIDENTIAL\.csv"
    ),
}

LEGACY_REGEXES = {
    "personalized_instruction_summary": (
        r"personalized_instruction_summary_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
    "personalized_instruction_by_lesson": (
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
    "instruction_by_lesson": (
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
    "diagnostic_results": (
        r"diagnostic_results_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),
}

# filenames verified on the i-Ready SFTP on 2026-09-01
CURRENT_FILENAMES = {
    ("personalized_instruction_summary", "ela"): (
        "personalized_instruction_summary_reading_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_summary", "math"): (
        "personalized_instruction_summary_math_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_by_lesson", "ela"): (
        "iready_instruction_by_lesson_reading_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_by_lesson", "math"): (
        "iready_instruction_by_lesson_math_CONFIDENTIAL.csv"
    ),
    ("instruction_by_lesson", "ela"): (
        "iready_pro_instruction_by_lesson_reading_CONFIDENTIAL.csv"
    ),
    ("instruction_by_lesson", "math"): (
        "iready_pro_instruction_by_lesson_math_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "ela"): (
        "i-ready_inform_results_reading_english_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "math"): "i-ready_inform_results_math_CONFIDENTIAL.csv",
}

LEGACY_FILENAMES = {
    ("personalized_instruction_summary", "ela"): (
        "personalized_instruction_summary_ela_CONFIDENTIAL.csv"
    ),
    ("personalized_instruction_summary", "math"): (
        "personalized_instruction_summary_math_CONFIDENTIAL.csv"
    ),
    ("diagnostic_results", "ela"): "diagnostic_results_ela_CONFIDENTIAL.csv",
    ("diagnostic_results", "math"): "diagnostic_results_math_CONFIDENTIAL.csv",
}

# stale pre-rename files the vendor left in Current_Year on 2026-07-18
STALE_CURRENT_YEAR_FILENAMES = [
    "diagnostic_results_ela_CONFIDENTIAL.csv",
    "diagnostic_results_math_CONFIDENTIAL.csv",
    "personalized_instruction_summary_ela_CONFIDENTIAL.csv",
    "iready_pro_instruction_by_lesson_ela_CONFIDENTIAL.csv",
]


def _composed(regex, subject, academic_year):
    from teamster.libraries.iready.subjects import remote_subject_token

    return compose_regex(
        regexp=regex,
        partition_key=MultiPartitionKey(
            {
                "academic_year": academic_year,
                "subject": remote_subject_token(
                    subject=subject, academic_year=academic_year
                ),
            }
        ),
    )


@pytest.mark.parametrize(("asset_name", "subject"), sorted(CURRENT_FILENAMES))
def test_current_era_regex_matches_live_filename(asset_name, subject):
    composed = _composed(CURRENT_REGEXES[asset_name], subject, "Current_Year")

    assert re.fullmatch(composed, CURRENT_FILENAMES[(asset_name, subject)]) is not None


@pytest.mark.parametrize(("asset_name", "subject"), sorted(LEGACY_FILENAMES))
def test_legacy_era_regex_matches_archive_filename(asset_name, subject):
    composed = _composed(LEGACY_REGEXES[asset_name], subject, "2025")

    assert re.fullmatch(composed, LEGACY_FILENAMES[(asset_name, subject)]) is not None


@pytest.mark.parametrize("stale_filename", STALE_CURRENT_YEAR_FILENAMES)
@pytest.mark.parametrize("subject", ["ela", "math"])
def test_current_era_regex_never_matches_a_stale_file(stale_filename, subject):
    """The July 2026 leftovers must be unmatchable in the current era.

    This is the bug: a stale FY26 file matching a FY27 partition is how 3,933
    rows of last year's data ended up labelled as this year's.
    """
    for regex in CURRENT_REGEXES.values():
        composed = _composed(regex, subject, "Current_Year")

        assert re.fullmatch(composed, stale_filename) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/libraries/test_iready_remote_file_regex.py -v`

Expected: FAIL. The `test_current_era_regex_matches_live_filename` cases for
`subject="ela"` fail, because nothing yet translates `ela` to `reading`.

- [ ] **Step 3: Add the parameter to the iready builder**

In `src/teamster/libraries/iready/assets.py`, add the parameter and forward it.
The full file after the change:

```python
from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.libraries.sftp.assets import build_sftp_file_asset


def build_iready_sftp_asset(
    asset_key,
    region_subfolder,
    remote_file_regex,
    avro_schema,
    start_fiscal_year: int,
    end_fiscal_year: int,
    legacy_remote_file_regex: str | None = None,
    op_tags=None,
):
    partition_keys = [str(y - 1) for y in range(start_fiscal_year, end_fiscal_year + 1)]

    return build_sftp_file_asset(
        asset_key=asset_key,
        remote_dir_regex=rf"/exports/{region_subfolder}/(?P<academic_year>\w+)",
        remote_file_regex=remote_file_regex,
        legacy_remote_file_regex=legacy_remote_file_regex,
        ssh_resource_key="ssh_iready",
        group_name="iready",
        avro_schema=avro_schema,
        slugify_replacements=[["%", "percent"]],
        op_tags=op_tags,
        partitions_def=MultiPartitionsDefinition(
            {
                "subject": StaticPartitionsDefinition(["ela", "math"]),
                "academic_year": StaticPartitionsDefinition(partition_keys),
            }
        ),
    )
```

- [ ] **Step 4: Add the parameter to the shared builder signature**

In `src/teamster/libraries/sftp/assets.py`, add `legacy_remote_file_regex` to
`build_sftp_file_asset`'s signature, immediately after `remote_file_regex`:

```python
def build_sftp_file_asset(
    asset_key: list[str],
    remote_dir_regex: str,
    remote_file_regex: str,
    ssh_resource_key: str,
    avro_schema,
    legacy_remote_file_regex: str | None = None,
    partitions_def=None,
```

Leave the rest of the signature untouched.

- [ ] **Step 5: Import the translation helpers**

Add to the imports at the top of `src/teamster/libraries/sftp/assets.py`:

```python
from teamster.libraries.iready.subjects import is_legacy_year, remote_subject_token
```

- [ ] **Step 6: Compose the era's regex inside the iready block**

In `src/teamster/libraries/sftp/assets.py`, the `if group_name == "iready":`
block currently computes only `remote_dir_regex_composed`, and
`remote_file_regex_composed` is computed once afterwards for every source
system. Replace the whole `if group_name == "iready": ... else: ...` block plus
the `remote_file_regex_composed` assignment that follows it with:

```python
        if group_name == "iready":
            partition_key = check.inst(obj=partition_key, ttype=MultiPartitionKey)

            academic_year_key, subject_key = partition_key.keys_by_dimension.values()

            multi_partitions_def = check.inst(
                obj=context.assets_def.partitions_def, ttype=MultiPartitionsDefinition
            )

            academic_year_last_partition_key = (
                multi_partitions_def.get_partitions_def_for_dimension("academic_year")
            ).get_last_partition_key()

            if academic_year_key == academic_year_last_partition_key:
                academic_year_dir = "Current_Year"
            else:
                academic_year_dir = academic_year_key

            remote_dir_regex_composed = compose_regex(
                regexp=remote_dir_regex,
                partition_key=MultiPartitionKey(
                    {"academic_year": academic_year_dir, "subject": subject_key}
                ),
            )

            # The filename era is a FIXED fiscal year, not "is this the newest
            # partition". Next July, FY27 rolls into a 2026/ archive that
            # carries the NEW names, so keying off the Current_Year branch
            # above would wrongly translate it back to `ela`.
            if is_legacy_year(academic_year_key):
                remote_file_regex_era = (
                    legacy_remote_file_regex
                    if legacy_remote_file_regex is not None
                    else remote_file_regex
                )
            else:
                remote_file_regex_era = remote_file_regex

            remote_file_regex_composed = compose_regex(
                regexp=remote_file_regex_era,
                partition_key=MultiPartitionKey(
                    {
                        "academic_year": academic_year_key,
                        "subject": remote_subject_token(
                            subject=subject_key, academic_year=academic_year_key
                        ),
                    }
                ),
            )
        else:
            remote_dir_regex_composed = compose_regex(
                regexp=remote_dir_regex, partition_key=partition_key
            )

            remote_file_regex_composed = compose_regex(
                regexp=remote_file_regex, partition_key=partition_key
            )
```

Note that `academic_year_dir` collapses the two near-identical `compose_regex`
calls the original had, so the directory behavior is unchanged.

- [ ] **Step 7: Run tests to verify they pass**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/libraries/test_iready_remote_file_regex.py tests/libraries/test_iready_subjects.py -v`

Expected: PASS.

- [ ] **Step 8: Verify no other source system regressed**

The `else` branch must behave exactly as before for every non-i-Ready SFTP
asset.

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/test_dagster_definitions.py -v`

Expected: PASS. This loads every code location for real via
`dagster definitions validate`.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/teamster/libraries/sftp/assets.py src/teamster/libraries/iready/assets.py tests/libraries/test_iready_remote_file_regex.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "feat(dagster): compose i-Ready file regex per filename era

Refs #4949"
```

---

### Task 3: Sensor translates the remote token back to a partition subject

**Files:**

- Modify: `src/teamster/libraries/iready/sensors.py`

**Interfaces:**

- Consumes: `partition_subject` from Task 1.
- Produces: no new signatures. The sensor's `MultiPartitionKey` subject values
  remain drawn from `["ela", "math"]`.

- [ ] **Step 1: Add the import**

In `src/teamster/libraries/iready/sensors.py`, add to the imports:

```python
from teamster.libraries.iready.subjects import partition_subject
```

- [ ] **Step 2: Translate when building the partition key**

The sensor currently reads `group_dict["subject"]` straight into the partition
key. Replace this block:

```python
                if group_dict["academic_year"] == "Current_Year":
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": str(current_fiscal_year - 1),
                            "subject": group_dict["subject"],
                        }
                    )
                else:
                    partition_key = MultiPartitionKey(group_dict)
```

with:

```python
                # The regex alternation carries the vendor's current token
                # (`reading`); the partition space does not. Translate back
                # before building the key, or the RunRequest names a partition
                # that does not exist.
                subject_key = partition_subject(
                    remote_token=group_dict["subject"],
                    academic_year=group_dict["academic_year"],
                )

                if group_dict["academic_year"] == "Current_Year":
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": str(current_fiscal_year - 1),
                            "subject": subject_key,
                        }
                    )
                else:
                    partition_key = MultiPartitionKey(
                        {
                            "academic_year": group_dict["academic_year"],
                            "subject": subject_key,
                        }
                    )
```

- [ ] **Step 3: Verify the code locations still load**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/test_dagster_definitions.py -v`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/teamster/libraries/iready/sensors.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "feat(dagster): map i-Ready remote subject token to partition subject

Refs #4949"
```

---

### Task 4: Declare the renamed and new Inform fields

**Files:**

- Modify: `src/teamster/libraries/iready/schema.py`

**Interfaces:**

- Consumes: nothing.
- Produces: 4 new optional string fields on `DiagnosticResults`:
  `assessment_gain`, `baseline_assessment_y_n`,
  `most_recent_assessment_ytd_y_n`, `tactile_graphics`.

Context: the model is already a superset carrying both
`most_recent_diagnostic_y_n` and `most_recent_diagnostic_ytd_y_n` from a prior
vendor rename. These 4 names were derived by running the real ingest slugifier
over the live headers, not guessed:

```text
'Baseline Assessment (Y/N)'        -> baseline_assessment_y_n
'Most Recent Assessment YTD (Y/N)' -> most_recent_assessment_ytd_y_n
'Assessment Gain'                  -> assessment_gain
'Tactile Graphics'                 -> tactile_graphics
```

- [ ] **Step 1: Add the fields**

In `src/teamster/libraries/iready/schema.py`, add these 4 lines to the
`DiagnosticResults` class, keeping the class's existing alphabetical ordering:

```python
    assessment_gain: str | None = None
    baseline_assessment_y_n: str | None = None
    most_recent_assessment_ytd_y_n: str | None = None
    tactile_graphics: str | None = None
```

Do **not** add an `assessment_language` field. The prior spec and #4949 both
claim `Diagnostic Language` was renamed to `Assessment Language`; neither column
exists in either file in either region, verified 2026-09-01.

- [ ] **Step 2: Verify the avro schema still generates**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/test_dagster_definitions.py -v`

Expected: PASS. The schema is generated at module import by
`py_avro_schema.generate`, so a malformed model fails the location load.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/teamster/libraries/iready/schema.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "feat(dagster): declare i-Ready Inform renamed and new fields

Refs #4949"
```

---

### Task 5: Wire the 8 asset definitions

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/iready/assets.py`
- Modify: `src/teamster/code_locations/kippnewark/iready/assets.py`

**Interfaces:**

- Consumes: `build_iready_sftp_asset(..., legacy_remote_file_regex=...)` from
  Task 2; the schema fields from Task 4.
- Produces: nothing consumed by later tasks.

Both files get identical regex values. Only `region_subfolder`, the
`start_fiscal_year` values, and the Newark `op_tags` differ, and none of those
change.

- [ ] **Step 1: Set the regexes in kippmiami**

In `src/teamster/code_locations/kippmiami/iready/assets.py`, replace the
`remote_file_regex` value of each of the 4 assets and add
`legacy_remote_file_regex` to each. The 4 pairs:

```python
# personalized_instruction_summary
    remote_file_regex=(
        r"personalized_instruction_summary_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    legacy_remote_file_regex=(
        r"personalized_instruction_summary_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),

# diagnostic_results
    remote_file_regex=(
        r"i-ready_inform_results_(?P<subject>ela|math|reading)"
        r"(_english)?_CONFIDENTIAL\.csv"
    ),
    legacy_remote_file_regex=(
        r"diagnostic_results_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),

# instruction_by_lesson  (asset key personalized_instruction_by_lesson)
    remote_file_regex=(
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math|reading)(_CONFIDENTIAL)?\.csv"
    ),
    legacy_remote_file_regex=(
        r"(personalized|iready)_instruction_by_lesson_"
        r"(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv"
    ),

# instruction_by_lesson_pro  (asset key instruction_by_lesson)
    remote_file_regex=(
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math|reading)"
        r"_CONFIDENTIAL\.csv"
    ),
    legacy_remote_file_regex=(
        r"iready_pro_instruction_by_lesson_(?P<subject>ela|math)_CONFIDENTIAL\.csv"
    ),
```

Every `legacy_remote_file_regex` value above is the file's current
`remote_file_regex`, unchanged. The `reading` alternative in each current-era
regex exists for the sensor, which matches uncomposed; the asset never sees it,
because `regex_pattern_replace` substitutes the whole named group.

- [ ] **Step 2: Set the same 8 values in kippnewark**

Apply the identical 4 pairs to
`src/teamster/code_locations/kippnewark/iready/assets.py`. Do not change
`region_subfolder`, `start_fiscal_year`, `end_fiscal_year`, or the
`personalized_instruction_summary` `op_tags` block.

- [ ] **Step 3: Verify both code locations load**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/test_dagster_definitions.py -v`

Expected: PASS.

- [ ] **Step 4: Verify the sensor matches live FY27 files**

This hits the real SFTP and needs the 1Password bootstrap, so it must run under
pytest.

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/sensors/sftp/test_sensors_sftp_iready.py -v -s`

Expected: PASS. In the captured log output, confirm run requests appear for
partition `2026|ela` — that is a `_reading_` file correctly mapping back to the
`ela` partition. If `test_iready_sftp_sensor_kippnewark` fails on its hardcoded
cursor values, raise them past 2026-09-01 and note the change in the commit.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/teamster/code_locations/kippmiami/iready/assets.py src/teamster/code_locations/kippnewark/iready/assets.py tests/sensors/sftp/test_sensors_sftp_iready.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "fix(dagster): match FY2027 i-Ready export filenames

Refs #4949"
```

---

### Task 6: Absorb the renamed columns in dbt

**Files:**

- Modify: `src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql`
- Modify:
  `src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml`

**Interfaces:**

- Consumes: the 4 schema fields from Task 4, which reach BigQuery as columns on
  `src_iready__diagnostic_results`.
- Produces: nothing consumed by later tasks.

The contract is enforced, so every column reaching output must be declared. The
3 redundant `assessment_*` columns are coalesced into their legacy-named
counterparts and excluded; only `tactile_graphics` is newly declared.

- [ ] **Step 1: Exclude the redundant new columns and coalesce the gain**

In the first CTE of
`src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql`, add these 3
entries to the `* except (...)` list, keeping its alphabetical ordering:

```sql
                assessment_gain,
                baseline_assessment_y_n,
                most_recent_assessment_ytd_y_n,
```

Also add `baseline_diagnostic_y_n` to that same `except` list — it currently
flows through `*` untouched and must be excluded so it can be re-emitted as a
coalesce.

Then change the existing `diagnostic_gain` cast (currently
`cast(cast(diagnostic_gain as numeric) as int) as diagnostic_gain,`) to:

```sql
            cast(
                cast(coalesce(diagnostic_gain, assessment_gain) as numeric) as int
            ) as diagnostic_gain,
```

- [ ] **Step 2: Coalesce the two Y/N columns**

The model already coalesces one pair of vendor-renamed columns, at
`coalesce(most_recent_diagnostic_y_n, most_recent_diagnostic_ytd_y_n) as most_recent_diagnostic_ytd_y_n,`.
Extend that expression and add one beside it, so the block reads:

```sql
            coalesce(
                most_recent_diagnostic_y_n,
                most_recent_diagnostic_ytd_y_n,
                most_recent_assessment_ytd_y_n
            ) as most_recent_diagnostic_ytd_y_n,

            coalesce(
                baseline_diagnostic_y_n, baseline_assessment_y_n
            ) as baseline_diagnostic_y_n,
```

Legacy names come first in every coalesce so history wins where both are
present.

- [ ] **Step 3: Translate the raw subject token in the final select**

The final select currently reads:

```sql
select
    *,

    overall_scale_score + typical_growth as overall_scale_score_plus_typical_growth,
    overall_scale_score + stretch_growth as overall_scale_score_plus_stretch_growth,
from calcs
```

Replace it with:

```sql
select
    * except (_dagster_partition_subject),

    -- The partition subject stays `ela` in Dagster because the GCS object path
    -- is derived from it. The warehouse reports the vendor's current name. This
    -- must stay in the final select: the HS growth-measure CASE expressions in
    -- `hs_goals` compare against the raw `ela` token.
    if(
        _dagster_partition_subject = 'ela', 'reading', _dagster_partition_subject
    ) as _dagster_partition_subject,

    overall_scale_score + typical_growth as overall_scale_score_plus_typical_growth,
    overall_scale_score + stretch_growth as overall_scale_score_plus_stretch_growth,
from calcs
```

- [ ] **Step 4: Declare the new column in the contract**

In
`src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml`,
add beside the other string columns:

```yaml
- name: tactile_graphics
  data_type: string
```

- [ ] **Step 5: Build the model and its children**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run dbt build --select stg_iready__diagnostic_results+ --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames/src/dbt/iready`

Expected: PASS. A contract violation here means a column reached output without
a YAML declaration — compare the error's column list against Step 1's `except`
list.

- [ ] **Step 6: Confirm the token translated and the subject column did not**

Run this against the built model, either through the BigQuery MCP or `dbt show`:

```sql
select
    _dagster_partition_subject,
    `subject`,
    discipline,
    count(*) as n,
from {{ ref("stg_iready__diagnostic_results") }}
group by 1, 2, 3
order by 1, 2
```

Expected: `_dagster_partition_subject` shows only `reading` and `math`;
`subject` still shows `Reading` and `Math`; `discipline` still shows `ELA` and
`Math`. If `discipline` shows anything else, Step 3 landed in the wrong CTE.

- [ ] **Step 7: Lint the SQL before committing**

`sqlfluff` runs at pre-push and CI, not at pre-commit, so a lint-clean commit
can still fail CI.

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml </dev/null`

Expected: No issues. If the binary is missing on a cold Codespace, use
`~/.cache/trunk/launcher/trunk` instead.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "fix(dbt): absorb i-Ready Inform column renames

Refs #4949"
```

---

### Task 7: Verify end to end against the live SFTP

**Files:**

- Test: `tests/assets/test_assets_iready_sftp.py` (read only; do not commit
  changes unless a case is genuinely broken)

**Interfaces:**

- Consumes: everything from Tasks 1 to 6.
- Produces: evidence for the PR body.

This task proves both eras resolve. It runs credentialed, against real files.

- [ ] **Step 1: Write the throwaway verification test**

`tests/assets/test_assets_iready_sftp.py` already has a `_test_asset` helper,
but every existing case calls it with no partition, and it then picks a
**random** partition key. Pass the partition explicitly instead. Multi-partition
keys are `academic_year|subject`, so FY2027 is `2026|ela`.

Create `tests/assets/test_zz_iready_fy27_verify.py`:

```python
"""Throwaway: prove both filename eras resolve. Delete after verifying."""

import pytest

from tests.assets.test_assets_iready_sftp import _test_asset

CURRENT_PARTITION = "2026|ela"
ARCHIVE_PARTITION = "2025|ela"


def _assets(code_location):
    if code_location == "kippmiami":
        from teamster.code_locations.kippmiami.iready import assets
    else:
        from teamster.code_locations.kippnewark.iready import assets

    return {a.key.path[-1]: a for a in assets.assets}


@pytest.mark.parametrize("code_location", ["kippmiami", "kippnewark"])
@pytest.mark.parametrize(
    "asset_name",
    [
        "diagnostic_results",
        "instruction_by_lesson",
        "personalized_instruction_by_lesson",
        "personalized_instruction_summary",
    ],
)
def test_zz_fy27_partition_materializes(code_location, asset_name):
    _test_asset(
        asset=_assets(code_location)[asset_name], partition_key=CURRENT_PARTITION
    )


@pytest.mark.parametrize("code_location", ["kippmiami", "kippnewark"])
def test_zz_archive_partition_still_materializes(code_location):
    _test_asset(
        asset=_assets(code_location)["diagnostic_results"],
        partition_key=ARCHIVE_PARTITION,
    )
```

- [ ] **Step 2: Run the FY27 cases**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/assets/test_zz_iready_fy27_verify.py -k fy27 -v -s`

Expected: 7 of 8 PASS. Each passing run fetches a `_reading_`,
`_reading_english_`, or `_math_` file and reports a non-zero record count in the
captured log. The known failure is `kippnewark` + `instruction_by_lesson` — see
Step 4.

- [ ] **Step 3: Run the archive case**

Run:
`cd /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames && uv run pytest tests/assets/test_zz_iready_fy27_verify.py -k archive -v -s`

Expected: PASS for both regions, each fetching
`/exports/<region>/2025/diagnostic_results_ela_CONFIDENTIAL.csv`. This is the
case that regresses if the era boundary is keyed off the `Current_Year` branch
instead of the fiscal year — if it fetches a `_reading_` file or raises
`FileNotFoundError`, Task 2 Step 6 is wrong.

- [ ] **Step 4: Confirm the polluted FY27 partition healed**

The FY27 `diagnostic_results` partition held 3,933 stale FY26 rows in Miami.
Check the record count logged by the Step 2 run.

Expected: a count different from 3,933, with FY27 completion dates. Two known
exceptions that are **not** failures:

- `kippnewark/iready/instruction_by_lesson` partition `2026|math` — no
  `iready_pro_instruction_by_lesson_math` file exists in `nj-kipp_nj` at all.
  This is a pre-existing vendor gap, tracked separately.
- Any partition for FY2024 or earlier — `2023/` and older archive folders are
  empty in both regions.

- [ ] **Step 5: Record the evidence, redacted**

Capture record counts and filenames for the PR body. Filenames, sizes and counts
are safe to post; **do not** paste data rows, student names, or IDs to the PR.

- [ ] **Step 6: Delete the throwaway test**

It materializes real assets against the live SFTP and must not land on the
branch.

```bash
rm /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames/tests/assets/test_zz_iready_fy27_verify.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames status --short
```

Expected: no `test_zz_` file listed.

- [ ] **Step 7: Commit any test fixture updates**

Only if Task 5 Step 4 required changing the hardcoded sensor cursors, and only
if that change is not already committed:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames add tests/sensors/sftp/test_sensors_sftp_iready.py
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-iready-fy27-export-renames commit -m "test(dagster): update i-Ready sensor cursors for FY2027

Refs #4949"
```

---

## Follow-up issues to file

These are out of scope for this plan and were split out deliberately during
brainstorming. File each before opening the PR so the PR body can reference
them.

1. **`standards_results` ingestion** (`feat`). Never ingested. Per-grade files
   `_2` through `_8`, grade- and state-specific columns, embedded newlines in
   quoted header cells. Needs a third partition dimension and a long-not-wide
   shape. No urgency: Miami-only, and the FY27 `_reading_` copies are
   byte-for-byte the same sizes as the July `_ela_` copies across all 7 grades.
1. **Retire `instructional_usage_data`** (`fix`). No Dagster asset, staging
   disabled in both district projects, snapshot disabled, no consumer, SFTP
   files frozen since 2025-07-21.
1. **Missing NJ `iready_pro_instruction_by_lesson_math`** (`fix`). No such file
   exists in `nj-kipp_nj`; `kippnewark/iready/instruction_by_lesson` has only
   ever materialized `ela`. Vendor configuration gap.

## Manual steps for the repo owner

Neither is required for this plan to be correct, and neither should block the
PR.

- Mark historical partitions materialized in Dagster rather than backfilling.
- Ask Curriculum Associates to archive and remove the stale `Current_Year`
  files. Note that the `2025/` archive copies were written 2026-06-30 and are
  smaller than the 2026-07-18 `Current_Year` copies, so this is not a no-op.
