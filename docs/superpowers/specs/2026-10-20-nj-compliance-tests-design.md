# NJ compliance dbt tests — design

Design spec for the epic "NJ compliance data tests for the SLEDS student and
course roster submissions" (issue number assigned when the drafts in
`.claude/scratch/nj-compliance-reference/issues/` are posted). Refs #5558,
#5549, #5861, #4281.

## Intent

KTAF's New Jersey state submissions are built from PowerSchool data, and the
warehouse has no tests for the rules the state enforces on them. Problems are
found by hand in the week before each window closes, or by the state after
upload. This project encodes the published rejection rules for four submissions
as dbt data tests, in the shape #5558 needs so each failure can later become a
ticket with an owner:

- Student Management (Fall snapshot taken 5 PM October 15; End-of-Year window
  October 19 to June 30; Graduation snapshot in July and August).
- Student Course Roster (official window July 2 to August 3; inputs accumulate
  all year).
- Staff Course Roster (same window).
- The checks behind the Student Assessment Registration report (no longer
  submitted; the accommodation and test-assignment rules still drive vendor
  pre-ID files and the accommodations dashboard).

Student Management goes first. It is the largest (92 elements, 134 candidate
tests) and its End-of-Year window is open now.

## Goals

- Every mandatory element and every published rejection rule for the four
  submissions has a dbt test, or a written reason it cannot have one.
- Every test points back to the state rule it encodes, so a handbook or
  PowerSchool spec change can be traced to the tests it affects.
- No new test duplicates an existing one.
- Tests run in all three NJ regions from the first merge. Paterson is never
  carved out of a check; where its setup is incomplete, the test fails.
