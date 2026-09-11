# Cube sandbox — build, sync, and prove it

## Summary

Build the synthetic-data sandbox that
[#4501](https://github.com/TEAMSchools/teamster/pull/4501) named as Deliverable
2 but did not specify. Five pieces, in build order: prove the isolation, declare
the coverage contract, generate the data, gate the drift, pin the model version.

This spec is a child of
[2026-08-06-cube-partner-shape-first-integration-design.md](2026-08-06-cube-partner-shape-first-integration-design.md).
Read that first. It settles the integration shape, the token-exchange path, the
partner obligations, and the repoint. This spec expands only its
[Deliverable 2 — the sandbox](2026-08-06-cube-partner-shape-first-integration-design.md)
section, and changes exactly one of its decisions.

Tracked in [#5266](https://github.com/TEAMSchools/teamster/issues/5266).

## What changed since the parent spec

### MasterBorn is building a kit, not a product

The parent spec models MasterBorn as building one application. They are building
a **developer kit** that KTAF internal developers use to build many
applications. That inserts a third tier the parent spec has no design for:

| Tier | Who        | What they hold                      | Data they see  |
| ---- | ---------- | ----------------------------------- | -------------- |
| 1    | MasterBorn | The kit source, sandbox credentials | Synthetic only |
| 2    | KTAF devs  | An app built on the kit             | Synthetic only |
| 3    | KTAF staff | The finished app                    | Production     |

The consequence that drives this whole spec: **a wrong assumption in the kit
gets frozen and copied into every app built on it.** A single application can
carry a misunderstanding of `access_policy` and only its own users suffer. A kit
propagates it. So the sandbox's job is not to look like production — it is to
_teach the awkward parts_ of the access model, loudly, before the kit freezes a
guess about them.

That reframe is why Pieces 2 and 3 below exist at all. The parent spec's
fidelity rule stated the right intent in prose. A kit needs it asserted by a
script.

### Cube confirmed a separate deployment with a separate data source

The only open question blocking the build is closed. The parent spec's analysis
of why a branch environment cannot work
([`CUBEJS_API_SECRET`](../../../src/cube/CLAUDE.md) is deployment-wide) stands
unchanged.

## Decisions

| Decision                                                     | Status                              |
| ------------------------------------------------------------ | ----------------------------------- |
| Hosted Cube Cloud deployment over a sandbox BigQuery project | Confirmed, per parent spec          |
| Sandbox holds zero real records, always                      | Confirmed, per parent spec          |
| No de-identified mirror                                      | Confirmed, per parent spec          |
| **Deploy the sandbox deliberately, not by tracking `main`**  | **Changed from the parent spec**    |
| Local Cube Core container as the daily surface               | Considered and declined, 2026-09-11 |

### The one change: pin a tag, do not track `main`

The parent spec says the sandbox deployment tracks `main`, reasoning that a
tracking sandbox matches production's catalog by construction. That is the wrong
default for a consumer outside KTAF. Matching production _instantly_ means a
model change merged on a Tuesday afternoon breaks MasterBorn's in-flight build
with no warning and no changelog.

Deploy the sandbox deliberately instead. Bumping it is an act by the
analytics-engineering team, and each bump ships a diff report of added, removed,
and retyped members as a release note. The sandbox still matches a known
production state exactly — just a state both sides agreed to move to.

The drift gate in Piece 4 is what makes this safe rather than stale: it measures
the distance between the deployed state and current production, so a pin that
has drifted too far is visible rather than silent.

**Correction, 2026-09-11.** An earlier draft said "deploy from a tag named
`sandbox-YYYY.MM.DD`". Cube Cloud has no such setting. Its Build & Deploy tab
offers exactly 2 modes, and neither takes a tag:

| Mode            | Source                                   | Production build fires       |
| --------------- | ---------------------------------------- | ---------------------------- |
| Deploy with Git | A chosen **production branch**           | On every push to that branch |
| Deploy with CLI | Whatever `npx cubejs-cli deploy` uploads | Only when that command runs  |

The intent survives; the mechanism changes. See
[Piece 5](#piece-5--deploy-the-model-deliberately) for the 2 ways to get it and
which to prefer. Confirm the modes in the console before building, the same way
the credential-scoping facts in the parent spec were confirmed — this is read
from vendor documentation, not observed.

### Why the local container was declined

A local Cube Core container with the synthetic data baked in was the strongest
alternative considered. The dialect audit supports it: 129 YAML files under
`src/cube/model/`, and exactly 2 non-portable SQL expressions, so the model
layer would mount byte-identical against DuckDB.

It was declined on 2026-09-11 in favor of a single hosted surface. Recording the
reason it _would_ have cost work, for whoever reconsiders:
[`cube.js:93-137`](../../../src/cube/cube.js) builds an `@google-cloud/bigquery`
client from `CUBEJS_DB_BQ_PROJECT_ID` and reads `dim_locations` and
`dim_staff_cube_access` directly with backtick-quoted identifiers. Identity
resolution, not the model layer, is what pins Cube to BigQuery. A local engine
therefore needs an injected query function in `resolveAccess`, which is a real
seam in KTAF's own code.

Because the container is out, two things stay as the parent spec has them:
`cube.js` needs no new seam, and persona switching remains a write to the
sandbox `dim_staff_cube_access` table rather than a container restart. The
parent spec's gated `act_as` passthrough therefore stays in scope.

## Piece 1 — prove the isolation before any data exists

The sandbox deployment's service account gets no IAM on `teamster-332318`. This
is the parent spec's claim; this piece makes it a test that runs before there is
anything to protect.

Every other guarantee in the design is downstream of this one, so it is the
first thing built and the first thing verified.

### The Organization Policy constraint may not be available

The first draft of this spec preferred a **GCP Organization Policy constraint**
denying cross-project IAM bindings, on the reasoning that an absence of role
grants is undone by one well-meaning IAM edit six months from now, while a
constraint refuses the edit.

Whether that control exists here is unresolved. Two things were checked in the
console on 2026-09-11:

- `teamster-332318` shows **no organization** row on its IAM Settings page, so
  it has no organization parent.
- `cbaldor@apps.teamschools.org` sees no organizations when creating a project,
  and cannot create one.

Those two facts point in opposite directions, and the reconciliation matters.
With no organization anywhere, creating a project needs no role at all — only a
billing account — so the permission error implies an organization **does** exist
for the `apps.teamschools.org` Workspace domain. The likely state: new projects
created by a Workspace user land inside that organization, while
`teamster-332318` predates it or was moved out.

So the question is not "does an organization exist" but **where the sandbox
project lands once someone with the right role creates it.** If it lands inside
the organization, the constraint is available and should be applied. If it lands
outside, it cannot be. Resolve this when the project is created, not before.

### The substitute, and the primary control either way

Do not wait on that resolution. Run the isolation check on a schedule as a
Dagster asset check, not only at build time. A one-time proof answers "was it
isolated when we built it"; a scheduled one answers "is it isolated now", which
is the question that matters after an IAM edit nobody remembers making.

Wire the check so a failure blocks the generator, the same way the drift gate in
Piece 4 does. An isolation regression must stop synthetic-data writes, because
at that point the sandbox's central guarantee is gone.

Treat the Organization Policy constraint as a second layer to add if it turns
out to be available, never as a replacement for the scheduled check. A
constraint proves the binding cannot be created; the check proves the read
actually fails. Those are different claims, and the design wants both.

Acceptance: a test confirms the sandbox service account cannot read
`teamster-332318.kipptaf_marts` at all, and that test runs on a schedule rather
than once.

## Piece 2 — declare the coverage contract before generating data

Write the manifest generator first. Not the data generator — the thing that says
what the data must contain.

`scripts/sandbox_coverage_manifest.py` reads `INFORMATION_SCHEMA.COLUMNS` for
the 20 `kipptaf_marts` tables, parses the 6 views' `access_policy` blocks, reads
`SENSITIVE_TIERS` in [`access.js`](../../../src/cube/access.js), and emits
`src/cube/sandbox/coverage_manifest.yml` with every required cell listed and
marked `uncovered`.

### Required cells

- **Every column**: at least 1 null row and 1 non-null row. Measured against
  production on 2026-09-11: **230 columns across the 20 tables, every one of
  them nullable and none nested.** So the "unless declared not-nullable"
  exemption never fires — 460 column cells with no exceptions, the bulk of the
  manifest.
- **Every `*_scope` enum value the code handles**: at least 1 fabricated
  `dim_staff_cube_access` row. There are **7 scope columns, not 6** —
  `student_location_scope`, `staff_location_scope`, `staff_department_scope`,
  `staff_pii_scope`, `staff_compensation_scope`, `staff_observations_scope`,
  `staff_benefits_scope`.
- **Every derived state `buildGroups` branches on**: `hasRemit` and `hasChain`
  each true and false. An empty remit or chain takes the no-group default-deny
  path rather than emitting a group, because Cube throws "Values required for
  filter" on an `equals []` row filter (#4269). That branch is unreachable in
  production by design, so only the sandbox can exercise it.
- **One unresolvable identity**, with no `dim_staff_cube_access` row at all, to
  exercise clean default-deny.
- **Every snapshot anchor**: a true/false mix strictly between 0 and 1, for
  `is_latest_record`, `is_month_end_record`, `is_week_end_record`, and
  `is_current_record`. A uniformly true anchor makes anchored measures look
  additive, and the kit then freezes the wrong aggregation.
- **Every join path**: 1 orphan on each side, as a named fixture a test can
  reference — a mid-year transfer with no attendance, a staff member with no
  reportees, a section enrollment whose stint ended.

### Why the manifest is generated, not hand-written

A hand-written list goes stale silently. A generated one turns a new production
column, view, or scope enum into an **uncovered cell** — a loud gap rather than
an absence nobody notices. That property is what makes this file worth more than
the sum of its assertions: it is simultaneously the data generator's
specification, the CI assertion target, and half the drift detector.

Producing it costs 1 read-only query plus a YAML parse, so it is cheap enough to
get wrong on the first attempt.

### Generate the enum domain from `access.js`, never from production data

Production data is a **subset** of the enum domain the code handles, so a
manifest derived from `SELECT DISTINCT` would silently omit live policy
branches. Measured on 2026-09-11 against `dim_staff_cube_access`:

| Scope value                                       | Handled in `access.js` | Rows in production |
| ------------------------------------------------- | ---------------------- | ------------------ |
| `staff_pii_scope = teaching_staff`                | Yes                    | **0**              |
| `staff_pii_scope = reporting_chain`               | Yes                    | **0**              |
| `staff_pii_scope = reporting_chain_or_below_rank` | Yes                    | **0**              |
| `staff_benefits_scope != none`                    | Yes                    | **0**              |

`staff_pii.yml` carries an `access_policy` block for all 4 `staff_pii_scope`
values, and `buildGroups` emits `staff-benefits` for any non-`none` benefits
scope. Three of those policies and that group have **no production row that
reaches them**. The sandbox is the only place they can ever be exercised.

This does not violate the fidelity rule from the parent spec. That rule says
make the sandbox narrower than production; here **production is narrower than
the code**, which is a case the rule does not cover. Cover the code's domain,
and note in the handoff that 4 of those personas exist nowhere in production
today.

### The 20th table is invisible to the model

`scripts/sandbox_coverage_manifest.py` must not derive its table set by parsing
`sql_table:`. Only **19** tables appear there. The 20th,
`dim_staff_reporting_chain`, is read directly by
[`cube.js:145`](../../../src/cube/cube.js) and appears in no cube YAML at all.

Miss it and the failure is quiet: the sandbox compiles, every view resolves, and
identity resolution then fails for exactly the `reporting_chain` and
`reporting_chain_or_below_rank` personas — the 3 that production cannot test
either. The generator reads the union of `sql_table:` values and the
`kipptaf_marts.*` references in `cube.js`, and asserts the result has 20
members.

## Piece 3 — generate the data, and make it adversarial

Seeded RNG, parameterized, production scale, per the parent spec. Commit the
persona fixtures: they are fabricated, so they are not PII.

### Generate per table, in dependency order

The generator is **per warehouse table, not per cube**. 21 cubes read 19 tables,
because two pairs share one: `student_enrollments` and `student_attendance` both
read `fct_student_attendance_daily`, and `student_homeroom_section` and
`student_section_enrollments` both read `dim_student_section_enrollments`. A
generator keyed on cube names would write two of those twice. Add
`dim_staff_reporting_chain`, which no cube reads, for 20.

Order comes from the 26 join edges in the model. Generate a table only after
every table it references:

1. **No dependencies.** `dim_regions`, `dim_dates`, `dim_courses`,
   `dim_students`, `dim_terms`, `dim_assessments`, `dim_staff`,
   `dim_school_calendars`, `dim_student_enrollment_status`.
1. **One hop.** `dim_locations`, `dim_course_sections`,
   `dim_assessment_administrations`, `dim_staff_cube_access`,
   `dim_staff_reporting_chain`.
1. **The spine.** `dim_student_enrollments`, then
   `dim_student_section_enrollments`.
1. **Facts.** `fct_student_attendance_daily`,
   `fct_assessment_scores_enrollment_scoped`, `dim_staff_work_history`.

Facts never invent a key. Every foreign key is **sampled from the rows already
generated** in an earlier tier, which is what makes referential integrity hold
by construction rather than by a check afterwards.

### The spine has a cycle, so it needs two passes

`dim_student_enrollments` and `dim_student_section_enrollments` reference each
other: an enrollment points at its homeroom section, and a section enrollment
points back at its enrollment. No ordering satisfies both.

Generate in three steps. Write `dim_student_enrollments` with its homeroom
section key null, generate `dim_student_section_enrollments` against those
enrollments, then update the enrollment rows with a homeroom key sampled from
the sections just written. Leaving a deliberate slice of homeroom keys null is
correct rather than sloppy — it is one of the manifest's required residents.

This is the single most likely place for the generator to produce a dataset that
loads cleanly and then fails at query time, because a broken cycle shows up as a
join returning nothing rather than as an error.

### Production scale, measured

The parent spec estimated "10,000 students across 180 school days is roughly
1.8M attendance rows." Measured on 2026-09-11, production is about 7 times that:

| Table                                     | Production rows |
| ----------------------------------------- | --------------- |
| `fct_assessment_scores_enrollment_scoped` | 13,504,949      |
| `fct_student_attendance_daily`            | 12,603,269      |
| `dim_dates`                               | 2,921,940       |
| `dim_students`                            | 31,194          |
| `dim_assessment_administrations`          | 14,656          |
| `dim_assessments`                         | 6,507           |
| `dim_staff`                               | 4,799           |
| `dim_courses`                             | 3,852           |
| `dim_regions`                             | 5               |

Attendance spans 2007-08-13 to the present across 84,477 enrollments — 19
academic years, not 1. Size the generator against these numbers, because
pagination and query-timeout behaviour is what the partner is meant to discover
here rather than at repoint.

Bound `dim_dates` deliberately. Production's calendar spine runs to the year
9999, and an unbounded date dimension is what drove the partitioned
pre-aggregation incident (#4460). Generate the real academic-year range only.

### The sandbox will be faster than production, and that is a fidelity break

**12 of the 20 are BigQuery views in production, not tables**:
`dim_course_sections`, `dim_locations`, `dim_school_calendars`,
`dim_staff_cube_access`, `dim_staff_reporting_chain`,
`dim_staff_reporting_periods`, `dim_staff_work_history`,
`dim_student_enrollment_status`, `dim_student_enrollments`,
`dim_student_section_enrollments`, `dim_terms`, and
`fct_student_attendance_daily`. The other 8 are physical.

The sandbox has no dbt and no upstream model graph, so every one of the 20
becomes a flat table there. Cube does not care — it issues the same SQL either
way, and `INFORMATION_SCHEMA.COLUMNS` compares views and tables identically, so
the Piece 4 fingerprint still works.

What it costs is latency fidelity, in the one direction the fidelity rule
forbids. Production recomputes view chains on read, which is compute-bound
(#4464 moved the assessment star to tables for exactly this). The sandbox reads
flat tables and will therefore be **systematically faster** than production —
cleaner, not messier. That is unfixable short of rebuilding the view chains,
which is absurd for fabricated data.

So do not fix it; state it. Tell the partner in writing that sandbox latency is
not representative and must not be used to size timeouts, pick page sizes, or
decide what to cache. The parent spec says to leave pre-aggregations off until
the partner reports a latency surprise. That surprise is now predicted rather
than hypothetical, and it lands at repoint.

### Nothing is anonymized — every value is fabricated

Worth stating because the question comes up as "what do we anonymize." Nothing.
No real row enters the generator at any point.

De-identification starts from real records and removes identifiers, which
carries re-identification risk, needs a stated risk threshold (the decision
blocking [#4237](https://github.com/TEAMSchools/teamster/issues/4237)), and per
PTAC is not achieved by removing direct identifiers alone. Fabrication carries
none of that, which is the whole reason this is days of work rather than a
governance project. The only thing read from production is **schema and
codesets** — column names, types, nullability, and the distinct values of
categorical fields. No rows.

### Where the invented values come from

The PII-shaped columns are concentrated in 2 tables: `dim_students` (11 columns)
and `dim_staff` (16). Each class of field gets a different rule.

**Names: a reserved surname namespace, realistic given names.**

Start from the question that actually gets asked. The partner pastes a
screenshot into a ticket, it shows a student row, and someone asks whether that
is a real child. The answer has to take 10 seconds.

A closed list of plausible names cannot give that answer. "Jayden Rodriguez"
being on our committed list proves the **generator emitted it** — provenance —
and is perfectly compatible with a real student having that name. Provenance is
not non-existence, and no amount of list-checking closes the gap. Checking
against the real roster would close it, and is refused: the generator would have
to read real student data, building the exact bridge to PII it exists to
prevent.

So the names carry the proof themselves. Split the two parts:

- **Surnames come from a documented reserved set** — coined words, used for
  nothing else, committed to the repo and named in the partner handoff as KTAF's
  synthetic-person namespace. This works the way `example.com` works: not
  because the string is impossible, but because it is **reserved and
  documented**, so its appearance is self-identifying. IANA reserved
  `example.com` for exactly this purpose, and `.invalid` and the `555-01xx`
  phone block are the same move.
- **Given names stay realistic**, because that is where the character classes
  that break user interfaces live: apostrophes, hyphens, diacritics, non-Latin
  scripts, single characters, and lengths that overflow a column. A realistic
  given name beside a reserved surname keeps the layout stress without the
  plausible identity.

`Amara Fennworth` reads as a name and is unmistakable once you know the
convention. `Zoë Quillamber-Strand` does the same while exercising a diacritic,
a hyphen, and 21 characters.

Three levels of proof, fastest first:

1. **By glance.** The surname is from the reserved set, and the row's email is
   at a `.invalid` domain. The email is the tell that works on someone who has
   never heard of the convention, since nothing at `.invalid` can resolve.
1. **By grep.** The surname list is committed, so membership is one command. A
   surname outside the set appearing in sandbox output is a contamination signal
   — the canary idea generalized, and sound now only because the set is coined
   rather than plausible.
1. **By construction.** The sandbox project holds no IAM on `teamster-332318`
   and Piece 1's isolation check runs on a schedule, so no path exists by which
   a real row could be present. This is the actual proof; the first two are the
   fast ones.

Reserving a namespace only works if it is written down, or the glance test
serves whoever happens to remember it. Name the set in the partner handoff and
in `docs/reference/`.

**Birth dates: derived from grade, never independent.** A 3rd grader born in
1998 breaks every age calculation downstream. Sample the enrolled grade first,
then a `birth_date` inside the plausible window for that grade and academic
year. Include a deliberate minority off-cohort — retained, accelerated, late
entry — because those students are real and they are exactly the edge cases a
kit gets wrong.

**Identifiers: format-valid, from a reserved range.**
`district_student_identifier`, `state_student_identifier`,
`lea_student_identifier`, `salesforce_contact_id`, `staff_unique_id`. These must
parse like the real thing — right length, right character set, right check-digit
shape where one exists — so client code works unchanged at repoint. But draw
them from a range production never issues. A sandbox identifier then cannot
collide with a real one, and one appearing in the wrong system is immediately
identifiable as fabricated.

**Emails and phones: reserved namespaces, and one hard prohibition.**
`work_email`, `google_email`, `personal_email`, `active_directory_username`,
`personal_cell_phone`.

**Fold addresses to ASCII.** The given-name classes include diacritics and
non-Latin and right-to-left scripts, so deriving an address by lowercasing the
name yields a non-ASCII local part (`søren.gimblewood@…`), which needs SMTPUTF8
and is not what any real directory holds. Transliterate to ASCII first. This is
not cosmetic: `google_email` is the key `resolveAccess` matches exactly, so a
non-ASCII address is a realistic-looking identity that silently resolves to
nobody. The starter fixture's own illustration got this wrong, which is why it
is called out here.

**No fabricated address may use `@apps.teamschools.org`.** `google_email` is the
identity-resolution key that `resolveAccess` matches on, and `canSwitchSqlUser`
gates on that exact suffix. A synthetic row carrying a real-domain address is a
real-looking credential in a system meant to contain none. Use a domain under
`.invalid` — reserved by RFC 2606 and guaranteed never to resolve — so no mail
can reach a fabricated person even by accident. Same principle for phones: the
`555-01xx` block is reserved for fiction, so nobody ever dials a real number
from a test fixture.

**Categorical fields: derive the codeset from production, never transcribe it.**
`gender_identity`, `race`, `is_hispanic`, `enrollment_status`. Every value the
real codeset holds must appear, because a dropdown, a filter, and a group-by all
have to see the full domain. The manifest generator extracts these during
introspection; hardcoding them into the generator would go stale silently, the
same failure the manifest exists to prevent.

Proportions are a separate matter and need no real data — published state
figures are enough, and are not PII.

**The codesets are inconsistent, and that must be reproduced.** Measured on
2026-09-11: `dim_staff.race` carries both
`Black or African American (not Hispanic or Latino)` and
`Black/African American`; `dim_staff.gender_identity` carries both `F`/`M` and
`Cis Man`/`Cis Woman`. Two source systems, never reconciled. `dim_students.race`
likewise mixes an ethnicity value (`Not Hispanic or Latino`) in among races.

A generator that emits one canonical spelling per category would make the
sandbox **cleaner than production** — the direction the fidelity rule forbids.
The partner's grouping and filtering would then work in the sandbox and split
into two buckets on real data. Emit the duplicates. This is the most concrete
instance of the fidelity rule in the whole spec, and it is free: deriving the
codeset rather than authoring it produces the duplicates automatically.

### What the generator actually produces

**Avro files, staged to GCS, loaded into native BigQuery tables.** Not CSV, and
not external tables. Both of those deserve their reason.

**Avro over CSV, because the manifest is mostly about nulls.** All 230 columns
are nullable and 183 of the 295 dimensions are strings, so the dataset's central
assertion — at least 1 null and 1 non-null per column — lands almost entirely on
string columns. In CSV, whether a field is `NULL` or the empty string depends on
quoting: a bare empty field loads as `NULL`, a quoted `""` loads as an empty
string. That distinction surviving 26M rows of generated output rests on nothing
but quoting discipline, and if it slips, the coverage assertion passes while the
data is wrong. That is precisely the silent failure this spec exists to prevent.
Avro encodes null in the type, so the question cannot arise. It is also the
house format — 286 `AVRO` declarations across the dbt source definitions — so
the existing GCS tooling applies.

**Native tables over external tables, diverging from the house pattern on
purpose.** The repo stages Avro in GCS and reads it through BigQuery external
tables created by dbt `stage_external_sources`. Three reasons that does not fit
here:

1. There is no dbt in the sandbox project, and nothing upstream for an external
   source to be defined against.
1. External-table metadata is cached (`metadata_cache_mode: MANUAL`,
   `max_staleness`), and BigQuery's file listing lags an overwrite by minutes. A
   regenerated dataset would serve stale rows for a while, which is
   indistinguishable from a generator bug to anyone debugging it — the partner
   included.
1. Piece 4's fingerprint compares deployed schema, and Cube queries a 12.6M-row
   fact repeatedly. Native tables are the right shape for both.

**Schema is created explicitly, not inferred.** Derive each table's BigQuery
schema from production `INFORMATION_SCHEMA.COLUMNS` — name, type, nullability —
and create the table from that before loading. Letting BigQuery infer types from
the Avro would make the drift fingerprint depend on inference matching
production by luck; an explicit schema makes it match by construction.

The fiddly part is logical types. 23 time dimensions and 45 numeric ones mean
Avro's `date` / `timestamp-micros` / `decimal` annotations have to map exactly
onto BigQuery `DATE` / `TIMESTAMP` / `NUMERIC`, or the fingerprint fails on
types while every row looks fine. Budget for that rather than assuming it is
free.

So the deliverables, in build order:

| Script                                    | Produces                                                                                  | Needs the sandbox? |
| ----------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------ |
| `sandbox_coverage_manifest.py`            | `coverage_manifest.yml` and the per-table BigQuery schemas, from production introspection | No                 |
| `sandbox_generate.py --scale {tiny,full}` | Avro files in a local directory                                                           | No                 |
| `sandbox_coverage.py`                     | Pass or fail against the manifest, reading the Avro directly                              | No                 |
| The load step                             | GCS upload, `CREATE OR REPLACE TABLE`, `bq load`                                          | Yes                |

Only the last one waits on the GCP project, and only it touches the warehouse —
so it runs from a terminal or Dagster, never from an assistant session.

### Do not ship the partner a smaller dataset

The obvious economy is to generate a fraction of production scale so the build
loop is quick. Take the `--scale` parameter, not the smaller sandbox. Three
reasons, in the order they should change your mind.

**Volume buys exactly 3 things, and they are the 3 a kit freezes wrong.**
Pagination, query timeouts, and pre-aggregation routing are invisible at a few
hundred rows and load-bearing at production scale. Client code that never had to
paginate does not start paginating on its own, and in a kit that omission is
inherited by every app built on it. Nothing else in the design depends on row
count.

**The cost intuition does not survive measurement.** A single
`count(distinct student_enrollment_key)` against production
`fct_student_attendance_daily` scans **945 MB and references 15 upstream tables
across 6 datasets** (dry run, 2026-09-11), because in production that mart is a
view over the PowerSchool and Focus graph for 4 districts. The sandbox answers
the same query from 1 flat table with no join. Production is expensive because
of the view chain, not the row count — so a full-scale sandbox is already
dramatically cheaper and faster than production, and shrinking it optimises
something that is not the constraint.

**The manifest already sets a floor.** A dataset still has to satisfy 460 column
cells, every scope enum the code handles, non-uniform snapshot anchors, and a
join orphan on each side of every path. "Small" is therefore bounded from below
by coverage, not chosen freely — and a dataset that clears that floor is
complete in every way except volume.

The real friction is **generation and load wall-clock**, not query cost. Solve
that where it bites, in KTAF's own iteration, with 2 named profiles from the
same seeded generator:

| Profile | Rows               | Lives                        | Used by                                                      |
| ------- | ------------------ | ---------------------------- | ------------------------------------------------------------ |
| `tiny`  | The manifest floor | Local files                  | Generator development, coverage assertions in CI on every PR |
| `full`  | Production scale   | The sandbox BigQuery dataset | The partner, the canary and RLS suites, load testing         |

Same generator, same seed, same manifest coverage. Only the row multiplier
differs, so a `tiny` run that satisfies the manifest proves the generator
correct without waiting on a full build.

**One size at a time, through Cube.** Every `sql_table` is dataset-qualified
(`kipptaf_marts.dim_students`) while the repoint variable is
`CUBEJS_DB_BQ_PROJECT_ID` — a project, not a dataset. So two sizes visible
through Cube simultaneously would need 2 sandbox GCP projects and 2 Cube
deployments, not 2 datasets in one project. Not worth it: `tiny` exists to
validate generated rows directly, which needs no Cube at all.

Everything above builds a dataset that is correct and correctly sized. The two
mechanisms below are what make it an instrument rather than a stand-in.

### Colonization resistance

Saturate every column and every join path with benign-but-ugly residents, so no
empty niche is left for a sloppy kit assumption to occupy. The manifest from
Piece 2 defines what "saturated" means, and `scripts/sandbox_coverage.py`
asserts it: one row per `(cell, observed count)`, exit non-zero on any zero.

The parent spec's fidelity rule — narrower and messier than production, never
wider or cleaner — is the intent. The manifest is the enforcement.

### Must-be-empty canaries

`src/cube/sandbox/canaries.yml` holds entries shaped
`{persona, query_shape, expect}` where `expect` is one of `BLOCKED`, `ROWS`, or
`ZERO`.

`BLOCKED` asserts the real denial text. For the SQL API that is
`Table or CTE with name '<view>' not found`. **A quiet zero rows against a
`BLOCKED` canary is a failure, not a pass.** That single distinction is what
mechanically forces sign-off under `NODE_ENV=production CUBEJS_DEV_MODE=false`:
a dev-mode runner fails its own canaries immediately instead of reporting a
falsely benign matrix. See
[#4605](https://github.com/TEAMSchools/teamster/issues/4605).

[`scripts/cube_rls_matrix.py`](../../../scripts/cube_rls_matrix.py) already
emulates 1 viewer per SQL connection, so the work is adding an
`--expect <canaries.yml>` flag and a non-zero exit. That converts a human-read
matrix into an assertion runner.

Both tiers run the same 2 files. KTAF CI owns them, because KTAF owns the dbt
marts and the `access_policy` blocks and must break first when a policy changes.
MasterBorn's kit test suite runs them unmodified as its acceptance gate.

### Poison-pill scale ranges

Seed 2 assessment scopes with deliberately incomparable ranges — 200 to 800
beside 0 to 36 — so a wrong cross-scope `avg_scale_score` pooling produces an
absurd number instead of a plausible one.

This is the one failure no assertion can catch. Scope-bound measures recompute
correctly at any grain; they are simply meaningless across incomparable scopes.
Only a human noticing catches that, so make the error announce itself in a
screenshot.

### Mutation-test the canaries

A canary that would still pass with the policy deleted proves nothing. Perturb
one `access_policy` block or one persona's scope value and require at least one
canary to flip red. Report the uncaught mutations as a percentage. This is the
only honest measure of whether the canaries are load-bearing.

## Piece 4 — gate the drift

A Dagster asset named `sandbox_marts_contract` compares the two datasets and
blocks regeneration when they disagree.

### What it compares

Run `INFORMATION_SCHEMA.COLUMNS` against both projects, normalize each result to
a sorted list of `(table, column, data_type, is_nullable)` tuples, and reduce to
a sha256 fingerprint.

Use `INFORMATION_SCHEMA` on both sides rather than dbt's `catalog.json`. The
sandbox is not built by dbt, so only production has a catalog — and
`catalog.json` records intent, which drifts from deployed DDL by one run.

**Scope the fingerprint to the Cube-referenced column subset, not all 229.** A
production column that no cube references would otherwise turn the gate red for
a reason that cannot affect the kit. A gate that cries wolf over 229 columns
gets routinely overridden within a month, at which point it is worse than
nothing.

A second leg fetches `/meta` from the sandbox deployment and asserts all 6 views
resolve member-for-member against the committed
[`cube-catalog-meta.json`](../../reference/cube-catalog-meta.json). That leg is
the one that actually proves the kit's surface, because Cube compiling a view
against the sandbox is the real acceptance test.

### What blocking means

A `blocking=True` asset check on the contract asset, with the generator assets
declared downstream. A mismatch then **skips** regeneration rather than writing
rows against a schema the kit no longer matches.

The generator also re-computes the fingerprint at start and exits non-zero if it
disagrees with the one in its input manifest, so a manual `launch_run` cannot
bypass the gate.

### Repair the additive case, block the rest

Most real drift is additive. For an added column, emit an `ADD COLUMN` patch
with null fill and apply it, then regenerate. Reserve the hard block for drops
and type changes, which cannot be applied safely.

Blocking on additive drift is strictly worse than healing it: MasterBorn keeps a
working sandbox and KTAF gets a notification instead of an incident. It also
keeps the override path narrow enough that a red check still means something.

### The run manifest

Each generator run writes an immutable manifest to a versioned GCS bucket:
generator commit SHA, RNG seed, per-table row counts, fixture list, the
production schema fingerprint, and the Cube tag. Commit only its sha256, so git
history is the notary and no KMS signing is needed.

The kit asserts the current manifest hash at test time. A kit bug is then
immediately classifiable as their code or as a surface that moved under them,
which is where most cross-organization debugging time otherwise goes.

## Piece 5 — deploy the model deliberately

The sandbox must never follow `main` automatically. The rationale is in
[The one change](#the-one-change-pin-a-tag-do-not-track-main) above; this
section is the mechanism, which is not what the first draft claimed.

### Two ways to get it

**Preferred: Deploy with CLI, from a tagged checkout.** Put the sandbox
deployment in CLI mode. A bump is then
`git checkout sandbox-YYYY.MM.DD && npx cubejs-cli deploy --token <token>`. The
tag stays the human-meaningful pin even though Cube Cloud never reads it, and
nothing auto-deploys — a production build happens only when someone runs that
command. Cube Cloud keeps an internal repository that each successful deploy
overwrites, so the deployed state is exactly what was uploaded.

Two costs. It needs a deploy token stored somewhere, and it contradicts
`src/cube/CLAUDE.md`'s "no manual deploy command" — which is a rule about the
**production** deployment, so state the exception rather than quietly breaking
the rule.

**Alternative: Deploy with Git, tracking a long-lived branch.** Point the
sandbox deployment at a branch such as `cube-sandbox-release` and fast-forward
it to a chosen `main` commit to bump. No deploy token, and the bump is an
ordinary git push. The cost is that a push to that branch deploys immediately,
so the deliberateness rests on branch discipline rather than on a separate
command.

**Why CLI is preferred.** Connecting a GitHub repository auto-syncs
non-production branches into staging environments _regardless of deploy mode_.
On the sandbox deployment that means a staging environment per repo branch, each
sharing the deployment's API secret. Harmless, since the data is fabricated, but
it is noise around a surface handed to an outside party. CLI mode with no GitHub
connection avoids it entirely.

### Each bump

1. Regenerate the catalog and commit it, so the move is a reviewable diff.
1. Tag the commit `sandbox-YYYY.MM.DD`.
1. Generate a member-level diff report of additions, removals, and retypes.
1. Send that report to MasterBorn as a release note.
1. Deploy that checkout to the sandbox deployment.
1. Re-run the coverage and canary suites against the new state.

## How each tier sets up

### MasterBorn's kit developers

1. Read `docs/reference/cube-semantic-catalog.md` and parse
   `cube-catalog-meta.json`. This is available before the sandbox exists.
1. Sign in through WorkOS AuthKit and exchange the OIDC identity at the
   `cube-sandbox` Cloud Run service for a 5-minute Cube token. Their auth code
   is the production auth code, which is what makes the repoint a configuration
   change.
1. Explore interactively through Cube Cloud console access, scoped by an
   Enterprise custom role to the sandbox deployment only.
1. Switch personas through the gated `act_as` passthrough on `cube-sandbox`,
   default off, never enabled on the production `cube-mcp` service.
1. Run the coverage and canary suites as the kit's acceptance gate, and attach
   the runner's JSON output — including the mode flags — to each kit release.

They keep using the sandbox after the production cutover. The repoint grants the
product's end users access, not MasterBorn's engineers.

### KTAF internal app developers

This tier has no design yet, and that gap is the spec's main open question. See
[Open questions](#open-questions). What is settled: they build against the
sandbox on the same terms as MasterBorn's engineers, and they never hold a
production Cube credential.

### KTAF staff, in production

Unchanged from the parent spec's
[Production identity pass-through](2026-08-06-cube-partner-shape-first-integration-design.md).
The app passes an identity, never a scope; the Cloud Run service derives scope
server-side from HR data; every staff member already has a
`dim_staff_cube_access` row.

## Rejected alternatives

Recorded so they are not re-proposed. Each was generated during the 2026-09-11
divergent pass.

| Idea                                                                              | Why not                                                                                                   |
| --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Make the sandbox token exchange architecturally different from production         | Destroys the repoint property, which is the parent spec's foundation                                      |
| Hardcode the sandbox project in the kit build with no override path               | Same failure: the repoint _is_ a configuration change, so forbidding configuration forbids the repoint    |
| A decoy field mirroring the `contextToGroups` gap, rigged to alert                | Means keeping a live known hole. Fix [#4526](https://github.com/TEAMSchools/teamster/issues/4526) instead |
| Check synthetic rows for quasi-identifier collisions against a hashed real roster | The generator would have to read real student data, building the exact bridge to PII it exists to prevent |
| Serve only static mocked responses derived from the catalog                       | Teaches nothing about whole-query `access_policy` denial, the parent spec's likeliest production surprise |
| Reseed only tables above a dependency-distance threshold                          | 20 flat tables rebuild in minutes                                                                         |
| CI that deletes kit code paths returning PII                                      | Unbuildable as stated. The viable form is a failing build, which Piece 3 covers                           |

## Open questions

**Should the kit be the only sanctioned path to Cube for internal apps?** The
kit is a third access-control surface. Every internal app inherits the kit's
defaults for token lifetime, result caching, and the audit `surface` value. The
parent spec's 3 partner obligations are written as contract terms because
MasterBorn sits outside the boundary. In a kit world those obligations move
inside KTAF and multiply by the number of internal apps, where a contract term
cannot reach them. The alternative is making the kit the enforcement point: the
exchange service refuses any client that does not present a kit-issued app
identity. That scales with app count rather than degrading with it.

**How far may the pinned tag drift before it is stale?** Piece 4 measures the
distance. Nothing yet decides the threshold at which a bump becomes mandatory.

**Who owns the tag bump cadence?** Analytics engineering by default, but the
trigger is unsettled: scheduled, or on MasterBorn's request, or on a drift
threshold.

**Where does the sandbox project land in the resource hierarchy?** Unknown until
someone with `roles/resourcemanager.projectCreator` creates it. The answer
decides whether an Organization Policy constraint can back up the isolation, per
[Piece 1](#the-organization-policy-constraint-may-not-be-available).

Inherited from the parent spec and still open: which features query when the
user is absent, whether MasterBorn will commit in writing that results are never
cached across users, how external users are provisioned in the Cube Cloud SAML
tenant, and whether the product wants REST or MCP.

## Testing strategy

- **Isolation proof**: the sandbox service account cannot read
  `teamster-332318.kipptaf_marts`. Runs before any data exists, and then on a
  schedule, because an Organization Policy constraint may not be available to
  enforce it structurally. A failure blocks the generator.
- **Coverage assertion**: `scripts/sandbox_coverage.py` exits non-zero on any
  uncovered manifest cell.
- **Catalog equality**: all 6 views resolve against the sandbox and match the
  committed catalog member-for-member.
- **Canary suite**: every canary passes under
  `NODE_ENV=production CUBEJS_DEV_MODE=false`, and the mode canary fails under
  `CUBEJS_DEV_MODE=true`.
- **Mutation coverage**: perturbing one `access_policy` block flips at least one
  canary red.
- **Drift gate**: a deliberate schema change in the sandbox turns the Dagster
  asset check red and skips the generator.
- **Anchor fidelity**: a snapshot measure over a date range returns the anchored
  count on synthetic data, not the additive one.
- **The standing invariant**: no real record ever lands in the sandbox project.

## Related

- [#5266](https://github.com/TEAMSchools/teamster/issues/5266) — this work.
- [#4501](https://github.com/TEAMSchools/teamster/pull/4501) — the parent
  design.
- [#4455](https://github.com/TEAMSchools/teamster/issues/4455) — the
  integration.
- [#4268](https://github.com/TEAMSchools/teamster/issues/4268) — `access_policy`
  blocks rather than strips. The behavior the canaries exist to teach.
- [#4526](https://github.com/TEAMSchools/teamster/issues/4526) — the
  `buildSecurityContext` requirement every new resolver must respect.
- [#4605](https://github.com/TEAMSchools/teamster/issues/4605) — dev mode
  downgrades a denial to zero rows. The reason the mode canary exists.
- [#4237](https://github.com/TEAMSchools/teamster/issues/4237) — small-cell
  suppression. Only relevant if the generator ever proves insufficient.
