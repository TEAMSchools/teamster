# Focus SIS Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Focus SIS (PostgreSQL) into the teamster data platform for
KIPP Miami — extraction via dlt, transformation via dbt, orchestration via
Dagster.

**Architecture:** dlt `sql_database` source extracts ~75 tables from Focus
Postgres to BigQuery (daily full-replace). A new `focus` dbt source-system
project provides contract-enforced staging models consumed by `kippmiami` as a
local package and exposed to `kipptaf` via regional sources.

**Spec deviation:** The spec calls for `sql_table` (standalone resource), but
`dlt_assets` requires a `DltSource`, not `DltResource`. Using `sql_database`
with `table_names=[table_name]` + `reflection_level="full_with_precision"`
achieves the same extraction behavior while staying compatible with the
dagster-dlt API.

**Tech Stack:** Python 3.13, dlt 1.24.0 (`sql_database` + PyArrow backend),
dagster-dlt, dbt (BigQuery), 1Password Kubernetes operator

---

## Phasing

This plan has two phases with a hard dependency boundary:

- **Phase A (Tasks 1–9):** Extraction pipeline + dbt scaffolding. Can be
  implemented immediately.
- **Phase B (Tasks 10–13):** Staging models, intermediate models, and kipptaf
  integration. Blocked on a successful branch deployment and first dlt
  extraction run — column schemas must be introspected from BigQuery after data
  lands.

Phase B will be planned in a follow-up document after Phase A deploys and data
is available for introspection.

---

## File Map

| File                                                                | Action | Responsibility                          |
| ------------------------------------------------------------------- | ------ | --------------------------------------- |
| `.k8s/1password/items.yaml`                                         | Modify | Add Focus DB OnePasswordItem            |
| `src/teamster/code_locations/kippmiami/dagster-cloud.yaml`          | Modify | Add Focus DB env vars (both env blocks) |
| `src/teamster/libraries/dlt/focus/__init__.py`                      | Create | Package init                            |
| `src/teamster/libraries/dlt/focus/assets.py`                        | Create | Factory function + translator           |
| `src/teamster/libraries/dlt/CLAUDE.md`                              | Create | Document Focus sub-library              |
| `src/teamster/code_locations/kippmiami/dlt/__init__.py`             | Create | Wire dlt module assets/schedules        |
| `src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`       | Create | Package init                            |
| `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`         | Create | Credential setup + asset factory calls  |
| `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`      | Create | Daily schedule from YAML config         |
| `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml` | Create | Table list                              |
| `src/teamster/code_locations/kippmiami/definitions.py`              | Modify | Add dlt module + DLT_RESOURCE           |
| `src/teamster/code_locations/kippmiami/CLAUDE.md`                   | Modify | Document Focus integration              |
| `src/dbt/focus/dbt_project.yml`                                     | Create | Project config                          |
| `src/dbt/focus/profiles.yml`                                        | Create | Dagster-only profile                    |
| `src/dbt/focus/packages.yml`                                        | Create | dbt_utils dependency                    |
| `src/dbt/focus/CLAUDE.md`                                           | Create | Document Focus dbt project              |
| `src/dbt/focus/models/staging/sources-bigquery.yml`                 | Create | BQ source definitions for all tables    |
| `src/dbt/kippmiami/packages.yml`                                    | Modify | Add focus local package                 |
| `src/dbt/kippmiami/CLAUDE.md`                                       | Modify | Document Focus as active package        |

---

## Phase A: Extraction Pipeline + dbt Scaffolding

### Task 1: Add 1Password item and dagster-cloud.yaml env vars

**Files:**

- Modify: `.k8s/1password/items.yaml:361`
- Modify: `src/teamster/code_locations/kippmiami/dagster-cloud.yaml:142,240`

- [ ] **Step 1: Add OnePasswordItem for Focus DB**

Append to `.k8s/1password/items.yaml` after line 361:

