# Cube validation and build skill: design

Issue: #6150. Approved rules carried over from the first tool:
[2026-10-26-cube-validation-approved-rules.md](2026-10-26-cube-validation-approved-rules.md).

## Intent

Cube now serves 43 measures to staff through Claude. The analyst who builds Cube
needs to know that each one gives users the right number, and needs a repeatable
way to add the measures dashboards have and Cube still lacks.

The first tool tried to answer this by capturing a Tableau extract and Cube's
answers in an evening window. For 2 weeks most of the gaps it reported were
timing: the extract, Cube's fact tables and the capture each read the warehouse
at a different moment, and upstream tables rebuild about every 15 minutes. That
tool and its branch are deleted. This design replaces the capture with a
comparison rebuilt from the warehouse at 1 shared moment.

## Goals

1. **Validate** every measure Cube serves today, with the strongest check that
   exists for it, so the analyst can say which numbers users can trust.
2. **Build**: let an analyst say "add this dashboard measure to Cube" and get
   the dashboard's full definition, a drafted Cube member, and a validation of
   the draft.
3. **CI**, later: on a pull request, flag any change to a Cube measure that no
   recorded decision covers.

## Non-goals

- Data quality at the source. A separate project owns monitoring for data
  changes nobody made in code (a new untagged assessment, an edited attendance
  record). This tool runs only when an analyst starts it, and in CI.
- Changing any production tool: no extract refresh, no schedule change, no
  Tableau content change outside a test project.
- Making Cube copy a dashboard. Matching is evidence, not the goal.

## Anti-goals (failure even if it technically works)

- Cube inherits a dashboard's temporary workaround just so the numbers match. In
  the case that shaped this, the dashboard's view excluded an assessment type
  because of a temporary data issue; Cube rightly kept it.
- A measure reads as "validated" when only its internal consistency was checked.
- Timing shows up as a finding. Every disagreement the analyst sees has timing
  ruled out by construction.
- CI that fires on every intended change, so people learn to ignore it.

## Who uses it and what they do

The reader is the Cube analyst. A run ends in a triage list. For each
disagreement the analyst makes 1 of 4 calls:

- **Deliberate**: the difference is intended on both sides. The analyst records
  it, and it stays quiet on later runs.