- The reference material the tests depend on (code lists, handbooks, PowerSchool
  specs, the state's own copy of our data) refreshes on a schedule rather than
  living in downloads.

## Non-goals

- Ticket ownership and routing. #5558 defines them; this project leaves a
  provisional owner hint per test as a YAML comment, taken from the candidate
  catalogs, and nothing routes on it.
- Fixing the data. Tests surface problems; fixes land in PowerSchool, Finalsite,
  or ADP through whatever process #5558 settles on.
- The fate of `rpt_tableau__student_info_audit` and its Tableau workbook
  (#5549).
- Miami. Florida reporting is a separate project with its own rules.

## Anti-goals

- A model built only to host tests. No model reproduces a state file; file-level
  rules are tests on models that already exist (see _Decision 1_).
- Tests scoped to one region, or a region excluded "for now".
- Waivers. A failure that looks like it needs a waiver is either a wrong test or
  missing cleanup in the SQL (#5558, "No waivers").
- Roster tests that fire forever on prior-year records nobody can change.

## Constraints

- #5558's pattern governs test placement: a warn-level ticketable test on the
  earliest model that carries record id, school, region, and period; a defending
  model below it; error-level regression tests on the defending model and on any
  model that rebuilds the same logic from raw inputs.
- A test re-runs only when its host model materializes, and the data-change
  automation rematerializes tables, not views (`.claude/rules/dbt-yaml.md`).
  Compliance tests therefore sit on tables. The PowerSchool staging models are
  tables in every NJ district project, so they qualify.
- dbt seeds are banned repo-wide (`src/dbt/CLAUDE.md`, _No seeds_): a seed
  commits data to the repo, so any data change needs a code change and a
  redeploy. Lookups are external tables or Google Sheets (_Decision 2_).
- Staging tests set `severity: error` explicitly; kipptaf and district defaults
  are `warn`. Stored failures are views, and failure rows on student or staff
  models are PII.
- Under `dbt build`, a failing `error` test skips every model downstream of its
  host. An error-level compliance test therefore never sits on an intermediate
  that other models read (_Severity_).
- PowerSchool, not dbt, produces the state files. The extract specs are public
  and fetchable; the handbook rules are public and fetchable; the state's copy
  of our data is not (myNJ login, no API).
- Four PowerSchool NJ extension tables the extracts read are not ingested by dlt
  in any region: `s_nj_usr_x` (staff SMID and NJ staff fields), `s_nj_sec_x`
  (section-level CDS and SCED overrides, section exclude flag), `s_nj_ssf_x`
  (per-school staff exclude flag), `s_nj_sgr_x` (section start and end dates on
  stored grades). Tests that need them are blocked until ingestion lands.
  `s_nj_usr_x` already has a staging model, `stg_powerschool__s_nj_usr_x`, on
  the archived ODBC path; its ingestion work adds the dlt path under that model
  and does not write a second one.

## Decisions

Numbered in the order they were made in brainstorming on 2026-10-20. Anthony
made each unless marked as the author's call.

### 1. File-level rules are tests on existing models; no replica models

Revised 2026-11-12 in review on #6029. The first draft had one replica model per
submission and a student-section stint rollup; review dropped all four.

No model reproduces a state file. The file-level rules are tests on the
PowerSchool staging tables, the earliest models that can route a ticket, and the
columns they need already exist:

- Credits earned not above credits available: `earnedcrhrs` against
  `potentialcrhrs` on `stg_powerschool__storedgrades`.
- Grade present when an exit date exists: `stg_powerschool__cc.dateleft` joined
  to `stg_powerschool__storedgrades.grade` on `studentid` and `sectionid`.
- Section parity between the two rosters: `stg_powerschool__cc.sectionid`
  against `stg_powerschool__sectionteacher.sectionid`. Until `s_nj_sec_x` is
  ingested this test also flags sections meant to be excluded, and its
  description says so.
- No overlapping `cc` rows for the same student and section.

`cc` stores a dropped enrollment with a negative `sectionid`, so these tests
compare on `abs_sectionid`.

`cc` keeps one row per stint, not only the latest entry and exit per
student-section. Across all history in prod on 2026-11-12, student-section pairs
with more than one row number 10,181 in Newark, 2,323 in Camden, and 107 in
Paterson. The later rows take three shapes (same region order):

- Overlapping the previous row (656 / 205 / 0). This is bad source data; the
  overlap test above is `warn` and ticketable.
- Starting after a gap (6,916 / 1,854 / 94). This is a real second stint. The
  state wants a row for each, and `cc` has one.
- Starting the day the previous row ended (3,120 / 332 / 13). This is one
  continuous stint split in two. The state wants one row per continuous stint,
  and only the generated file shows whether PowerSchool's extract merges them.
  It is the one extract question left on stints (_Verification steps_, step 6).

Pre-upload check: tests on the PowerSchool-generated file itself. The file for
each submission lands in the same drop location as the portal exports (_Decision
3_) and loads the same way, and its staging model hosts the checks only the
finished file can answer, starting with one row per continuous stint. The check
runs only when someone drops the file each window. That person is not yet named;
it is an open question for Compliance (_Open questions_), and the pre-upload
check does not ship until it is answered.

Field-level tests sit on grain-level intermediates that carry the NJ fields
beside school, region, and period:

- a student NJ fields model, one row per student, with every `s_nj_stu_x` field
  the handbook names. `s_nj_stu_x` holds only current values, so at this grain a
  bad value fails once and opens one ticket, not one per stint.
- a stint NJ fields model, one row per enrollment stint (`student_number`,
  `schoolid`, `academic_year`, `entrydate`, the grain of
  `int_students__student_enrollments`), with every `s_nj_ren_x` field the
  handbook names. The Student Management catalog calls these two models together
  `njx`.
- a section-staff-assignment model (section, staff member, role, allocation,
  assignment dates, with `nj_section_teacher_tracking` rows once ingested),
- a Student Management population model (student x snapshot, see _Snapshot
  populations_ below).

Where the intermediates live (author's call): the two NJ fields models and the
section-staff-assignment model are single-source, so each is a `powerschool`
package model built per region and materialized as a table, with a kipptaf
`union_relations` passthrough carrying `_dbt_source_project`. Package tests set
`severity` explicitly, since the package default is `error`. The population
model is kipptaf, in a new domain folder `nj_sleds/` (added to `DOMAIN_FOLDERS`
in `scripts/check_dbt_standard.py`, rule A11).

Snapshot populations (author's call): the population model,
`int_nj_sleds__student_management_population`, at student x snapshot grain,
holds the membership logic. It reads a `nj_sleds_report_date` var that defaults
to the run date and emits a row for each population whose window is open on that
date. For 2026-27 the windows are `fall` (July 6 to October 15), `end_of_year`
(October 19 to June 30), and `graduation` (July 6 to August 31, keyed on the
prior academic year so July's rollover of `current_academic_year` does not drop
last year's graduates while their snapshot is open). A student in two open
windows is two rows. Rows for a closed window do not exist, because `s_nj_stu_x`
holds only current values, a closed window cannot be corrected, and a stale Fall
row would be the "fires forever" anti-goal. Windowed rules (pathways, FAFSA,
Seal of Biliteracy) join this model to the NJ fields models on keys and read the
`snapshot` column.

Window dates are not SQL literals. NJDOE sets them each year (the 2026-27 Fall
and End-of-Year openings are both Mondays), so they live in a Google Sheet, one
row per school year and window, read through a `stg_google_sheets__*` model
(author's call; a dbt var would also keep them out of SQL, but makes each year's
dates a code change).

The population table carries `dbt_cron_automation_condition`, set through a
daily `cron_schedule` under `meta.dagster.automation_condition`. A table
otherwise rebuilds only on an upstream data or code change, and crossing a
window date is neither, so without the cron the table would keep a closed
window's rows until PowerSchool happened to update. The dbt Cloud CI job pins
`nj_sleds_report_date` so test results can be reproduced.

No window is open from October 16 to 18 or from July 1 to 5. Both yield an empty
population and no failures. Whether those gaps are intended, and which school
year "exited during the current school year" means across the July rollover, is
an open question for Anthony and Compliance (_Open questions_).

The population model reads enrollments from `stg_powerschool__students` and
`stg_powerschool__reenrollments`. The state requires no-shows (exit date not
after entry date) in the file, and neither
`base_powerschool__student_enrollments` nor
`int_powerschool__student_enrollment_union` keeps them: both hold zero such rows
in every NJ region. The `students` rows of that shape likely include graduates
as well as no-shows, so the population rule has to tell them apart.
`includeinnjsmart_tf` is blank for about 99.6 percent of students and cannot be
the filter. Verification step 1 confirms the population rule against the
generated file.

Field-level tests use _Decision 4_'s scope plus the graduation population
through August 31, so graduation-only rules keep firing on last year's graduates
while their window is open.

### 2. Lookup tables: fetch assets for NJDOE lists, Google Sheets for KTAF lists

Lists NJDOE publishes as spreadsheets on the NJ SLEDS Key Documents page
(county/district/school codes, SCED codes, home language codes, world language
assessment codes, job codes and subcategories, OPE IDs) are fetched by a Dagster
asset per list on a schedule, written to GCS under a dated prefix, and exposed
as external tables through `sources-external.yml`, the same shape as the SFTP
file assets with HTTP in place of SFTP. No human in the loop. District Point of
Contacts is left out. The CIP and Industry-Valued Credential lists are added
only if career and technical education fields come into scope.

One generic loader will not read these workbooks correctly. The asset:

- takes settings per list for sheet name, header row, and text columns. Row 1 of
  every sheet is a sentence describing the table, headers sit on row 2, 3, or 5,
  codes depend on leading zeros (`01`, `0010`, `000`), and the job-code list
  mixes category rows such as "Administrators" in with the codes.
- reads only the named sheets and columns. The Updates sheet of the
  county/district/school workbook reports about 77,500 rows by 16,383 columns.
- fails loudly when a column or URL changes, and retries only transient errors.
- skips a file whose `Last-Modified` header has not changed.
- dates the GCS prefix in local time.
- reads `.xlsx` with `openpyxl`, a new dependency, so it ships with an image
  rebuild.

Every workbook has an "Updates" sheet listing dated adds, removals, and renames.
The NJDOE fetch skill (sub-issue 4) can read those instead of comparing files.

Country codes are the exception. NJDOE publishes them only as
`Country-Codes.pdf` (handbook Appendix C), whose own text says the list is
current as of March 2005. They are copied once into a Google Sheet.

Short stable domains (entry and exit codes, grade levels, course level,
completion status, alpha grade, course sequence, homeless codes) go into
`accepted_values` in the test YAML with the handbook page cited.

Lists KTAF maintains itself (school-to-CDS crosswalk, the entry-code mapping,
Title I status, the country codes, the window dates in _Decision 1_) stay in
Google Sheets through `stg_google_sheets__*`.

Why not seeds: a seed commits data to the repo, so any data change needs a code
change and a redeploy (`src/dbt/CLAUDE.md`, _No seeds_). Lists KTAF maintains
belong in Google Sheets, and a list another organization publishes at a stable
URL is the case the fetch asset exists for.

### 3. The state's copy of our data: drop folder now, pull method open

The identity checks (SID exists in NJ SLEDS; the SID's name and birth date match
ours; SMID is registered; the state's resident codes differ from ours) need the
Student Submission export and the Staff Management export from the portal. The
portal requires a personal myNJ account with no API, and a shared robot account
is not acceptable.

Phase 1 (this project): a watched drop location, a Google Drive folder or SFTP
path, where the person with portal access saves each export. A Dagster sensor
picks the file up, projects it to identity and CDS columns only (dropping
demographics, health, program fields, and the masked SSN column), and loads it
like any other file source. The trimmed export still holds names and birth
dates, so its identity columns carry `config.meta.contains_pii: true`. Cadence
is a calendar reminder: once per submission window at minimum, weekly while a
window is open.

Phase 2 (follow-on issue): a way for the credential holder to pull both exports
without clicking through the portal by hand. The method is open. NJDOE's New
User Toolkit calls an API a long-term strategy, not a current option, and review
found bot protection in front of the myNJ login, so a scripted login is out.
What is still unknown is what the Export button does after login. Before Phase 2
picks a method, the person with portal access records a HAR file while clicking
Export once (who that is: _Open questions_). If the export is a single HTTP
request, a small script that reuses their own browser session cookie is simpler
than browser automation. Either way the credential never leaves their machine,
and the tests `ref()` the same table.

### 4. Year scope

- Student Management tests cover currently enrolled students plus students who
  exited during the current school year.
- Course roster tests cover the current school year, plus the prior year until
  its official window closes on August 3, then drop it. NJ SLEDS refuses
  prior-year uploads, so a prior-year roster defect is unfixable and must not
  generate tickets.
- Both scopes depart from #5558's "tests cover all history". The departure is
  deliberate: a state file is a point-in-time certification, and a record the
  state will never accept again is not a ticket anyone can close.

### 5. Program status: the marts are the referee

Every consistency check that compares a PowerSchool NJ field against a program
status reads the status from `dim_student_iep_status`, `dim_student_ell_status`,
and the current 504 derivation. A disagreement means the PowerSchool state field
is wrong. Where a mart itself reads the PowerSchool field being tested, that
test is circular and is dropped.

Anthony was not involved in those marts' design and will verify them before
tests depend on them; issue draft `10-verify-status-marts.md`.

### 6. Ownership and routing are out of scope

Each test carries a provisional owner hint as a YAML comment, taken from the
candidate catalogs (school registrar or ops, school scheduler, HR, Compliance,
SRE-enrollment, data team). Nothing routes on it. #5558 owns the rest.

The hint does not stand in for the test's description. Every `warn` test also
gets a description naming the source system, what is wrong, and what to change
there, as _Warn, defend, error_ in `.claude/rules/dbt-yaml.md` requires.

### 7. Traceability: a `meta` contract on every compliance test

Every compliance test carries:

```yaml
config:
  meta:
    nj_sleds:
      submission: student_management # | student_course_roster | staff_course_roster | assessment_registration
      element: ResidentMunicipalCode # the state's element name
      citation: "Student Management Data Handbook v2.2 (Oct 2026) p.41" # or a PowerSchool spec section
      catalog_id: SM-12
```

Singular tests are named `nj_sleds__<submission>__<element>__<rule>`. A
test-metadata check fails any test under the `nj_sleds` meta that lacks one of
the four keys, and fails any singular test named `nj_sleds__*` that lacks the
meta. The check lives in its own script, not in `scripts/check_dbt_standard.py`,
which covers the architecture rules only. #5558's ticketing keys need the same
kind of check, so one test-metadata script covers both. The fetch skills
(sub-issues 4 and 5) report changes by element, so this meta is how a change
maps to tests.

The meta is traceability, not a ticket marker. Every compliance test carries it,
including the error-level code-defect tests, so a handbook change traces to them
too. What makes a test ticketable is `severity: warn` plus, once #5558 lands,
its runbook key; this project sets severity and leaves the runbook key to #5558.

Stored-failure shape (answered by #5558): `accepted_values`, `unique`,
`relationships`, and `unique_combination_of_columns` store a value and a count,
not the failing rows. #5558 plans to override those four to `select *` for
ticketed tests. This project writes generic tests in their normal form and
relies on that override; until it lands, their stored failures are value-level,
which is enough for engineers and not yet enough for a punch list.

Author's call on overlaps: where a candidate overlaps an existing test that can
serve as written (same predicate, a table host, the right scope and severity),
the existing test gets the `nj_sleds` meta added and no duplicate is written.
Where the existing test cannot serve (its host is a view, so it never re-runs;
its scope is all history; it is a package uniqueness test at error where the
rule should warn and ticket), the compliance test is written on the compliance
host with an extra meta key `overlaps: <existing test name>`, and the existing
test is left alone, since its current consumers depend on its behavior. "No
duplicate" means no second test with the same predicate on the same host. Where
an existing test is wrong against the handbook (the three audit checks #5549
names), the fix goes through #5549, not here.

### 8. Order, regions, and policy checks

Build order: Student Management; then the two course rosters together, because
their year-round checks fire at course and section creation and the parity
checks need both; then the SAR-derived checks, after retirement is confirmed and
the two code defects below are fixed on their own. Within each submission,
field-level tests ship before file-level tests.

The first deliverable stands alone: the Student Management field tests that can
sit on models that exist today. It ships ahead of the ingestion work, the fetch
assets, the drop-folder sensor, and the two skills, and depends on none of them.
Its code-list checks use `accepted_values` until the lookup tables ship.

All three NJ regions from the first merge. Paterson's missing CDS setup and SCED
gaps are failures to surface, not reasons to exclude it.

KTAF policy checks that are not state rules (an upper bound on co-teachers per
section, staff on sections at schools they do not work at, staff on sections
after their ADP termination, paraprofessionals as teacher of record, more than
one lead teacher at a time) ship as a separate, labeled group. Where their
thresholds live is open and Ops' call (_Open questions_): a dbt `vars` change is
a code change, so only a Google Sheet lets Ops tune them without one. The state
sets no cap on co-teachers; its only count rule is that a section marked
co-taught needs more than one staff row.

## Severity

- Ticketable rules (a person can fix the value in a source system):
  `severity: warn`, stored failures, on the earliest routable table, each with
  the description _Decision 6_ requires.
- Code-defect rules (fields our autocomm feeds write into PowerSchool: entry
  dates, graduation year, retained flag, graduation pathways, FAFSA status; the
  two SAR defects): `severity: error`. They carry the `nj_sleds` traceability
  meta like every other compliance test but never a runbook key, since the fix
  is a pull request, not a ticket. An error-level test sits only on a model that
  nothing outside this project reads (the NJ fields models, the population
  model, a loaded-file staging model), so a data blip in an autocomm-fed field
  cannot stop unrelated reporting. Where the only possible host is an
  intermediate other models read, the test is `warn` with no runbook key
  (author's call).
- Extract-defect rules (a third bucket, author's call): failures caused by how
  PowerSchool's extract behaves rather than by a source value or our code
  (touching `cc` rows left as two stints, blank program fields filled on output,
  legacy codes translated). They are error-level tests on the loaded generated
  file (_Decision 1_, pre-upload check), carry the meta, and get no ticket; the
  fix is a PowerSchool setup change or a vendor case. A correct value the state
  might still reject, such as an accented legal name, is not a failure at all:
  the handbook says nothing about accents, and "no waivers" means the test is
  wrong, not the name.

## Dependencies and sequencing

| Sub-issue                                                                      | Unblocks                                                                               | Needed by                                                        |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 1 Ingest `s_nj_usr_x`, `s_nj_sec_x`, `s_nj_ssf_x`, `s_nj_sgr_x` in all regions | every SMID test; section-level overrides and exclude flags; stored-grade section dates | Staff Course Roster wave 2; Student Course Roster override tests |
| 2 Lookup-table home                                                            | every "value on the published list" test                                               | Student Management field tests                                   |
| 3 Portal export drop and load                                                  | identity checks                                                                        | any submission's spine checks                                    |
| 4 NJDOE fetch skill                                                            | change reports                                                                         | ongoing                                                          |
| 5 PowerSchool spec fetch skill                                                 | change reports                                                                         | ongoing                                                          |
| 10 Verify status marts                                                         | program-consistency checks                                                             | SAR checks, several SM checks                                    |

Sub-issues 6 to 9 are the per-submission test issues. They block nothing, so the
table leaves them out.

The first deliverable (_Decision 8_) needs none of 1 to 5. The two NJ fields
models and the tests on them follow it and also start before 1 to 3 land.

## Verification steps the builder runs first

Facts the catalogs could not settle from documentation alone, each a task in the
plan before the dependent tests are written:

1. Obtain the last generated Student Management file and the NJ SLEDS error
   report for it. Settle whether PowerSchool fills blank program fields on
   output (Title I is blank on about 98 percent of enrolled students, homeless
   on about 87 percent) and whether it translates legacy codes (graduates stored
   as G1, exit codes T1/PR/TO/RE/TS/D2, entry codes P/OE/R/RT, immigrant status
   mixing Y/N with 0/1). Eleven SM candidates depend on the first answer, six on
   the second.
2. Confirm which of the two PowerSchool graduation-year fields the report reads;
   they disagree for about 63 percent of enrolled students.
3. Confirm the SAR's retirement with Compliance and capture the successor specs
   (TIDE Student File, NJSLA/NJGPA-Adaptive templates).
4. Confirm which PowerSchool roles the staff extract's role mapping excludes;
   859 SY2025-26 assignment rows put Gradebook Access or Blended Learning staff
   at 100 percent allocation.
5. Confirm what produces KTAF's Staff Management file and whether it sends ADP
   legal names or PowerSchool preferred names (60 first and 31 last names differ
   among roster-eligible staff).
6. Obtain a generated Student Course Roster file and check whether PowerSchool
   merges `cc` rows that start the day the previous row ended into one stint
   (_Decision 1_).

## Known defects to fix on their own

Found while cataloging, counted 2026-10-20, each a code or setup fix with its
own small issue or PR rather than a compliance test:

- Math state assessment code `'4'` means DLM in
  `int_reporting__promotional_status` but not in
  `rpt_gsheets__nj_state_test_roster`.
- `rpt_gsheets__nj_state_test_roster` ignores `asmt_exclude_ela` and
  `asmt_exclude_math`.
- `SchoolEntryDate` equals `DistrictEntryDate` for every enrolled student
  because autocomm writes both from one value; the handbook defines school entry
  per school.
- About 320 current-year stints carry entry code R13, which the handbook defines
  as returning to the resident district from a charter.
- Newark has 2 courses with 2-character course IDs (232 roster rows); Camden 6
  courses with no SCED code; Paterson AY2025 has 443 rows whose section exit
  date is July 1; every region's grade scales include `F*`, not a legal state
  value; Paterson students carry no accountable or testing-site CDS codes.

## Inputs the builder plans from

The catalogs are committed beside this spec at
`docs/superpowers/nj-sleds-compliance/catalog/`, so the `catalog_id` meta key
points at something permanent and reviewers can open what the spec rests on. The
first plan task adds a `decision` column recording each candidate row's
disposition (ship, decline with reason, defer with link), which also satisfies
the first goal's "written reason it cannot have one". They hold aggregate counts
only, no student or staff rows, and any count of students or staff under 10
reads "fewer than 10".

- `catalog/<submission>-fields.md`: every element with every rule, cited to the
  handbook page or PowerSchool spec section.
- `catalog/candidate-tests-<submission>.md`: the candidate tests, each with
  predicate, host model, test form, prerequisites, overlap, and confidence;
  "Considered and not proposed" sections list rules declined as stricter than
  the handbook.
- `catalog/existing-tests-inventory.md`, `powerschool-ingestion-gaps.md`,
  `pr4281-runbook-checks.md`, `source-change-cadence.md`.

The epic and sub-issue drafts are not committed; they stay under
`.claude/scratch/nj-compliance-reference/issues/` in the main checkout
(gitignored) until they are posted.

The catalogs are planning inputs, not the spec. Where a catalog row conflicts
with a decision above, the decision wins. The catalogs were written before
review, so rows that name a replica model or the stint rollup as their host move
to the hosts _Decision 1_ names.

## Open questions

- Who drops the PowerSchool-generated file for each submission each window, and
  who records the one-time HAR file of a portal export (_Decisions 1 and 3_).
  Owner: Compliance. The pre-upload check and Phase 2 both wait on a name.
- Who supplies the last generated Student Management file and its NJ SLEDS error
  report (_Verification steps_, step 1).
- Whether the two stretches with no open window (October 16 to 18 and July 1
  to 5) are meant to run no population tests, and which school year "exited
  during the current school year" means across the July rollover. Owners:
  Anthony and Compliance.
- Where policy-check thresholds live, dbt `vars` or a Google Sheet. Owner: Ops.

## Left to the builder

- Exact column lists of the four grain-level intermediates; the state's column
  order and formats are in the handbooks and templates.
- Which candidate rows ship in wave 1 versus wave 2 per submission, within the
  order above; the confidence column in each catalog is the starting point.
- The external-table schemas per list, and each list's sheet, header-row, and
  text-column settings.
- The drop-folder location and sensor for the portal exports and the generated
  files.
- The two fetch skills' structure, following `superpowers:writing-skills`.
