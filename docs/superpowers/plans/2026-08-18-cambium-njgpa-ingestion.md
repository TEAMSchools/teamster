# Cambium TIDE NJGPA Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the Cambium TIDE NJGPA district summative record file for
Newark and Camden and union it into the existing NJ state assessment stream so
every current consumer picks it up with no change in behavior.

**Architecture:** A new `cambium` Dagster library plus per-region SFTP file
assets on the existing Couchdrop sensor, landing Avro in GCS. A new
`src/dbt/cambium` source-system dbt project stages the file in Cambium's own
vocabulary under an enforced contract. A kipptaf `stg_cambium__njgpa` model
unions the two regions and maps into the shared NJ-assessment column shape,
after which one added relation in `int_pearson__all_assessments` carries the
data to all ~15 downstream consumers.

**Tech Stack:** Dagster (`build_sftp_file_asset`, `MultiPartitionsDefinition`),
Pydantic + `py_avro_schema`, BigQuery AVRO external tables, dbt (BigQuery
adapter, `dbt_external_tables`, `dbt_utils`), `uv`, trunk (ruff, sqlfluff,
yamllint, markdownlint).

**Spec:**
[`docs/superpowers/specs/2026-08-18-cambium-njgpa-ingestion-design.md`](../specs/2026-08-18-cambium-njgpa-ingestion-design.md)

Refs #4899

## Global Constraints

- **Worktree.** All work happens in
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa`.
  Every git call uses `git -C <worktree>`; a bare `git` from the main repo
  commits to the wrong checkout. Every dbt call uses
  `--project-dir <worktree>/src/dbt/<project>`.
- **Python.** `requires-python = ">=3.13"`. Built-in generics (`list[str]`),
  `X | None` for nullable. Always `uv run`; never bare `python` or `dbt`.
- **Line length 88** — enforced by sqlfluff (`.trunk/config/.sqlfluff`) and by
  the ruff **formatter**, which reflows. Ruff-as-linter ignores `E501`
  (`.trunk/config/ruff.toml`), so a long Python line is reflowed, not failed.
- **Contract enforcement.** `src/dbt/cambium/models/staging/` is
  contract-enforced (set at directory level in `dbt_project.yml`). The kipptaf
  `cambium` layer is **not** contract-enforced — this matches the existing
  `pearson` block in `src/dbt/kipptaf/dbt_project.yml`, which is only
  `+schema: pearson`.
- **District codes.** Newark `7325`, Camden `1799`. Hardcoded per region, never
  a `\d+` wildcard (spec D6).
- **Partition dimensions.** `administration_year` (4-digit, from 2026) and
  `administration`, whose values and the regex alternation **derive from one
  shared `ADMINISTRATIONS` list** so they cannot drift (spec D5 and D8). This is
  load-bearing: an unrecognized season token that MATCHES the regex but is not a
  declared partition raises inside `resolve_run_requests`, failing the entire
  sensor tick and — because the cursor is not persisted on FAILURE — stalling
  all six of that region's Couchdrop assets indefinitely.
- **`test_grade`** is
  `case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end` (spec D3) —
  asserted, not derived, but keyed so an unknown code yields NULL rather than a
  confident 11. It carries an explanatory SQL comment.
- **`testscorecomplete` is a passthrough, genuinely NULL for Cambium** (spec
  D2). Do NOT synthesize a constant. The single consumer,
  `int_students__graduation_path_codes`, is changed to
  `coalesce(n.testscorecomplete, 1) = 1` in Task 9.
- **`test_date` must coalesce to a parsed
  `assessmentsessionactualstartdatetime`** (spec, _Verified source
  characteristics_). The unit online start timestamps are ELA-only; unit-only
  derivation nulls 406 of 813 rows and silently removes every Mathematics score
  from `fct_assessment_scores_enrollment_scoped`.
- **SQL conventions.** BigQuery dialect, trailing commas, single quotes,
  backtick reserved words (`` `subject` ``, `` `period` ``). Plain column
  references before computed ones (sqlfluff ST06). Do **not** introduce
  `select distinct`, `qualify row_number() = 1`, or `dbt_utils.deduplicate` — no
  deduplication is needed anywhere in this plan; `student_test_uuid` is already
  unique per row.
- **Markdown.** Fenced blocks always carry a language (MD040). Backtick every
  model and column name in prose. Use `1.` for every ordered-list item (MD029).
- **Trunk.** Do not run `trunk fmt` manually; the pre-commit hook formats. For
  lint verification run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd set to the worktree.

---

### Task 1: Cambium library schema

Generate the Pydantic model mechanically from a real file. Do not hand-type 225
fields.

**Files:**

- Create: `src/teamster/libraries/cambium/schema.py`
- Create: `scripts/gen-cambium-schema.py`
- Test: `tests/libraries/test_cambium_schema.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `teamster.libraries.cambium.schema.NJGPA` — a `BaseModel` subclass
  with 225 fields, all `str | None = None`, plus `source_file_name` inherited
  from a local `SFTPFile`. Task 2 imports `NJGPA`.

Note: `src/teamster/libraries/pearson/` has no `__init__.py` (namespace
package). Do not create one for `cambium` either.

- [ ] **Step 1: Write the generator script**

Create `scripts/gen-cambium-schema.py`:

```python
"""Generate the Cambium NJGPA Pydantic model from a real summative record file.

The sample CSV is local-only (it contains student PII and is never committed).
The GENERATED file is the committed artifact. Re-run this only when Cambium
changes the file layout.

Usage:
    uv run --with python-slugify python scripts/gen-cambium-schema.py \\
        "<path to a District_Summative_Record_File_GPA.csv>" \\
        src/teamster/libraries/cambium/schema.py
"""

import csv
import sys
from pathlib import Path

from slugify import slugify

HEADER = '''from pydantic import BaseModel


class SFTPFile(BaseModel):
    source_file_name: str | None = None


class NJGPA(SFTPFile):
'''


def main() -> None:
    sample_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    with open(file=sample_path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))

    slugs = sorted({slugify(text=h, separator="_") for h in header})

    body = "".join(f"    {slug}: str | None = None\n" for slug in slugs)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(HEADER + body)

    print(f"wrote {out_path} with {len(slugs)} NJGPA fields")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

The sample file lives outside the repo (gitignored, contains PII). Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run --with python-slugify python scripts/gen-cambium-schema.py \
  "/workspaces/teamster/.claude/scratch/NJGPA SY25-26/2026_Spring_7325_District_Summative_Record_File_GPA.csv" \
  src/teamster/libraries/cambium/schema.py
```

Expected output:
`wrote src/teamster/libraries/cambium/schema.py with 225 NJGPA fields`

Verify shape (233 lines total, longest line 87 chars — both already confirmed):

```bash
wc -l src/teamster/libraries/cambium/schema.py
awk '{ print length }' src/teamster/libraries/cambium/schema.py | sort -rn | head -1
```

Expected: `233` and `87`.

- [ ] **Step 3: Write the failing test**

Create `tests/libraries/test_cambium_schema.py`, modeled on
`tests/libraries/test_adp_wfn_schema.py`:

```python
import json

import py_avro_schema

from teamster.libraries.cambium.schema import NJGPA

PAS_OPTIONS = (
    py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
)


def _njgpa_avro_schema() -> dict:
    return json.loads(py_avro_schema.generate(py_type=NJGPA, options=PAS_OPTIONS))


def test_field_count():
    # 225 columns in the Cambium summative record file, plus the
    # source_file_name the SFTP factory appends to every row
    assert len(NJGPA.model_fields) == 226


def test_avro_schema_includes_load_bearing_fields():
    schema = _njgpa_avro_schema()

    top_level = {f["name"] for f in schema["fields"]}

    # every field the dbt staging model selects must survive generation —
    # py_avro_schema silently drops what it cannot represent, and the asset
    # check only compares top-level keys
    for field in [
        "source_file_name",
        "assessment_grade",
        "assessment_year",
        "grade_level_when_assessed",
        "local_student_identifier",
        "period",
        "state_student_identifier",
        "student_test_uuid",
        "student_with_disabilities",
        "subject",
        "summative_flag",
        "test_attemptedness_flag",
        "test_code",
        "test_performance_level",
        "test_scale_score",
        "test_status",
        "unit_1_online_test_start_date_time",
        "unit_4_online_test_start_date_time",
    ]:
        assert field in top_level, f"{field} missing from generated Avro schema"


def test_all_fields_are_nullable_strings():
    # the SFTP factory hands every CSV value through as a string or None;
    # a non-string annotation would fail Avro validation at write time
    for name, field in NJGPA.model_fields.items():
        assert field.default is None, f"{name} has a non-None default"
```

