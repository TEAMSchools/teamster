# ADP WFN Worker Attribute Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture the complete retrievable ADP WFN worker representation in the
`Worker` pydantic model, expand the curated `$select` and dbt staging/int layers
to surface every grain-aligned attribute, while keeping `governmentIDs` and
`identityDocuments` off the wire and out of the warehouse.

**Architecture:** The pydantic model becomes the full representation (the Avro
gate); curation happens at two points — the asset `$select` (PII off the wire)
and the staging contract (PII out of the warehouse). Staging flattens new
worker-grain scalars; `int_l__work_assignments` flattens new
work-assignment-grain fields; repeated sub-records stay nested. One-time
whole-struct surrogate-key recomposition → deliberate SCD2 re-key.

**Tech Stack:** Python 3.13 + pydantic + `py_avro_schema` (Dagster asset),
BigQuery Avro external tables, dbt (contract-enforced staging + intermediate).

**Spec:**
[2026-06-05-adp-wfn-worker-attributes-design.md](../specs/2026-06-05-adp-wfn-worker-attributes-design.md)

**Human-in-the-loop checkpoints** (Claude cannot run these — they need ADP
credentials / Dagster / dbt Cloud secrets): the enumeration pull (Task 1), the
live `test_workers` materialization (Task 3), the branch-deployment
materialization + `stage_external_sources` (Task 5), and dbt Cloud CI (Task 8).
Each is marked **USER RUNS**.

---

## File Structure

- `.claude/scratch/enumerate_adp_workers.py` — **throwaway**, gitignored;
  discovery only (Task 1). Never committed.
- `src/teamster/libraries/adp/workforce_now/api/schema.py` — pydantic model +
  `WORKER_SCHEMA` source (Task 2).
- `tests/libraries/test_adp_wfn_schema.py` — **new** local unit test for the
  model + generated Avro schema (Task 2). No secrets required.
- `src/teamster/code_locations/kipptaf/adp/workforce_now/api/assets.py` —
  `$select` (Task 3).
- `src/dbt/kipptaf/models/adp/workforce_now/api/staging/stg_adp_workforce_now__workers.sql`
  and `.../staging/properties/stg_adp_workforce_now__workers.yml` (Task 6).
- `src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/int_adp_workforce_now__workers__work_assignments.sql`
  and its `properties/int_adp_workforce_now__workers__work_assignments.yml`
  (Task 7).
