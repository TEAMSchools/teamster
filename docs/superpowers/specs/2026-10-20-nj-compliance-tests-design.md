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

- Ticket ownership and routing. #5558 defines them; this project only leaves a
  provisional owner hint per test as a YAML comment, taken from the candidate
  catalogs.
- Fixing the data. Tests surface problems; fixes land in PowerSchool, Finalsite,
  or ADP through whatever process #5558 settles on.
- The fate of `rpt_tableau__student_info_audit` and its Tableau workbook
  (#5549).
- Miami. Florida reporting is a separate project with its own rules.

## Anti-goals

- A replica model that grows its own logic. The replica is a projection of
  grain-level intermediates; if it carries a join or a derived column the design
  has failed (see _Replica models_).
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
  Compliance tests therefore sit on tables.
- dbt seeds are banned repo-wide (`src/dbt/CLAUDE.md`, _No seeds_). Lookups are
  external tables or Google Sheets. See _Lookup tables_ for the note on this.
- Staging tests set `severity: error` explicitly; kipptaf and district defaults
  are `warn`. Stored failures are views, and failure rows on student or staff
  models are PII.
- PowerSchool, not dbt, produces the state files. The extract specs are public
  and fetchable; the handbook rules are public and fetchable; the state's copy
  of our data is not (myNJ login, no API).
- Four PowerSchool NJ extension tables the extracts read are not ingested in any
  region: `s_nj_usr_x` (staff SMID and NJ staff fields), `s_nj_sec_x`
  (section-level CDS and SCED overrides, section exclude flag), `s_nj_ssf_x`
  (per-school staff exclude flag), `s_nj_sgr_x` (section start and end dates on
  stored grades). Tests that need them are blocked until ingestion lands.

## Decisions

Numbered in the order they were made in brainstorming on 2026-10-20. Anthony
made each unless marked as the author's call.

### 1. Replica models host the file-level rules

One dbt model per submission reproduces the state file row-for-row from
warehouse data:

- `int_nj_sleds__student_management` (one row per student per snapshot
  population)
- `int_nj_sleds__student_course_roster` (one row per student-section stint)
- `int_nj_sleds__staff_course_roster` (one row per staff-section assignment)

They live in a new kipptaf domain folder `nj_sleds/` (added to `DOMAIN_FOLDERS`
in `scripts/check_dbt_standard.py`, rule A11), materialized as tables, columns
named as the state names them, values in the state's formats. They are the
defending models for #5558, the host for file-level tests (credits earned not
above available credit, one row per continuous stint, grade present when an exit
date exists, section parity between the two rosters), and the pre-upload gate: a
comparison of the replica against the PowerSchool-generated extract before
anyone certifies a file.

The replicas hold no logic. Every join and every derived column lives one level
down in grain-level intermediates that are useful on their own:

- a student-year NJ fields model (student, school, year, every `s_nj_stu_x` and
  `s_nj_ren_x` field the handbook names, materialized as a table; the Student
  Management catalog calls it `njx`),
- a student-section-stint model (the enrollment stint grain, since PowerSchool
  keeps only the latest entry and exit per student-section while the state wants
  one row per continuous stint),
- a section-staff-assignment model (section, staff member, role, allocation,
  assignment dates, with `nj_section_teacher_tracking` rows once ingested).