```yaml
---
apiVersion: onepassword.com/v1
kind: OnePasswordItem
metadata:
  name: op-focus-db-kippmiami
  namespace: dagster-cloud
spec:
  itemPath: vaults/Data Team/items/Focus DB - Miami
```

- [ ] **Step 2: Add Focus DB env vars to server_k8s_config**

In `dagster-cloud.yaml`, insert after line 142 (after the `DEANSLIST_SUBDOMAIN`
entry, inside `server_k8s_config.container_config.env`):

```yaml
- name: FOCUS_DB_DRIVERNAME
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: drivername
- name: FOCUS_DB_HOST
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: host
- name: FOCUS_DB_DATABASE
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: database
- name: FOCUS_DB_USERNAME
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: username
- name: FOCUS_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: password
- name: FOCUS_DB_PORT
  valueFrom:
    secretKeyRef:
      name: op-focus-db-kippmiami
      key: port
```

- [ ] **Step 3: Add identical env vars to run_k8s_config**

Add the same 6 env var entries to the `run_k8s_config.container_config.env`
block (after the `DEANSLIST_SUBDOMAIN` entry at line 240).

- [ ] **Step 4: Commit**

```bash
git add .k8s/1password/items.yaml src/teamster/code_locations/kippmiami/dagster-cloud.yaml
git commit -m "feat(k8s): add Focus DB 1Password item and kippmiami env vars"
```

---

### Task 2: Create dlt Focus library

**Files:**

- Create: `src/teamster/libraries/dlt/focus/__init__.py`
- Create: `src/teamster/libraries/dlt/focus/assets.py`

- [ ] **Step 1: Create package init**

Create `src/teamster/libraries/dlt/focus/__init__.py` (empty file).

- [ ] **Step 2: Create the factory function and translator**

Create `src/teamster/libraries/dlt/focus/assets.py`:

```python
from collections.abc import Iterator

from dagster import AssetExecutionContext, AssetKey, AssetSpec
from dagster_dlt import DagsterDltResource, DagsterDltTranslator, dlt_assets
from dlt import pipeline
from dlt.common.configuration.specs import ConnectionStringCredentials
from dlt.common.runtime.collector import LogCollector
from dlt.destinations import bigquery
from dlt.sources.sql_database import sql_database


class FocusDagsterDltTranslator(DagsterDltTranslator):
    def __init__(self, code_location: str):
        self.code_location = code_location
        return super().__init__()

    def get_asset_spec(self, data) -> AssetSpec:
        asset_spec = super().get_asset_spec(data)

        asset_spec = asset_spec.replace_attributes(
            key=AssetKey(
                [
                    self.code_location,
                    "dlt",
                    "focus",
                    data.resource.explicit_args["table_names"][0],
                ]
            ),
            deps=[],
        )

        asset_spec = asset_spec.merge_attributes(kinds={"postgresql"})

        return asset_spec


def build_focus_dlt_assets(
    sql_database_credentials: ConnectionStringCredentials,
    code_location: str,
    table_name: str,
    op_tags: dict[str, object] | None = None,
):
    if op_tags is None:
        op_tags = {}

    dlt_source = sql_database.with_args(name="focus", parallelized=True)(
        credentials=sql_database_credentials,
        schema="public",
        table_names=[table_name],
        defer_table_reflect=True,
        backend="pyarrow",
        reflection_level="full_with_precision",
    )

    dlt_pipeline = pipeline(
        pipeline_name="focus",
        destination=bigquery(autodetect_schema=True),
        dataset_name=f"dagster_{code_location}_dlt_focus",
        progress=LogCollector(dump_system_stats=False),
    )

    @dlt_assets(
        dlt_source=dlt_source,
        dlt_pipeline=dlt_pipeline,
        name=f"{code_location}__dlt__focus__{table_name}",
        dagster_dlt_translator=FocusDagsterDltTranslator(code_location),
        group_name="focus",
        pool=f"dlt_focus_{code_location}",
        op_tags=op_tags,
    )
    def _assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> Iterator:
        yield from dlt.run(context=context, write_disposition="replace")

    return _assets
```