- **Fix the dashboard**: Cube is right and the dashboard is wrong. It goes to
  the domain's single Asana task for dashboard fixes, and stays quiet while that
  task is open. (The repo's `cube-correct` label names the same ruling.)
- **Fix Cube**: Cube is wrong. It goes to the domain's single GitHub issue for
  Cube fixes. (`cube-wrong` label.)
- **Domain owner**: the analyst cannot tell which side is right. It goes into
  the domain's review issue as "which of these is right?" This happens when a
  disagreement has no SQL or timing explanation.

So each disagreement must arrive small enough to decide: the rows that differ,
grouped by what explains them (for example, assessment type), and where the
difference comes from on each side.

## What was proven before this design

On the Attendance Dashboard capture from 2026-10-22, for average daily
attendance in 2 Miami cells (school and grade):

- Cube's compiled SQL, run with BigQuery time travel (`FOR SYSTEM_TIME AS OF`)
  at the moment of Cube's captured answer, reproduced that answer to 9 decimals.
- The dashboard's view `rpt_tableau__attendance_dashboard`, rebuilt as of 15:00
  ET with its date function pinned, reproduced the real Tableau extract row for
  row and to 9 decimals.
- The same view rebuilt as of Cube's fact-table build (16:44 ET) gave Cube's
  number exactly. The old tool had reported both cells as row gaps; they were
  timing alone.
- Time travel survives dbt's `CREATE OR REPLACE`; retention is 7 days.

Not yet proven: any other measure, view, or workbook formula heavier than an
average.

## Decided by the analyst

- The reader, and the deliberate, fix-Cube and domain-owner calls above. A
  deliberate difference is written into a YAML description.
- Fixes consolidate: 1 Asana task for dashboard fixes and 1 GitHub issue for
  Cube fixes per domain (decided 2026-10-20, carried over).
- Runs happen at 2 moments only: when an analyst starts one, and on pull
  requests.
- In CI, compare new Cube with the dashboard as it will be after the merge, and
  flag only disagreements that are new or changed. CI always runs; a recorded
  decision committed in the pull request keeps an intended change quiet.
- Test Cube's compiled SQL rather than the answer the Cube MCP returns. Cube has
  1 pre-aggregation, on a set schedule.
- Finding comparisons is a step of every validation: the analyst lists the
  measures to validate, and the tool finds every workbook that computes each
  one, not only the dashboard the analyst had in mind (`days_to_90_percent` has
  a comparison on a dashboard the first tool never looked at).
- Source anchors are in the first plan. The analyst enters each figure by hand
  and judges any difference in triage, with no automatic threshold (below).
- Recorded decisions live beside the Cube models: 1 YAML file per Cube view in
  `src/cube/validation/<view>.yml`.
- The tool never posts to Slack. Results go to the terminal and local files, and
  to GitHub only for the domain-owner review issue and CI.
- Build fresh. Do not port the first tool's code. Re-measure each carried-over
  rule before relying on it.
- Defaults accepted: Python in this repo run with `uv run`; a new package; a
  rewritten skill driving a plain command line; Cube's compiled SQL from its
  REST API run in BigQuery; recorded decisions as YAML in the repo; CI as a
  GitHub Actions job.
- One design: the validator in full, the builder and CI in shorter sections,
  each with its own plan later.

## Part 1: the validator

### The shared moment

A comparison happens at a **moment**: 1 build of the Cube fact table the measure
reads. Both sides are rebuilt for that build.

- The dashboard's rows are its `rpt_tableau__*` view rebuilt as of the fact
  build's `start_time`, because a BigQuery job reads its sources as of its
  start. They are the rows the extract would have held had it refreshed from the
  same source data the fact read.
- Cube's answer is its compiled SQL with every base table read
  `FOR SYSTEM_TIME AS OF` the fact build's `end_time`: what Cube served right
  after that build.
- Other tables Cube reads (dimensions) can change between those 2 times. The
  tool fingerprints each one at both times and names any that changed in the
  result, so a dimension rebuild never reads as a finding.
- Build times come from `INFORMATION_SCHEMA.JOBS_BY_PROJECT`
  (`destination_table`, `start_time`, `end_time`), so nobody needs to know a
  schedule. The default is the latest successful build inside the 7-day
  time-travel window.
- Each Cube view in scope reads 1 fact. A measure that reads 2 facts has no
  single moment; the tool refuses it with that reason.
- The compiled SQL is the raw query, not Cube's 1 pre-aggregation. A one-time
  check per view compares the API answer with the compiled SQL at the same time.
- Cube compiles SQL for the security context of the request. The tool mints its
  token for an email with Cube's `network` grant (`src/cube/access.js`), so the
  compiled school filter lists every school, and refuses to run if it lists
  fewer. Testing per-viewer row-level security is out of scope here; the
  `cube-ops` skill covers it.

Why the fact build and not the extract refresh: Cube serves users whatever its
fact held at its last build, while the dashboard's view reads its sources live.
On 2026-10-22 the attendance fact built 3 times while its sources built about 50
times, so at the extract's own refresh time Cube held an older build.

Rebuilding a view as of a moment has rules the first proof hit, each of which
the tool must handle:

- Views cannot time travel. Expand each view recursively into its base tables
  and put the clause on each table. The attendance view expands to 9 views and
  16 tables.
- In BigQuery the table alias comes before `FOR SYSTEM_TIME`.
- dbt's `union_relations` writes table names inside string literals. Leave
  quoted references alone.
- Pin every clock function (`current_date(...)`, `current_timestamp()`,
  `current_datetime(...)`) to the moment. Unpinned, `current_date` added 224
  rows to 1 cell.
- Use each view's SQL as it stood at the moment. `JOBS_BY_PROJECT` keeps the
  `CREATE VIEW` text; git keeps it too.
- External tables (Google Sheets) cannot time travel. Read them as they are now
  and say so in the result.

### Proving the dashboard side once per formula

The warehouse holds the dashboard's rows, but most of its logic lives in the
workbook: aggregations, filters, calculated fields, detail-level calculations.
Only Tableau can say what those produce. So each workbook formula a comparison
relies on is proven once:

- Pair a real Tableau export of the sheet with the extract that produced it.
  Download the workbook with its embedded extract, publish a copy to the
  `TEMP-CB` test project with each measure's number format dropped (so exports
  carry raw values), and export the copy's sheets through the REST API
  (`tableauserverclient`). The copy reads its own embedded extract, so no
  refresh can fall between the 2 reads. The Tableau PAT comes through the pytest
  secrets fixture. The Tableau MCP cannot set a parameter on this server
  (`get-view-data` returns 400), so a parameter cut is exported through REST or
  checked in the browser.
