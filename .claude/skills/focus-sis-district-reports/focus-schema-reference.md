# Focus SIS Schema & District Reports Reference

Distilled from Focus's Level 1 Certification training materials and this repo's
`src/dbt/focus` staging models. Focus SIS runs **PostgreSQL** — search for help
specifying that dialect.

## Interface screen → table map

| Focus screen                 | Table                                            |
| ---------------------------- | ------------------------------------------------ |
| Student demographic tabs     | `students`                                       |
| Student Enrollment           | `student_enrollment`                             |
| Student Schedules            | `schedule`                                       |
| Course Catalog               | `master_courses`                                 |
| Subject / Courses / Sections | `course_subjects` / `courses` / `course_periods` |

**`students` is NOT year-specific.** Always join `student_enrollment` to scope
to a school year — that table (not `students`) also carries `grade_id`, since
grade level changes year to year.

## Field type → storage table

| Table                              | Holds                                                                          |
| ---------------------------------- | ------------------------------------------------------------------------------ |
| `students` (or other entity table) | checkbox / text / date custom fields, inline as `custom_NNN`                   |
| `custom_field_select_options`      | pulldown (select-one) option `code` / `label`; decode rule below               |
| `custom_field_log_entries`         | logging-field entries (checkbox/text/date), joined by `field_id` + `source_id` |
| `student_enrollment_codes`         | enrollment/withdrawal code lookup                                              |
| `schools`                          | school name                                                                    |
| `school_gradelevels`               | grade level short name, joined via `student_enrollment.grade_id`               |

Decoding a pulldown value: some fields store the option's `id`, others its
`code` (`prior_state` stores `FL`). Join `source_id` to the field's
`custom_fields.id` with `source_class = 'CustomField'`, match the stored value
against both `id` and `code`, then read `label` — or use `fieldoptionlabel()`
(see _Useful extras_). Matching on `id` alone returns all-null labels for a
code-stored field, with no error. Full rule: `src/dbt/focus/CLAUDE.md`, _Focus
field value codes_.

## Finding a real column name (in order of speed)