- `src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/unit_tests/` (or
  the project's unit-test location) — **new** dbt unit test for int flattening
  (Task 7).

---

## Task 1: Enumeration pull (discovery) — USER RUNS

**Files:**

- Create: `.claude/scratch/enumerate_adp_workers.py` (throwaway, gitignored)

- [ ] **Step 1: Write the enumeration script to scratch**

Write a script that pulls the full worker population with `$select` **dropped**,
unions every field path across all records, and prints the sorted set. Keep all
output local (PII).

```python
# .claude/scratch/enumerate_adp_workers.py
import json
from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE


def _paths(obj, prefix=""):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}/{k}" if prefix else k
            out.add(p)
            out |= _paths(v, p)
    elif isinstance(obj, list):
        for item in obj:
            out |= _paths(item, prefix)
    return out


def main():
    # NOTE: pass masked=false header per resource config to see real shapes.
    records = ADP_WORKFORCE_NOW_RESOURCE.get_records(
        endpoint="hr/v2/workers",
        params={"asOfDate": "2025-07-01"},  # no $select => full representation
    )
    paths = set()
    for r in records:
        paths |= _paths(r)
    with open(".claude/scratch/adp_worker_field_paths.json", "w") as f:
        json.dump(sorted(paths), f, indent=2)
    print(f"{len(records)} workers, {len(paths)} distinct field paths")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: USER RUNS the pull**

In a terminal with `OP_SERVICE_ACCOUNT_TOKEN` set:

```bash
uv --directory .worktrees/cbini/feat/claude-adp-wfn-worker-attributes run \
  python .claude/scratch/enumerate_adp_workers.py
```

Expected: prints worker count + path count; writes
`.claude/scratch/adp_worker_field_paths.json`.

- [ ] **Step 3: Reconcile the field set**

Compare `adp_worker_field_paths.json` against the spec's Appendix-A-derived
list. Record, in `.claude/scratch/adp_enum_notes.md` (local), the answers to:

- Exact shape of `workers/workAssignments/customCountryInputs` (single object vs
  repeated record? what leaves?).
- Exact shape of `workers/person/identityDocuments` (confirm it mirrors
  `governmentIDs`).
- Whether `workers/workerDates/retirementDate` and `.../adjustedServiceDate`
  actually appear.
- Any field paths present in live data but **not** in the spec's list (new
  surprises) — these get added to the model in Task 2.

No commit (scratch is gitignored).

---

## Task 2: Expand the `Worker` pydantic model

**Files:**

- Modify: `src/teamster/libraries/adp/workforce_now/api/schema.py`
- Test: `tests/libraries/test_adp_wfn_schema.py` (create)

- [ ] **Step 1: Write the failing local test**

Create `tests/libraries/test_adp_wfn_schema.py`. This needs no secrets — it
constructs a `Worker` from a literal record exercising the new fields and
asserts they parse and appear in the generated Avro schema.

```python
import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.api.schema import Worker


def _worker_avro_field_names() -> set[str]:
    schema = json.loads(
        py_avro_schema.generate(
            py_type=Worker,
            namespace="worker",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    )
    return {f["name"] for f in schema["fields"]}


def test_new_work_assignment_fields_parse():
    worker = Worker.model_validate(
        {
            "associateOID": "X",
            "customFieldGroup": {},
            "person": {
                "birthDate": "2000-01-01",
                "disabledIndicator": False,
                "customFieldGroup": {},
                "genderCode": {"codeValue": "M"},
                "legalName": {},
                "preferredName": {},
                "militaryClassificationCodes": [],
                "deathDate": "2099-01-01",
            },
            "workerDates": {
                "originalHireDate": "2020-01-01",
                "adjustedServiceDate": "2020-01-01",
                "retirementDate": "2099-01-01",
            },
            "workerID": {"idValue": "123"},
            "workerStatus": {"statusCode": {"codeValue": "A"}},
            "workAssignments": [
                {
                    "actualStartDate": "2020-01-01",
                    "hireDate": "2020-01-01",
                    "itemID": "1",
                    "managementPositionIndicator": False,
                    "positionID": "p1",
                    "primaryIndicator": True,
                    "assignmentStatus": {"statusCode": {"codeValue": "A"}},
                    "payrollProcessingStatusCode": {"codeValue": "X"},
                    "jobFunctionCode": {"codeValue": "JF"},
                    "rehireEligibleIndicator": True,
                    "payGradeCode": {"codeValue": "PG"},
                    "payGradePayRange": {
                        "minimumRate": {"amountValue": 1.0},
                        "medianRate": {"amountValue": 2.0},
                        "maximumRate": {"amountValue": 3.0},
                    },
                    "laborUnion": {"laborUnionCode": {"codeValue": "U"}},
                    "workShiftCode": {"codeValue": "S"},
                }
            ],
        }
    )

    wa = worker.workAssignments[0]
    assert wa.jobFunctionCode is not None and wa.jobFunctionCode.codeValue == "JF"
    assert wa.rehireEligibleIndicator is True
    assert wa.payGradePayRange.maximumRate.amountValue == 3.0
    assert wa.laborUnion.laborUnionCode.codeValue == "U"
    assert worker.workerDates.adjustedServiceDate == "2020-01-01"
    assert worker.person.deathDate == "2099-01-01"


def test_avro_schema_includes_business_communication_faxes():
    # Communication gains faxes/pagers; ensure the generated Avro still builds.
    assert "workAssignments" in _worker_avro_field_names()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv --directory .worktrees/cbini/feat/claude-adp-wfn-worker-attributes run \
  pytest tests/libraries/test_adp_wfn_schema.py -v
```

Expected: FAIL — `WorkAssignment` has no `jobFunctionCode` (pydantic ignores or
errors on unknown field depending on config; the assertion fails).

- [ ] **Step 3: Add the new model classes**

In `schema.py`, add these classes (place near the related existing classes).
Reconcile `IdentityDocument` and `customCountryInputs` against Task 1, Step 3
notes — the shapes below are the Appendix-A best-fit defaults:

```python
class IdentityDocument(BaseModel):
    countryCode: str | None = None
    idValue: str | None = None
    itemID: str | None = None
    expirationDate: str | None = None

    nameCode: Code | None = None
    statusCode: Code | None = None


class LaborUnion(BaseModel):
    laborUnionCode: Code | None = None


class PayGradeRate(BaseModel):
    amountValue: float | None = None


class PayGradePayRange(BaseModel):
    minimumRate: PayGradeRate | None = None
    medianRate: PayGradeRate | None = None
    maximumRate: PayGradeRate | None = None


class AmountField(CustomField):
    amountValue: float | None = None
    currencyCode: str | None = None


class PercentField(CustomField):
    percentValue: float | None = None


class TelephoneField(CustomField):
    formattedNumber: str | None = None
```

If Task 1 shows `customCountryInputs` is a repeated record, add a matching class
(e.g. `class CustomCountryInput(BaseModel): ...` with the observed leaves);
otherwise model it as a single object.

- [ ] **Step 4: Add fields to existing classes**

```python
# Address — add:
    deliveryPoint: str | None = None

# Communication — add:
    faxes: list[Phone] | None = None
    pagers: list[Phone] | None = None

# CustomFieldGroup — add:
    amountFields: list[AmountField] | None = None
    percentFields: list[PercentField] | None = None
    telephoneFields: list[TelephoneField] | None = None

# WorkerDates — add:
    adjustedServiceDate: str | None = None
    retirementDate: str | None = None

# Person — add (KEEP existing governmentIDs; ADD identityDocuments + deathDate):
    deathDate: str | None = None
    identityDocuments: list[IdentityDocument] | None = None

# WorkAssignment — add:
    rehireEligibleIndicator: bool | None = None

    jobFunctionCode: Code | None = None
    payGradeCode: Code | None = None
    payGradePayRange: PayGradePayRange | None = None
    laborUnion: LaborUnion | None = None
    workShiftCode: Code | None = None
    # customCountryInputs: <shape per Task 1>
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
uv --directory .worktrees/cbini/feat/claude-adp-wfn-worker-attributes run \
  pytest tests/libraries/test_adp_wfn_schema.py -v
```

Expected: PASS.

- [ ] **Step 6: Smoke-test `WORKER_SCHEMA` generation**

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini/feat/claude-adp-wfn-worker-attributes \
  run python -c "from teamster.code_locations.kipptaf.adp.workforce_now.api.schema import WORKER_SCHEMA; print(len(WORKER_SCHEMA['fields']))"
```

Expected: prints an int (no exception) — confirms the Avro schema still
generates after the model change.

- [ ] **Step 7: Commit**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes add \
  src/teamster/libraries/adp/workforce_now/api/schema.py \
  tests/libraries/test_adp_wfn_schema.py
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes commit -m \
  "feat(adp): model full WFN worker representation in Worker schema (#4106)"
```

---

## Task 3: Expand the curated `$select`

**Files:**

- Modify:
  `src/teamster/code_locations/kipptaf/adp/workforce_now/api/assets.py:46-71`

- [ ] **Step 1: Add the new `person` sub-paths**

Insert these into the `$select` list (keep it alphabetized within the `person/`
block). Do **not** add `workers/person/governmentIDs` or
`workers/person/identityDocuments`.

```python
                    "workers/person/birthName",
                    "workers/person/deathDate",
                    "workers/person/disabilityTypeCodes",
                    "workers/person/maritalStatusCode",
                    "workers/person/militaryDischargeDate",
                    "workers/person/otherPersonalAddresses",
                    "workers/person/preferredGenderPronounCode",
                    "workers/person/socialInsurancePrograms",
                    "workers/person/tobaccoUserIndicator",
```

- [ ] **Step 2: Syntactic check**

```bash
VIRTUAL_ENV= uv --directory .worktrees/cbini/feat/claude-adp-wfn-worker-attributes \
  run python -c "import teamster.code_locations.kipptaf.adp.workforce_now.api.assets"
```

Expected: no output, exit 0 (module imports clean).

- [ ] **Step 3: USER RUNS the live acceptance test**

This materializes the asset against live ADP and asserts the schema-valid check
finds **no extras** (`extras.text == ""`) — i.e. the model now covers everything
the curated `$select` returns. Needs `OP_SERVICE_ACCOUNT_TOKEN`.

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes && \
  uv run pytest tests/assets/test_assets_adp_wfn.py::test_workers -v
```

Expected: PASS. If `extras.text` is non-empty, it lists field paths still
missing from the model → add them to Task 2 Step 4 and re-run.

- [ ] **Step 4: Commit**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes add \
  src/teamster/code_locations/kipptaf/adp/workforce_now/api/assets.py
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes commit -m \
  "feat(adp): expand workers \$select with curated person sub-paths (#4106)"
```

---

## Task 4: Push Python; trigger branch-deployment materialization — USER RUNS

The staging contract (Task 6) needs the new-schema Avro to exist in GCS so the
external table exposes the new columns. This requires the Python change deployed
to a branch deployment and at least one partition re-materialized.

- [ ] **Step 1: Push the branch**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes push
```

Expected: branch updated; Dagster+ builds a branch deployment.

- [ ] **Step 2: USER materializes a recent partition in the branch deployment**

In the branch deployment (writes to `teamster-test`), materialize
`kipptaf/adp/workforce_now/workers` for one recent partition. Confirm the run
succeeds and the schema-valid check passes (no extras).

- [ ] **Step 3: Verify new-schema Avro landed**

Confirm the partition's Avro in
`gs://teamster-test/dagster/kipptaf/adp/workforce_now/workers/...` carries the
new fields (e.g. via the branch-deployment run logs / record_count). No commit.

---

## Task 5: Stage the external source — USER RUNS

- [ ] **Step 1: Re-stage the external table against staging**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes/src/dbt/kipptaf && \
  uv run dbt run-operation stage_external_sources \
  --args "select: adp_workforce_now.src_adp_workforce_now__workers" \
  --target staging
```

Expected: external table recreated with the widened Avro schema.

- [ ] **Step 2: Capture the authoritative BigQuery column types**

Query the external table's column types to drive the contract YAML in Task 6
(BigQuery's inference is ground truth for contract enforcement). Save to
`.claude/scratch/adp_external_columns.json`:

```sql
select column_name, data_type
from `teamster-332318`.`zz_stg_kipptaf_adp_workforce_now`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'src_adp_workforce_now__workers'
order by ordinal_position
```

(Use the BigQuery MCP / `bq`; paginate `ordinal_position` past 50 if needed.)

---

## Task 6: Staging model + contract YAML

**Files:**

- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/staging/stg_adp_workforce_now__workers.sql`
- Modify:
  `src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml`

- [ ] **Step 1: Read both files end-to-end first**

The properties YAML carries the contract; the SQL does the flattening. Confirm
which person-grain scalars already have flatten expressions (most do; they were
just NULL) versus which are genuinely new.

- [ ] **Step 2: Add flatten expressions for new worker-grain scalars (SQL)**

Add to the staging `SELECT` (follow the file's existing alias pattern):

```sql
    person.deathdate as person__death_date,
    person.legaladdress.deliverypoint as person__legal_address__delivery_point,
```

Do **not** add `person.governmentids` / `person.identitydocuments` expressions —
they stay unstaged (always-null external columns).

- [ ] **Step 3: Pass through the new repeated records (SQL)**

Add the new array columns to the passthrough (they stay nested):

```sql
    business_communication.faxes as business_communication__faxes,
    business_communication.pagers as business_communication__pagers,
    person.communication.faxes as person__communication__faxes,
    person.communication.pagers as person__communication__pagers,
    person.customfieldgroup.amountfields as person__custom_field_group__amount_fields,
    person.customfieldgroup.percentfields as person__custom_field_group__percent_fields,
    person.customfieldgroup.telephonefields
    as person__custom_field_group__telephone_fields,
    customfieldgroup.amountfields as custom_field_group__amount_fields,
    customfieldgroup.percentfields as custom_field_group__percent_fields,
    customfieldgroup.telephonefields as custom_field_group__telephone_fields,
```

(Confirm exact source struct field names against
`.claude/scratch/adp_external_columns.json`.)

- [ ] **Step 4: Regenerate the `work_assignments` struct `data_type` + add new
      contract columns (YAML)**

From `.claude/scratch/adp_external_columns.json`, paste the new BigQuery types:

- Replace the `work_assignments` `data_type` block with the widened
  `ARRAY<STRUCT<...>>` (now containing `jobFunctionCode`, `customCountryInputs`,
  `rehireEligibleIndicator`, `payGradeCode`, `payGradePayRange`, `laborUnion`,
  `workShiftCode`, plus the new `workerDates`-side fields where applicable).
- Add new column entries for the Step-2 scalars (`person__death_date` →
  `data_type: string` (or `date` if the SQL casts it; match the SQL),
  `person__legal_address__delivery_point` → `string`).
- Add new column entries for the Step-3 arrays with their full
  `ARRAY<STRUCT<...>>` `data_type` from the JSON.
- Add a `description:` to **every** new column (qualitative; profile values via
  BigQuery MCP after the staging table rebuilds).

- [ ] **Step 5: Compile-check the staging model**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes/src/dbt/kipptaf && \
  uv run dbt parse && \
  uv run dbt compile --select stg_adp_workforce_now__workers
```

Expected: parses and compiles with no error. (Full contract enforcement runs in
dbt Cloud CI, Task 8.)

- [ ] **Step 6: Lint**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes && \
  .trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/adp/workforce_now/api/staging/stg_adp_workforce_now__workers.sql \
  src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml
```

Expected: no issues.

- [ ] **Step 7: Commit**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes add \
  src/dbt/kipptaf/models/adp/workforce_now/api/staging/stg_adp_workforce_now__workers.sql \
  src/dbt/kipptaf/models/adp/workforce_now/api/staging/properties/stg_adp_workforce_now__workers.yml
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes commit -m \
  "feat(adp): flatten new worker-grain columns + widen staging contract (#4106)"
```

---

## Task 7: Intermediate model — flatten work-assignment-grain fields

**Files:**

- Modify:
  `.../api/intermediate/int_adp_workforce_now__workers__work_assignments.sql`
- Modify:
  `.../api/intermediate/properties/int_adp_workforce_now__workers__work_assignments.yml`
- Test: dbt unit test (create in the project's unit-test location)

- [ ] **Step 1: Write the failing dbt unit test**

Mock one `stg_adp_workforce_now__workers` row whose `work_assignments` array
carries the new subfields; assert the int model flattens them. Add to the model
properties YAML (follow `dbt:adding-dbt-unit-test`):

```yaml
unit_tests:
  - name: test_int_work_assignments_flattens_new_fields
    model: int_adp_workforce_now__workers__work_assignments
    given:
      - input: ref('stg_adp_workforce_now__workers')
        rows:
          - associate_oid: A1
            effective_date_start: 2025-07-01
            effective_date_end: 2025-07-02
            effective_date_start_timestamp: 2025-07-01 00:00:00
            is_current_record: true
            work_assignments:
              - itemid: i1
                positionid: p1
                jobfunctioncode:
                  { codevalue: JF, longname: Job Fn, shortname: JF }
                rehireeligibleindicator: true
                workshiftcode: { codevalue: S, longname: Shift, shortname: S }
    expect:
      rows:
        - item_id: i1
          job_function_code__code_value: JF
          rehire_eligible_indicator: true
          work_shift_code__code_value: S
```

(Provide the full `given` row covering every NOT NULL column the model
references — copy the column set from the model's source CTE. Unquoted scalars
per `tests/` conventions.)

- [ ] **Step 2: Run the unit test to verify it fails**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes/src/dbt/kipptaf && \
  uv run dbt test --select int_adp_workforce_now__workers__work_assignments,test_type:unit
```

Expected: FAIL — columns `job_function_code__code_value`, etc. don't exist yet.

- [ ] **Step 3: Add flatten expressions to the parsed CTE (SQL)**

In `work_assignments_parsed`, add (match the file's `wa.<field>` alias style):

```sql
            wa.rehireeligibleindicator as rehire_eligible_indicator,

            wa.jobfunctioncode.codevalue as job_function_code__code_value,
            wa.jobfunctioncode.longname as job_function_code__long_name,
            wa.jobfunctioncode.shortname as job_function_code__short_name,

            wa.paygradecode.codevalue as pay_grade_code__code_value,
            wa.paygradecode.longname as pay_grade_code__long_name,
            wa.paygradecode.shortname as pay_grade_code__short_name,

            wa.paygradepayrange.minimumrate.amountvalue
            as pay_grade_pay_range__minimum_rate__amount_value,
            wa.paygradepayrange.medianrate.amountvalue
            as pay_grade_pay_range__median_rate__amount_value,
            wa.paygradepayrange.maximumrate.amountvalue
            as pay_grade_pay_range__maximum_rate__amount_value,

            wa.laborunion.laborunioncode.codevalue
            as labor_union_code__code_value,
            wa.laborunion.laborunioncode.longname as labor_union_code__long_name,
            wa.laborunion.laborunioncode.shortname
            as labor_union_code__short_name,

            wa.workshiftcode.codevalue as work_shift_code__code_value,
            wa.workshiftcode.longname as work_shift_code__long_name,
            wa.workshiftcode.shortname as work_shift_code__short_name,
```

Add `__effective_date` `date(...)` derivations for the `Code`-typed fields in
the "transformations" block, matching the file's existing pattern (e.g.
`date(wa.jobfunctioncode.effectivedate) as job_function_code__effective_date`).

For `customCountryInputs`: if single-object, flatten its leaves here; if a
repeated record, add `wa.customcountryinputs as custom_country_inputs` to the
"repeated records" passthrough block instead.

- [ ] **Step 4: Add the same columns to the final `SELECT`**

Append every new column from Step 3 to the outer `select` list (the file
re-projects each column explicitly).

- [ ] **Step 5: Run the unit test to verify it passes**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes/src/dbt/kipptaf && \
  uv run dbt test --select int_adp_workforce_now__workers__work_assignments,test_type:unit
```

Expected: PASS.

- [ ] **Step 6: Add descriptions (YAML)**

Add a `description:` for every new column in
`int_adp_workforce_now__workers__work_assignments.yml`. Retain the existing
uniqueness test. Run `dbt parse --no-partial-parse` after editing.

- [ ] **Step 7: Lint**

```bash
cd .worktrees/cbini/feat/claude-adp-wfn-worker-attributes && \
  .trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/int_adp_workforce_now__workers__work_assignments.sql \
  src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/properties/int_adp_workforce_now__workers__work_assignments.yml
```

Expected: no issues.

- [ ] **Step 8: Commit**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes add \
  src/dbt/kipptaf/models/adp/workforce_now/api/intermediate/
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes commit -m \
  "feat(adp): flatten work-assignment-grain fields in int model (#4106)"
```

---

## Task 8: CI, verification, and PR

- [ ] **Step 1: Confirm dbt Cloud CI is terminal before pushing**

Check the PR's dbt Cloud check is not mid-run (pushing cancels + restarts).

- [ ] **Step 2: Push and let CI build**

```bash
git -C .worktrees/cbini/feat/claude-adp-wfn-worker-attributes push
```

CI runs `dbt build --select state:modified+ --full-refresh` (target staging).
The widened contract is enforced here against the re-staged external table.

- [ ] **Step 3: USER confirms CI passes; fetch warnings**

After CI passes, fetch test warnings:

```text
mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)
```

Expected: no new warnings attributable to this change. Pre-existing/stale-dev
warnings per repo conventions are ignored.

- [ ] **Step 4: Open the PR**

Use `.github/pull_request_template.md` as the body. Include the **divergence
note** (this PR carries it — issue #4106 body is not edited): keep a curated
`$select`; model the full representation; exclude `governmentIDs` /
`identityDocuments` from `$select` and staging. Reference `Closes #4106`.

- [ ] **Step 5: Plan the recent-window re-pull (deploy step)**

Note in the PR that, post-merge, a recent-window re-pull of
`kipptaf/adp/workforce_now/workers` brings every active worker's current SCD2
segment up to the full field set (window decided at execution time). Flag the
deliberate SCD2 re-key (whole-struct hash recomposition) for reviewers.

---

## Self-Review notes

- **Spec coverage:** enumeration (T1), schema incl. cut-PII-in-model (T2),
  `$select` (T3), branch-deploy + `stage_external_sources` rollout (T4–T5),
  staging flatten + contract + cut-PII-unstaged (T6), int flatten all
  grain-aligned fields (T7), CI + warnings + PR + re-pull + divergence note
  (T8).
- **Enumeration-dependent shapes** (`customCountryInputs`, `identityDocuments`):
  resolved in T1 and threaded into T2/T6/T7 with explicit reconciliation steps —
  not left as silent placeholders.
- **Hash discipline:** whole-struct surrogate key kept; one-time SCD2 re-key
  called out in T8.