- Write the formula as SQL over the dashboard's rows (a **probe**, the first
  tool's term), filtered the way the sheet filters.
- Export the sheet in its default filter state plus cuts the analyst picks, so
  each filter card is exercised at least once. The probe is proven when it
  reproduces every exported value at the sheet's displayed decimals. Record the
  proof with a fingerprint of the workbook formula and filters it covers.
- Once proven, the probe evaluates any cut. A result for a cut nobody exported
  says so.
- Re-prove only when the workbook changes. Tableau's workbook `updated_at` and
  the formula fingerprint say when.

After that, the dashboard's number at any moment is the proven probe run over
the dashboard's rows rebuilt at that moment. Tableau is not involved again until
the workbook changes.

### Checks, strongest first

Each measure gets every check available, and the result names the strongest one
it has.

1. **Matches a dashboard.** A proven probe over the dashboard's rows at the
   moment, compared with Cube's answer at the same moment, cut the way the
   sheet's filters cut it.
2. **Anchored to a source.** Cube's answer compared with a number from outside
   the warehouse: a source-system report (for example, PowerSchool's or Focus's
   own attendance report) or a figure already filed with the state (NJ SMART,
   Florida FTE, CRDC). Anchor the base counts of a family of measures; the
   consistency checks carry that trust to measures derived from them. The
   analyst enters each figure by hand: the value, its source, its date, and the
   filters it covers. Cube computes the same figure over the same date range. An
   exact match is not expected, because the figure is frozen at its date and
   Cube includes every later edit, so any difference goes to triage for the
   analyst to judge. There is no automatic threshold.
3. **Consistent only.** Cube's own measures agree with each other: for example,
   `avg_daily_attendance` equals `sum_attendance_value` divided by
   `sum_membership_value`, and present plus absent days add up to membership
   days. This catches wiring and formula mistakes, never a wrong definition.

A measure whose strongest check is "consistent only" is never reported as
validated.

### Finding comparisons

When the analyst lists the measures to validate, the tool finds each measure's
comparisons before running anything:

- The dbt exposures name every workbook and the models it reads.
- The workbook's calculated fields show which ones compute something that
  matches the measure.
- The analyst confirms each match before it becomes a check, because a
  name-alike field can mean something else.

### Comparing and explaining

- Compare at row level first: Cube's fact rows and the dashboard's rows at the
  moment, joined on the grain they share (for example, student and day). Each
  row is a match, a value difference, dashboard only, or Cube only.
- Apply the dashboard's own row scope to Cube when Cube exposes the column it
  scopes on (for example, APM shows grades K to 8 only, so compare Cube's K to
  8). The result lists each scope applied. A scope Cube cannot express becomes a
  deliberate difference the analyst records.
- Then compare the numbers per cut at the sheet's displayed decimals.
- Group disagreeing rows by the columns that explain them, and point each group
  at the clause behind it: the filter in the view's SQL, or in Cube's member,
  that keeps or drops those rows. This is how a deliberate exclusion like the
  temporary assessment-type filter shows up.
- The full result goes to the analyst's terminal and local files. Anything
  posted to GitHub (the domain-owner review issue, CI comments) shows counts
  under 10 as `<10`. Row-level output never leaves local files. The tool never
  posts to Slack.

### Recorded decisions

A recorded decision is the analyst's call on a group of disagreements. It
records the measure, the group it covers, the call, the reason, and a
fingerprint of the SQL on both sides at the time of the call.