- [ ] **Step 3: Verify import**

Run:
`uv run python -c "from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/teamster/libraries/dlt/focus/
git commit -m "feat(dlt): add Focus SIS library with sql_database factory"
```

---

### Task 3: Create dlt Focus code location (config, assets, schedule)

**Files:**

- Create: `src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`
- Create: `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`
- Create: `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`
- Create: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`

- [ ] **Step 1: Create config YAML**

Create `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`:

```yaml
assets:
  # Students
  - table_name: students
  - table_name: students_join_users
  - table_name: students_join_people
  - table_name: students_join_address
  - table_name: students_join_groups
  - table_name: students_join_students
  - table_name: people
  - table_name: people_join_contacts
  - table_name: address
  - table_name: student_groups
  # Enrollment
  - table_name: student_enrollment
  - table_name: student_enrollment_codes
  - table_name: school_gradelevels
  - table_name: schools
  - table_name: districts
  - table_name: scheduling_teams
  - table_name: attendance_calendars
  - table_name: grad_subject_programs
  # Attendance Day
  - table_name: attendance_day
  - table_name: attendance_notes
  - table_name: attendance_codes
  - table_name: marking_periods
  # Attendance Period
  - table_name: attendance_period
  - table_name: attendance_completed
  - table_name: school_periods
  # Courses/Schedule
  - table_name: courses
  - table_name: course_periods
  - table_name: schedule
  - table_name: course_subjects
  - table_name: course_weights
  - table_name: master_courses
  - table_name: course_code_directory
  - table_name: co_teachers
  - table_name: co_teacher_days
  - table_name: resources
  # Grades
  - table_name: student_report_card_grades
  - table_name: report_card_grades
  - table_name: report_card_grade_scales
  - table_name: report_card_comments
  - table_name: grad_subjects
  - table_name: grad_subject_credits
  - table_name: student_standard_grades
  - table_name: standards
  - table_name: standard_categories_1
  - table_name: standard_categories_2
  - table_name: standard_categories_3
  - table_name: standard_categories_4
  - table_name: standards_join_courses
  - table_name: gradebook_grades
  - table_name: gradebook_assignments
  - table_name: gradebook_assignment_types
  - table_name: gradebook_templates
  # Discipline
  - table_name: discipline_referrals
  - table_name: discipline_incidents
  - table_name: discipline_incidents_join_referrals
  - table_name: referral_codes
  - table_name: referral_actions
  - table_name: referral_code_offenses
  # Users
  - table_name: users
  - table_name: user_enrollment
  - table_name: user_profiles
  - table_name: permission
  - table_name: login_history
  # Custom Fields
  - table_name: custom_fields
  - table_name: custom_field_categories
  - table_name: custom_field_select_options
  - table_name: custom_field_log_columns
  - table_name: custom_field_log_entries
  - table_name: custom_fields_join_categories
  # Test History
  - table_name: test_history_tests
  - table_name: test_history_test_types
  - table_name: test_history_administrations
  - table_name: test_history_scores
  - table_name: test_history_parts
  - table_name: test_history_score_types
  - table_name: test_history_score_ranges
```

- [ ] **Step 2: Create assets.py**

Create `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`:

```python
import pathlib

import yaml
from dagster import EnvVar
from dagster_shared import check
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = ConnectionStringCredentials(
    {
        "drivername": check.not_none(
            value=EnvVar("FOCUS_DB_DRIVERNAME").get_value()
        ),
        "database": EnvVar("FOCUS_DB_DATABASE").get_value(),
        "password": EnvVar("FOCUS_DB_PASSWORD").get_value(),
        "username": EnvVar("FOCUS_DB_USERNAME").get_value(),
        "host": EnvVar("FOCUS_DB_HOST").get_value(),
        "port": EnvVar("FOCUS_DB_PORT").get_value(),
    }
)

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        **a,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
```

- [ ] **Step 3: Create schedules.py**

Create `src/teamster/code_locations/kippmiami/dlt/focus/schedules.py`:

```python
import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"
config = yaml.safe_load(config_file.read_text())

