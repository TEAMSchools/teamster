# Finalsite Contacts Ingestion + Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land KIPP Miami's Finalsite Enrollment **contacts** (with expanded
guardians) from the REST API into BigQuery as Avro, and expose them as
normalized, contract-enforced dbt staging models.

**Architecture:** Reuse the dormant `build_finalsite_asset` /
`FinalsiteResource`. Add a contacts-specific asset factory that resolves the
current school year (via `/school_years`) and pages `/contacts` with the
`contacts.relationships.contact` expansion. Generate the Avro schema from the
existing `Contact` Pydantic model via `py_avro_schema` (the house pattern). Wire
Miami's resource + asset, add the dbt external source, and build two staging
models (student grain + guardian grain). This is **Plan 1 of 3** for the
Finalsite → Focus integration (issue
[#4073](https://github.com/TEAMSchools/teamster/issues/4073)); Plan 2 =
eligibility + identity crosswalk, Plan 3 = Focus output models + SFTP transport.
See `docs/superpowers/specs/2026-05-29-finalsite-focus-integration-design.md`.

**Tech Stack:** Python 3.13, Dagster (`@asset`, `ConfigurableResource`),
`fastavro` + `py_avro_schema`, BigQuery external tables (`dbt-external-tables`),
dbt (contract-enforced staging models, BigQuery dialect).

---

## Scope & boundaries

**In scope:** ingestion of the `contacts` endpoint → landed Avro → queryable
BigQuery external table → two normalized staging models. Every field here was
live-validated against Miami in the design phase (100% export reproduction).

**Explicitly out of scope (later plans):**

- Eligibility filtering, lifecycle state mapping, identity resolution /
  crosswalk (Plan 2).
- The join to `stg_finalsite__status_report` for `enrolled_date` / status
  timeline (Plan 2 — it produces the integrated roster, not raw staging).
- Focus-shaped output models + SFTP transport (Plan 3).
- **Medical columns** (`med_doctor_txt`, `med_hospital_txt`, etc.) are
  deliberately **NOT** surfaced in staging here. The medical-destination gate is
  unresolved; the PII-minimization default is to not propagate medical data
  until Focus is confirmed as its home. They are added in Plan 3 only if that
  gate resolves to "Focus."

**External dependency (not a code task — flag to ops before running the
asset):** the cluster must hold the secrets `FINALSITE_CREDENTIAL_ID_KIPPMIAMI`
and `FINALSITE_SECRET_KIPPMIAMI` (1Password → k8s secret-volume, same mechanism
as other resources). The design phase validated these creds locally; confirm
they are deployed before materializing the asset in branch/prod.

---

## Design decision: attribute `value` is coerced to a string at ingestion

`Contact.custom_attributes` / `track_attributes` / `id_attributes` items carry a
`value` typed `bool | str | list[str]` (e.g. `race_ms` is a list). A multi-type
Avro union loads badly into a BigQuery external table. **Decision:** narrow
`CustomAttribute.value` to `str | None` and JSON-encode non-scalar values in the
asset before the Avro write. The landed column is a clean nullable `STRING`;
list-valued fields (`race_ms`) round-trip as a JSON array string and are parsed
in staging. This is the single design choice in this plan; it is implemented in
Tasks 1 and 3.

---

## File Structure

| File                                                                                   | Action | Responsibility                                                                                                                                        |
| -------------------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/teamster/libraries/finalsite/api/schema.py`                                       | Modify | Narrow `CustomAttribute.value` to `str`; add `RelatedContact` model + `contact` field on `Relationship` (captures expanded guardians, non-recursive). |
| `src/teamster/libraries/finalsite/api/assets.py`                                       | Modify | Add `build_finalsite_contacts_asset` (school-year resolution + paged expansion call + value coercion).                                                |
| `src/teamster/code_locations/kippmiami/finalsite/schema.py`                            | Modify | Generate `CONTACTS_SCHEMA` from the `Contact` Pydantic model.                                                                                         |
| `src/teamster/core/resources.py`                                                       | Modify | Define `FINALSITE_RESOURCE` (Miami server + EnvVar creds).                                                                                            |
| `src/teamster/code_locations/kippmiami/definitions.py`                                 | Modify | Register `"finalsite"` resource.                                                                                                                      |
| `src/teamster/code_locations/kippmiami/finalsite/assets.py`                            | Modify | Wire the contacts asset into the code location.                                                                                                       |
| `src/dbt/finalsite/models/sources-external.yml`                                        | Modify | Add the `contacts` external Avro source + Dagster asset_key meta.                                                                                     |
| `src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql`                         | Create | Student-grain normalization (one row per contact).                                                                                                    |
| `src/dbt/finalsite/models/staging/properties/stg_finalsite__contacts.yml`              | Create | Contract + grain test for the above.                                                                                                                  |
| `src/dbt/finalsite/models/staging/stg_finalsite__contact_relationships.sql`            | Create | Guardian-grain normalization (one row per relationship).                                                                                              |
| `src/dbt/finalsite/models/staging/properties/stg_finalsite__contact_relationships.yml` | Create | Contract + grain test for the above.                                                                                                                  |

---

## Task 1: Capture expanded guardians + narrow the attribute value type (Pydantic)

**Files:**

- Modify: `src/teamster/libraries/finalsite/api/schema.py`

The `contacts.relationships.contact` expansion inlines each guardian's full
contact under `relationships[].contact`. The current `Relationship` model has no
`contact` field, so `fastavro` would silently drop it. Add a **bounded,
non-recursive** `RelatedContact` (it must NOT reference
`Relationship`/`Contact`, or the generated Avro schema recurses infinitely).
Also narrow `CustomAttribute.value` to `str | None` per the design decision
above.

- [ ] **Step 1: Narrow `CustomAttribute.value`**

In `src/teamster/libraries/finalsite/api/schema.py`, change the
`CustomAttribute` class body from:

```python
class CustomAttribute(BaseModel):
    field_id: str | None = None
    field_name: str | None = None
    field_display_name: str | None = None

    value: bool | str | list[str] | None = None
```

to:

```python
class CustomAttribute(BaseModel):
    field_id: str | None = None
    field_name: str | None = None
    field_display_name: str | None = None

    # value is coerced to a string at ingestion (lists JSON-encoded) to avoid a
    # multi-type Avro union that BigQuery external tables handle poorly.
    value: str | None = None
```

- [ ] **Step 2: Add the `RelatedContact` model**

Insert this class immediately **above** the existing `Relationship` class:

```python
class RelatedContact(BaseModel):
    id: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    preferred_name: str | None = None
    email: str | None = None
    gender: str | None = None

    phone_1: Phone | None = None
    phone_2: Phone | None = None
    phone_3: Phone | None = None

    households: list[Household] | None = None
    custom_attributes: list[CustomAttribute] | None = None
    id_attributes: list[CustomAttribute] | None = None
```

- [ ] **Step 3: Add the `contact` field to `Relationship`**

Add one field to the existing `Relationship` class (after `portal_access`):

```python
    contact: RelatedContact | None = None
```

- [ ] **Step 4: Verify the module imports and the Avro schema generates without
      recursion**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run python -c "
import json, py_avro_schema
from teamster.libraries.finalsite.api.schema import Contact
opts = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
s = json.loads(py_avro_schema.generate(py_type=Contact, options=opts))
print('fields:', len(s['fields']))
"
```

Expected: prints `fields: <n>` (a positive integer) with no `RecursionError` and
no exception.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/teamster/libraries/finalsite/api/schema.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): capture expanded guardians, stringify attribute values"
```

---

## Task 2: Generate the contacts Avro schema

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/finalsite/schema.py`

Follow the existing `STATUS_REPORT_SCHEMA` pattern (and `deanslist/schema.py`):
generate the Avro schema dict from the Pydantic model via `py_avro_schema`.

- [ ] **Step 1: Add the schema generation**

The file currently reads:

```python
import json

import py_avro_schema

from teamster.libraries.finalsite.sftp.schema import StatusReport

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STATUS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StatusReport, options=pas_options)
)
```

Add an import for `Contact` and a `CONTACTS_SCHEMA` generation. The final file:

```python
import json

import py_avro_schema

from teamster.libraries.finalsite.api.schema import Contact
from teamster.libraries.finalsite.sftp.schema import StatusReport

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STATUS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StatusReport, options=pas_options)
)

CONTACTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Contact, options=pas_options)
)
```

- [ ] **Step 2: Verify it imports**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run python -c "
from teamster.code_locations.kippmiami.finalsite.schema import CONTACTS_SCHEMA
print('type:', CONTACTS_SCHEMA['type'], 'name:', CONTACTS_SCHEMA['name'])
"
```

Expected: prints `type: record name: Contact` (or similar record name) with no
exception.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/teamster/code_locations/kippmiami/finalsite/schema.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): generate contacts avro schema"
```

---

## Task 3: Add the contacts asset factory

**Files:**

- Modify: `src/teamster/libraries/finalsite/api/assets.py`

Add `build_finalsite_contacts_asset`. It resolves the current school year (the
design-validated pattern: list `/school_years`, sort by `start_year` desc, pick
the first that returns contacts), pages `/contacts` with the expansion, coerces
attribute `value`s to strings, then yields the Avro output + schema-validity
check. Keep the existing `build_finalsite_asset` untouched.

- [ ] **Step 1: Add the factory and value-coercion helper**

Append to `src/teamster/libraries/finalsite/api/assets.py` (the existing imports
at the top — `AssetExecutionContext`, `Output`, `asset`, the asset-check
helpers, `FinalsiteResource` — already cover everything except `json`; add
`import json` at the top of the file):

```python
def _coerce_attr_values(record: dict) -> dict:
    """Stringify custom/track/id attribute values (lists -> JSON) in place.

    A multi-type Avro union for the attribute ``value`` field loads poorly into a
    BigQuery external table, so the asset narrows every value to a string before
    the Avro write. Recurses into expanded guardian contacts under
    ``relationships[].contact``.
    """
    for key in ("custom_attributes", "track_attributes", "id_attributes"):
        for attr in record.get(key) or []:
            value = attr.get("value")
            if value is None or isinstance(value, str):
                continue
            attr["value"] = (
                json.dumps(value) if isinstance(value, list) else str(value)
            )

    for rel in record.get("relationships") or []:
        contact = rel.get("contact")
        if contact:
            _coerce_attr_values(contact)

    return record


def build_finalsite_contacts_asset(code_location: str, schema):
    key = [code_location, "finalsite", "contacts"]

    @asset(
        key=key,
        io_manager_key="io_manager_gcs_avro",
        check_specs=[build_check_spec_avro_schema_valid(key)],
        group_name="finalsite",
        kinds={"python"},
    )
    def _asset(context: AssetExecutionContext, finalsite: FinalsiteResource):
        school_years = finalsite.get(path="school_years").json().get(
            "school_years", []
        )

        data: list[dict] = []
        chosen_year = None
        for year in sorted(
            school_years, key=lambda y: y.get("start_year") or 0, reverse=True
        ):
            data = finalsite.list(
                path="contacts",
                params={
                    "school_year_id": year.get("id"),
                    "count": 25,
                    "includes": "contacts.relationships.contact",
                },
            )
            if data:
                chosen_year = year
                break

        data = [_coerce_attr_values(record) for record in data]

        context.log.info(
            f"school_year start={chosen_year.get('start_year') if chosen_year else None}; "
            f"contacts={len(data)}"
        )

        yield Output(value=(data, schema), metadata={"record_count": len(data)})
        yield check_avro_schema_valid(
            asset_key=context.asset_key, records=data, schema=schema
        )

    return _asset
```

- [ ] **Step 2: Verify the module imports**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run python -c "
from teamster.libraries.finalsite.api.assets import build_finalsite_contacts_asset, _coerce_attr_values
r = _coerce_attr_values({'custom_attributes': [{'field_name': 'race_ms', 'value': ['A', 'B']}, {'field_name': 'x', 'value': True}]})
print(r['custom_attributes'][0]['value'], '|', r['custom_attributes'][1]['value'])
"
```

Expected: prints `["A", "B"] | True` (the list became a JSON string, the bool
became `"True"`).

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/teamster/libraries/finalsite/api/assets.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): add contacts asset factory with school-year resolution"
```

---

## Task 4: Define the Miami Finalsite resource

**Files:**

- Modify: `src/teamster/core/resources.py`

Add a `FINALSITE_RESOURCE` singleton following the `OVERGRAD_RESOURCE` /
`DEANSLIST_RESOURCE` pattern. Miami is the only consumer today; the `server` is
the tenant subdomain (`kippmiami`), creds come from EnvVar (names match the
design-phase harness: `FINALSITE_CREDENTIAL_ID_KIPPMIAMI` /
`FINALSITE_SECRET_KIPPMIAMI`).

- [ ] **Step 1: Import the resource class**

Add to the imports at the top of `src/teamster/core/resources.py` (alongside the
other resource-class imports — match the existing import grouping):

```python
from teamster.libraries.finalsite.api.resources import FinalsiteResource
```

- [ ] **Step 2: Add the resource singleton**

Add after the `DEANSLIST_RESOURCE` definition (near line 90):

```python
FINALSITE_RESOURCE = FinalsiteResource(
    server="kippmiami",
    credential_id=EnvVar("FINALSITE_CREDENTIAL_ID_KIPPMIAMI"),
    secret=EnvVar("FINALSITE_SECRET_KIPPMIAMI"),
)
```

- [ ] **Step 3: Verify it imports**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run python -c "
from teamster.core.resources import FINALSITE_RESOURCE
print('server:', FINALSITE_RESOURCE.server)
"
```

Expected: prints `server: kippmiami` with no exception.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/teamster/core/resources.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): define kippmiami finalsite api resource"
```

---

## Task 5: Wire the contacts asset + resource into the Miami code location

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/finalsite/assets.py`
- Modify: `src/teamster/code_locations/kippmiami/definitions.py`

- [ ] **Step 1: Build the contacts asset**

`src/teamster/code_locations/kippmiami/finalsite/assets.py` currently imports
only the SFTP pieces. Replace its contents with:

```python
from teamster.code_locations.kippmiami import CODE_LOCATION, CURRENT_FISCAL_YEAR
from teamster.code_locations.kippmiami.finalsite.schema import (
    CONTACTS_SCHEMA,
    STATUS_REPORT_SCHEMA,
)
from teamster.libraries.finalsite.api.assets import build_finalsite_contacts_asset
from teamster.libraries.finalsite.sftp.assets import (
    get_finalsite_school_year_partition_keys,
)
from teamster.libraries.sftp.assets import build_sftp_file_asset

status_report = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "finalsite", "status_report"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/finalsite/status_report",
    remote_file_regex=(
        rf"{CODE_LOCATION}_SwissArmyExport_SFTP_Export___"
        r"Status_Report_SFTP_Status_Export___"
        r"(?P<school_year>\d+_\d+)\.csv"
    ),
    partitions_def=get_finalsite_school_year_partition_keys(
        start_year=2025, end_year=CURRENT_FISCAL_YEAR.fiscal_year
    ),
    avro_schema=STATUS_REPORT_SCHEMA,
    ssh_resource_key="ssh_couchdrop",
)