- [ ] **Step 4: Run the test**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run pytest tests/libraries/test_cambium_schema.py -v
```

Expected: 3 passed. If `test_field_count` fails with 226 != N, the generator
read a different file layout — stop and reconcile against the spec's 225-column
finding rather than editing the assertion.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/libraries/cambium/schema.py \
  scripts/gen-cambium-schema.py \
  tests/libraries/test_cambium_schema.py </dev/null
```

Expected: no issues.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/teamster/libraries/cambium/schema.py scripts/gen-cambium-schema.py \
      tests/libraries/test_cambium_schema.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dagster): add Cambium NJGPA Pydantic schema and generator

Refs #4899"
```

---

### Task 2: Per-region Dagster assets, sensor, and definitions wiring

Both regions in one task — the modules are symmetric and an asset without its
sensor entry is inert, so a reviewer would accept or reject them together.

**Files:**

- Create: `src/teamster/code_locations/kippnewark/cambium/__init__.py`
- Create: `src/teamster/code_locations/kippnewark/cambium/schema.py`
- Create: `src/teamster/code_locations/kippnewark/cambium/assets.py`
- Create: `src/teamster/code_locations/kippcamden/cambium/__init__.py`
- Create: `src/teamster/code_locations/kippcamden/cambium/schema.py`
- Create: `src/teamster/code_locations/kippcamden/cambium/assets.py`
- Modify: `src/teamster/code_locations/kippnewark/couchdrop/sensors.py`
- Modify: `src/teamster/code_locations/kippcamden/couchdrop/sensors.py`
- Modify: `src/teamster/code_locations/kippnewark/definitions.py`
- Modify: `src/teamster/code_locations/kippcamden/definitions.py`

**Interfaces:**

- Consumes: `teamster.libraries.cambium.schema.NJGPA` from Task 1.
- Produces: Dagster assets keyed `kippnewark/cambium/njgpa` and
  `kippcamden/cambium/njgpa`, writing Avro to
  `gs://teamster-<region>/dagster/<region>/cambium/njgpa/`. Task 3's external
  source reads that prefix.

- [ ] **Step 1: Write the Newark schema module**

Create `src/teamster/code_locations/kippnewark/cambium/schema.py`, mirroring
`src/teamster/code_locations/kippnewark/pearson/schema.py`:

```python
import json

import py_avro_schema

from teamster.libraries.cambium.schema import NJGPA

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

NJGPA_SCHEMA = json.loads(py_avro_schema.generate(py_type=NJGPA, options=pas_options))
```

- [ ] **Step 2: Write the Newark assets module**

Create `src/teamster/code_locations/kippnewark/cambium/assets.py`:

```python
from dagster import MultiPartitionsDefinition, StaticPartitionsDefinition

from teamster.code_locations.kippnewark import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippnewark.cambium.schema import NJGPA_SCHEMA
from teamster.libraries.sftp.assets import build_sftp_file_asset

ssh_resource_key = "ssh_couchdrop"
remote_dir_regex_prefix = f"/data-team/{CODE_LOCATION}/cambium"
key_prefix = [CODE_LOCATION, "cambium"]

# Feeds BOTH the filename regex alternation and the partition values, so the two
# cannot drift. Spring is verified from the files in hand; the rest are the fall
# tokens Pearson actually used (FallBlock in 2024, FALL in 2025).
#
# This is not belt-and-braces. A token that matches the regex but is NOT a
# declared partition raises inside Dagster's resolve_run_requests, which
# processes every run request for the tick in one pass — so the whole tick fails,
# the cursor is not persisted on FAILURE, the file is re-listed forever, and all
# six of this region's Couchdrop assets stall until a redeploy. Sharing the list
# makes an unknown token simply not match, which skips the file and leaves the
# rest of the sensor working.
ADMINISTRATIONS = ["Spring", "Fall", "FALL", "FallBlock"]

# The district code is hardcoded rather than matched with `\d+`: each region has
# its own Couchdrop folder, and build_sftp_file_asset raises on multiple
# matches, so a wildcard would break if the other district's file ever landed
# here.
njgpa = build_sftp_file_asset(
    asset_key=[*key_prefix, "njgpa"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/njgpa",
    remote_file_regex=(
        r"(?P<administration_year>\d{4})"
        # longest-first so FallBlock is not shadowed by Fall
        rf"_(?P<administration>{'|'.join(sorted(ADMINISTRATIONS, key=len, reverse=True))})"
        r"_7325_District_Summative_Record_File_GPA\.csv"
    ),
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=MultiPartitionsDefinition(
        {
            # 4-digit year as it appears in the filename. Deliberately not named
            # fiscal_year: academic year comes from the file's own
            # assessment_year field, not from this. range(2026, FY+1) covers the
            # value whether Cambium means calendar year or school-year-end year.
            "administration_year": StaticPartitionsDefinition(
                [
                    str(year)
                    for year in range(2026, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                ]
            ),
            "administration": StaticPartitionsDefinition(ADMINISTRATIONS),
        }
    ),
)

assets = [
    njgpa,
]
```

- [ ] **Step 3: Write the Newark package init**

Create `src/teamster/code_locations/kippnewark/cambium/__init__.py`:

```python
from teamster.code_locations.kippnewark.cambium.assets import assets

__all__ = [
    "assets",
]
```

- [ ] **Step 4: Create the Camden modules**

Identical to Steps 1-3 with two substitutions: `kippnewark` becomes `kippcamden`
in every import path, and `_7325_` becomes `_1799_` in `remote_file_regex`.
Write all three files in full — do not import across code locations.

- [ ] **Step 5: Register both assets on the Couchdrop sensors**

In `src/teamster/code_locations/kippnewark/couchdrop/sensors.py`, add the import
and the selection entry. The file currently imports from
`kippnewark.pearson.assets`; add above it (alphabetical):

```python
from teamster.code_locations.kippnewark.cambium.assets import njgpa as cambium_njgpa
```

The existing `pearson.assets` import already binds the name `njgpa`, so the
Cambium asset must be aliased. Then add `cambium_njgpa` as the first entry of
`asset_selection`.

Apply the same two edits to
`src/teamster/code_locations/kippcamden/couchdrop/sensors.py`.

- [ ] **Step 6: Wire both modules into definitions**

In `src/teamster/code_locations/kippnewark/definitions.py`, add `cambium` to the
`from teamster.code_locations.kippnewark import (...)` list (alphabetically,
before `couchdrop`) and add `cambium` to the `modules=[...]` list passed to
`load_assets_from_modules`. Same for `kippcamden`.

- [ ] **Step 7: Verify the modules import and the asset keys are right**

`dagster definitions validate` needs a dbt manifest and is unreliable in the
codespace, so import the submodules directly instead:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run python -c "
from teamster.code_locations.kippnewark.cambium.assets import njgpa as n
from teamster.code_locations.kippcamden.cambium.assets import njgpa as c
for a in (n, c):
    print('key: ', a.key.to_user_string())
    print('  dir: ', a.metadata_by_key[a.key]['remote_dir_regex'])
    print('  file:', a.metadata_by_key[a.key]['remote_file_regex'])
    print('  dims:', [d.name for d in a.partitions_def.partitions_defs])