asset_key_prefix = f"{CODE_LOCATION}/dlt/focus"

focus_dlt_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[
        f"{asset_key_prefix}/{a['table_name']}" for a in config["assets"]
    ],
)

schedules = [focus_dlt_daily_asset_job_schedule]
```

- [ ] **Step 4: Create focus **init**.py**

Create `src/teamster/code_locations/kippmiami/dlt/focus/__init__.py`:

```python
from teamster.code_locations.kippmiami.dlt.focus.assets import assets
from teamster.code_locations.kippmiami.dlt.focus.schedules import schedules

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 5: Commit**

```bash
git add src/teamster/code_locations/kippmiami/dlt/focus/
git commit -m "feat(kippmiami): add Focus dlt code location with config and schedule"
```

---

### Task 4: Create kippmiami dlt **init**.py and wire definitions.py

**Files:**

- Create: `src/teamster/code_locations/kippmiami/dlt/__init__.py`
- Modify: `src/teamster/code_locations/kippmiami/definitions.py:1-82`

- [ ] **Step 1: Create dlt **init**.py**

Create `src/teamster/code_locations/kippmiami/dlt/__init__.py`:

```python
from teamster.code_locations.kippmiami.dlt import focus

assets = [
    *focus.assets,
]

schedules = [
    *focus.schedules,
]

__all__ = [
    "assets",
    "schedules",
]
```

- [ ] **Step 2: Add dlt import to definitions.py**

In `src/teamster/code_locations/kippmiami/definitions.py`, add `dlt` to the code
location imports (line 9-21). Add after `couchdrop,`:

```python
    dlt,
```

- [ ] **Step 3: Add DLT_RESOURCE import**

Add `DLT_RESOURCE` to the core resources import (line 22-36):

```python
from teamster.core.resources import (
    BIGQUERY_RESOURCE,
    DB_POWERSCHOOL,
    DEANSLIST_RESOURCE,
    DLT_RESOURCE,
    GCS_RESOURCE,
    ...
```

- [ ] **Step 4: Add dlt to assets module list**

In the `load_assets_from_modules` call (line 40-51), add `dlt` to the modules
list:

```python
    assets=load_assets_from_modules(
        modules=[
            dbt,
            dlt,
            extracts,
            ...
```

- [ ] **Step 5: Add dlt schedules**

In the schedules list (line 52-56), add:

```python
        *dlt.schedules,
```

- [ ] **Step 6: Add DLT_RESOURCE to resources dict**

In the resources dict (line 67-81), add:

```python
        "dlt": DLT_RESOURCE,
```

- [ ] **Step 7: Verify definitions load**

Run:
`uv run python -c "from teamster.code_locations.kippmiami.definitions import defs; print(f'Assets: {len(list(defs.get_all_asset_specs()))}')"`

Expected: prints asset count without errors. The FOCUS_DB env vars will be
`None` locally (no 1Password access) but definitions should still load —
`EnvVar.get_value()` returns `None` when unset.

Note: if this fails because `EnvVar` raises on missing values, the error will
indicate which var. This is expected locally — it will work in deployed
environments where secrets are injected.

- [ ] **Step 8: Commit**

```bash
git add src/teamster/code_locations/kippmiami/dlt/__init__.py src/teamster/code_locations/kippmiami/definitions.py
git commit -m "feat(kippmiami): wire Focus dlt module into Dagster definitions"
```

---

### Task 5: Create dbt Focus project scaffolding

**Files:**

- Create: `src/dbt/focus/dbt_project.yml`
- Create: `src/dbt/focus/profiles.yml`
- Create: `src/dbt/focus/packages.yml`

- [ ] **Step 1: Create dbt_project.yml**

Create `src/dbt/focus/dbt_project.yml`:

```yaml
name: focus
version: 1.0.0
config-version: 2
require-dbt-version: [">=1.3.0", <2.0.0]

profile: focus

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
  current_academic_year: 0
  current_fiscal_year: 0
  local_timezone: UTC

models:
  +schema: focus
  focus:
    staging:
      +contract:
        enforced: true
```

- [ ] **Step 2: Create profiles.yml**

Create `src/dbt/focus/profiles.yml`:

```yaml
# Dagster-only profile (defer + prod). Developers use .dbt/profiles.yml for
# full target support (defer/dev/staging/prod).
focus:
  target: prod
  outputs:
    defer:
      type: bigquery
      schema: zz_dagster_focus
      method: oauth
      project: teamster-332318
      threads: 40
    prod:
      type: bigquery
      schema: focus
      method: oauth
      project: teamster-332318
      threads: 40
```

- [ ] **Step 3: Create packages.yml**

Create `src/dbt/focus/packages.yml`:

```yaml
# trunk-ignore-all(yamllint/quoted-strings)
packages:
  # https://github.com/dbt-labs/dbt-utils
  - package: dbt-labs/dbt_utils
    version: [">=1.3.2", "<2.0.0"]
```

- [ ] **Step 4: Commit**

```bash
git add src/dbt/focus/
git commit -m "feat(dbt): scaffold Focus source-system project"
```

---

### Task 6: Create dbt source definitions

**Files:**

- Create: `src/dbt/focus/models/staging/sources-bigquery.yml`

- [ ] **Step 1: Create sources-bigquery.yml**

Create `src/dbt/focus/models/staging/sources-bigquery.yml`:

```yaml
sources:
  - name: focus
    schema:
      "{{ var('focus_schema', 'dagster_' ~ project_name ~ '_dlt_focus') }}"
    tables:
      # Students
      - name: students
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students
      - name: students_join_users
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students_join_users
      - name: students_join_people
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students_join_people
      - name: students_join_address
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students_join_address
      - name: students_join_groups
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students_join_groups
      - name: students_join_students
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - students_join_students
      - name: people
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - people
      - name: people_join_contacts
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - people_join_contacts
      - name: address
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - address
      - name: student_groups
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - student_groups
      # Enrollment
      - name: student_enrollment
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - student_enrollment
      - name: student_enrollment_codes
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - student_enrollment_codes
      - name: school_gradelevels
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - school_gradelevels
      - name: schools
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - schools
      - name: districts
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - districts
      - name: scheduling_teams
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - scheduling_teams
      - name: attendance_calendars
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_calendars
      - name: grad_subject_programs
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - grad_subject_programs
      # Attendance Day
      - name: attendance_day
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_day
      - name: attendance_notes
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_notes
      - name: attendance_codes
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_codes
      - name: marking_periods
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - marking_periods
      # Attendance Period
      - name: attendance_period
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_period
      - name: attendance_completed
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - attendance_completed
      - name: school_periods
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - school_periods
      # Courses/Schedule
      - name: courses
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - courses
      - name: course_periods
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - course_periods
      - name: schedule
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - schedule
      - name: course_subjects
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - course_subjects
      - name: course_weights
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - course_weights
      - name: master_courses
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - master_courses
      - name: course_code_directory
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - course_code_directory
      - name: co_teachers
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - co_teachers
      - name: co_teacher_days
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - co_teacher_days
      - name: resources
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - resources
      # Grades
      - name: student_report_card_grades
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - student_report_card_grades
      - name: report_card_grades
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - report_card_grades
      - name: report_card_grade_scales
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - report_card_grade_scales
      - name: report_card_comments
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - report_card_comments
      - name: grad_subjects
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - grad_subjects
      - name: grad_subject_credits
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - grad_subject_credits
      - name: student_standard_grades
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - student_standard_grades
      - name: standards
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standards
      - name: standard_categories_1
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standard_categories_1
      - name: standard_categories_2
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standard_categories_2
      - name: standard_categories_3
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standard_categories_3
      - name: standard_categories_4
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standard_categories_4
      - name: standards_join_courses
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - standards_join_courses
      - name: gradebook_grades
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - gradebook_grades
      - name: gradebook_assignments
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - gradebook_assignments
      - name: gradebook_assignment_types
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - gradebook_assignment_types
      - name: gradebook_templates
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - gradebook_templates
      # Discipline
      - name: discipline_referrals
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - discipline_referrals
      - name: discipline_incidents
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - discipline_incidents
      - name: discipline_incidents_join_referrals
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - discipline_incidents_join_referrals
      - name: referral_codes
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - referral_codes
      - name: referral_actions
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - referral_actions
      - name: referral_code_offenses
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - referral_code_offenses
      # Users
      - name: users
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - users
      - name: user_enrollment
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - user_enrollment
      - name: user_profiles
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - user_profiles
      - name: permission
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - permission
      - name: login_history
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - login_history
      # Custom Fields
      - name: custom_fields
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_fields
      - name: custom_field_categories
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_field_categories
      - name: custom_field_select_options
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_field_select_options
      - name: custom_field_log_columns
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_field_log_columns
      - name: custom_field_log_entries
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_field_log_entries
      - name: custom_fields_join_categories
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - custom_fields_join_categories
      # Test History
      - name: test_history_tests
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_tests
      - name: test_history_test_types
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_test_types
      - name: test_history_administrations
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_administrations
      - name: test_history_scores
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_scores
      - name: test_history_parts
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_parts
      - name: test_history_score_types
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_score_types
      - name: test_history_score_ranges
        config:
          meta:
            dagster:
              asset_key:
                - "{{ project_name }}"
                - dlt
                - focus
                - test_history_score_ranges
```