1. **Check this repo first**:
   `src/dbt/focus/models/staging/stg_focus__<table>.sql` selects the raw source
   columns — free ground truth for anything already ingested. The Focus name is
   the left side of each `as` (`custom_9 as second_school`). Read the `.sql`,
   not just its `properties.yml` (the properties file may omit columns the model
   doesn't project).
2. **Student Field Setup** — Students → Setup → Student Fields. Categories live
   in `custom_field_categories`, fields in `custom_fields`, joined via
   `custom_fields_join_categories`. Note: `alias` may not be `custom_NNN` for
   renamed system fields — never change a system field's alias.
3. **`all_fields.php`** — append to the Focus root URL
   (`https://<district>.focusschoolsoftware.com/focus/all_fields.php`) to list
   custom field names from frequently-used tables.
4. **Inspect Element** on the field in the Focus UI — the HTML `data-column` /
   `data-alias` attributes give the exact column.
5. **`custom_fields` table** — master registry: `source_class` (owning entity),
   `type`, `column_name`, `default_value`/`fallback_value`, `system`/`required`,
   `deleted`.
6. **No coverage anywhere above** (a module-specific table like
   `positive_behaviors`) — ask the user for a screenshot of the table's columns
   rather than guessing.

## Confirmed core tables

| Table                                                      | Key columns                                                                                                                                                                                                                  |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `students`                                                 | `student_id` (PK), `first_name`, `last_name`, `deleted`                                                                                                                                                                      |
| `student_enrollment`                                       | `student_id`, `school_id`, `syear`, `grade_id`, `start_date`, `end_date`, `custom_9` (null/`'N'` = primary/home-campus record)                                                                                               |
| `schools`                                                  | `id` (PK), `title`, `deleted`                                                                                                                                                                                                |
| `school_gradelevels`                                       | `id` (PK), `short_name`                                                                                                                                                                                                      |
| `users`                                                    | `staff_id` (PK), `first_name`, `last_name`, `deleted`                                                                                                                                                                        |
| `schedule`                                                 | `student_id`, `school_id`, `syear`, `course_period_id`, `start_date`, `end_date`                                                                                                                                             |
| `course_periods`                                           | `course_period_id` (PK), `school_id`, `course_id`, `teacher_id`, `title`, `short_name`, `syear`, `active`, `period_id`                                                                                                       |
| `courses`                                                  | `course_id` (PK), `short_name`                                                                                                                                                                                               |
| `master_courses`                                           | joined to `courses` on `short_name` (many-to-1 catalog)                                                                                                                                                                      |
| `student_report_card_grades`                               | `student_id`, `course_history` (`'Y'` = official history row), `course_num`, `credits`, `credits_earned`, `grade_title`, `percent_grade`, `custom_5`/`custom_6` (district/school of credit), `custom_7` (grade level earned) |
| `custom_field_log_entries`                                 | `field_id` (join key — never `legacy_field_id`), `source_id`, `source_class`, `log_field1..N` (all VARCHAR regardless of field type)                                                                                         |
| `students_join_address` → `address`                        | `sja.residence = 'Y'` for primary address                                                                                                                                                                                    |
| `students_join_people` → `people` → `people_join_contacts` | `sjp.custody = 'Y'`, `sjp.deleted IS NULL`, `sjp.sort_order = 1` = enrolling parent                                                                                                                                          |

Soft-delete convention: `deleted` is `NULL` for live rows (never `0`) on
`students`, `users`, `schools`, and most entity tables — filter
`WHERE deleted IS NULL`.

## The canonical "active enrollment" predicate

Don't under-specify this — a bare `end_date IS NULL` misses students with a
future-dated end date and doesn't exclude a non-primary enrollment record for a
student enrolled at more than one school:

```sql
se.syear = {syear}
AND se.start_date <= current_date
AND (se.end_date IS NULL OR se.end_date >= current_date)
AND (se.custom_9 IS NULL OR se.custom_9 = 'N')
```

The `current_date` checks assume `{syear}` is the current year. Run for a past
year, no enrollment row covers today and the report returns empty with no error.
When a report must work for past years, swap `current_date` for an optional Date
variable: `coalesce(nullif('{AS_OF}', '')::date, current_date)`.

Same shape for `schedule` (active roster membership), using `>` for `end_date`
since a schedule row's end date is exclusive of that day:

```sql
sch.start_date <= current_date
AND (sch.end_date IS NULL OR sch.end_date > current_date)
```

## Join patterns

| Style                         | When                                                                                                                                                                                                |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FROM a, b WHERE a.id = b.id` | Older pattern, still seen in Focus's own examples — avoid for new queries                                                                                                                           |
| `JOIN b ON a.id = b.id`       | Default — drops rows with no match                                                                                                                                                                  |
| `LEFT JOIN b ON a.id = b.id`  | Use whenever the right side is optional — classically `custom_field_select_options` for a pulldown field, since not every row has a value. A regular `JOIN` silently drops every row with no value. |

Filters that should preserve a `LEFT JOIN`'s unmatched rows belong in that
join's `ON` clause, not in the outer `WHERE` — a `WHERE` condition on the
right-hand table collapses the `LEFT JOIN` back to an inner join.

## Report variables

| Type                       | Behavior                                                                                                                                              |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Checkbox                   | User selects from checkboxes                                                                                                                          |
| Date                       | User picks a date                                                                                                                                     |
| Pull-down                  | Static options, one per line as `label [value]`                                                                                                       |
| Pull-down (Multiple)       | Same, multi-select                                                                                                                                    |
| Pull-down Query            | Options generated by a SQL query at runtime — `SELECT title, value` (or `value AS value, title AS title`, both orders appear in Focus's own examples) |
| Pull-down (Multiple) Query | Same, multi-select — **defaults to all options selected** when the report runs, so no extra "select all" handling is needed for an unfiltered default |
| Text / Integer / Numeric   | Free-entry, parameterized                                                                                                                             |
| URL Parameters             | Value supplied via the report's URL, not user input                                                                                                   |
| Student Group / User Group | User picks a saved dynamic/custom group                                                                                                               |

**Substitution is raw, unquoted text** — `{VARIABLE}` is inserted into the SQL
as-is. Numeric system variables (`{syear}`, `{school_id}`, `{student_id}`) are
used bare; a text comparison needs your own quotes (`ac.title = '{status}'`).
For an **optional** Text/Date variable (blank = no filter), quote-and-nullif it
yourself:

```sql
AND (nullif('{START_DATE}', '') IS NULL OR pbt.school_date >= nullif('{START_DATE}', '')::date)
```

### System variables

| Variable               | Meaning                                         |
| ---------------------- | ----------------------------------------------- |
| `{date}`               | Current date                                    |
| `{syear}`              | Currently selected school year                  |
| `{staff_id}`           | Currently selected/logged-in user               |
| `{student_id}`         | Currently selected/logged-in student            |
| `{marking_period_id}`  | Currently selected marking period               |
| `{school_id}`          | Currently selected school                       |
| `{course_period_id}`   | Currently selected section                      |
| `{original_staff_id}`  | Originally logged-in user (survives "login as") |
| `{logged_in_staff_id}` | Logged-in user                                  |
| `{report_id}`          | ID of the running report                        |

## Report configuration

| Setting             | Notes                                                                                                                                           |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Profiles            | Blank = visible to **everyone**; you must also select your own profile to see the report you're building                                        |
| Schools             | Restricts which schools' users can access it — separate from row-level filtering, which still needs `{school_id}` in the query                  |
| Freeze Left Columns | Number of leftmost columns pinned while scrolling                                                                                               |
| Chart               | Requires the `SELECT` to include an aggregate with a column alias                                                                               |
| Portal Alert        | Runs on **every** portal page load for users with access — keep the query fast, or it delays the whole portal                                   |
| SSRS Report         | Different report type entirely — invokes a report-server template by exact name; needs exactly one variable flagged "Holds SSRS Template Names" |
| Multiple queries    | Semicolon-separated in the Edit box; each becomes its own result dataset/tab                                                                    |
| Export              | Bypasses the 20,000/50,000-row in-screen display limit — always the right choice for a full data pull                                           |

## Known platform limitation

The report grid is a flat, paginated table — it does **not** dynamically pivot a
dimension into columns the way some other systems' analysis tools do (e.g.
turning distinct category values into side-by-side columns). When a source
report wants that shape:

- Ship a **long-format** breakdown query instead (one row per
  entity-per-category) as a second semicolon-separated dataset, and say
  explicitly that it's the flat-grid equivalent, not a literal recreation.
- Or enable **Chart** on an aggregate query for a simple bar/pie view.
- Or tell the user to export and pivot in Excel/Sheets if they need the exact
  wide layout.

## Useful extras

- **Barcode column**: `s.student_id AS student_id_barcode` renders a scannable
  barcode in the report output.
- **Form Builder deep link**:
  `/Modules.php?modname=form-builder/requests/instance-viewer/[instance_id]/[editable]`
  links directly to a specific form instance.
- **Clickable student link** (Verify: copied from Focus training. Here
  `custom_53` is `local_student_id` and `student_id` is Focus's internal key;
  confirm which one the URL's `student_id=` takes against a working link):
  ```sql
  CONCAT(
    '<a href="https://<domain>/',
    REPLACE(current_database(), 'yourdb_', ''),
    '/Modules.php?modname=Students%2FStudent.php&student_id=',
    COALESCE(s.custom_53, ''), '&school_id=', se.school_id,
    '#!1" target="_blank">', s.student_id, '</a>'
  ) AS student_url_link
  ```
- `fieldoptioncode(s.custom_xxx)` / `fieldoptionlabel(s.custom_xxx)` — shortcuts
  for resolving a select-option field without a manual join to
  `custom_field_select_options`.
- `time_to_decimal(t text)` — converts a time value to decimal hours, used for
  attendance sums.

## Adjacent Focus features (not District Reports, but query-driven)

These use the same SQL/schema knowledge but live elsewhere in Focus: **Execute
SQL** (runs on field save), **Validations** (query-based save blocking/warning),
**Computed Fields/Tables** (read-only, query must alias the value column `value`
and include the entity's id column), **Automated Cron Messages** (scheduled
query-driven emails). Ask the user for specifics if a request turns out to be
one of these instead of a District Report.

## Safety note (out of scope for District Reports, in scope if asked)

District Reports are read-only `SELECT`. If a request drifts into `UPDATE`/
`DELETE`, always write and run the `SELECT` version first to confirm the exact
row set, and create a `CREATE TABLE ... AS SELECT` backup before any mutation.
