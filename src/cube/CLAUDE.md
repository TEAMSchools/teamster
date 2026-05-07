# CLAUDE.md — `src/cube/`

Cube semantic layer. BigQuery driver; cubes read from `kipptaf_marts` tables
produced by [`src/dbt/kipptaf/`](../dbt/kipptaf/). Setup, env vars, and Cube
Cloud deployment: [`docs/guides/cube.md`](../../docs/guides/cube.md).

## Layout

```text
src/cube/
  cube.js                   # Auth, group resolution, queryRewrite, sql-user gating
  package.json              # Cube server + bigquery driver + googleapis
  .env.example              # Hook-blocked — Read/Grep return errors; ask user to inspect
  model/
    cubes/
      <domain>/<name>.yml   # Fact and dim cubes — private at cube level
      conformed/            # Shared dims joined from multiple fact cubes
    views/
      <domain>/<name>.yml   # Analyst-facing views — the only public surface
```

One cube or view per file. Filename matches `name:`. New cubes go under
`cubes/<domain>/`; cross-domain shared dims (dates, regions, locations, terms,
school_calendars) go in `cubes/conformed/`.

## Authoring conventions

- **Cubes private, views public.** Every cube YAML gets `public: false` at the
  cube level. Dimensions/measures use `public: true` only when meant to be
  exposed via a view. Never flip a cube to `public: true`.
- **Naming.** Fact cubes unprefixed (`attendance`); dim cubes match the
  warehouse table (`dim_students`). View names are `<domain>_<grain>`
  (`attendance_detail`, `attendance_summary`). `sql_table` always points at
  `kipptaf_marts.<table>` — cubes never read district datasets directly.
- **Joins use cube-reference syntax** (`{dim_x.col} = {CUBE}.col`), not raw
  identifiers. Dim joins from facts set `relationship: many_to_one`.
- **Avoid diamond paths.** Two join paths to the same dim → either a compound
  join on the canonical path (see `attendance.yml` → `dim_school_calendars`) or
  a degenerate FK with no declared join (see
  `dim_student_enrollments.location_key`). Comment the choice.
- **Time dimensions** must cast to `TIMESTAMP` in the dim's `sql:`; joins from
  facts cast through (`CAST({CUBE}.date_key AS TIMESTAMP)`).
- **Hidden helper measures** prefix with `_` and set `public: false` (see
  `_sum_attendance_value` building blocks).
- **`meta.folders` is the only Cube-rendered `meta.*` key.** Put guidance in
  `description:`, not `meta.usage` / `meta.synonyms` / etc. — those land in
  `/v1/meta` but Cube Cloud and the chat agent don't read them.
- **Folders group dimensions only.** Cube Cloud separates measures natively;
  don't list measures under `members:`.
- **Folder member naming.** Bare for top-cube members; `<prefix>_<member>` for
  `prefix: true` joins, where `<prefix>` is the last `join_path` segment — so
  `dim_regions_region_name` for the two-hop
  `attendance.dim_locations.dim_regions`.
- **Branch schema validation is manual.** Cube Cloud Staging Environments don't
  auto-create from pushes. Open Cube Cloud → Data Model → Dev Mode → add branch
  by name to spin up a per-branch staging instance.

## View access policies

Views own access via `access_policy:`. Two patterns:

- **Detail views** (row-level, contain student identifiers): two policy blocks —
  `cube-access-student-data` with `member_level.excludes` listing PII fields
  (names, DOB, all `*_student_identifier`, `salesforce_contact_id`), and
  `cube-access-student-pii` with `includes: "*"`.
- **Summary views** (no direct identifiers, demographic breakdowns only): single
  `cube-access-student-data` block with `includes: "*"`. Add a comment
  explaining why no PII tier is needed.

When adding a field to a detail view, decide PII status per project CLAUDE.md
FERPA guidance. If PII, add it to the `excludes` list under the
`cube-access-student-data` policy block.

## `cube.js` security model

Default-deny, group-driven. Read [`cube.js`](cube.js) before modifying.

- **`contextToGroups`** resolves the requester's email to `cube-*` Google
  Workspace groups via the Admin Directory API, cached until next midnight ET.
  Two bypass paths (priority order):
  - `CUBE_TESTING_USERS` — Cube Cloud testing/staging only, never production.
  - `CUBE_GROUP_MAP` — local dev only, gated on `NODE_ENV !== "production"`.
- **`queryRewrite`** enforces three filters:
  - Strips dims/measures from `STUDENT_CUBES` for users without
    `cube-access-student-data`.
  - Adds a `dim_locations` filter based on the highest-priority scope group:
    network (no filter) → region (`region_key`) → school (`abbreviation`). No
    scope group → empty `IN ()` filter (default deny).
  - For queries touching `STAFF_CUBES`, injects the `dim_staff.reporting_chain`
    segment unless the user has `cube-access-staff-all`.
- **`STUDENT_CUBES` / `STAFF_CUBES` arrays.** Entries must match the cube
  `name:` field — `queryRewrite` matches via `startsWith` on
  `<cube_name>.<member>` query members. Both arrays are currently placeholders
  flagged TODO in `cube.js`; when adding a new student-data or staff-data cube,
  append its `name:` to the matching array.
- **`canSwitchSqlUser`** only allows the SQL super-user to impersonate
  `@apps.teamschools.org` accounts (Superset integration). Do not broaden the
  suffix check.

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