- [ ] **Step 2: Verify dbt parse**

Run: `uv run dbt parse --project-dir src/dbt/focus --profiles-dir src/dbt/focus`

Expected: parse succeeds with no errors. Sources are recognized.

- [ ] **Step 3: Commit**

```bash
git add src/dbt/focus/models/
git commit -m "feat(dbt): add Focus source definitions for all Phase 1 tables"
```

---

### Task 7: Update kippmiami dbt project to consume Focus

**Files:**

- Modify: `src/dbt/kippmiami/packages.yml:5`
- Modify: `src/dbt/kippmiami/dbt_project.yml:30`

- [ ] **Step 1: Add focus to kippmiami packages.yml**

In `src/dbt/kippmiami/packages.yml`, add after the existing local packages
(after `- local: ../powerschool`):

```yaml
- local: ../focus
```

- [ ] **Step 2: Add focus_schema var to kippmiami dbt_project.yml**

In `src/dbt/kippmiami/dbt_project.yml`, add to the `vars:` block (after line
30):

```yaml
focus_schema: dagster_kippmiami_dlt_focus
```

- [ ] **Step 3: Add focus model config to kippmiami dbt_project.yml**

In `src/dbt/kippmiami/dbt_project.yml`, add to the `models:` block (before the
package overrides section starting at line 51 `deanslist:`):

```yaml
focus:
  +materialized: table
  staging:
    +contract:
      enforced: true
```

- [ ] **Step 4: Verify kippmiami dbt parse**

Run:
`uv run dbt parse --project-dir src/dbt/kippmiami --profiles-dir src/dbt/kippmiami`

Expected: parse succeeds. Focus sources appear in the manifest.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kippmiami/packages.yml src/dbt/kippmiami/dbt_project.yml
git commit -m "feat(dbt): add focus package to kippmiami"
```

---

### Task 8: Create CLAUDE.md files

**Files:**

- Create: `src/teamster/libraries/dlt/focus/CLAUDE.md`
- Create: `src/dbt/focus/CLAUDE.md`
- Modify: `src/teamster/libraries/dlt/CLAUDE.md`
- Modify: `src/teamster/code_locations/kippmiami/CLAUDE.md`
- Modify: `src/dbt/kippmiami/CLAUDE.md`

- [ ] **Step 1: Create Focus dlt library CLAUDE.md**

Create `src/teamster/libraries/dlt/focus/CLAUDE.md`:

```markdown
# CLAUDE.md — `teamster/libraries/dlt/focus/`