Decisions live in `src/cube/validation/<view>.yml`, 1 file per Cube view. A pull
request that changes Cube already touches `src/cube/`, so CI finds its decisions
in the same pull request, and the `analytics-engineers` team owns the folder.
They stay out of the view YAML because Cube serves a member's `meta:` to every
caller through `/v1/meta`. Before relying on the folder, confirm Cube Cloud
loads only `src/cube/model/` and ignores YAML beside it.

- A decision keeps its group quiet on later runs while both fingerprints hold.
- If either side's SQL changes, the decision asks to be re-confirmed instead of
  silently covering new rows.
- If the group it covers disappears (the dashboard dropped its workaround, say),
  the tool flags the decision as no longer needed.
- For a deliberate difference, the Cube member's `description:` says what the
  member counts, so a user sees it. The reasoning and numbers go in the decision
  record, per `.claude/rules/comments.md`.

### Result

1 result per run, in this order:

- each requested measure with its strongest check and its verdict
- the triage list: open disagreement groups, each with rows, explanation and
  clause
- decisions applied, decisions needing re-confirmation, decisions no longer
  needed
- any source read as it is now instead of at the moment

Disagreements the analyst sends to the domain owner collect into 1 review issue
per domain, posted only on the analyst's OK.

### Constraints

- Every comparison runs inside the 7-day time-travel window of its moment.
- BigQuery cost: each run prices its queries first with free dry runs and states
  the cost.
- Snapshot-like data (row-level output) holds student-level rows. It stays in
  local files that are never committed. Nothing committed names a person.
- No Tableau sign-in except to prove a formula, and then only reads and a copy
  in a test project.

## Part 2: the builder

The analyst names a dashboard measure and the Cube fact it should come from. The
builder then:

1. Assembles the dashboard's full definition: the workbook formula, its filters
   and detail-level calculations, and the `rpt_tableau__*` view's SQL traced
   upstream (which days it keeps, what it counts as present).
2. Lines that up against the Cube fact's lineage, which is often different: the
   view reads `int_*` models while Cube reads the marts. It lists each place
   they differ.
3. Drafts the Cube member as a proposal the analyst edits. It does not commit
   it.
4. Runs the validator on the draft and hands back the triage list.

The builder replaces the inference work of adding average daily attendance:
working out which days the dashboard left out and what it counted as present.

## Part 3: CI (later)

On a pull request that touches `src/dbt/` or `src/cube/`:

1. Find the affected measures: the Cube members whose models sit downstream of
   the changed models (`state:modified+` in the dbt manifest).
2. Compare new Cube with the dashboard as it will be after the merge, and
   current Cube with the current dashboard.
3. Report only disagreements that are new or changed. Recorded decisions in the
   pull request keep intended changes quiet. Anything they do not cover gets
   flagged, including side effects on measures nobody meant to touch.

Known catch: dbt Cloud CI builds from `zz_stg` copies that lag prod, so both
sides in CI read the same copies.

## Left to the builder

- Package name and layout, command names, file formats beyond "YAML in the
  repo".
- How the skill is structured and what it says.
- Where formula proofs live in the repo.
- How source-anchor figures are stored.
- How CI gets its credentials and the Cube compiled SQL.

## Calls I made (not discussed with the analyst)

- The moment is 1 Cube fact build: dashboard rows as of its start, Cube as of
  its end, with any dimension change between them named.
- A fourth triage call, fix the dashboard, taken from your 2026-10-20 rule of 1
  Asana task for dashboard fixes and the repo's `cube-correct` label.
- The dashboard's row scope is applied to Cube when Cube can express it.
- Formula proofs use a copy in `TEMP-CB` with number formats dropped, exported
  through REST, as the first tool did.
- A probe proven on the default state plus chosen cuts evaluates any cut.
- The tool's Cube token uses an email with the `network` grant.
- A measure that reads 2 facts is refused.
- Decisions carry SQL fingerprints and re-confirm on change.
- A decision whose group disappears is flagged as no longer needed.
- The analyst confirms each comparison the tool finds before it becomes a check.
- A one-time check per view that compiled SQL equals the API answer, to rule out
  row-level security or pre-aggregation effects.
