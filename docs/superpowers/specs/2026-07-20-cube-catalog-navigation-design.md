# Cube Data Catalog — Navigation and Field Finder Design

**Issue:** Refs #4438 (continuation of the Cube API reference / field catalog
work)

## Problem

`docs/reference/cube-data-catalog.md` is a single ~600-line generated page with
a flat list of `## {view_name}` sections. Two usability gaps:

1. **No domain-level navigation.** Sections are raw machine names
   (`student_attendance_view`, `staff_pii`) in file order — no human-friendly
   grouping to orient a reader landing on the page.
2. **No way to find a field across views.** A reader who knows they want a field
   but not which view exposes it has to scroll or `Ctrl-F` the whole page.

## Goals

- Group views by **domain**, derived from the `src/cube/model/views/` folder
  structure, with human-friendly headings.
- A visible top-of-page domain index plus a sidebar TOC that mirrors Domain ->
  View.
- A single **Find a field** table spanning every view, **sortable and
  filterable** in the browser.
- **Future-proof:** domains are discovered from the folder layout at generation
  time. Adding a new `views/{domain}/` folder later must surface a new domain
  automatically — no hardcoded domain list anywhere.

## Non-goals

- No change to the freshness check contract (`--check` and the CI workflow keep
  working; all page changes live in the generator).
- No interactivity on the per-view tables — only the Find-a-field table.
- No external JavaScript library or CDN dependency.

## Design

### Domain derivation (folder-structure-driven)

Each view's domain is the **first path segment under `views_dir`** — i.e.
`path.relative_to(views_dir).parts[0]`. A view placed directly in `views_dir`
(no subfolder) falls back to the domain `Other`.

Domain slug -> friendly title is a general transform (no lookup map): replace
`_` with space, title-case each word, and keep known acronyms uppercase (`PII`).
Examples from today's folders:

| Folder (`views/...`)  | Domain title        |
| --------------------- | ------------------- |
| `staff`               | Staff               |
| `student_attendance`  | Student Attendance  |
| `student_assessments` | Student Assessments |
| `students`            | Students            |

View titles use the same transform on the view `name`, with a trailing `_view`
stripped first: `student_assessment_scores_view` -> "Student Assessment Scores",
`staff_pii` -> "Staff PII".

Ordering is deterministic: domains sorted by slug, views sorted by `name` within
a domain.

### `ResolvedView` gains a `domain` field

`parse_views` captures the domain slug while walking the tree and stores it on
each `ResolvedView` (alongside the friendly title, computed at render time or
stored). This is the only new state the parser needs.

### Page structure

```text
# Cube data catalog
{banner}
{intro}

## Views by domain          <- human-friendly jump index
### Staff
- Staff Directory (`staff_directory`) — {one-line summary}
- Staff PII (`staff_pii`) — {one-line summary}
### Student Attendance
- Student Attendance (`student_attendance_view`) — ...
...

## Find a field             <- master sortable/filterable table

## Staff                    <- one H2 per domain
### Staff Directory         <- one H3 per view; exact name as code beneath
#### Access
#### Measures
#### Dimensions
##### {folder}
### Staff PII
...
## Student Attendance
...
```

Headings increment by one level (MD001-safe): domain H2, view H3, section H4,
folder H5. The sidebar TOC (`toc.integrate`, already enabled) mirrors the Domain
-> View tree.

The one-line summary in the index is the first sentence of the view
`description` (truncated), or the placeholder if none.

### Find a field table

One row per exposed field across all views:

| Column    | Content                                                         |
| --------- | --------------------------------------------------------------- |
| Field     | exact `exposed_name` as code                                    |
| View      | friendly view title, linked to that view's section anchor       |
| Domain    | domain title                                                    |
| Type      | member type                                                     |
| Kind      | `measure` or `dimension`                                        |
| Sensitive | `Yes` when `exposed_name` is in `SENSITIVE_MEMBERS`, else empty |

No description column — full descriptions stay in each view section; the finder
stays scannable. Rows are emitted sorted by field name for a stable default.

### Interactivity — self-contained vanilla JS

New `docs/javascripts/cube-catalog.js`, wired via one `extra_javascript` entry
in `mkdocs.yml`. Behavior:

- Subscribe to Material's `document$` observable (fires on initial load and on
  every instant-navigation) so it re-initializes correctly.
- Locate the Find-a-field table by the `find-a-field` section anchor (the table
  immediately following that heading) — no inline HTML in the generated
  Markdown, so no MD033 concern.
- Inject a text `input` above the table; on `keyup`, hide rows whose text does
  not contain the query (case-insensitive).
- Make each column header click-to-sort (toggle asc/desc) with a small homegrown
  comparator (numeric-aware). ~50 lines, no dependency.

Rationale for homegrown over vendoring `tablesort`: no new package, no CDN, no
offline-build breakage, no license to track — the behavior is small.

### Freshness check

All Markdown changes are produced by the generator, so `_normalize` /
`check_stale` / the CI workflow are unaffected. The JS file and `mkdocs.yml`
entry live outside the generated file and are not part of the check.

## Testing

- **Move the fixture**
  `tests/scripts/fixtures/cube_ref_sample/views/sample_view.yml` into a domain
  subfolder (`views/sample_domain/sample_view.yml`) so tests exercise the same
  folder -> domain path logic as the real model.
- **Update** existing structural assertions: the page now has one `## ` per
  domain (plus `Views by domain` and `Find a field`) and one `### ` per view,
  not one `## ` per view.
- **Add** tests for:
  - domain derivation from the folder (`sample_domain` -> "Sample Domain");
    fallback to `Other` when a view sits directly in `views_dir`.
  - friendly-title transform (trailing `_view` stripped; `PII` uppercased).
  - the Find-a-field table: a row per field, correct `Sensitive` flag, View cell
    links to the view anchor.
  - deterministic domain/view ordering.
- The JS is static and not unit-tested by pytest; verify by building the site
  and driving the page (filter narrows rows; header click sorts).

## Files touched

| Path                                            | Change                                                                |
| ----------------------------------------------- | --------------------------------------------------------------------- |
| `scripts/generate_cube_reference.py`            | domain capture + friendly titles + restructured render + finder table |
| `tests/scripts/test_generate_cube_reference.py` | updated + new tests                                                   |
| `tests/scripts/fixtures/cube_ref_sample/views/` | fixture moved into a domain subfolder                                 |
| `docs/reference/cube-data-catalog.md`           | regenerated                                                           |
| `docs/javascripts/cube-catalog.js`              | new — filter + sort for the finder table                              |
| `mkdocs.yml`                                    | `extra_javascript` entry                                              |
| `docs/CLAUDE.md` / `scripts/CLAUDE.md`          | note the JS dependency if warranted                                   |

## Edge cases

- A domain with a single view whose friendly title matches the domain title
  (e.g. `Student Attendance` domain containing the `Student Attendance` view)
  renders an H2 and H3 with the same text; anchors auto-dedupe. Harmless.
- Empty or missing `description` -> placeholder summary in the index, consistent
  with the per-view sections.
- Prettier pads the regenerated table; committed churn is expected, same as the
  rest of the catalog.