"
```

Expected: keys `kippnewark/cambium/njgpa` and `kippcamden/cambium/njgpa`; dirs
`/data-team/kippnewark/cambium/njgpa` and `/data-team/kippcamden/cambium/njgpa`;
file regexes carrying `_7325_` and `_1799_` respectively.

- [ ] **Step 8: Verify the regex matches the real Couchdrop paths**

The files are already on Couchdrop at their final paths. Assert the sensor's
matching logic against them — the sensor uses `re.compile(...).match()` on the
joined `dir/file` pattern:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run python -c "
import re
from teamster.code_locations.kippnewark.cambium.assets import njgpa as n
from teamster.code_locations.kippcamden.cambium.assets import njgpa as c

cases = [
    (n, '/data-team/kippnewark/cambium/njgpa/2026_Spring_7325_District_Summative_Record_File_GPA.csv', True),
    (c, '/data-team/kippcamden/cambium/njgpa/2026_Spring_1799_District_Summative_Record_File_GPA.csv', True),
    (n, '/data-team/kippnewark/cambium/njgpa/2026_Spring_1799_District_Summative_Record_File_GPA.csv', False),
    (n, '/data-team/kippnewark/pearson/njgpa/pcspr25_NJ-807325_District_Summative_Record_File_GPA_Spring.csv', False),
]
for a, path, want in cases:
    md = a.metadata_by_key[a.key]
    pat = re.compile(f\"{md['remote_dir_regex']}/{md['remote_file_regex']}\")
    got = pat.match(path) is not None
    assert got == want, f'{path} expected {want} got {got}'
    if got:
        print('match', pat.match(path).groupdict())
print('all regex cases OK')
"
```

Expected: two
`match {'administration_year': '2026', 'administration': 'Spring'}` lines, then
`all regex cases OK`.

- [ ] **Step 9: Lint**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/teamster/code_locations/kippnewark/cambium/ \
  src/teamster/code_locations/kippcamden/cambium/ \
  src/teamster/code_locations/kippnewark/couchdrop/sensors.py \
  src/teamster/code_locations/kippcamden/couchdrop/sensors.py \
  src/teamster/code_locations/kippnewark/definitions.py \
  src/teamster/code_locations/kippcamden/definitions.py </dev/null
```

Expected: no issues.

- [ ] **Step 10: Commit**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/teamster/code_locations/kippnewark/cambium \
      src/teamster/code_locations/kippcamden/cambium \
      src/teamster/code_locations/kippnewark/couchdrop/sensors.py \
      src/teamster/code_locations/kippcamden/couchdrop/sensors.py \
      src/teamster/code_locations/kippnewark/definitions.py \
      src/teamster/code_locations/kippcamden/definitions.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dagster): add Cambium NJGPA assets for Newark and Camden

Refs #4899"
```

---

### Task 3: `src/dbt/cambium` project scaffold and external source

**Files:**

- Create: `src/dbt/cambium/dbt_project.yml`
- Create: `src/dbt/cambium/packages.yml`
- Create: `src/dbt/cambium/package-lock.yml`
- Create: `src/dbt/cambium/.gitignore`
- Create: `src/dbt/cambium/CLAUDE.md`
- Create: `src/dbt/cambium/models/sources-external.yml`

**Interfaces:**

- Consumes: the GCS prefix written by Task 2's assets.
- Produces: source `cambium.src_cambium__njgpa`, referenced as
  `source("cambium", "src_cambium__njgpa")` by Task 4.

- [ ] **Step 1: Write `dbt_project.yml`**

```yaml
name: cambium
version: 1.0.0
config-version: 2
require-dbt-version: [">=1.3.0", <2.0.0]

profile: integration_tests

model-paths: [models]
analysis-paths: [analyses]
test-paths: [tests]
seed-paths: [seeds]
macro-paths: [macros]
snapshot-paths: [snapshots]

target-path: target
clean-targets:
  - target
  - dbt_packages

vars:
  bigquery_external_connection_name: null

models:
  +schema: cambium
  cambium:
    staging:
      +contract:
        enforced: true
```

- [ ] **Step 2: Write `packages.yml`**

Copied verbatim from `src/dbt/pearson/packages.yml`:

```yaml
# trunk-ignore-all(yamllint/quoted-strings)
packages:
  # https://github.com/dbt-labs/dbt-external-tables
  - package: dbt-labs/dbt_external_tables
    version: [">=0.12.0", "<1.0.0"]
  # https://github.com/dbt-labs/dbt-utils
  - package: dbt-labs/dbt_utils
    version: [">=1.3.2", "<2.0.0"]
```

- [ ] **Step 3: Copy the `.gitignore` and generate the lockfile**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
cp src/dbt/pearson/.gitignore src/dbt/cambium/.gitignore && \
uv run dbt deps --project-dir src/dbt/cambium
```

Expected: `package-lock.yml` created. Confirm it pins the same versions as
`src/dbt/pearson/package-lock.yml` (`dbt_external_tables` 0.12.3, `dbt_utils`
1.4.1); a different resolution means the version ranges were mistyped.

- [ ] **Step 4: Write `models/sources-external.yml`**

Mirrors the `src_pearson__njgpa` block in
`src/dbt/pearson/models/sources-external.yml`, including the target-conditional
schema pattern. Do not use a macro in `schema:` — `SchemaYamlContext` provides
only `env_var()`, `var()`, `target`, and `project_name`.

```yaml
sources:
  - name: cambium
    schema:
      "{%- if target.name in ['defer', 'dev'] -%}zz_{{ env_var('GITHUB_USER',
      'dev') }}_{%- elif target.name == 'staging' -%}zz_stg_{%- endif -%}{{
      var('cambium_schema', project_name ~ '_cambium') }}"
    tables:
      - name: src_cambium__njgpa
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - cambium
                - njgpa
        external:
          location:
            "{{ var('cloud_storage_uri_base',
            env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/cambium/njgpa/*"
          options:
            connection_name: "{{ var('bigquery_external_connection_name') }}"
            metadata_cache_mode: MANUAL
            max_staleness: INTERVAL 7 DAY
            format: AVRO
            enable_logical_types: true
            hive_partition_uri_prefix:
              "{{ var('cloud_storage_uri_base',
              env_var('DBT_DEV_CLOUD_STORAGE_URI_BASE', '')) }}/cambium/njgpa/"
```

- [ ] **Step 5: Write `CLAUDE.md`**

```markdown
# CLAUDE.md — `dbt/cambium/`

Source-system staging project for **Cambium TIDE** New Jersey state assessments.
New Jersey moved NJGPA score reporting from Pearson Access Next to Cambium TIDE
with the Spring 2026 administration; NJSLA and NJSLA Science are still on
Pearson. Staging-only. Consumers:
`grep -l 'local: ../cambium' src/dbt/*/packages.yml`.

Only `kippnewark` and `kippcamden` import this package — Paterson does not sit
for NJGPA and has `stg_pearson__njgpa` disabled.

Column names are snake_case because Cambium ships spaced CSV headers, where
Pearson shipped camel case. Only 11 of 225 column names overlap with
`stg_pearson__njgpa`; the two are unrelated schemas over the same assessment.
Alignment into the shared NJ-assessment column shape happens in kipptaf's
`stg_cambium__njgpa`, not here.
```

- [ ] **Step 6: Verify the project parses**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt parse --project-dir src/dbt/cambium
```

Expected: parse succeeds. There are no models yet, so an empty-project notice is
fine; a Jinja or YAML error is not.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/cambium/dbt_project.yml src/dbt/cambium/packages.yml \
  src/dbt/cambium/models/sources-external.yml src/dbt/cambium/CLAUDE.md </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/cambium
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): scaffold cambium source project and NJGPA external source

Refs #4899"
```

---

### Task 4: `stg_cambium__njgpa` in the source project

Cleans Cambium in Cambium's own vocabulary. Casting, the attemptedness filter,
`test_date`, `academic_year`. No renaming to Pearson names here — that is
Task 6.

**Files:**

- Create: `src/dbt/cambium/models/staging/stg_cambium__njgpa.sql`
- Create: `src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml`