Loads tables from the **Focus SIS** PostgreSQL database directly to BigQuery
using dlt's `sql_database` source with PyArrow backend.

## Factory

`build_focus_dlt_assets(sql_database_credentials, code_location, table_name)`

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Uses `reflection_level="full_with_precision"` — no custom type adapters
- No custom callbacks — add only if Postgres-specific issues surface
- All tables from the `public` schema (Focus default)

## Differences from Illuminate

| Aspect              | Illuminate                              | Focus                      |
| ------------------- | --------------------------------------- | -------------------------- |
| Schema dimension    | Multi-schema (asset key includes it)    | Single `public` schema     |
| Type adapters       | `unbounded_numeric_adapter`             | None (full_with_precision) |
| Query callbacks     | `filter_date_taken_callback` (optional) | None                       |
| Nullability adapter | `remove_nullability_adapter`            | None (full_with_precision) |

## Testing Constraints

Focus uses an IP allowlist. Codespace cannot reach the database. Connection
verification requires a branch deployment (GKE has static egress IP).
```

- [ ] **Step 2: Create Focus dbt project CLAUDE.md**

Create `src/dbt/focus/CLAUDE.md`:

````markdown
# CLAUDE.md — `dbt/focus/`

Source-system staging project for **Focus SIS** data (PostgreSQL). Produces
clean, contract-enforced staging models consumed by district-specific dbt
projects (currently `kippmiami`).

## Data Flow

Focus Postgres → dlt `sql_database` → BigQuery (`dagster_<project>_dlt_focus`) →
dbt staging models → dbt intermediate models

## Model Structure

```text
models/
  staging/
    sources-bigquery.yml   # BQ-native sources (dlt-loaded, not external tables)
    stg_focus__*.sql       # one per source table
    properties/
      stg_focus__*.yml     # column contracts + tests
  intermediate/
    int_focus__*.sql       # domain-specific joins
    properties/
      int_focus__*.yml
```
````

All staging models have `contract: enforced: true`. Data comes from dlt (not
external tables), so sources use `sources-bigquery.yml` with a plain schema var.

## Key Variables

| Variable                | Default                            | Notes                           |
| ----------------------- | ---------------------------------- | ------------------------------- |
| `focus_schema`          | `dagster_<project_name>_dlt_focus` | BQ dataset with dlt-loaded data |
| `current_academic_year` | `0`                                | Overridden per district         |
| `current_fiscal_year`   | `0`                                | Overridden per district         |
| `local_timezone`        | `UTC`                              | Overridden per district         |

## Cross-Project Usage

This project is never run standalone in production. District projects reference
it as a dbt package and override variables. `{{ project_name }}` in source
definitions resolves to the consuming district project name, enabling correct
Dagster asset key lineage.

````

- [ ] **Step 3: Update dlt library CLAUDE.md**

The file `src/teamster/libraries/dlt/CLAUDE.md` does not currently exist (it was
deleted or never created at this path). Create it with the Focus sub-library
documented. Read the existing content first — if it exists, append the Focus
section under `## Sub-libraries`.

Add a `### focus/` section following the existing `### illuminate/` pattern:

```markdown
### focus/

Loads tables from the **Focus SIS** (student information system) PostgreSQL
database directly to BigQuery using `dlt`'s `sql_database` source with PyArrow
backend.

- Asset keys: `[code_location, "dlt", "focus", table_name]`
- Uses `reflection_level="full_with_precision"` — no custom type or nullability
  adapters
- Factory: `build_focus_dlt_assets(sql_database_credentials, code_location, table_name)`
````

- [ ] **Step 4: Update kippmiami code location CLAUDE.md**

In `src/teamster/code_locations/kippmiami/CLAUDE.md`, add a row to the Active
Integrations table:

```markdown
| `dlt/focus` | dlt assets | schedule (daily midnight ET) |
```

- [ ] **Step 5: Update kippmiami dbt CLAUDE.md**

In `src/dbt/kippmiami/CLAUDE.md`, add to the Active Source Packages list:

```markdown
- `focus` — `focus_schema` points to `dagster_kippmiami_dlt_focus`
```

And update the Model Structure to include:

```text
  focus/         # Focus SIS staging (refs focus package, dlt-loaded)
    staging/
