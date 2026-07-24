# Cube Data Catalog — Navigation and Field Finder Design

**Issue:** Refs #4438 (continuation of the Cube API reference / field catalog
work)

**Preview:** an interactive MkDocs-Material mockup of this design — built from
the real member list resolved from the repo model — is published for team review
at <https://claude.ai/code/artifact/21187c36-25a1-4749-a9b8-543c2072eadc>.

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
- A single **Find a field** finder spanning every view, **filterable** in the
  browser (a text filter plus a Measures quick-filter).
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

## Find a field             <- two-column finder (filter + Measures quick-filter)

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

Per-view rendering notes:

- A view's **Measures** table (and likewise **Dimensions**) is emitted only when
  that kind has members — never an empty table.
- Member **names stay on one line** in these tables (no mid-word wrapping); the
  Name column sizes to fit.
- Dimensions retain the existing **folder grouping** (H5). The shared preview
  flattens them for brevity; the generator keeps folders.

### Find a field

A two-column **glossary** spanning every view — one row per exposed member,
listing the complete member set (278 members today), not a curated subset:

| Column  | Content                                           |
| ------- | ------------------------------------------------- |
| Field   | exact `exposed_name`, monospace, kept on one line |
| Details | a tag row, then the full description              |

The **Details** cell holds, in order:

1. a **link to the field's view section** (`↗ {View Title}`),
1. a **domain** tag,
1. a **kind** tag (`measure` / `dimension`),
1. a **type** tag (data type),
1. a **sensitive** tag — only when the member is sensitive,

then the full **description** beneath the tags. Tags are lowercase and share one
calm translucent-blue style; the **sensitive** tag is the single exception,
rendered in the warning orange. Rows default to domain-then-field order. The
full description is shown (not truncated) so the filter can match on its text.

**Sensitivity is per member, not per view.** The `sensitive` tag is driven by
the generator's curated `SENSITIVE_MEMBERS` set (personal contact, DOB,
demographics, student identifiers) matched against each member's exposed name —
NOT by the member's view. Blanketing a whole view is wrong: `staff_pii` pulls in
non-PII join dimensions (e.g. `dates_academic_year`, locations) that must not be
tagged. The set deliberately excludes directory-public names like `full_name`
(the `staff_directory` roster is open). This is a hint, not authoritative (the
access policy is), and it matches bare names only — a follow-up (#4450-style)
should source per-member sensitivity from model metadata for full fidelity.

**Rendering approach.** The finder is emitted as a **pure-Markdown table**
(`| Field | Details |`), NOT raw HTML — keeping the generated file free of
inline HTML avoids markdownlint `MD033` and, crucially, keeps prettier and the
`_normalize` freshness comparison working exactly as they do for the per-view
tables. Per-tag styling is applied at runtime: the Details cell carries the view
link plus the tags as backtick code spans (`` `staff` `` `` `dimension` ``
`` `string` `` and, when sensitive, `` `sensitive` ``) followed by the
description; the JS enhancer classifies those code spans by content and restyles
them as chips. Before JS runs they degrade gracefully to inline code. Material's
search indexes the visible text either way.

### Interactivity — self-contained vanilla JS

New `docs/javascripts/cube-catalog.js`, wired via one `extra_javascript` entry
in `mkdocs.yml`. Behavior:

- Subscribe to Material's `document$` observable (fires on initial load and on
  every instant-navigation) so it re-initializes correctly.
- A **filter box** above the finder: on input, hide any row whose full text —
  field, tags (domain / kind / type / sensitive), view, and description — does
  not contain the query (case-insensitive). A description keyword narrows the
  table even when the field name is unknown.
- A **"Measures" quick-filter** button beside the box: when active, show only
  `measure` rows; it combines with the text filter. A Dimensions counterpart can
  be added later if useful.
- The finder is capped to ~10 rows with its own **vertical scroll**, its header
  pinned within that scroll box. This sticky is scoped to the finder only — the
  per-view member tables use normal, non-sticky headers so they never float over
  their rows on the long page.
- **No sort controls:** ordering is domain-then-field; filtering is the find
  path.

Material's site-wide search independently indexes all of this page text, so
description keywords are also discoverable through the top search box.

No external library or CDN — the filter / scroll behavior is a few dozen lines
of vanilla JS.

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
  - the Find-a-field finder: a row per exposed member; the sensitive tag present
    only for sensitive members; the view link points at the view section;
    measures precede dimensions in domain-then-field order.
  - measures/dimensions tables omitted when a view has none of that kind.
  - deterministic domain/view ordering.
- The JS is static and not unit-tested by pytest; verify by building the site
  and driving the page (filter narrows rows; the Measures quick-filter limits to
  measures; the finder scrolls within its box).

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