**Interfaces:**

- Consumes: `source("cambium", "src_cambium__njgpa")` from Task 3.
- Produces: relation `stg_cambium__njgpa` with these columns. Task 6 reads all
  of them except `grade_level_when_assessed` and `test_status`, which are
  carried for analysis and are deliberately not promoted into the shared shape:
  `academic_year` (int64), `assessment_grade` (string), `assessment_year`
  (string), `american_indian_or_alaska_native` (string), `asian` (string),
  `black_or_african_american` (string), `first_name` (string),
  `grade_level_when_assessed` (int64), `hispanic_or_latino_ethnicity` (string),
  `last_or_surname` (string), `local_student_identifier` (int64),
  `multilingual_learner` (string), `native_hawaiian_or_other_pacific_islander`
  (string), `period` (string), `state_student_identifier` (int64),
  `student_test_uuid` (string), `student_with_disabilities` (string), `subject`
  (string), `test_code` (string), `test_date` (date), `test_performance_level`
  (numeric), `test_scale_score` (numeric), `test_status` (string),
  `two_or_more_races` (string), `white` (string).

- [ ] **Step 1: Write the model**

Create `src/dbt/cambium/models/staging/stg_cambium__njgpa.sql`:

```sql
with
    njgpa as (
        select
            american_indian_or_alaska_native,
            asian,
            assessment_grade,
            assessment_year,
            black_or_african_american,
            first_name,
            hispanic_or_latino_ethnicity,
            last_or_surname,
            multilingual_learner,
            native_hawaiian_or_other_pacific_islander,
            `period`,
            student_test_uuid,
            student_with_disabilities,
            `subject`,
            test_code,
            test_status,
            two_or_more_races,
            white,

            cast(grade_level_when_assessed as int) as grade_level_when_assessed,
            cast(local_student_identifier as int) as local_student_identifier,
            cast(state_student_identifier as int) as state_student_identifier,

            cast(test_performance_level as numeric) as test_performance_level,
            cast(test_scale_score as numeric) as test_scale_score,

            /* Cambium sends this entirely null where Pearson set it to 1.
               Carried through explicitly rather than omitted so the vendor
               difference is visible in the contract instead of appearing
               downstream as a union_relations null-fill artifact. The single
               consumer coalesces it -- see the design spec, decision D2. */
            cast(test_score_complete as numeric) as test_score_complete,

            cast(left(assessment_year, 4) as int) as academic_year,

            /* MMDDYYYYHHMM. safe_cast to timestamp returns NULL on this format;
               parse_datetime with an explicit format is required. This is the
               ONLY test-date source for Mathematics rows -- the unit-level
               timestamps below are populated for ELA only. */
            safe.parse_datetime(
                '%m%d%Y%H%M', assessmentsessionactualstartdatetime
            ) as session_start_datetime,

            safe_cast(
                unit_1_online_test_start_date_time as timestamp
            ) as unit_1_start_timestamp,
            safe_cast(
                unit_2_online_test_start_date_time as timestamp
            ) as unit_2_start_timestamp,
            safe_cast(
                unit_3_online_test_start_date_time as timestamp
            ) as unit_3_start_timestamp,
            safe_cast(
                unit_4_online_test_start_date_time as timestamp
            ) as unit_4_start_timestamp,

        from {{ source("cambium", "src_cambium__njgpa") }}
        where summative_flag = 'Y' and test_attemptedness_flag = 'Y'
    ),

    earliest_test_start as (
        select
            * except (
                unit_1_start_timestamp,
                unit_2_start_timestamp,
                unit_3_start_timestamp,
                unit_4_start_timestamp
            ),

            (
                select min(s),
                from
                    unnest(
                        [
                            unit_1_start_timestamp,
                            unit_2_start_timestamp,
                            unit_3_start_timestamp,
                            unit_4_start_timestamp
                        ]
                    ) as s
            ) as earliest_test_start_timestamp,

        from njgpa
    )

select
    * except (earliest_test_start_timestamp, session_start_datetime),

    /* Unit start wins where it exists, which preserves ELA behavior exactly;
       the session fallback fills Mathematics, whose unit timestamps are ALL
       null (verified: 0 of 282 Newark and 0 of 124 Camden MATGP rows carry any
       unit start). Without the coalesce, test_date is null on 406 of 813 rows,
       int_assessments__resolved_section_enrollments filters them out, and the
       enrollment-scoped fact inner-joins that model -- so every Cambium math
       score would silently never reach the fact, with all tests still green.
       Where both sources exist they agree on 363 of 407 ELA rows and differ on
       44, so the ordering is deliberate. */
    coalesce(
        date(earliest_test_start_timestamp), date(session_start_datetime)
    ) as test_date,

from earliest_test_start
```

- [ ] **Step 2: Write the properties file**

Create `src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml`.
Contract enforcement matches on name and type, not YAML order.

```yaml
models:
  - name: stg_cambium__njgpa
    description: >-
      Cambium TIDE NJGPA district summative record file, one row per student per
      subject test. Filtered to summative, attempted records. Columns keep
      Cambium's own vocabulary; alignment into the shared NJ state assessment
      shape happens in kipptaf's stg_cambium__njgpa.
    columns:
      - name: student_test_uuid
        data_type: string
        description: Cambium's per-test identifier. Unique per row.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: state_student_identifier
        data_type: int64
        description: NJ SMART state student identifier (10 digits).
      - name: local_student_identifier
        data_type: int64
        description: >-
          PowerSchool student_number. Null for a small number of students each
          administration; patched downstream from the student crosswalk sheet.
      - name: first_name
        data_type: string
        description: Student first name as reported by Cambium.
      - name: last_or_surname
        data_type: string
        description: Student surname as reported by Cambium.
      - name: academic_year
        data_type: int64
        description:
          Start year of assessment_year, e.g. '2025-2026' becomes 2025.
      - name: assessment_year
        data_type: string
        description: Vendor-reported school year, e.g. '2025-2026'.
      - name: assessment_grade
        data_type: string
        description: >-
          The test DESIGN level, not the student's grade — 'Grade 10' for ELA
          and 'Grade 11' for Math. Not used for reporting grade level; see
          grade_level_when_assessed.
      - name: grade_level_when_assessed
        data_type: int64
        description: >-
          The student's grade at the time of testing. 11 for every row in the
          spring administration; expect 12 for fall retakers.
      - name: period
        data_type: string
        description: >-
          Vendor-reported administration season. 'Spring' in the files seen so
          far; the fall token is unconfirmed and has drifted historically, so
          downstream normalization is case-insensitive.
      - name: subject
        data_type: string
        description: 'English Language Arts' or 'Mathematics'.
      - name: test_code
        data_type: string
        description: ELAGP (ELA) or MATGP (Mathematics).
      - name: test_status
        data_type: string
        description: >-
          Cambium test lifecycle status — completed, pending, or invalidated.
          Every row surviving the summative and attemptedness filter is
          'completed', so this is informational rather than a filter.
      - name: test_performance_level
        data_type: numeric
        description: >-
          1 (Not Yet Graduation Ready) or 2 (Graduation Ready). Same two-level
          scale Pearson used for NJGPA.
      - name: test_scale_score
        data_type: numeric
        description: Scale score. Non-null on every filtered row.
      - name: test_score_complete
        data_type: numeric
        description: >-
          Entirely NULL from Cambium, where Pearson set it to 1 on every filtered
          row. Carried through so the vendor difference is visible here rather
          than appearing downstream as a union null-fill. The single consumer,
          int_students__graduation_path_codes, coalesces it. See design spec D2.
      - name: test_date
        data_type: date
        description: >-
          Date of the earliest online unit start across units 1 through 4,
          coalesced to the parsed assessment session start. The coalesce is
          required, not defensive: unit timestamps are populated for ELA only, so
          unit-only derivation nulls every Mathematics row.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: student_with_disabilities
        data_type: string
        description: N, IEP, 504, or B (both IEP and 504).
      - name: multilingual_learner
        data_type: string
        description: Y/N multilingual learner flag; maps to englishlearnerel downstream.
      - name: hispanic_or_latino_ethnicity
        data_type: string
        description: Y/N federal ethnicity flag.
      - name: american_indian_or_alaska_native
        data_type: string
        description: Y/N federal race flag.
      - name: asian
        data_type: string
        description: Y/N federal race flag.
      - name: black_or_african_american
        data_type: string
        description: Y/N federal race flag.
      - name: native_hawaiian_or_other_pacific_islander
        data_type: string
        description: Y/N federal race flag.
      - name: two_or_more_races
        data_type: string
        description: Y/N federal race flag.
      - name: white
        data_type: string
        description: Y/N federal race flag.
```