```

- [ ] **Step 6: Commit**

```bash
git add src/teamster/libraries/dlt/focus/CLAUDE.md src/dbt/focus/CLAUDE.md src/teamster/libraries/dlt/CLAUDE.md src/teamster/code_locations/kippmiami/CLAUDE.md src/dbt/kippmiami/CLAUDE.md
git commit -m "docs: add CLAUDE.md files for Focus SIS integration"
```

---

### Task 9: Final Phase A verification

- [ ] **Step 1: Verify Dagster definitions load**

Run:
`uv run python -c "from teamster.code_locations.kippmiami.definitions import defs; print('OK:', len(list(defs.get_all_asset_specs())), 'assets')"`

Expected: loads without error, asset count includes ~75 new Focus dlt assets.

- [ ] **Step 2: Verify dbt parse**

Run:
`uv run dbt parse --project-dir src/dbt/kippmiami --profiles-dir src/dbt/kippmiami`

Expected: parse succeeds. Focus sources appear in the manifest.

- [ ] **Step 3: Verify no lint errors**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --no-fix src/teamster/libraries/dlt/focus/ src/teamster/code_locations/kippmiami/dlt/ src/dbt/focus/`

Expected: no errors.

---

## Phase B: Staging Models, Intermediate Models, and kipptaf Integration

> **Blocked on:** successful branch deployment + first dlt extraction run.
> Column schemas must be introspected from BigQuery after data lands. This phase
> will be planned in a follow-up document.

### Prerequisites

1. Push Phase A branch, open PR for branch deployment
2. Ensure 1Password item "Focus DB - Miami" exists with correct credentials
3. Ensure Cloud NAT rule and Focus IP allowlist are configured
4. Trigger Focus dlt schedule in Dagster UI (or materialize manually)
5. Verify data lands in `dagster_kippmiami_dlt_focus` dataset

### Task 10: Schema introspection

After data lands, introspect BigQuery to discover column schemas:

```sql
SELECT table_name, column_name, data_type, is_nullable
FROM `teamster-332318`.dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS
ORDER BY table_name, ordinal_position
```

Use this to generate staging models and properties files.

### Task 11: Staging models

For each table, create:

- `src/dbt/focus/models/staging/stg_focus__<table>.sql` — SELECT from source
  with column renames (boolean `is_` prefixes, reserved word quoting),
  soft-delete filters where applicable
- `src/dbt/focus/models/staging/properties/stg_focus__<table>.yml` — column
  contracts (`data_type` on every column), uniqueness test on PK, descriptions

Pattern (example for `students`):

```sql
select
    student_id,
    school_id,
    district_id,
    first_name,
    last_name,
    -- ... columns from BQ introspection
from {{ source("focus", "students") }}
```

### Task 12: Intermediate models

Domain-specific joins per the spec:

- `int_focus__student_enrollment` — enrollment + schools + grade levels + codes
- `int_focus__attendance_day` — attendance_day + codes + marking_periods
- `int_focus__attendance_period` — attendance_period + course_periods +
  school_periods
- `int_focus__schedule` — schedule + course_periods + courses + marking_periods
- `int_focus__gradebook_grades` — gradebook_grades + assignments +
  assignment_types
- `int_focus__report_card_grades` — student_report_card_grades +
  report_card_grades + scales

### Task 13: kipptaf integration

- `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` — regional source
  pointing to kippmiami's Focus dataset
- `src/dbt/kipptaf/models/focus/staging/stg_kippmiami__focus__*.sql` — wrapper
  models for mart consumption
