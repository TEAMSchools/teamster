# Report-card feeds

The four `rpt_deanslist__*` feeds deliver nightly at 01:25 (Dagster
`deanslist-annual.yaml`, json.gz to DeansList's SFTP). This file carries the
routing and verification procedures; the exact ladders and cut points live in
the reference doc's "DeansList report-card extracts" section — a deep dive for
when a label or threshold itself is in question. "RT reporting term" below means
the term windows typed `RT` in the reporting-terms sheet, per school.

## Which feed carries a subject

- ELA ("Text Study", Writing folded in) and Math reporting-group averages →
  `mod_standards` (the "overall" course grades, all grades).
- Every other K-4 subject → `mod_assessment` (the Enrichment table).
- K-4 standard-domain and progress-report performance → `mod_standards_domains`
  (the mastery pages).
- Sight words → `rpt_deanslist__sight_words` (the K-1 sight-words table).

A subject can be on two tables at once: its average in the Enrichment table
(`mod_assessment`) and its standard-domain mastery in the mastery pages
(`mod_standards_domains`) — route by which table the report card actually shows.
The date and region tags live in
`kipptaf_google_appsheet.stg_google_appsheet__illuminate_assessments_extension`.

## A score is missing from a report card

A score already visible on the DDI Suite is tagged, synced, star-ticked and
refreshed — the triage ladder is satisfied, so skip it and check the report-card
path only, in order:

1. **The gate.** `mod_standards_domains` and non-Unit-Assessment scopes of
   `mod_assessment` require the student's region in `regions_report_card` (or
   `regions_progress_report` for the PR branch). Untagged Unit Assessments pass
   the enrichment feed anyway; `mod_standards` needs only
   `is_internal_assessment`, no region tag.
2. **The population.** `mod_assessment` and `mod_standards_domains` are K-4 only
   (enrollment `grade_level < 5`, `rn_year = 1`); `mod_assessment` and
   `mod_standards` are current-year only.
3. **The term.** `term_administered` is the RT reporting term containing the
   (possibly tag-overridden) `administered_at` for the student's school — a
   wrong date tag moves the score to another term or drops it.
4. **The band.** `mod_assessment` and `mod_standards` inner-join the band sets;
   a response with no matching band row drops. Same-day scores can sit unbanded
   until the midnight band sync (#5399).
5. **DeansList itself.** The CDO lands nightly; a fixed row appears on the next
   delivery, not immediately.

## Verifying a published average

`rpt_gsheets__deanslist_mod_audit` (the DeansList Mod Audit sheet) holds the
pre-aggregation response rows with `computed_avg_pct_correct` reproducing each
feed's GROUP BY. Compare it to the published `avg_pct_correct` /
`avg_percent_correct`, minding three scope gaps:

- Years: the audit holds current + prior year; `mod_assessment`/`mod_standards`
  publish current only; `mod_standards_domains` publishes every year.
- Writing: the audit keeps `Writing`; `mod_standards` publishes it as
  `Text Study`.
- Bands: the audit has no band join, so it keeps rows the published feeds drop.

## Recurring asks

The shapes schools actually write in about, beyond a single missing score:

- **A whole subject or section missing from (or appearing on) the Enrichment
  table.** Driven by two things jointly: which of that subject's assessments are
  tagged report-card-eligible for the school's region, and what DeansList's
  report-card template for that school shows. The warehouse side is the tag; the
  template side is a DeansList configuration change, not a dbt one (who submits
  template edits is not yet written down — owner to confirm).
- **"Remove X from Enrichment — we no longer offer it."** Untag the region on
  that subject's assessments (or stop assessing it), and ask for the matching
  DeansList template edit; the feed only carries subjects with eligible scored
  assessments, so stale sections usually mean a stale template.
- **A student missing just their enrichment or i-Ready score.** Run the
  missing-score ladder above; the usual ends are no banded `overall` response in
  the term, or the score landing in a different RT term than the report card's.

## Sight words

`rpt_deanslist__sight_words` is raw per-word mastery, current year forward, no
grade or region filter (`retested` counts as mastered). Report cards use the K-1
slice. Duplicate words on a quiz come from duplicated field labels in the
Illuminate repository — the sight-words dashboard's warn test counts them
([qa.md](qa.md)).