Note for the reviewer: `src/dbt/pearson` staging models carry **no** uniqueness
tests. This model adds one because `src/dbt/CLAUDE.md` requires it for staging
and `student_test_uuid` is verified unique (252 of 252 and 598 of 598). The
asymmetry with `pearson` is deliberate, not an oversight.

- [ ] **Step 3: Attempt a build and expect it to fail on the missing external**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt parse --project-dir src/dbt/cambium
```

Expected: parse succeeds. The model cannot be **built** yet — the external table
does not exist until the Dagster asset materializes once and
`stage_external_sources` runs, which is the data engineer's step in the rollout
sequence. Do not attempt `dbt build` here; a failure would be expected and
uninformative.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/cambium/models/staging/stg_cambium__njgpa.sql \
  src/dbt/cambium/models/staging/properties/stg_cambium__njgpa.yml </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/cambium/models/staging
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): add stg_cambium__njgpa staging model

Refs #4899"
```

sqlfluff will likely flag layout issues on first pass. Fix them by rerunning
with the pre-commit hook (which formats) rather than hand-aligning.

---

### Task 5: Register the package in both district projects

**Files:**

- Modify: `src/dbt/kippnewark/packages.yml`
- Modify: `src/dbt/kippnewark/dbt_project.yml`
- Modify: `src/dbt/kippcamden/packages.yml`
- Modify: `src/dbt/kippcamden/dbt_project.yml`

**Interfaces:**

- Consumes: the `cambium` project from Tasks 3 and 4.
- Produces: `<region>_cambium.stg_cambium__njgpa` relations that Task 6's
  kipptaf sources point at.

- [ ] **Step 1: Add the package to both `packages.yml`**

The `local:` entries are alphabetical. Insert `- local: ../cambium` between
`- local: ../amplify` and `- local: ../deanslist` in
`src/dbt/kippnewark/packages.yml`, and make the identical insertion in
`src/dbt/kippcamden/packages.yml`.

- [ ] **Step 2: Add the model config to both `dbt_project.yml`**

In `src/dbt/kippnewark/dbt_project.yml`, under the top-level `models:` key, add
alphabetically (after the `amplify:` block, before `deanslist:`):

```yaml
cambium:
  +materialized: table
```

This matches the `pearson: +materialized: table` block already present. Same
edit for `src/dbt/kippcamden/dbt_project.yml`.

Before committing, grep for a duplicated top-level key — a line merge can keep
two `models:` or two `cambium:` entries with no conflict marker:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
grep -c '^  cambium:$' src/dbt/kippnewark/dbt_project.yml \
  src/dbt/kippcamden/dbt_project.yml
```

Expected: `1` for each file.

- [ ] **Step 3: Install and verify the model resolves in both districts**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt deps --project-dir src/dbt/kippnewark && \
uv run dbt ls --project-dir src/dbt/kippnewark --select stg_cambium__njgpa && \
uv run dbt deps --project-dir src/dbt/kippcamden && \
uv run dbt ls --project-dir src/dbt/kippcamden --select stg_cambium__njgpa
```

Expected: each `dbt ls` prints `<region>.cambium.staging.stg_cambium__njgpa`
(one node). Zero nodes means the package or the model config did not take.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kippnewark/packages.yml src/dbt/kippnewark/dbt_project.yml \
  src/dbt/kippcamden/packages.yml src/dbt/kippcamden/dbt_project.yml </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/kippnewark/packages.yml src/dbt/kippnewark/dbt_project.yml \
      src/dbt/kippnewark/package-lock.yml \
      src/dbt/kippcamden/packages.yml src/dbt/kippcamden/dbt_project.yml \
      src/dbt/kippcamden/package-lock.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): register cambium package in Newark and Camden

Refs #4899"
```

---

### Task 6: kipptaf sources and the alignment model

The single place where Cambium becomes NJ-state-assessment-shaped. Every
translation decision from the spec lives in this one file.

**Files:**

- Create: `src/dbt/kipptaf/models/cambium/sources-kippnewark.yml`
- Create: `src/dbt/kipptaf/models/cambium/sources-kippcamden.yml`
- Create: `src/dbt/kipptaf/models/cambium/staging/stg_cambium__njgpa.sql`
- Create:
  `src/dbt/kipptaf/models/cambium/staging/properties/stg_cambium__njgpa.yml`
- Modify: `src/dbt/kipptaf/dbt_project.yml`

**Interfaces:**

- Consumes: `stg_cambium__njgpa` in each district project (Task 5), via
  `source("kippnewark_cambium", ...)` and `source("kippcamden_cambium", ...)`.
- Produces: kipptaf relation `stg_cambium__njgpa` exposing exactly these
  columns, which Task 7's `union_relations` `include` list matches by name:
  `_dbt_source_project`, `academic_year`, `administration_period`,
  `americanindianoralaskanative`, `asian`, `assessment_name`, `assessmentgrade`,
  `assessmentyear`, `blackorafricanamerican`, `discipline`, `englishlearnerel`,
  `firstname`, `hispanicorlatinoethnicity`, `is_proficient`, `lastorsurname`,
  `localstudentidentifier`, `module_code`,
  `nativehawaiianorotherpacificislander`, `period`, `statestudentidentifier`,
  `studenttestuuid`, `studentwithdisabilities`, `subject`, `subject_area`,
  `test_date`, `test_grade`, `testcode`, `testperformancelevel`,
  `testperformancelevel_text`, `testscalescore`, `testscorecomplete`,
  `twoormoreraces`, `white`.

- [ ] **Step 1: Write the two regional source files**

Create `src/dbt/kipptaf/models/cambium/sources-kippnewark.yml`, mirroring
`src/dbt/kipptaf/models/pearson/sources-kippnewark.yml`. kipptaf regional
sources hardcode the project name and prefix for `dev` only:

```yaml
sources:
  - name: kippnewark_cambium
    schema:
      "{%- if target.name == 'dev' -%}zz_{{ env_var('GITHUB_USER', 'dev') }}_{%-
      elif target.name == 'staging' -%}zz_stg_{%- endif -%}kippnewark_cambium"
    tables:
      - name: stg_cambium__njgpa
        config:
          meta:
            dagster:
              group: cambium
              asset_key:
                - kippnewark
                - cambium
                - stg_cambium__njgpa
```

Create `sources-kippcamden.yml` identically with `kippcamden` substituted in all
four places.

- [ ] **Step 2: Write the alignment model**

Create `src/dbt/kipptaf/models/cambium/staging/stg_cambium__njgpa.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_cambium", model.name),
                    source("kippcamden_cambium", model.name),
                ]
            )
        }}
    )

