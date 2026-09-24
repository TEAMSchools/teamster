# Cube sandbox — build design

A Cube Cloud deployment that answers real queries against a fabricated
warehouse, so an outside party can build against KTAF's semantic layer without
ever holding a credential that reads real student or staff data.

Expands Deliverable 2 of
[2026-08-06-cube-partner-shape-first-integration-design.md](2026-08-06-cube-partner-shape-first-integration-design.md).
Tracked in [#5266](https://github.com/TEAMSchools/teamster/issues/5266).

## Why a sandbox

MasterBorn, a contracted agency, is building a developer kit. KTAF internal
developers build applications on that kit. Neither group may hold a credential
that reads production. But you cannot build against a semantic layer you cannot
query.

| Tier | Who        | Holds                               | Data sees      |
| ---- | ---------- | ----------------------------------- | -------------- |
| 1    | MasterBorn | The kit source, sandbox credentials | Synthetic only |
| 2    | KTAF devs  | An app built on the kit             | Synthetic only |
| 3    | KTAF staff | The finished app                    | Production     |

**The sandbox's job is not to look like production. It is to teach the awkward
parts of the access model loudly.** A wrong assumption inside one application
hurts that application's users. A wrong assumption inside a kit is frozen and
copied into every app built on it. That is why the coverage contract is a
generated file a script asserts, rather than prose asking people to be careful.

The data is **fabricated, never de-identified**. De-identification starts from
real records, carries re-identification risk, and needs a risk threshold nobody
at KTAF has set. Fabrication carries none of that, which is what makes this days
of work rather than a governance project.

### What the sandbox reproduces, and what it does not

"Teach the awkward parts loudly" is not a licence to seed defects. The audience
is developers learning to build, and a sandbox full of dirty data teaches them
to filter around it. In production that same instinct means a workaround instead
of a data ticket.

Test every proposed hazard against this:

| Kind                | Example                                         | In the sandbox |
| ------------------- | ----------------------------------------------- | -------------- |
| Semantic hazard     | ISO week grouping over PowerSchool school weeks | Reproduce      |
| Domain reality      | Diacritics in names, orphans, legitimate nulls  | Reproduce      |
| Data-quality defect | Two unreconciled spellings of one category      | Do not         |

A semantic hazard means the data is right and the query is wrong. No ticket
exists, the model is correct and documented, and the only remedy is learning it
— so the sandbox is the one place to meet it.

A data-quality defect has a fix, in dbt, filed as a ticket. Reproducing it
teaches the wrong layer and rewards a workaround.

Domain reality is neither: it is what the world contains, it will never be
ticketed away, and a kit that cannot handle it is broken.

## What the sandbox is, precisely

A separate Cube Cloud deployment reading a separate BigQuery project. Three
things differ from production, and only the second needs a mechanism:

| What                 | Sandbox versus production                       |
| -------------------- | ----------------------------------------------- |
| Model files          | Identical                                       |
| Revision             | Older — a tagged commit on `main`'s own history |
| Deployment variables | `CUBEJS_DB_BQ_PROJECT_ID` and its credentials   |

The model files are identical because every `sql_table:` is project-unqualified,
so the same files read a different warehouse from one variable. That
single-variable repoint is the property the whole design rests on. A forked
sandbox YAML would mean the kit is no longer building against the production
semantic layer.

There is no sandbox branch. The sandbox needs a revision, not a branch.

### One thing is read from production, by one step

**Schema** — column names, types and nullability. No data of any kind, ever.

Only the refresh step reads it, and it writes what it read into the repo as a
pull request. **The generator never reads production**; it reads the committed
snapshot at the pinned revision. So production schema is an input to the repo,
never an input to a build.

Values the kit must match come from the model. `access.js` settles the
access-control enums, and every other load-bearing value is documented in the
cube YAML, because a value that matters gets written down. Everything else is
invented.

### Three committed artifacts, moving on one pin

| Artifact                 | Generated from                       | Needs         |
| ------------------------ | ------------------------------------ | ------------- |
| `schema_snapshot`        | Production `INFORMATION_SCHEMA`      | BigQuery read |
| `coverage_manifest.yml`  | The snapshot, `access.js`, cube YAML | Nothing       |
| `cube-catalog-meta.json` | Production Cube `/meta`              | Cube API read |

All three live under `src/cube/sandbox/`, except the catalog, which is published
to `docs/reference/`. **One pin covers all three**, and a bump moves that single
revision. Pinning them separately would make the checks in Piece 4 compare the
wrong pair.

**Refreshing an artifact is not deploying it.** A refresh lands as a reviewed
pull request and changes nothing MasterBorn sees. The diff accumulated between
bumps is the release note the bump ships.

## Piece 1 — isolation

Built and verified 2026-09-23.

| Thing             | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Sandbox project   | `teamster-cube-sandbox`, dataset `kipptaf_marts`, US               |
| Service account   | `cube-cloud-sandbox@teamster-cube-sandbox.iam.gserviceaccount.com` |
| Its roles         | `bigquery.jobUser`, `bigquery.dataViewer`, sandbox project only    |
| Cross-project IAM | None, in either direction                                          |
| Deny policy       | `deny-sandbox-bigquery` on `teamster-332318`                       |

The deny policy blocks every service account in the sandbox project from
BigQuery reads, queries and writes in production. A deny overrides any grant, so
a later well-meaning grant cannot reopen the read, and it does not depend on
where the project sits in the resource hierarchy.

### The isolation test has two legs

- **Negative:** the sandbox service account reading
  `teamster-332318.kipptaf_marts` fails with a permission error.
- **Positive:** the same account, in the same run, reads the sandbox project
  successfully.

Both, or neither counts. A service account whose credentials are broken fails
the production read exactly like an isolated one, so without the positive leg
the test goes green on the day the sandbox breaks.

Authenticate with the service account's own key, which is the path Cube Cloud
uses through `CUBEJS_DB_BQ_CREDENTIALS`, so the test exercises the real
connection rather than a stand-in.

### The scheduled check asserts two things

1. The 403 and the successful sandbox read, as one run.
2. That `deny-sandbox-bigquery` still exists.

The second catches a later deletion or edit. An absent grant and an active deny
policy produce the same 403, so the first assertion cannot cover it.

**It runs daily, and again as a blocking check before each generator run.** The
generator writes only on deliberate bumps, so it could otherwise write against a
boundary that broke since the last daily run. A failure blocks generation: an
isolation regression must stop synthetic-data writes.

### It needs two identities, so it is two checks

| Assertion                      | Identity                            |
| ------------------------------ | ----------------------------------- |
| The 403 and the sandbox read   | The sandbox service account key     |
| `deny-sandbox-bigquery` exists | A production identity with IAM read |

Neither is dangerous alone: the sandbox account cannot read production data by
construction, and an IAM-read identity touches no warehouse data and cannot
write to the sandbox. One account holding both would be a step toward the
binding this design exists to prevent, so the check is built as two, split on
the same boundary as the generator.

Reading a deny policy needs `iam.googleapis.com/denypolicies.list` on
`teamster-332318`. Granting it, and to whom, is open.

## Piece 2 — the coverage contract

`coverage_manifest.yml` lists every cell the sandbox data must contain, each
marked `uncovered` until the generator fills it. It is written before the data
generator, because it is that generator's specification.

**It is generated, not hand-written.** A new production column, view or scope
value becomes a loud uncovered cell rather than an absence nobody notices. Every
rule below preserves that property.

The manifest generator reads the pinned snapshot, `access.js` and the cube YAML.
It needs no cloud access, so it runs in CI and on any laptop, and its output is
deterministic from committed inputs.

### Required cells

- **A null row and a non-null row per column, except where the warehouse says
  otherwise.** Three exemptions, each derived rather than listed: columns with a
  dbt `not_null` test, which is the warehouse's own declaration that the column
  is never null; join and surrogate keys, from the join-path fixtures; and
  columns any `access_policy` filters on, from parsing the views' policy blocks.
  A null join key breaks the fixtures the manifest defines, and a null policy
  column makes the persona resolve to nothing.

  `INFORMATION_SCHEMA` cannot drive this — every column in `kipptaf_marts`
  reports `NULLABLE`, so it exempts nothing. The dbt tests carry the real
  contract, and they are committed, so this needs no production read.

  A column that is never null in practice but carries no `not_null` test is a
  missing test. The sandbox nulling it surfaces that, and the fix is a dbt
  ticket — which is the right layer.

- **Every `*_scope` enum value the code handles**, as a fabricated
  `dim_staff_cube_access` row.
- **Every derived state `buildGroups` branches on**: `hasRemit` and `hasChain`,
  each true and false. An empty remit or chain takes the no-group default-deny
  path, because Cube throws on an `equals []` row filter
  ([#4269](https://github.com/TEAMSchools/teamster/issues/4269)). Production
  cannot reach that branch by design.
- **One unresolvable identity**, with no `dim_staff_cube_access` row, to
  exercise clean default-deny.
- **Every join path**: one orphan on each side, as a named fixture a test can
  reference.
- **Three divergence cells** — see below.

### The divergence cells

Three queries compile, run, and return a plausible wrong number. The fabricated
data must make each one visibly wrong, or the sandbox teaches that the careless
form is fine.

| Cell                          | What the data must make true                                      |
| ----------------------------- | ----------------------------------------------------------------- |
| Unpinned cumulative measures  | A date range returns a materially higher count than a pinned date |
| The two attendance views      | Day-weighted and student-weighted rates disagree                  |
| School weeks versus ISO weeks | An ISO week grouping is visibly wrong                             |

`count_chronically_absent` and `count_truants` read a cumulative position the
fact re-stamps on every daily row, so over an open range they count students who
crossed on any day. The two attendance views weight differently and diverge by
0.66 points in production. `period_type = 'week'` is the PowerSchool school
week, and an ISO grouping silently returns a meaningless breakdown with no
query-time guard.

### Two rules that decide what the manifest covers

**The table set is the union of `sql_table:` values and the `kipptaf_marts.*`
references in `cube.js`, asserted against the count found.** Parsing
`sql_table:` alone finds 20 distinct tables; `dim_staff_reporting_chain` is read
directly by [`cube.js:145`](../../../src/cube/cube.js) and appears in no cube
YAML, making the union 21. Miss it and the sandbox still compiles, while
identity resolution fails for exactly the `reporting_chain` personas production
cannot test either. Assert the count rather than hard-coding it.

**Enum domains come from `access.js`, never from `SELECT DISTINCT`.** Production
is a subset of the domain the code handles — several policy branches have no
production row that reaches them. A sandbox wider than production here is
correct: the rule against a sandbox wider than production covers data, not the
code's own domain.

## Piece 3 — the generator

### Two steps, two identities, two systems

| Step              | Reads                                       | Writes                    | Identity    |
| ----------------- | ------------------------------------------- | ------------------------- | ----------- |
| Refresh           | Production `INFORMATION_SCHEMA`             | The snapshot, to the repo | Production  |
| Generate and load | The pinned snapshot, `access.js`, cube YAML | Sandbox tables            | Sandbox key |

No single identity can read production and write the sandbox, and none should be
created. The refresh runs in Dagster, where production credentials already are.
Generate-and-load needs only committed files and the sandbox key, so it runs in
CI.

### Order, and the spine cycle

Derive the table set from the union above, and the order from the model's join
edges: generate a table only after everything it references. Assert the counts
found rather than maintaining a list.

**Facts never invent a key.** Every foreign key is sampled from rows already
generated in an earlier tier, which makes referential integrity hold by
construction rather than by a check afterwards.

`dim_student_enrollments` and `dim_student_section_enrollments` reference each
other, so neither can go first. Write enrollments with a null homeroom section
key, generate section enrollments against them, then update the enrollments with
a homeroom key sampled from the sections just written. Leaving a slice of
homeroom keys null is one of the manifest's required cells.

This is the most likely place to produce a dataset that loads cleanly and fails
at query time, because a broken cycle shows up as a join returning nothing
rather than as an error.

### Personas are declared, not generated

Every other row in the sandbox comes out of the seeded generator. **Personas do
not.** `personas.yml` declares each one explicitly — address, display name,
every `*_scope` value, and the remit or reporting-chain shape it needs — and the
generator writes those rows into `dim_staff_cube_access` verbatim, along with
the supporting rows that make `hasRemit` and `hasChain` resolve as declared.

Two reasons they cannot be emergent:

- **`canaries.yml` names them.** A persona referenced by name has to survive a
  seed change and a generator refactor. Seed-derived personas mean changing the
  seed silently changes who the canaries test, and the suite stays green while
  testing something else.
- **A developer has to be able to be a specific person.** "Connect as this
  address and you get school-scoped student access" is the instruction the
  partner handoff gives. That requires a stable, documented identity, not
  whichever row happened to land on that scope value this run.

The declaration stays honest the same way everything else does: **the coverage
manifest asserts the declared set covers every enum value the code handles.**
Adding a scope value to `access.js` turns into an uncovered cell until a persona
is declared for it, so the hand-written file cannot quietly fall behind the
code.

Personas are fabricated, so `personas.yml` carries no PII and is committed.

### Where invented values come from

**Names: coined surnames, realistic given names.** Every fabricated person takes
a surname from `reserved_names.yml`, and nothing else uses those words. A closed
list of _plausible_ names would prove only provenance, since a real student
could be called Jayden Rodriguez too; an invented surname makes the appearance
of the name the proof. Given names stay realistic, because that is where the
character classes that break interfaces live — apostrophes, hyphens, diacritics,
non-Latin scripts, single characters, overflow lengths. Each given name carries
the class it exercises, so coverage asserts every class is present.

**Birth dates: derived from grade, never independent.** Sample the enrolled
grade first, then a birth date inside the plausible window for that grade and
academic year. Include a deliberate minority off-cohort — retained, accelerated,
late entry — because those students are real and are what a kit gets wrong.

**Identifiers: format-valid, from a range production never issues.** Right
length, character set, and check-digit shape, so client code works unchanged at
repoint. Drawn from a reserved range, so a sandbox identifier cannot collide
with a real one.

**Emails: on a domain under `.invalid`.** RFC 2606 reserves `.invalid` and
guarantees it never resolves, so a fabricated address cannot collide with a real
account and no mail can reach a synthetic person even by accident. Non-collision
is then structural rather than a promise anyone has to keep.

Nothing in the access path restricts the domain. `checkSqlAuth` resolves
identity from the connecting user, and `checkAuth` from the signed `email`
claim; neither checks a suffix. `canSwitchSqlUser` does check one, but it gates
only in-session `SET USER`, which is the Superset path and not how personas are
emulated here.

Fold addresses to ASCII before deriving them from a name: `google_email` is the
key `resolveAccess` matches exactly, so a non-ASCII address is a
realistic-looking identity that silently resolves to nobody.

**Phones: the `555-01xx` block**, reserved for fiction.

**Categorical values: one spelling per category.** Production carries
unreconciled spellings from two source systems in some categorical columns. The
sandbox does not reproduce that, on the rule below: it is a data-quality defect,
and the fix is a dbt ticket rather than kit code.

**`staff_benefits_scope`: two distinct non-`none` values, plus `none`.**
`access.js` branches on `!== "none"`, never on a value list. One non-`none`
value would let a kit author write an equality check and pass every test,
freezing a mistake the sandbox exists to expose.

### Scale

Generate at production scale. Pagination, query timeouts and pre-aggregation
routing are invisible at a few hundred rows and load-bearing at production
scale, and those are exactly what a kit freezes wrong.

| Table                                       | Production rows |
| ------------------------------------------- | --------------- |
| `fct_student_attendance_enrollment_daily`   | 29,791,485      |
| `fct_assessment_scores_enrollment_scoped`   | 15,080,518      |
| `fct_student_attendance_enrollment_periods` | 4,402,039       |
| `dim_dates`                                 | 2,921,940       |
| `dim_students`                              | 31,297          |
| `dim_staff_work_history`                    | 30,116          |
| `dim_staff_reporting_chain`                 | 9,310           |

Measured 2026-09-24. Re-measure rather than trusting these; they have moved
before.

**Bound `dim_dates` to the real academic-year range.** Production's calendar
spine runs to the year 9999, and an unbounded date dimension is what drove the
partitioned pre-aggregation incident
([#4460](https://github.com/TEAMSchools/teamster/issues/4460)).

Two profiles from the same seeded generator, differing only in row multiplier:

| Profile | Rows               | Lives               | Used by                                          |
| ------- | ------------------ | ------------------- | ------------------------------------------------ |
| `tiny`  | The manifest floor | Local files         | Generator development, coverage assertions in CI |
| `full`  | Production scale   | The sandbox dataset | The partner, the canary suites, load testing     |

One size is visible through Cube at a time, because the repoint variable is a
project rather than a dataset. `tiny` exists to validate generated rows
directly, which needs no Cube.

**Sandbox latency is not representative.** 9 of the 21 tables are BigQuery views
in production and flat tables in the sandbox, so the sandbox is systematically
faster — cleaner, the direction the fidelity rule forbids. Rebuilding view
chains for fabricated data is absurd, so state it instead: tell the partner in
writing that sandbox latency must not be used to size timeouts, pick page sizes,
or decide what to cache.

### What it produces

**Avro files, staged to GCS, loaded into native BigQuery tables.**

Avro over CSV because the manifest is mostly about nulls. In CSV, whether a
field is null or the empty string rests on quoting discipline across tens of
millions of rows, and if it slips the coverage assertion passes while the data
is wrong. Avro encodes null in the type. It is also the house format, so
existing GCS tooling applies.

Native tables over external tables, diverging from the house pattern on purpose:
there is no dbt in the sandbox project, external-table metadata caching would
serve stale rows for minutes after a regeneration, and Cube queries a 29.8M-row
fact repeatedly.

**Create each table's schema explicitly from the pinned snapshot**, rather than
letting BigQuery infer it from the Avro. Budget for logical types: Avro's `date`
/ `timestamp-micros` / `decimal` annotations must map exactly onto BigQuery
`DATE` / `TIMESTAMP` / `NUMERIC`.

Deliverables, in build order:

| Script                                    | Produces                                            | Needs the sandbox? |
| ----------------------------------------- | --------------------------------------------------- | ------------------ |
| `sandbox_snapshot_refresh.py`             | The schema snapshot, from production introspection  | No                 |
| `sandbox_coverage_manifest.py`            | `coverage_manifest.yml` and the per-table schemas   | No                 |
| `sandbox_generate.py --scale {tiny,full}` | Avro files in a local directory                     | No                 |
| `sandbox_coverage.py`                     | Pass or fail against the manifest, reading the Avro | No                 |
| The load step                             | GCS upload, `CREATE OR REPLACE TABLE`, `bq load`    | Yes                |

Only the load step touches the warehouse, so it runs from a terminal, CI or
Dagster, never from an assistant session.

### Colonization resistance

Saturate every column and every join path with benign-but-ugly residents, so no
empty niche is left for a sloppy kit assumption to occupy. The manifest defines
what saturated means and `sandbox_coverage.py` asserts it: one row per cell and
observed count, exit non-zero on any zero.

### Must-be-empty canaries

`canaries.yml` holds entries shaped `{persona, query_shape, expect}`, where
`expect` is `BLOCKED`, `ROWS` or `ZERO`. `BLOCKED` asserts the real denial text
— for the SQL API, `Table or CTE with name '<view>' not found`.

**A quiet zero rows against a `BLOCKED` canary is a failure, not a pass.** That
one rule is what mechanically forces sign-off in production mode: a dev-mode
runner fails its own canaries rather than reporting a falsely benign matrix
([#4605](https://github.com/TEAMSchools/teamster/issues/4605)). The Cube Cloud
form of the same criterion: run them against the sandbox's production
environment, never a Dev Mode one.

[`scripts/cube_rls_matrix.py`](../../../scripts/cube_rls_matrix.py) already
emulates one viewer per connection. The work is an `--expect <canaries.yml>`
flag and a non-zero exit, which turns a human-read matrix into an assertion
runner.

Both tiers run the same files. KTAF CI owns them, because KTAF owns the dbt
marts and the `access_policy` blocks and must break first when a policy changes.
MasterBorn's kit suite runs them unmodified as its acceptance gate.

### How a developer emulates a persona

Two paths, both covering every persona the manifest fabricates:

- **SQL API** — open one connection per persona, with the persona's address as
  the connecting user and the deployment's SQL password. Identity is the
  connecting user, so the connection _is_ the switch; there is no in-session
  swap and none is needed. This is what the matrix runner already does.
- **REST** — mint a token carrying the persona's `email` claim, signed with the
  sandbox deployment's API secret. `checkAuth` verifies the signature and
  resolves that identity.

Holding a deployment's API secret therefore means being able to become any
persona on it. On the sandbox that is the point, and it is safe because every
row is fabricated. It is also exactly why the sandbox is a separate deployment
with its own secret.

`CUBE_IMPERSONATORS` is not part of this. It governs the Cube Cloud web UI,
which MasterBorn does not have.

### Divergence assertions, in their own file

The three divergence cells need pairs of queries asserted to return materially
different numbers. They go in a separate file from `canaries.yml`.

Not for tidiness: MasterBorn runs `canaries.yml` unmodified as their acceptance
gate. A canary going red means the access model broke; a divergence assertion
going red means KTAF's generator regressed. Merged, MasterBorn's gate fails for
something MasterBorn cannot fix, which is how a gate starts getting overridden.
One runner serves both.

### Mutation-test both

A canary that would still pass with the policy deleted proves nothing. Perturb
one `access_policy` block or one persona's scope value and require at least one
canary to flip red. Report uncaught mutations as a percentage. Perturb the
generator so a divergence pair converges, and require that assertion to fail.

### Scale ranges announce their own errors

Seed assessment scopes with realistic, incomparable ranges — SAT at 400–1600
beside ACT at 1–36. A wrong cross-scope `avg_scale_score` pooling then produces
a number nobody can read as plausible.

This is the one failure no assertion catches. Scope-bound measures recompute
correctly at any grain and are simply meaningless across incomparable scopes, so
only a person noticing catches it. Make the error announce itself in a
screenshot.

## Piece 4 — the checks

Three checks and one signal. None of them is a fingerprint.

**Every column the model references exists in the snapshot, at the same
commit.** A set difference between two files in one checkout: no credentials, no
warehouse read. It runs in CI on every pull request and blocks the generator.

Comparing within a commit rather than against the pin is what makes it work on a
refresh PR. A refresh computes the snapshot from the model as it stood when the
refresh ran; if a model change lands while that PR is open, merging it would
otherwise produce a commit whose model and snapshot disagree. Holding the
invariant at every commit means the pinned pair is consistent for free, because
the pin is a commit.

It runs before anything is generated or deployed, it catches the case that
happens — a model change outrunning the snapshot — and it cannot cry wolf,
because it reads no moving input.

**After loading, the sandbox's columns equal the pinned snapshot's columns.**
Catches a partial load, which is the one way the sandbox can end up short of the
snapshot it was built from.

**`/meta` resolves member-for-member against the pinned catalog.** `/meta` is
generated by `CubeToMetaTransformer.compile()` and never touches the warehouse,
so this proves the deployed model is the pinned model and nothing about the
data. That is worth having: Piece 5 deploys by running a command against a
tagged checkout, and a deploy that silently did not take is the failure nobody
notices.

It compares against the **pinned** catalog, not the newest on `main`. Comparing
against `main` would turn it red on every production change, and a gate that
cries wolf gets overridden.

**Drift is a signal, not a gate.** Report the distance between the pinned
snapshot and the newest one on `main`, as the diff a bump would ship. Nobody is
paged because a pin is three weeks old.

## Piece 5 — deploy and cadence

**Deploy with CLI, from a tagged checkout.** A bump is
`git checkout sandbox-YYYY.MM.DD && npx cubejs-cli deploy`. Nothing deploys
until someone runs that command, whereas Git mode deploys on every push to the
tracked branch and leaves deliberateness resting on branch discipline.

Two costs, both accepted: a deploy token to store, and an explicit exception to
[`src/cube/CLAUDE.md`](../../../src/cube/CLAUDE.md)'s "no manual deploy
command". **Scope that rule to production** rather than leaving the sandbox
quietly contradicting it; a rule with a silent exception stops being followed.

### Cadence

**The review is scheduled; the bump is not.** Read the drift report monthly.
Bump when MasterBorn asks, or when KTAF has a reason — the kit needs a member
that does not exist yet, or the pin has drifted far enough that the repoint is
getting worse.

A drift threshold that compels a bump is tracking `main` with extra steps, and
it reopens the failure this design rejects: MasterBorn's in-flight build moving
under them without anyone deciding. Analytics engineering owns the bump.

### Each bump

1. Move the single pin — model, snapshot and catalog together.
2. Regenerate the catalog and commit it, so the move is a reviewable diff.
3. Tag the commit `sandbox-YYYY.MM.DD`.
4. Take the member-level diff of additions, removals and retypes as the release
   note.
5. Send that note to MasterBorn **before** deploying. A note arriving after the
   surface changed is a changelog, not a warning, and warning is the point.
6. Deploy that checkout.
7. Re-run the coverage, canary and divergence suites against the new state.

## How each tier sets up

### MasterBorn's kit developers

1. Read the published catalog reference and parse `cube-catalog-meta.json`.
   Available before the sandbox exists.
2. Query the sandbox with its own API secret and SQL API password.
3. Run the coverage and canary suites as the kit's acceptance gate, attaching
   the runner's JSON output, including mode flags, to each kit release.

**No Cube Cloud account and no web UI**, so no Playground and no data model
browser. A seat governed by a role is a configuration guarantee; no seat is a
structural one, and MasterBorn needs neither to build the kit. If they ever need
the web UI, the answer is a separate Cube Cloud account, not a seat in KTAF's.

They keep using the sandbox after the production cutover. The repoint grants the
product's end users access, not MasterBorn's engineers.

### KTAF internal app developers

They build against the sandbox on the same terms, and never hold a production
Cube credential.

### KTAF staff, in production

Unchanged from the parent spec's production identity pass-through. The app
passes an identity, never a scope; the Cloud Run service derives scope
server-side from HR data; every staff member already has a
`dim_staff_cube_access` row.

## Deployment configuration

The sandbox deployment carries:

- **`CUBEJS_DB_BQ_PROJECT_ID` and `CUBEJS_DB_BQ_CREDENTIALS`, both set.**
  `cube.js` builds its own BigQuery client, and without explicit credentials it
  falls back to Cube Cloud's ambient host identity
  ([#4466](https://github.com/TEAMSchools/teamster/issues/4466)), which denies
  everyone. A deployment that denies everyone looks exactly like perfect
  isolation, so Piece 1's test would pass for the wrong reason.
- **`CUBE_IMPERSONATORS`.** Web UI users resolve through `cubeCloud.username`
  against the fabricated `dim_staff_cube_access`, so a real KTAF person matches
  no row and is denied. Anyone testing personas needs an entry. This list is
  KTAF-only.

## Sign-offs

**`reserved_names.yml` needs adopting, not writing.** The set exists. Coinage
makes a surname unique; it does not make anyone recognise it. Agree the set
once, then publish it in `docs/reference/` and the partner handoff, and replace
the file's starter-set header with the reservation. Until then it is a list of
words rather than a namespace.

The contract — why surnames are coined, why given names carry character classes
— lives in this spec, not only in the file's comments.

## Out of scope

- **Whether the kit is the only sanctioned path to Cube for internal apps.** A
  policy decision affecting Deliverable 1 only.
  [#5522](https://github.com/TEAMSchools/teamster/issues/5522).
- **Exercising the kit's production authentication path.** MasterBorn queries
  the sandbox with its own credentials while internal apps reach production
  through the token-exchange service, so the kit's production auth path never
  runs in the sandbox.
  [#5523](https://github.com/TEAMSchools/teamster/issues/5523).

## Open

- **Who gets `iam.googleapis.com/denypolicies.list` on `teamster-332318`**, so
  the scheduled check can assert the deny policy exists.
- **Landing `cube-catalog-meta.json` on `main`.** Nothing should be built
  against a catalog carried forward from a branch.
- **Whether a Git-mode deployment can point production at a branch other than
  `main`.** A note for the record; CLI wins either way.

## Related

- [2026-08-06-cube-partner-shape-first-integration-design.md](2026-08-06-cube-partner-shape-first-integration-design.md)
  — the parent design
- [#5266](https://github.com/TEAMSchools/teamster/issues/5266) — this work
- [#5517](https://github.com/TEAMSchools/teamster/issues/5517) —
  `canSwitchSqlUser` rejects `@kippmiami.org`. Blocks Superset from
  impersonating Miami staff; does not affect this build, which never switches in
  session.