Where the intermediates live (author's call): the student-year NJ fields model
is single-source, so it is a `powerschool` package model built per region, at
the enrollment-stint grain (`student_number`, `schoolid`, `academic_year`,
`entrydate`, the same grain as `int_students__student_enrollments`), with a
kipptaf `union_relations` passthrough carrying `_dbt_source_project`. The
section-staff-assignment model follows the same shape. The student-section-stint
model extends the existing package `base_powerschool__course_enrollments` grain
rather than adding a sibling (rule A4). Package tests set `severity` explicitly,
since the package default is `error`. The kipptaf replicas read the union
wrappers; a `union_relations` passthrough is the repo's standard cross-region
shape and does not count as logic in the replica.

Snapshot populations (author's call): the Student Management replica carries
every population in one table with a `snapshot` column (`fall`, `end_of_year`,
`graduation`). Membership is computed from a `nj_sleds_report_date` var that
defaults to the run date, so windowed rules (pathways, FAFSA, Seal of
Biliteracy) evaluate against the window that is open on the day the test runs;
the graduation population keys off the prior academic year through August 31, so
July's rollover of `current_academic_year` does not drop last year's graduates
while their snapshot is open.

Pre-upload gate input (author's call, pending confirmation): the
PowerSchool-generated extract for each submission lands in the same drop
location as the portal exports (_Decision 3_) and loads the same way, so the
comparison is a dbt test between two tables.

Reversal cost, stated so the data engineer can weigh it: field-level tests never
sit on the replicas, so removing a replica does not touch them; file-level tests
move one hop up onto the intermediate whose columns they already read, losing
only the state-name aliases and the pre-upload gate.

The July 2026 grade and credit backfill
(`docs/superpowers/specs/2026-07-30-nj-sleds-grade-credit-backfill-design.md`)
ruled out a dbt model for a one-off patch to a native extract. This is a
different purpose; that spec's reasoning does not apply here.

### 2. Lookup tables: HTTP-fetch assets, with a note on seeds

Long NJDOE lists (county/district/school codes, SCED codes, country codes, home
language codes, world language assessment codes, job codes and subcategories,
OPE IDs) are fetched by a Dagster asset per list from the list's nj.gov URL on a
schedule, written to GCS under a dated prefix, and exposed as external tables
through `sources-external.yml`, the same shape as the SFTP file assets with HTTP
in place of SFTP. No human in the loop.

Short stable domains (entry and exit codes, grade levels, course level,
completion status, alpha grade, course sequence, homeless codes) go into
`accepted_values` in the test YAML with the handbook page cited.

Lists KTAF maintains itself (school-to-CDS crosswalk, the entry-code mapping,
Title I status) stay in Google Sheets through `stg_google_sheets__*`.

Note for the data engineer: several of these lists are the textbook case for dbt
seeds, which are short, public, versioned by NJDOE, and change a few times a
year. The repo bans seeds in every project (`seed-paths: []`) and no document we
found records why. Either the reason gets written down in `src/dbt/CLAUDE.md` or
the ban is lifted for public reference data. This spec builds the external-table
path because it works under the ban; it is not an argument that the ban is
right.

### 3. The state's copy of our data: drop folder now, browser skill later

The identity checks (SID exists in NJ SLEDS; the SID's name and birth date match
ours; SMID is registered; the state's resident codes differ from ours) need the
Student Submission export and the Staff Management export from the portal. The
portal requires a personal myNJ account with no API, and a shared robot account
is not acceptable.

Phase 1 (this project): a watched drop location, a Google Drive folder or SFTP
path, where the person with portal access saves each export. A Dagster sensor
picks the file up, projects it to identity and CDS columns only (dropping
demographics, health, program fields, and the masked SSN column), and loads it
like any other file source. Cadence is a calendar reminder: once per submission
window at minimum, weekly while a window is open.

Phase 2 (follow-on issue): a skill the credential holder runs in their own
browser session, using Claude in Chrome or a Playwright script against their
logged-in profile, that downloads both exports and saves them to the drop
location. The credential never leaves their machine. The tests `ref()` the same
table either way.

### 4. Year scope

- Student Management tests cover currently enrolled students plus students who
  exited during the current school year.
- Course roster tests cover the current school year, plus the prior year until
  its official window closes on August 3, then drop it. NJ SLEDS refuses
  prior-year uploads, so a prior-year roster defect is unfixable and must not
  generate tickets.
- This departs from #5558's "tests cover all history" for annual files. The
  departure is deliberate and applies to the rosters only.

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

Singular tests are named `nj_sleds__<submission>__<element>__<rule>`. A rule in
`scripts/check_dbt_standard.py` fails any test under the `nj_sleds` meta that
lacks one of the four keys, and fails any singular test named `nj_sleds__*` that
lacks the meta. The fetch skills (sub-issues 4 and 5) report changes by element,
so this meta is how a change maps to tests.

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

Author's call: where a candidate overlaps an existing test, the existing test
gets the `nj_sleds` meta added; no duplicate is written. Where an existing test
is wrong against the handbook (the three audit checks #5549 names), the fix goes
through #5549, not here.

### 8. Order, regions, and policy checks

Build order: Student Management; then the two course rosters together, because
their year-round checks fire at course and section creation and the parity
checks need both; then the SAR-derived checks, after retirement is confirmed and
the two code defects below are fixed on their own. Within each submission,
field-level tests ship before the replica model and its file-level tests.

All three NJ regions from the first merge. Paterson's missing CDS setup and SCED
gaps are failures to surface, not reasons to exclude it.

KTAF policy checks that are not state rules (an upper bound on co-teachers per
section, staff on sections at schools they do not work at, staff on sections
after their ADP termination, paraprofessionals as teacher of record, more than
one lead teacher at a time) ship as a separate, labeled group with thresholds in
dbt `vars` so Ops can tune them without a code change. The state sets no cap on
co-teachers; its only count rule is that a section marked co-taught needs more
than one staff row.

## Severity

- Ticketable rules (a person can fix the value in a source system):
  `severity: warn`, stored failures, on the earliest routable table.
- Code-defect rules (fields our autocomm feeds write into PowerSchool: entry
  dates, graduation year, retained flag, graduation pathways, FAFSA status;
  replica regression tests; the two SAR defects): `severity: error`. They carry
  the `nj_sleds` traceability meta like every other compliance test but never a
  runbook key, since the fix is a pull request, not a ticket.

## Dependencies and sequencing

| Sub-issue                                                                      | Unblocks                                                                               | Needed by                                                        |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| 1 Ingest `s_nj_usr_x`, `s_nj_sec_x`, `s_nj_ssf_x`, `s_nj_sgr_x` in all regions | every SMID test; section-level overrides and exclude flags; stored-grade section dates | Staff Course Roster wave 2; Student Course Roster override tests |
| 2 Lookup-table home                                                            | every "value on the published list" test                                               | Student Management field tests                                   |
| 3 Portal export drop and load                                                  | identity checks                                                                        | any submission's spine checks                                    |
| 4 NJDOE fetch skill                                                            | change reports                                                                         | ongoing                                                          |
| 5 PowerSchool spec fetch skill                                                 | change reports                                                                         | ongoing                                                          |
| 10 Verify status marts                                                         | program-consistency checks                                                             | SAR checks, several SM checks                                    |

Student Management field tests on existing staging models and the new
student-year NJ fields model can start before 1 to 3 land; their lookup joins
use `accepted_values` until 2 ships.

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

All under `.claude/scratch/nj-compliance-reference/` in the main checkout
(gitignored; no student or staff rows):

- `catalog/<submission>-fields.md`: every element with every rule, cited to the
  handbook page or PowerSchool spec section.
- `catalog/candidate-tests-<submission>.md`: the candidate tests, each with
  predicate, host model, test form, prerequisites, overlap, and confidence;
  "Considered and not proposed" sections list rules declined as stricter than
  the handbook.
- `catalog/existing-tests-inventory.md`, `powerschool-ingestion-gaps.md`,
  `pr4281-runbook-checks.md`, `source-change-cadence.md`.
- `issues/`: the epic and sub-issue drafts.

The catalogs are planning inputs, not the spec. Where a catalog row conflicts
with a decision above, the decision wins.

## Left to the builder

- Exact column lists of the three grain-level intermediates and the replica
  projections; the state's column order and formats are in the handbooks and
  templates.
- Which candidate rows ship in wave 1 versus wave 2 per submission, within the
  order above; the confidence column in each catalog is the starting point.
- The pre-upload comparison's form (a dbt test against a loaded extract, a
  script, or both).
- The HTTP-fetch asset's shape and the external-table schemas per list.
- The drop-folder location and sensor for the portal exports.
- The two fetch skills' structure, following `superpowers:writing-skills`.