select
    /* _dbt_source_relation is in the union's include list and every existing
       relation carries it. It is only READ inside extract_source_project, so it
       is easy to forget to select -- which would null-fill it for all 813 rows
       and break the _dbt_source_relation / _dbt_source_project pairing
       invariant in kipptaf/CLAUDE.md. */
    _dbt_source_relation,
    asian,
    academic_year,
    /* Genuinely NULL from Cambium. NOT synthesized -- the single consumer
       coalesces instead. See design spec D2. */
    test_score_complete as testscorecomplete,
    assessment_grade as assessmentgrade,
    assessment_year as assessmentyear,
    american_indian_or_alaska_native as americanindianoralaskanative,
    black_or_african_american as blackorafricanamerican,
    first_name as firstname,
    hispanic_or_latino_ethnicity as hispanicorlatinoethnicity,
    last_or_surname as lastorsurname,
    local_student_identifier as localstudentidentifier,
    multilingual_learner as englishlearnerel,
    native_hawaiian_or_other_pacific_islander
    as nativehawaiianorotherpacificislander,
    `period`,
    state_student_identifier as statestudentidentifier,
    student_test_uuid as studenttestuuid,
    student_with_disabilities as studentwithdisabilities,
    `subject`,
    test_code as testcode,
    test_code as module_code,
    test_date,
    test_performance_level as testperformancelevel,
    test_scale_score as testscalescore,
    two_or_more_races as twoormoreraces,
    white,

    'NJGPA' as assessment_name,

    /* NJGPA's reported grade is 11 across all Pearson history -- 4,130 rows,
       fall retakers in 12th grade included. Neither Cambium field reproduces
       that: assessment_grade is the test DESIGN level (10 for ELA, 11 for
       Math) and grade_level_when_assessed is the student's grade (11 or 12).
       So the value is asserted, keyed on test_code rather than written as a
       bare literal, so an unrecognized code yields NULL instead of a
       confident 11. Asserting 11 also keeps dim_assessments deterministic:
       its dedup tiebreaker is `title` (the constant 'NJGPA'), which cannot
       choose between two candidate grade levels for the ELAGP row. */
    case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end as test_grade,

    if(`subject` = 'Mathematics', 'Math', 'ELA') as discipline,

    if(
        `subject` = 'English Language Arts/Literacy',
        'English Language Arts',
        `subject`
    ) as subject_area,

    /* Case-insensitive, unlike the Pearson model's exact FallBlock match.
       The fall token has drifted historically (FallBlock in 2024, FALL in
       2025). An exact match would leave 'FALL' as-is, which creates a SEPARATE
       dim_assessment_administrations tuple from the Pearson 'Fall' rows and
       splits the Fall series on the dashboard -- invisibly, because the
       resolver joins the same value on both sides so nothing errors. */
    if(upper(`period`) like 'FALL%', 'Fall', `period`) as administration_period,

    if(test_performance_level = 2, true, false) as is_proficient,

    case
        test_performance_level
        when 2
        then 'Graduation Ready'
        when 1
        then 'Not Yet Graduation Ready'
    end as testperformancelevel_text,

    {{ extract_source_project("union_relations") }} as _dbt_source_project,

from union_relations
```

- [ ] **Step 3: Write the properties file**

Create
`src/dbt/kipptaf/models/cambium/staging/properties/stg_cambium__njgpa.yml`.
Following the `pearson` precedent, this layer is **not** contract-enforced, so
document only the derived columns rather than listing every one:

```yaml
models:
  - name: stg_cambium__njgpa
    description: >-
      Newark and Camden Cambium TIDE NJGPA results, unioned and mapped into the
      shared NJ state assessment column shape so int_pearson__all_assessments
      can union them alongside the Pearson relations. Every Cambium-to-shared
      translation lives here.
    config:
      materialized: table
    columns:
      - name: studenttestuuid
        data_type: string
        data_tests:
          - unique
          - not_null
      - name: test_grade
        data_type: int64
        description: >-
          Constant 11. NJGPA's reported grade is 11 across all Pearson history
          including 12th-grade fall retakers; neither Cambium field reproduces
          that. See the design spec, decision D3.
      - name: testscorecomplete
        data_type: int64
        description: >-
          Constant 1. Cambium sends this field null, while Pearson set it to 1
          on every row surviving the summative and attemptedness filter.
          Required so the (currently redundant) predicate in
          int_students__graduation_path_codes keeps admitting these rows. See
          the design spec, decision D2.
      - name: assessment_name
        data_type: string
        description: Constant 'NJGPA'.
      - name: subject_area
        data_type: string
        description: >-
          Normalized from `subject`. Cambium already sends 'English Language
          Arts', so the Pearson '/Literacy' normalization is a passthrough here.
      - name: module_code
        data_type: string
        description: >-
          Equal to `testcode` (ELAGP, MATGP). The NJSLA Science SC-to-SCI remap
          in the Pearson model does not apply to NJGPA.
      - name: administration_period
        data_type: string
        description: Normalized from `period` ('FallBlock' becomes 'Fall').
      - name: _dbt_source_project
        data_type: string
        description: >-
          Source REGION ('kippnewark' / 'kippcamden'), from
          extract_source_project(). Despite the name it is not the vendor.
```

- [ ] **Step 4: Add the kipptaf model config**

In `src/dbt/kipptaf/dbt_project.yml`, under the top-level `models: kipptaf:`
key, the per-integration blocks are alphabetical. `amplify:` sits between
`alchemer:` and `collegeboard:`, so the correct slot is immediately after the
`amplify:` block:

```yaml
cambium:
  +schema: cambium
```

This mirrors the `pearson:` block (`+schema: pearson`, around line 218) — schema
only, deliberately no `+contract: enforced: true` and no `+materialized`, per
the Global Constraints.

Verify exactly one such key landed:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
grep -c '^    cambium:$' src/dbt/kipptaf/dbt_project.yml
```

Expected: `1`.

- [ ] **Step 5: Verify it parses and the column list is right**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt parse --project-dir src/dbt/kipptaf && \
uv run dbt ls --project-dir src/dbt/kipptaf --select stg_cambium__njgpa
```

Expected: `kipptaf.cambium.staging.stg_cambium__njgpa`.

Then confirm the produced column names match Task 7's expectations exactly.

**This check MUST run `--target staging`, and only after the district
`--target staging` builds in the rollout sequence.** `union_relations` resolves
its column list from the warehouse at compile time, so a dev-target compile
resolves against `zz_<user>_*` schemas that hold nothing, expands to nothing,
and **still compiles clean** (`src/dbt/CLAUDE.md` -> _Validating a NEW union
wrapper locally_). A dev-target grep therefore returns zero lines and reads as a
pass -- the step meant to catch a misspelled alias cannot fire.

Check the **passthrough** columns too, not just the aliased ones: `asian`,
`academic_year`, `` `period` ``, `` `subject` ``, `test_date`, `white`, and
`_dbt_source_relation` are exactly the ones that depend on the union expansion,
and a `\bas [a-z_]+,` grep misses all of them.

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt compile --project-dir src/dbt/kipptaf --select stg_cambium__njgpa && \
grep -oE '\bas [a-z_]+,' \
  src/dbt/kipptaf/target/compiled/kipptaf/models/cambium/staging/stg_cambium__njgpa.sql \
  | sort -u
```

Cross-check every alias against the Interfaces list above. A typo here surfaces
as a silently null column after Task 7, not as an error.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/cambium/ src/dbt/kipptaf/dbt_project.yml </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/kipptaf/models/cambium src/dbt/kipptaf/dbt_project.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): add kipptaf cambium sources and NJGPA alignment model

Refs #4899"
```

---

### Task 7: Union into `int_pearson__all_assessments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`

**Interfaces:**

- Consumes: kipptaf `stg_cambium__njgpa` from Task 6.
- Produces: `int_pearson__all_assessments` carrying Cambium rows. No column
  changes, so all ~15 downstream consumers are untouched.

- [ ] **Step 1: Add the relation**

In the `dbt_utils.union_relations` call, add `ref("stg_cambium__njgpa")` to the
`relations` list after `ref("stg_pearson__njgpa")`:

```jinja
                relations=[
                    ref("stg_pearson__parcc"),
                    ref("stg_pearson__njsla"),
                    ref("stg_pearson__njsla_science"),
                    ref("stg_pearson__njgpa"),
                    ref("stg_cambium__njgpa"),
                ],