contacts = build_finalsite_contacts_asset(
    code_location=CODE_LOCATION, schema=CONTACTS_SCHEMA
)

assets = [
    status_report,
    contacts,
]
```

- [ ] **Step 2: Register the resource in `definitions.py`**

In `src/teamster/code_locations/kippmiami/definitions.py`, add
`FINALSITE_RESOURCE` to the `from teamster.core.resources import (...)` block
(keep alphabetical-ish grouping with the other resources):

```python
    FINALSITE_RESOURCE,
```

Then add one entry to the `resources={...}` dict (after the `"dlt"` / `"gcs"`
entries, before `"google_drive"` — keep it grouped with the other named
resources):

```python
        "finalsite": FINALSITE_RESOURCE,
```

- [ ] **Step 3: Verify definitions load**

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run python -c "
from teamster.code_locations.kippmiami.definitions import defs
keys = [a.key.to_user_string() for a in defs.get_asset_graph().assets_defs if 'finalsite' in a.key.to_user_string()]
print(sorted(set(keys)))
"
```

Expected: the printed list includes `kippmiami/finalsite/contacts` and
`kippmiami/finalsite/status_report`, with no resource-binding error (a missing
`"finalsite"` resource would raise `DagsterInvalidDefinitionError` at load).

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/teamster/code_locations/kippmiami/finalsite/assets.py src/teamster/code_locations/kippmiami/definitions.py
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): wire contacts asset into kippmiami"
```

---

## Task 6: Add the dbt external source for contacts

**Files:**

- Modify: `src/dbt/finalsite/models/sources-external.yml`

Mirror the existing `status_report` external-table entry. The contacts asset is
**non-partitioned**, so the location is a flat `contacts/*` glob (no
`hive_partition_uri_prefix`).

- [ ] **Step 1: Add the `contacts` table**

Under the `tables:` list in `src/dbt/finalsite/models/sources-external.yml`
(after the `status_report` entry), add:

```yaml
- name: contacts
  external:
    location: "{{ var('cloud_storage_uri_base') }}/finalsite/contacts/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      format: AVRO
      enable_logical_types: true
  config:
    meta:
      dagster:
        asset_key:
          - "{{ project_name }}"
          - finalsite
          - contacts
```

- [ ] **Step 2: Verify the YAML parses and the source resolves**

Run (from the kippmiami project, which imports the finalsite package):

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration/src/dbt/kippmiami
```

Expected: `dbt parse` completes without error (it loads and validates
`sources-external.yml`).

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/dbt/finalsite/models/sources-external.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): add contacts external source"
```

---

## Task 7: Staging model — `stg_finalsite__contacts` (student grain)

**Files:**

- Create: `src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql`
- Create:
  `src/dbt/finalsite/models/staging/properties/stg_finalsite__contacts.yml`

One row per contact. Scalars are projected directly; named custom/track/id
attributes are pulled via correlated `unnest` subqueries (each references only
the same row's array — a lateral correlation BigQuery supports); the single
household is flattened from offset 0. **No medical columns** (see Scope). The
model is materialized as a table with an **enforced contract**, so the SQL
output columns must match the YAML exactly.

> **Avro→BigQuery note before writing the SQL:** confirm the landed
> external-table column names/types once data exists (Task 9 materializes the
> asset). Run `bq show --schema teamster-332318:kippmiami_finalsite.contacts`
> (or the BigQuery MCP `get_table_info`). The `birth_date` source field is a
> string and is cast to `date`; `school_year` and `grade` land as `STRUCT`s;
> `households`/`relationships`/`*_attributes` land as `ARRAY<STRUCT>`. If a
> struct/array field name differs from the Pydantic field name, adjust the
> references below to match the observed schema. This is a verification of the
> generated schema, not a redesign.

- [ ] **Step 1: Write the model**

Create `src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql`:

```sql
select
    id as finalsite_enrollment_id,
    first_name,
    middle_name,
    last_name,
    gender,
    status,
    enrollment_type,

    grade.canonical_name as grade_canonical_name,
    school_year.start_year as school_year_start,

    safe_cast(birth_date as date) as birth_date,

    households[safe_offset(0)].address_1 as address_1,
    households[safe_offset(0)].address_2 as address_2,
    households[safe_offset(0)].city as city,
    households[safe_offset(0)].state as state,
    households[safe_offset(0)].zip as zip,

    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'race_ms'
    ) as race_ms,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'latino_hispanic_yn'
    ) as latino_hispanic_yn,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'assigned_school_ss'
    ) as assigned_school_ss,
    (
        select any_value(av.value),
        from unnest(custom_attributes) as av
        where av.field_name = 'sped_received_yn'
    ) as sped_received_yn,
    (
        select any_value(av.value),
        from unnest(id_attributes) as av
        where av.field_name = 'mdcps_id_txt'
    ) as mdcps_id_txt,
    (
        select any_value(av.value),
        from unnest(id_attributes) as av
        where av.field_name = 'powerschool_student_number'
    ) as powerschool_student_number,
from {{ source("finalsite", "contacts") }}
```

- [ ] **Step 2: Write the contract + grain test**

Create
`src/dbt/finalsite/models/staging/properties/stg_finalsite__contacts.yml`:

```yaml
models:
  - name: stg_finalsite__contacts
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - finalsite_enrollment_id
          config:
            severity: error
    columns:
      - name: finalsite_enrollment_id
        data_type: string
      - name: first_name
        data_type: string
      - name: middle_name
        data_type: string
      - name: last_name
        data_type: string
      - name: gender
        data_type: string
      - name: status
        data_type: string
      - name: enrollment_type
        data_type: string
      - name: grade_canonical_name
        data_type: string
      - name: school_year_start
        data_type: int64
      - name: birth_date
        data_type: date
      - name: address_1
        data_type: string
      - name: address_2
        data_type: string
      - name: city
        data_type: string
      - name: state
        data_type: string
      - name: zip
        data_type: string
      - name: race_ms
        data_type: string
      - name: latino_hispanic_yn
        data_type: string
      - name: assigned_school_ss
        data_type: string
      - name: sped_received_yn
        data_type: string
      - name: mdcps_id_txt
        data_type: string
      - name: powerschool_student_number
        data_type: string
```

- [ ] **Step 3: Build and test the model**

(Requires the asset to have materialized at least once — see Task 9. If running
before data lands, expect a "table not found" on the external source; in that
case run this step after Task 9.)

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration/src/dbt/kippmiami --select stg_finalsite__contacts
```

Expected: model builds; the `unique_combination_of_columns` test PASSES (one row
per `finalsite_enrollment_id`); contract enforcement passes (output columns
match the YAML).

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql src/dbt/finalsite/models/staging/properties/stg_finalsite__contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): add stg_finalsite__contacts staging model"
```

---

## Task 8: Staging model — `stg_finalsite__contact_relationships` (guardian grain)

**Files:**

- Create:
  `src/dbt/finalsite/models/staging/stg_finalsite__contact_relationships.sql`
- Create:
  `src/dbt/finalsite/models/staging/properties/stg_finalsite__contact_relationships.yml`

One row per (contact, relationship). Unnests `relationships`, projects the
expanded guardian's fields from `relationship.contact`, and derives the gendered
`mother`/`father` label from `rel_type` + the guardian's `gender` (the
design-validated rule, falling back to bare `rel_type` when gender is unset).
The guardian's PowerSchool Contact ID is pulled from the guardian's own
`id_attributes`.

- [ ] **Step 1: Write the model**

Create
`src/dbt/finalsite/models/staging/stg_finalsite__contact_relationships.sql`:

```sql
with
    relationships as (
        select
            c.id as finalsite_enrollment_id,
            r.id as relationship_id,
            r.rel_type,
            r.primary as is_primary,
            r.contact.id as guardian_finalsite_id,
            r.contact.first_name as guardian_first_name,
            r.contact.last_name as guardian_last_name,
            r.contact.email as guardian_email,
            r.contact.gender as guardian_gender,
            r.contact.phone_1.number as guardian_phone,
            (
                select any_value(av.value),
                from unnest(r.contact.id_attributes) as av
                where av.field_name = 'powerschool_contact_id'
            ) as guardian_powerschool_contact_id,
        from {{ source("finalsite", "contacts") }} as c
        cross join unnest(c.relationships) as r
        where r.contact is not null
    )

select
    *,
    case
        when rel_type = 'parent' and guardian_gender = 'F'
        then 'mother'
        when rel_type = 'parent' and guardian_gender = 'M'
        then 'father'
        else rel_type
    end as relationship_label,
from relationships
```

- [ ] **Step 2: Write the contract + grain test**

Create
`src/dbt/finalsite/models/staging/properties/stg_finalsite__contact_relationships.yml`:

```yaml
models:
  - name: stg_finalsite__contact_relationships
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - finalsite_enrollment_id
              - relationship_id
          config:
            severity: error
    columns:
      - name: finalsite_enrollment_id
        data_type: string
      - name: relationship_id
        data_type: string
      - name: rel_type
        data_type: string
      - name: is_primary
        data_type: boolean
      - name: guardian_finalsite_id
        data_type: string
      - name: guardian_first_name
        data_type: string
      - name: guardian_last_name
        data_type: string
      - name: guardian_email
        data_type: string
      - name: guardian_gender
        data_type: string
      - name: guardian_phone
        data_type: string
      - name: guardian_powerschool_contact_id
        data_type: string
      - name: relationship_label
        data_type: string
```

- [ ] **Step 3: Build and test the model**

(Same data prerequisite as Task 7 Step 3.)

Run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration/src/dbt/kippmiami --select stg_finalsite__contact_relationships
```

Expected: model builds; `unique_combination_of_columns` PASSES; contract passes.
If the grain test fails (duplicate `relationship_id` within a contact), inspect
whether the API returns multiple expansion rows per relationship and adjust the
grain key.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration add src/dbt/finalsite/models/staging/stg_finalsite__contact_relationships.sql src/dbt/finalsite/models/staging/properties/stg_finalsite__contact_relationships.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration commit -m "feat(finalsite): add stg_finalsite__contact_relationships staging model"
```

---

## Task 9: End-to-end materialization + lint + push

**Files:** none (operational verification).

This task materializes the asset (lands real data), runs the staging builds
against it, lints, and pushes for dbt Cloud CI.

- [ ] **Step 1: Materialize the contacts asset (requires OP token + deployed
      creds)**

In the VS Code terminal (where `OP_SERVICE_ACCOUNT_TOKEN` is available — Claude
sessions cannot access secrets):

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration
uv run dagster asset materialize --select kippmiami/finalsite/contacts -m teamster.code_locations.kippmiami.definitions
```

Expected: run succeeds; the `record_count` metadata is > 0; the
`avro_schema_valid` asset check passes (or WARNs on extra fields — a warn is
acceptable, it does not fail). If it 401s, the cluster/env creds are missing
(see Scope external dependency).

- [ ] **Step 2: Confirm the BigQuery external table is queryable**

Use the BigQuery MCP (or `bq query`) — confirm row count and the union-coercion
landed `race_ms` as a string:

```sql
select count(*) as n, count(race_ms) as n_race
from `teamster-332318.kippmiami_finalsite.stg_finalsite__contacts`
```

Expected: `n` > 0; `n_race` close to `n` (race populated for most students), no
query error on the `race_ms` STRING column.

- [ ] **Step 3: Build both staging models together**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration run dbt build --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration/src/dbt/kippmiami --select stg_finalsite__contacts stg_finalsite__contact_relationships
```

Expected: both build; all data_tests PASS.

- [ ] **Step 4: Lint the SQL + YAML**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/finalsite/models/staging/stg_finalsite__contacts.sql \
  src/dbt/finalsite/models/staging/stg_finalsite__contact_relationships.sql \
  src/dbt/finalsite/models/staging/properties/stg_finalsite__contacts.yml \
  src/dbt/finalsite/models/staging/properties/stg_finalsite__contact_relationships.yml \
  src/dbt/finalsite/models/sources-external.yml
```

Expected: `✔ No issues` (sqlfluff + yamllint clean).

- [ ] **Step 5: Push (hand to the user if the classifier blocks)**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-focus-integration push
```

Then confirm dbt Cloud CI is green on the PR before declaring done.

---

## Self-Review

**1. Spec coverage.** Plan 1's slice of the spec is "Architecture → ingestion
(Fork 1 = REST API) + dbt staging (normalize the source to one common shape)."
Covered: contacts ingestion via the validated one-call recipe (Tasks 3, 5), Avro
schema from the existing `Contact` model (Tasks 1–2), Miami resource (Task 4),
external source (Task 6), normalized student-grain + guardian-grain staging
incl. the gendered-relationship derivation (Tasks 7–8). Deferred-by-design and
called out in Scope: eligibility/identity/`status_report` join (Plan 2), Focus
output + transport (Plan 3), medical columns (gated). No in-scope spec
requirement is unaddressed.

**2. Placeholder scan.** No TBD/TODO/"handle edge cases"/"similar to Task N."
Every code step shows full content. The one genuine unknown — exact
Avro→BigQuery struct/array field names — is handled by an explicit inspection
step (Task 7 note + Task 9 Step 2) with concrete commands, not a guess; the
field names used come from the live-validated design (`race_ms`,
`assigned_school_ss`, `mdcps_id_txt`, etc.).

**3. Type/name consistency.** `CONTACTS_SCHEMA` (Task 2) is consumed in Task 5.
`build_finalsite_contacts_asset(code_location, schema)` signature (Task 3)
matches its call (Task 5). `FINALSITE_RESOURCE` (Task 4) is registered as
`"finalsite"` (Task 5), matching the asset's `finalsite: FinalsiteResource`
parameter. The asset key `[kippmiami, finalsite, contacts]` (Task 3) matches the
source `meta.dagster.asset_key` (Task 6, `project_name` → `kippmiami`) and the
staging `source("finalsite", "contacts")` (Tasks 7–8). `RelatedContact` (Task 1)
supplies the `relationship.contact.*` fields read in Task 8. Staging SQL output
columns match their contract YAML column lists (Tasks 7–8).

One open item for the implementer to confirm against live data (not a blocker):
the guardian PowerSchool-Contact-ID attribute key is assumed
`powerschool_contact_id` (Task 8) — verify the exact `field_name` against
`id_attributes` once data lands and adjust if Miami's tenant uses a different
slug.
