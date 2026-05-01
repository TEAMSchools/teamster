# CLAUDE.md — `src/cube/`

Cube semantic layer on top of BigQuery. Exposes `kipptaf_marts` to BI tools and
LLM chatbots with row- and column-level access control.

## Structure

```text
src/cube/
  cube.js                    # Driver config, contextToGroups, queryRewrite, canSwitchSqlUser
  package.json               # @cubejs-backend/bigquery-driver + @cubejs-backend/server
  model/
    cubes/                   # Private cube definitions (public: false)
      attendance/
      conformed/             # dim_dates, dim_locations, dim_regions, dim_school_calendars, dim_terms
      students/
    views/                   # Public views with access_policy
      attendance/
        attendance_detail.yml
        attendance_summary.yml
```

`.env` is gitignored — see `.env.example` for required vars. Never commit env
var values.

## Architecture

**Cubes** (`model/cubes/`) are always `public: false`. Raw cube members are
never queryable directly — they exist only to be composed into views.

**Views** (`model/views/`) are public. Each view selects members from one or
more cubes via `includes:` and gates access via `access_policy:`. Views come in
two shapes per domain:

- `*_detail` — individual-level data. Gated on `cube-access-student-data` or
  `cube-access-staff-data` with a PII sub-tier (`cube-access-student-pii`,
  `cube-access-staff-pii`) that unlocks direct identifiers.
- `*_summary` — aggregate-only, no direct identifiers. Gated on
  `cube-access-student-data` with a single access tier.

## Security Model (`cube.js`)

### `contextToGroups`

Resolves the requesting user's email to their Google Workspace group memberships
via the Admin Directory API. Returns only groups starting with `cube-`.

Cache: per-email, expires at Eastern midnight.

Local dev: set `CUBE_GROUP_MAP` in `.env` —
`{"user@example.com": ["cube-access-student-data"]}`. Never set in Cube Cloud.

Production testing: `CUBE_TESTING_USERS` in Cube Cloud env vars overrides the
Directory API entirely (all users resolved from the map, unlisted users get
`[]`). Remove once Directory API is validated.

### `queryRewrite`

Runs on every query. Enforces two orthogonal controls:

**Column-level (student cube gate):** Users without `cube-access-student-data`
have student cube dimensions/measures stripped from every query. The
`STUDENT_CUBES` array in `cube.js` must list every cube whose `sql_table` is a
student-level fact or dimension. When adding a new student cube, add its `name:`
to `STUDENT_CUBES`.

**Row-level (location scope):** Injects a `dim_locations` filter based on the
user's scope group:

- `cube-network-*` — no filter (full network)
- `cube-region-<slug>-detail|summary` — filter to `region_key = slug`
- `cube-school-<slug>-detail|summary` — filter to `abbreviation = slug`
- No scope group — default deny (empty filter, returns no rows)

**Org hierarchy (staff cubes):** Queries touching `STAFF_CUBES` and lacking
`cube-access-staff-all` get `dim_staff.reporting_chain` segment injected,
limiting results to the user's direct reports.

## Cube YAML Conventions

### Cubes

```yaml
cubes:
  - name: <snake_case> # matches sql_table suffix (e.g. fct_student_attendance_daily -> attendance)
    public: false # always
    sql_table: kipptaf_marts.<mart_table_name>
    joins: ...
    dimensions: ...
    measures: ...
```

**Dimension naming:** use `name: foo` + `sql: foo` for direct column references.
Only use `name: bar` + `sql: CAST(foo AS TIMESTAMP)` (or other expressions) for
computed/renamed dimensions. This distinction matters:
`scripts/sync-cube-descriptions.py` only syncs dbt metadata for dimensions where
`name == sql`.

**Computed dimensions** (where `name != sql`) need manually authored
`description:` — the sync script will not touch them.

**Primary keys** declare `primary_key: true` after `type:`.

**Private measures** (used only in derived measure SQL) are named `_<name>` and
set `public: false`.

### Views

```yaml
views:
  - name: <domain>_detail|summary
    cubes:
      - join_path: <root_cube>
        includes:
          - <measure_or_dimension>
      - join_path: <root_cube>.<joined_cube>
        prefix: true # prefixes members as <joined_cube>_<member>
        includes:
          - <member>
    access_policy:
      - group: cube-access-student-data
        member_level:
          includes: "*"
          excludes: # list PII members excluded at base tier
            - dim_students_full_name
      - group: cube-access-student-pii
        member_level:
          includes: "*"
```

`access_policy` belongs on **views only**, never on cubes.

## Access Groups

| Group                                | What it unlocks                              |
| ------------------------------------ | -------------------------------------------- |
| `cube-network-*`                     | Network-wide row access (no location filter) |
| `cube-region-<slug>-detail\|summary` | Region-scoped rows                           |
| `cube-school-<slug>-detail\|summary` | School-scoped rows                           |
| `cube-access-student-data`           | Student cubes + views                        |
| `cube-access-student-pii`            | Student PII dimensions (names, IDs)          |
| `cube-access-staff-pii`              | Staff PII dimensions                         |
| `cube-access-staff-compensation`     | Salary/compensation fields                   |
| `cube-access-staff-benefits`         | Benefits elections                           |
| `cube-access-staff-observations`     | Observation scores                           |
| `cube-access-staff-all`              | Staff org hierarchy bypass                   |

## dbt Metadata Sync

Dimension `description:` and `meta: {pii: true}` come from the dbt manifest, not
hand-authored in cube YAML. Run after adding a new cube or when dbt descriptions
change:

```bash
uv run scripts/sync-cube-descriptions.py --manifest src/dbt/kipptaf/target/prod/manifest.json
```

The script only patches dimensions where `name == sql`. Review the git diff
before committing — only `description:` and `meta:` lines should change.

Automation (pending `#3727`): a GitHub Actions workflow triggered by a dbt Cloud
webhook will run this automatically and open a PR when descriptions change.

## Development

```bash
cd src/cube
npm run dev        # starts Cube on http://localhost:4000
```

Requires `.env` with at minimum `CUBEJS_DEV_MODE=true`, `CUBE_GROUP_MAP`, and
BigQuery credentials. See `.env.example`.

`CUBEJS_SQL_SUPER_USER` enables the SQL API — set to a superuser email and use
`canSwitchSqlUser` to impersonate `@apps.teamschools.org` accounts.

## Adding a New Cube

1. Create `model/cubes/<domain>/<name>.yml` with `public: false`
2. Run `scripts/sync-cube-descriptions.py` to pull in dbt descriptions
3. If the cube is student-level, add its `name:` to `STUDENT_CUBES` in `cube.js`
4. If the cube is staff-level, add its `name:` to `STAFF_CUBES` in `cube.js`
5. Create `model/views/<domain>/<name>_detail.yml` and
   `model/views/<domain>/<name>_summary.yml` with appropriate `access_policy`