```

Leave the `include` list unchanged. Task 6's model produces every name in it
except `is_bl_fb`, which `stg_pearson__njgpa` does not produce either — it
null-fills for both NJGPA relations.

- [ ] **Step 2: Verify the union compiles and picks up the relation**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt compile --project-dir src/dbt/kipptaf \
  --select int_pearson__all_assessments && \
grep -c 'stg_cambium__njgpa' \
  src/dbt/kipptaf/target/compiled/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql
```

Expected: a count of at least 1. Zero means the `ref` did not land in the
compiled union.

Then confirm no column null-fills unexpectedly. `union_relations` emits a
`cast(null as ...)` for any `include` column a relation lacks; anything beyond
`is_bl_fb` means a Task 6 alias is misspelled:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
awk '/stg_cambium__njgpa/,/^$/' \
  src/dbt/kipptaf/target/compiled/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql \
  | grep -oE 'cast\(null as [a-z0-9]+\) as [a-z_]+' | sort -u
```

Expected: only `is_bl_fb`.

As in Task 6, run this with `--target staging` after the district staging
builds. Under the default dev target the union expands to nothing and the grep
returns zero lines, which is indistinguishable from a pass.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): union stg_cambium__njgpa into int_pearson__all_assessments

Refs #4899"
```

---

### Task 8: Assessment dimension wiring

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`

**Interfaces:**

- Consumes: kipptaf `stg_cambium__njgpa` from Task 6.
- Produces: no new columns. `dim_assessment_administrations` gains the Spring
  2026 administration rows the fact's FK requires.

- [ ] **Step 1: Add the administrations CTE**

In `dim_assessment_administrations.sql`, after the existing
`state_nj_njgpa_administrations` CTE, add a parallel CTE. Its shape must match
`union_cols` exactly:
`assessment_type, title, subject_area, scope, module_code, grade_level, administered_date, academic_year, _dbt_source_project, source_assessment_id, administration_period, test_type`.

```sql
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- Cambium TIDE took over NJGPA reporting with the Spring 2026
    -- administration. Required, not cosmetic: the administration key hashes
    -- academic_year and administration_period, and academic year 2025 with
    -- period Spring exists only in Cambium (Pearson's 2025 holds only Fall).
    -- Without this CTE the FK on
    -- fct_assessment_scores_enrollment_scoped.assessment_administration_key
    -- orphans every Cambium score.
    state_nj_njgpa_cambium_administrations as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,
            academic_year,
            administration_period,
            _dbt_source_project,

            'state_nj_njgpa' as assessment_type,
            'NJGPA' as title,

            cast(null as date) as administered_date,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("stg_cambium__njgpa") }}
        where testscalescore is not null
    ),
```

Then add to the union chain, after the `state_nj_njgpa_administrations` block:

```sql
        union all
        select {{ union_cols }},
        from state_nj_njgpa_cambium_administrations
```

- [ ] **Step 2: Add the assessments CTE**

In `dim_assessments.sql`, after the existing `state_nj_njgpa` CTE, add a
parallel CTE matching that file's `union_cols`:
`assessment_type, source_assessment_id, title, subject_area, scope, module_code, module_type, grade_level, is_internal_assessment, assessment_scope, combined_academic_subject, aligned_academic_subject, credit_category, test_type`.

```sql
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- Not strictly required: assessment_key hashes (assessment_type,
    -- module_code, source_assessment_id, test_type), which excludes grade
    -- level and academic year, so these rows dedup into the Pearson NJGPA
    -- rows and hash identically. Included so the dimension does not depend on
    -- Pearson history remaining in place forever.
    state_nj_njgpa_cambium as (
        select distinct
            subject_area,
            discipline as scope,
            module_code,
            test_grade as grade_level,

            'state_nj_njgpa' as assessment_type,
            'NJGPA' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("stg_cambium__njgpa") }}
        where testscalescore is not null
    ),
```

Then add to the union chain after the `state_nj_njgpa` block:

```sql
        union all
        select {{ union_cols }},
        from state_nj_njgpa_cambium
```

The `select distinct` here is the established grain projection in both files,
carrying the existing explanatory comment — it is not a dedup crutch, and every
sibling CTE uses it.

- [ ] **Step 3: Verify both compile**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt compile --project-dir src/dbt/kipptaf \
  --select dim_assessments dim_assessment_administrations && \
for m in dim_assessments dim_assessment_administrations; do
  echo "$m: $(grep -c 'stg_cambium__njgpa' \
    src/dbt/kipptaf/target/compiled/kipptaf/models/marts/dimensions/$m.sql)"
done
```

Expected: a nonzero count for each.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
      src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "feat(dbt): add Cambium NJGPA to the assessment dimensions

Refs #4899"
```

---

### Task 9: Consumer changes — the graduation-pathway predicate and two descriptions

Small but load-bearing. Without the `coalesce`, every Cambium NJGPA score drops
out of graduation-pathway determination silently.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__graduation_path_codes.sql:87`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml:45`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml:161`

**Interfaces:**

- Consumes: `int_pearson__all_assessments` as amended in Task 7.
- Produces: no new columns. Restores NJGPA rows to the graduation-pathway
  calculation for a vendor that reports `test_score_complete` as null.

- [ ] **Step 1: Coalesce the graduation-pathway predicate**

In `int_students__graduation_path_codes.sql`, line 87 currently reads:

```sql
            n.testscorecomplete = 1
```

Replace it with:

```sql
            -- Cambium reports test_score_complete as null where Pearson set it
            -- to 1 on every row surviving the summative + attemptedness filter
            -- (verified 4,130 of 4,130), so this predicate is already a no-op
            -- for Pearson and would silently exclude ALL Cambium NJGPA scores
            -- without the coalesce. Kept rather than deleted so a future vendor
            -- that genuinely reports incompleteness is still filtered.
            coalesce(n.testscorecomplete, 1) = 1
```

- [ ] **Step 2: Correct the two now-inaccurate column descriptions**

In `int_pearson__all_assessments.yml`, line 45 currently reads
`description: Assessment grade level as reported by Pearson.` Replace with:

```yaml
description: >-
  Assessment grade level as reported by the vendor. Pearson sent 'Grade 11' on
  every row. Cambium sends the test DESIGN level instead — 'Grade 10' for ELAGP
  and 'Grade 11' for MATGP — so this column carries two values and is NOT the
  student's grade. Use test_grade (always 11 for NJGPA) or the enrollment for
  reporting grade level.
```

Line 161 currently reads
`description: Score completeness indicator as reported by Pearson.` Replace
with:

```yaml
description: >-
  Score completeness indicator as reported by the vendor. Pearson set it to 1 on
  every row surviving the staging filter. Cambium does not populate it, so it is
  NULL for all Cambium NJGPA rows; consumers must coalesce rather than compare
  directly.
```

- [ ] **Step 3: Verify both models still compile**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run dbt compile --project-dir src/dbt/kipptaf \
  --select int_students__graduation_path_codes int_pearson__all_assessments && \
grep -c 'coalesce(n.testscorecomplete, 1) = 1' \
  src/dbt/kipptaf/target/compiled/kipptaf/models/students/intermediate/int_students__graduation_path_codes.sql
```

Expected: compile succeeds and the grep returns `1`.

- [ ] **Step 4: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__graduation_path_codes.sql \
  src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add src/dbt/kipptaf/models/students/intermediate/int_students__graduation_path_codes.sql \
      src/dbt/kipptaf/models/pearson/intermediate/properties/int_pearson__all_assessments.yml
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "fix(dbt): coalesce testscorecomplete so Cambium NJGPA reaches graduation paths

Refs #4899"
```

---

### Task 10: Repository plumbing and documentation

**Files:**

- Modify: `.github/workflows/deploy-prod-kippnewark.yaml`
- Modify: `.github/workflows/deploy-prod-kippcamden.yaml`
- Modify: `src/dbt/CLAUDE.md`
- Modify: `src/teamster/CLAUDE.md`

**Interfaces:**

- Consumes: everything above.
- Produces: no code interfaces. Ensures a change to the new paths triggers the
  right deploys.

- [ ] **Step 1: Add push-path filters**

In `.github/workflows/deploy-prod-kippnewark.yaml`, under the `push:` `paths:`
list, add two entries in the existing alphabetical order:

- `- src/dbt/cambium/**` immediately before `- src/dbt/deanslist/**`
- `- src/teamster/libraries/cambium/**` immediately before
  `- src/teamster/libraries/couchdrop/**`

Apply the same two additions to `.github/workflows/deploy-prod-kippcamden.yaml`.

Then add **`- src/teamster/libraries/cambium/**`** to the `pull_request:`
`paths:` list in both workflows as well, in the same relative position.

The `pull_request:` list intentionally excludes `src/dbt/*` source projects (dbt
Cloud CI covers those), but it **does** enumerate every library individually —
`src/teamster/libraries/pearson/**` and the rest all appear in both blocks.
Without the cambium entry, a future PR that regenerates only the Pydantic schema
gets no branch deployment, which is precisely the situation the rollout depends
on for staging a new Avro schema. This PR is unaffected either way, because Task
2 touches `src/teamster/code_locations/<region>/**`, which is in the list.

- [ ] **Step 2: Update `src/dbt/CLAUDE.md`**

Two edits:

- In the tier table, add `cambium` to the front of the **Source-system** project
  list and change the count in the opening line from "Sixteen dbt projects" to
  "Seventeen dbt projects".
- In the dependency map code block, add `cambium ──────┤` as the **second** row,
  between `amplify` and `deanslist`. Not the top: the first row carries a corner
  glyph (`amplify ──────┐`), so inserting above it both breaks the drawing and
  misplaces `cambium` alphabetically.

Verify the count claim rather than trusting it:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
ls -d src/dbt/*/ | wc -l
```

Expected: `17`.

- [ ] **Step 3: Update `src/teamster/CLAUDE.md`**

In the **Library Categories** table, add `cambium` to the front of the
alphabetical list in the **SFTP file drop** row, and add `cambium` to the
parenthetical "Schema-only libraries" sentence below the table (it lists
collegeboard, dayforce, fldoe, nsc, pearson, performance_management — `cambium`
belongs there since the asset is built in the code location).

- [ ] **Step 4: Add cambium to the two dbt-project enumerations**

`.vscode/scripts/update-dependencies.sh` holds a `DBT_PROJECTS=(...)` array of
15 projects. Add `cambium` after `amplify` so it is included in
`dbt deps --upgrade`. This file is **not** hook-protected and can be edited
directly.

Add a Script Catalog row to `scripts/CLAUDE.md` for
`scripts/gen-cambium-schema.py`; that table is an exhaustive inventory.

Then present the following to the user for **manual application** —
`.devcontainer/scripts/postCreate.sh` is hook-protected and cannot be edited or
staged by an agent. Without it, a fresh Codespace has no `dbt_packages/` for the
new project and every `dbt parse --project-dir src/dbt/cambium` in this plan
fails after a rebuild. The new line goes immediately before the `deanslist`
line, preserving alphabetical order:

```bash
uv run dbt deps --project-dir=src/dbt/cambium &
```

- [ ] **Step 5: Note the automations doc is deliberately NOT regenerated**

`docs/reference/automations.md` is generated by
`uv run scripts/gen-automations-doc.py`, which imports every code location and
**silently skips** any that fail. In the codespace `kipptaf` and `kippmiami`
fail on unset credentials, so regenerating here would drop them from the
catalog. Leave the file alone and note in the PR body that it needs regenerating
in a full environment. Do not hand-edit it.

- [ ] **Step 6: Lint and commit**

Do NOT `git add` `.devcontainer/scripts/postCreate.sh` — it is hook-protected
and the user applies and stages it themselves.

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .github/workflows/deploy-prod-kippnewark.yaml \
  .github/workflows/deploy-prod-kippcamden.yaml \
  src/dbt/CLAUDE.md src/teamster/CLAUDE.md </dev/null

git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  add .github/workflows/deploy-prod-kippnewark.yaml \
      .github/workflows/deploy-prod-kippcamden.yaml \
      src/dbt/CLAUDE.md src/teamster/CLAUDE.md
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  commit -m "docs: register cambium in deploy paths and project inventories

Refs #4899"
```

---

## Final verification before opening the PR

- [ ] **Full lint over the branch diff**, filtered to existing paths (a
      `--force` check hard-errors on a deleted path):

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
files=$(git -C . diff --name-only origin/main...HEAD | while read -r f; do
  [ -f "$f" ] && printf '%s ' "$f"; done)
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix ${files} </dev/null
```

Note: run this in the background — a `--force` check over ~25 files exceeds two
minutes, and its progress spinner emits no result lines, so grepping partial
output reads as a false clean.

- [ ] **Unit tests**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
uv run pytest tests/libraries/test_cambium_schema.py -v
```

- [ ] **Dagster definitions validate, both regions**

`src/teamster/CLAUDE.md` records that `kippnewark` and `kippcamden` import
cleanly once a dbt manifest exists, so this is the one cheap check that catches
a `Definitions`-level wiring error the submodule imports in Task 2 cannot.

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
for loc in kippnewark kippcamden; do
  uv run dagster definitions validate \
    -m "teamster.code_locations.${loc}.definitions" || echo "FAILED: ${loc}"
done
```

If it fails on a missing manifest, run
`uv run dagster-dbt project prepare-and-package --file src/teamster/code_locations/${loc}/__init__.py`
first.

- [ ] **Both districts and kipptaf parse**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa && \
for p in cambium kippnewark kippcamden kipptaf; do
  uv run dbt parse --project-dir src/dbt/$p || echo "FAILED: $p"
done
```

- [ ] **Merge check against main**

```bash
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  fetch origin main
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cambium-njgpa \
  merge-tree --write-tree --name-only origin/main HEAD | head
```

Expected: no CONFLICT lines.

## What this plan deliberately does NOT do

These require warehouse credentials or a deployed branch, and belong to the data
engineer per the design spec's rollout sequence:

1. `dbt run-operation stage_external_sources` to create the external tables.
1. **`dbt build --select stg_cambium__njgpa --target staging` in BOTH district
   projects**, plus seeding `zz_stg_kipptaf`. Staging the externals is not
   sufficient: the kipptaf source points at a district MODEL, and dbt Cloud CI
   fails deterministically without it (`union_relations` finds no columns).
   `dbt clone` cannot substitute — there is no prod relation for a new model.
1. Materializing the assets in the branch deployment or in prod.
1. Any `dbt build` of `stg_cambium__njgpa` or its descendants — impossible until
   the external table exists.
1. Adding student crosswalk rows for the students with no local identifier.

The PR body must state all four, plus the automations-doc regeneration from Task
10, so nothing silently drops.

## Post-merge verification (data engineer)

The design spec's _Verification plan_ section carries the full list. The
load-bearing checks:

1. Asset record counts: 598 Newark, 252 Camden.
1. `stg_cambium__njgpa` after the attemptedness filter: 564 Newark, 249 Camden.
1. `int_pearson__all_assessments` gains exactly 813 rows for academic year 2025
   period Spring.
1. `dim_assessments` — assert `grade_level_tested = 11` on both
   `type = 'state_nj_njgpa'` rows. **Not** a row-count check: `grade_level` is
   absent from the dedup partition
   (`assessment_type, source_assessment_id, module_code, test_type`), so the
   count stays at 2 whether or not D3 applied, and a row-count check cannot
   detect the failure it was meant to catch.
1. **`test_date` non-null per `test_code`**, never in aggregate — an aggregate
   check passes at 50 percent null, which is the exact failure mode being
   guarded. Then confirm `fct_assessment_scores_enrollment_scoped` carries both
   ELAGP and MATGP for Spring 2026 in comparable numbers; the fact is the only
   place that failure surfaces.
1. Zero orphans on
   `fct_assessment_scores_enrollment_scoped.assessment_administration_key`.
1. `int_students__graduation_path_codes` returns NJGPA rows for Cambium
   students.
