# Cube sandbox — requirements pass

This is the one file. Read it top to bottom, stop wherever you like, write `CB:`
where you want to say something.

It walks the sandbox design one part at a time and settles each before the next
is drafted. Its only output is a rewritten
[2026-09-11-cube-sandbox-build-design.md](2026-09-11-cube-sandbox-build-design.md).
When all 10 parts are approved, this file folds into that spec and is deleted.

Tracked in [#5266](https://github.com/TEAMSchools/teamster/issues/5266), on
[#5267](https://github.com/TEAMSchools/teamster/pull/5267).

## How to use this file

- **Write `CB:` anywhere** — inline, on its own line, or in an HTML comment.
  Everything marked that way gets answered before the part is redrafted.
- **One part at a time.** Only the part marked "Drafted" below needs you right
  now. The rest are one-line stubs on purpose.
- **Questions count as comments.** A part is not approved until it reads right
  to you.
- **Nothing is committed to.** The branch is specs only. Everything built before
  this pass was removed in
  `revert(cube): drop everything built before the plan`, so no decision here has
  to preserve a prior implementation.

## Where we are

| #   | Part                                      | Status                  |
| --- | ----------------------------------------- | ----------------------- |
| 1   | Why a sandbox at all                      | Approved                |
| 2   | Deployment shape and Cube Cloud isolation | Approved                |
| 3   | Piece 1 — isolation proof                 | Approved                |
| 4   | Piece 2 — coverage contract               | Approved                |
| 5   | Piece 3 — generator scope and fabrication | Approved                |
| 6   | Piece 3 — adversarial canaries            | Approved                |
| 7   | Piece 4 — drift gate                      | Approved                |
| 8   | Piece 5 — deploy mode and cadence         | Approved                |
| 9   | Sign-offs — reserved names, domain        | Approved                |
| 10  | Out of scope — kit enforcement            | **Drafted — needs you** |

Evidence gathered so far lives in the appendix at the bottom, filed under the
part it belongs to. You never need to read it unless a part's proposal looks
wrong and you want to see why it was made.

## Part 1 — Why a sandbox at all

Written for someone who has read neither spec. This part exists so the work can
be explained to stakeholders without walking them through the mechanics.

### The problem

MasterBorn is building a developer kit. KTAF internal developers build
applications on that kit. Neither group should ever hold a credential that reads
real student or staff data. But you cannot build against a semantic layer you
cannot query. They need a Cube deployment that answers real queries and contains
no real people.

### Three ways to give an outside party a queryable data surface

Two were rejected, for reasons a stakeholder can repeat without help:

- **Production with restricted access.** Rejected because `CUBEJS_API_SECRET` is
  deployment-wide. A token minted against a branch environment is verified by
  production's `checkAuth` using the same secret, so it is mechanically a
  production credential. There is no restricted version of production access to
  hand out.
- **A de-identified copy of production.** Rejected because de-identification
  starts from real records. It carries re-identification risk, needs a stated
  risk threshold nobody at KTAF has set, and per PTAC is not achieved by
  removing direct identifiers alone. That is a governance project, not an
  engineering task.
- **A fabricated dataset in a separate GCP project.** Chosen. No real row ever
  enters it, so there is no re-identification risk to assess and no threshold to
  set.

### Why fabrication is days of work rather than months

One thing is read from production: **schema** — column names, types and
nullability. No data of any kind, ever. The privacy argument is one sentence
long, and it is structural rather than statistical.

Values the kit must match come from the model rather than from production.
`access.js` settles the access-control enums, and every other load-bearing value
is already written down in the cube YAML, because a value that matters gets
documented. Everything else is invented.

### The part that is easy to miss

The sandbox is not a demo. A wrong assumption inside a single application hurts
that application's users. A wrong assumption inside a **kit** is frozen and
copied into every app built on it.

So the sandbox's job is not to look like production. It is to teach the awkward
parts of the access model loudly, before the kit freezes a guess about them.
That reframe is why the coverage contract is a generated file that a script
asserts, rather than a paragraph of prose asking people to be careful.

### The isolation claim, in one line

The sandbox service account holds no IAM on the production project, an IAM deny
policy makes that unreopenable by a later grant, and a scheduled check proves
the read actually **fails** — not merely that no grant was written. Those are
three different claims and the design wants all three.

### One terminology trap

"The sandbox" is not Cube's **Playground**. Playground is a Cube Cloud web UI
feature in the existing production deployment, and
[`src/cube/CLAUDE.md`](../../../src/cube/CLAUDE.md) forbids its Models tab
because it overwrites hand-authored YAML. The sandbox is a separate Cube Cloud
deployment pointed at a separate BigQuery project. If a stakeholder says
"playground", that is the thing to correct.

<!-- CB: comments on Part 1 go here, or inline above. -->

## Part 2 — Deployment shape and Cube Cloud account isolation

### What is already settled and not reopened here

The sandbox is a hosted Cube Cloud deployment reading a separate BigQuery
project. Cube confirmed a separate deployment with a separate data source, and a
local Cube Core container was considered and declined on 2026-09-11.

### The gap: the design has two boundaries and built one

| Boundary      | Separates                                       | Designed in |
| ------------- | ----------------------------------------------- | ----------- |
| Data plane    | Sandbox BigQuery project from `teamster-332318` | Piece 1     |
| Control plane | Sandbox Cube Cloud deployment from production's | Nowhere     |

Both deployments live in one Cube Cloud account. A GCP deny policy says nothing
about that. If MasterBorn holds a seat in that account, what they can reach in
the production deployment is decided by their Cube Cloud role — and nothing in
the spec says what that role is.

### Decision: MasterBorn gets no Cube Cloud account and no web UI access

Confirmed by Cristina, 2026-09-23. They hold the sandbox's own API secret and
SQL API password, and nothing else. No seat exists for them in KTAF's Cube Cloud
account, so the control-plane boundary has nothing to govern.

They build the kit against three things: the `/meta` endpoint, the committed
catalog `cube-catalog-meta.json`, and the query APIs. No Cube Cloud web UI, so
no Playground and no data model browser. Note that the catalog is not on `main`
yet — see [A9](#a9--the-specs-cube-model-facts-checked-against-main).

This is the move the design has already made twice. A shared dataset with a
templated name was rejected for turning a structural boundary into a string. The
local container was rejected for needing a new seam in `cube.js`. Seats governed
by a role would be a configuration guarantee; no seats is a structural one.

Two alternatives were available and are now moot. Recording them so the decision
is not reopened by someone who finds them:

- **Deployment-scoped custom roles.** The review cites these as Enterprise-only.
  I could not confirm that tier in the published documentation — and with no
  seats to scope, the question no longer has to be answered.
- **A separate Cube Cloud account for MasterBorn.** Structural, but it costs a
  second subscription to solve a problem that no longer exists.

**What would reopen this:** MasterBorn asking for the web UI. The answer then is
a separate Cube Cloud account, not a seat in KTAF's.

### What the sandbox deployment must be configured with

- **`CUBEJS_DB_BQ_PROJECT_ID` and `CUBEJS_DB_BQ_CREDENTIALS`, both set.**
  `cube.js` builds its own BigQuery client. Without explicit credentials it
  falls back to Cube Cloud's ambient host identity
  ([#4466](https://github.com/TEAMSchools/teamster/issues/4466)), which denies
  everyone. That failure matters more here than it normally would: a deployment
  that denies everyone looks exactly like perfect isolation, so Piece 1's test
  would pass for the wrong reason. Part 3 has to tell the two apart.
- **`CUBE_IMPERSONATORS`.** Web UI users resolve through `cubeCloud.username`
  against the fabricated `dim_staff_cube_access`, so a real KTAF person matches
  no row and is denied. Anyone testing personas in the sandbox web UI needs an
  entry. Per the decision above, this list is KTAF-only.

### Nothing here is open

Both questions this part opened are closed: MasterBorn needs no account, and the
custom-role tier question died with it.

<!-- CB: comments on Part 2 go here, or inline above. -->

Evidence: [A1](#a1--cube-cloud-account-isolation-is-unaddressed).

## Part 3 — Piece 1, isolation proof

### Piece 1 is built, and the isolation test passes

Built and tested on 2026-09-23.
[A3](#a3--the-sandbox-gcp-project-does-not-exist-yet) is closed.

| Thing             | Value                                                              |
| ----------------- | ------------------------------------------------------------------ |
| Sandbox project   | `teamster-cube-sandbox`, `kipptaf_marts` in US                     |
| Service account   | `cube-cloud-sandbox@teamster-cube-sandbox.iam.gserviceaccount.com` |
| Its roles         | `bigquery.jobUser`, `bigquery.dataViewer`, sandbox project only    |
| Cross-project IAM | None, in either direction                                          |
| Deny policy       | `deny-sandbox-bigquery` on `teamster-332318`                       |

The deny policy blocks every service account in the sandbox project from
BigQuery reads, queries and writes in production. A deny overrides any grant, so
a stray grant later cannot reopen access, and it does not depend on where the
project sits in the resource hierarchy.

### Three claims, and they are not the same claim

| #   | Claim                                                         | Proven by                | State    |
| --- | ------------------------------------------------------------- | ------------------------ | -------- |
| 1   | The sandbox service account holds no IAM on `teamster-332318` | Reading the allow policy | Reported |
| 2   | A later grant cannot reopen it                                | `deny-sandbox-bigquery`  | Attested |
| 3   | The read actually fails                                       | A test that errors       | Verified |

Claim 1 is about what was written. Claim 3 is about what happens. The design
wants all three because the first two can both hold while the third quietly does
not, and because claim 3 alone can pass for a reason that has nothing to do with
isolation — see the next section.

### The test needs a positive control, or it proves nothing

Part 2 established that a Cube deployment missing `CUBEJS_DB_BQ_CREDENTIALS`
falls back to Cube Cloud's ambient host identity, which denies everyone. A
service account with no working credentials at all fails on production reads
too. **A deployment that is simply broken is indistinguishable from a deployment
that is perfectly isolated, if the only thing you test is that production reads
fail.**

So the isolation test is two assertions, not one:

- **Negative:** the sandbox service account reading
  `teamster-332318.kipptaf_marts` fails with a permission error.
- **Positive:** the same service account, in the same run, reading the sandbox
  project's own dataset succeeds.

Without the positive leg the test goes green on the day the sandbox breaks. With
it, a broken deployment fails the test loudly instead of passing it silently.

Both legs were run on 2026-09-23, authenticating with the sandbox service
account's own key — the same path Cube Cloud uses through
`CUBEJS_DB_BQ_CREDENTIALS`, so the test exercises the real connection rather
than a stand-in:

- Positive: `SELECT 1`, billed to `teamster-cube-sandbox`, succeeded.
- Negative: `SELECT * FROM teamster-332318.kipptaf_marts.dim_locations LIMIT 1`
  returned `403 Access Denied … User does not have permission to query table`.

### What the passing test does and does not prove

It proves claim 3. It does **not** independently prove claim 2, because an
absent grant and an active deny policy produce the same 403 — the test cannot
tell which one refused the read.

Its 403 read `User does not have permission to query table`, the ordinary
absent-grant denial, and a deny policy would produce a 403 too. Closing that gap
is what the second assertion below is for, and it is what the review asked for
in [A2](#a2--the-backstop-is-an-iam-deny-policy).

### The boundary has a consequence: no single identity can build the sandbox

The generator was specified to read production's `INFORMATION_SCHEMA` and write
sandbox rows. **No identity can now do both**, and the two directions are closed
by different mechanisms, which is what decides whether an exception is even
possible:

| Direction            | Blocked by              | Can it be excepted?                   |
| -------------------- | ----------------------- | ------------------------------------- |
| Sandbox → production | `deny-sandbox-bigquery` | No. Only by deleting the deny policy. |
| Production → sandbox | Absence of a binding    | Yes, by granting one.                 |

So "make an exception" means exactly one thing: give a production service
account write access to the sandbox project.

**Reject that.** It creates an identity that can read real student data and
write to the surface MasterBorn queries. Of all the bindings the design could
add, that is the one whose failure mode is real rows landing in the sandbox —
the single thing the sandbox exists to make impossible.

### Decision: the generator reads a committed schema snapshot

Split the work at the boundary instead of punching through it:

1. **Refresh the snapshot.** Runs with production credentials, reads
   `INFORMATION_SCHEMA` for the Cube-referenced columns, writes a file to the
   repo. No sandbox access.
2. **Generate and load.** Runs with sandbox credentials, reads the committed
   snapshot, writes sandbox tables. No production access.

Each step holds one identity and needs no cross-project grant. That is not a
workaround — it is better than what it replaces, in three ways:

- **Reproducibility comes back.** The generator's inputs become seed, commit SHA
  and a committed file. The review's reason for cutting the GCS run manifest —
  "a seeded generator plus its commit SHA already makes every run reproducible"
  — was broken by live schema being an input, and this repairs it. See
  [A6](#a6--the-piece-4-cut-and-how-big-the-addition-is).
- **Drift becomes a reviewable diff.** A production column dropped or retyped
  shows up as a snapshot diff in a pull request, read by a person, before it
  reaches the sandbox. That is strictly more informative than a fingerprint
  mismatch and it arrives earlier.
- **It gives the deliberate-deploy story its release note.** The spec already
  wanted each sandbox bump to ship a diff of added, removed and retyped members.
  The snapshot diff is that document, for free.

### The snapshot carries schema only

Because the snapshot is committed and git history is permanent, the safest rule
is the narrowest one: **the snapshot carries column names, types and
nullability, and nothing else.** No values, no distinct-value pulls, no counts.
There is then no PII decision to get right on the refresh step, because it never
reads a row.

An earlier draft had it carry codesets too, with an allowlist, a cardinality
ceiling and a PII exclusion to keep the pull safe. Part 5 retires that: the
values the kit must match are in the model, not in production data, so the guard
protected a read that does not need to happen.

### What to do with the credentials

- **Never in the checkout.** The repo's hooks block credential JSON paths for
  every tool, and git history is permanent.
- **1Password is the store.** The Cube deployment reads the key as
  `CUBEJS_DB_BQ_CREDENTIALS`, set on the sandbox deployment alongside
  `CUBEJS_DB_BQ_PROJECT_ID`, per Part 2.
- **Prefer impersonation for local testing** over a second copy of a downloaded
  key. The Cube deployment needs a key because it runs outside GCP; your laptop
  does not.

### Who can read the deny policy, and why that shapes the check

The policy was created by the engineer who created the sandbox project, and its
existence rests on his attestation. Nobody on the analytics side can confirm it
independently — both identities tried on 2026-09-23 got 403 on
`denypolicies.list` against `teamster-332318`:

| Identity                               | Result                          |
| -------------------------------------- | ------------------------------- |
| `codespaces@teamster-332318` (the ADC) | 403, `denypolicies.list` denied |
| `cbaldor@apps.teamschools.org`         | 403, `denypolicies.list` denied |

That is an operational constraint, not a doubt about the policy.

### What the scheduled check must assert

Two assertions, not one:

1. The 403 on production, with the sandbox read succeeding in the same run.
2. That `deny-sandbox-bigquery` still exists on `teamster-332318`.

The second is not about today's state, which is attested. It catches a later
deletion or edit — the same reason the design wants claim 3 separately from
claim 1.

### When it runs

The child spec says only "run the isolation check on a schedule as a Dagster
asset check" and that a failure blocks the generator. It never says how often,
so this part sets it:

- **Daily, on a schedule.** The risk being guarded is an IAM edit nobody
  remembers making, which moves on the scale of days, not minutes.
- **And as a blocking check before each generator run.** The generator writes
  only on deliberate bumps, so it could otherwise write against a boundary that
  broke since the last daily run.

Neither leg is expensive: two small queries and one IAM call.

### It needs two identities, split the same way the generator is

| Assertion                      | Identity                            |
| ------------------------------ | ----------------------------------- |
| The 403, and the sandbox read  | The sandbox service account key     |
| `deny-sandbox-bigquery` exists | A production identity with IAM read |

Neither is the dangerous combination: the sandbox account cannot read production
data by construction, and an IAM-read identity touches no BigQuery data and
cannot write to the sandbox. But one service account holding both would be a
step toward the binding
[rejected above](#the-boundary-has-a-consequence-no-single-identity-can-build-the-sandbox),
so the check is built as two, split on the same boundary as the generator.

Nothing on the analytics side holds `denypolicies.list` on `teamster-332318`
today, so granting that read — and to whom — is the one thing this check needs
before it can be built.

### What is open

- **Who gets `denypolicies.list` on `teamster-332318`.** Needed before the
  second assertion can be built. It is an IAM-read grant, not data access, and
  it goes to whatever identity runs the check.

A2's last unchecked item — which role creates an IAM deny policy — is answered
by the engineer holding it. The snapshot's file location, its shape, and what
runs the refresh step are Part 5's, and are recorded there.

<!-- CB: comments on Part 3 go here, or inline above. -->

Evidence: [A2](#a2--the-backstop-is-an-iam-deny-policy),
[A3](#a3--the-sandbox-gcp-project-does-not-exist-yet).

## Part 4 — Piece 2, coverage contract

### What Piece 2 produces, and why it comes first

A generated file, `coverage_manifest.yml`, listing every cell the sandbox data
must contain, each marked `uncovered` until the generator fills it. It is
written before the data generator, because it is that generator's specification.

The property worth protecting: it is **generated, not hand-written**. A new
production column, view or scope value becomes a loud uncovered cell rather than
an absence nobody notices. Every decision below is judged against whether it
keeps that true.

### The null rule cannot work as written

The rule is one null row and one non-null row per column, "unless declared
not-nullable". Re-measured against production on 2026-09-23: **243 columns
across 21 tables, every one `NULLABLE`, none nested.** So the exemption never
fires, and the rule demands a null in all 243 — including join keys and the
columns `access_policy` filters on. A null join key breaks the very fixtures the
manifest defines, and a null policy column makes the persona resolve to nothing,
which is the one thing the sandbox exists to exercise.

The spec's "every one of them nullable" was right and the review's "nearly
every" was the imprecise one. The generator should still assert the count it
finds rather than carry 243 as a constant — the figure has already moved once,
from the spec's 230.

### Decision: exempt structurally, and err toward more nulls than production

Two exemption classes, each **derived rather than listed**, so the
generated-not-hand-written property survives:

| Class                                  | Derived from                       |
| -------------------------------------- | ---------------------------------- |
| Join and surrogate keys                | The join-path fixtures             |
| Columns any `access_policy` filters on | Parsing the 6 views' policy blocks |

Every other column requires both a null and a non-null.

The rejected alternative was to require a null only where production has one.
That is evidence-based, but it is the wrong direction twice over. It would make
the manifest depend on reading production **data**, not just schema — costing
Part 1 its one-sentence privacy argument for a null count nobody needs. And
mirroring production exactly lets the kit assume a column with no nulls today
never will have one. A sandbox with more nulls than production makes the kit
defensive, which is the same reasoning that already covers enum values
production has never had.

### Three committed artifacts, and none of them may go stale

Piece 2 has the manifest generator read `INFORMATION_SCHEMA` itself. That is the
same production read the snapshot refresh in
[Part 3](#decision-the-generator-reads-a-committed-schema-snapshot) already
does. Naming all three artifacts together makes the overlap visible and fixes a
worse problem underneath it:

| Artifact                 | Generated from                       | Needs         |
| ------------------------ | ------------------------------------ | ------------- |
| Schema snapshot          | Production `INFORMATION_SCHEMA`      | BigQuery read |
| `coverage_manifest.yml`  | The snapshot, `access.js`, cube YAML | Nothing       |
| `cube-catalog-meta.json` | Production Cube `/meta`              | Cube API read |

So the manifest takes committed inputs only and needs no cloud access: it runs
in CI and on any laptop, its output is deterministic, and its diff is reviewable
in a pull request exactly as the snapshot diff is. That sharpens A3's sequencing
note — the manifest and the contract need no cloud resources at all.

### The catalog is stale today, and nothing would have caught it

The catalog is what MasterBorn builds the kit against and what Piece 4's
surviving `/meta` check compares to. The copy that exists predates last week's
query-rewrite and attendance changes: it still carries `is_latest_record`,
`is_month_end_record` and `staff_department_scope`, and has no reference to the
new attendance periods view or table.

A stale catalog is not a housekeeping problem. It is Part 1's failure mode
exactly — a kit frozen against a model that no longer exists.

The `/meta` check is the control that should have caught it, and it did not,
because the catalog is not on `main` and no check runs. So:

- **Regenerate the catalog from the current deployment, and land it on `main`**
  before anything is built against it. Never carry it forward from a branch or
  from scratch. Doing this is plan work, not this branch's.
- **A model change refreshes the snapshot and the catalog together.** Both
  describe the surface the sandbox imitates, and last week moved both.
- **Wire the `/meta` check before the kit is handed over, not after.** Its value
  is catching this class of drift, and it has already missed one instance.

### Refreshing is not deploying, and the sandbox pins a revision

A refresh landing on `main` must change nothing MasterBorn sees. The spec
already rejected tracking `main` because "a model change merged on a Tuesday
afternoon breaks MasterBorn's in-flight build with no warning and no changelog",
and that reasoning applies to the data side exactly as it does to the model.

So the pipeline has a deliberate gap in the middle:

1. Production changes.
2. The snapshot and catalog refresh lands as a pull request — visible, diffed,
   reviewed. **Nothing has moved for MasterBorn.**
3. Someone decides to bump.
4. The generator rebuilds the sandbox and the model is redeployed.

The diff accumulated across step 2 is the release note step 4 ships. That is the
document Piece 5 already asked for, produced as a by-product rather than written
by hand.

**The generator pins a snapshot revision rather than reading the latest.** A
bump is the act of moving that pin. Without this, a generator run for any other
reason — a retry, a bugfix, a re-materialization — would quietly pull in every
refresh since the last bump, which is the Tuesday-afternoon break arriving by a
different route.

This also decides what the `/meta` check compares against: **the catalog at the
pinned revision, not the newest one on `main`.** Comparing against `main` would
turn the check red on every production change, and a gate that cries wolf gets
overridden within a month — the review's own objection to the fingerprint gate.
How far the pin has drifted from `main` is a separate and much softer signal,
which is what Piece 4 meant by measuring the distance. Part 7 settles that.

### Two things stay exactly as specified

Restated because both are load-bearing and easy to lose in a rewrite:

- **The table set is the union of `sql_table:` values and the `kipptaf_marts.*`
  references in `cube.js`, asserted against the count the generator finds.**
  Parsing `sql_table:` alone finds 20 distinct tables across 21 declarations.
  The missing one, `dim_staff_reporting_chain`, is read directly by
  [`cube.js:145`](../../../src/cube/cube.js) and appears in no cube YAML, making
  the union 21. Miss it and the sandbox still compiles, while identity
  resolution fails for exactly the `reporting_chain` personas that production
  cannot test either. Assert the count rather than hard-coding it: the spec said
  20 and it is now 21.
- **Enum domains come from `access.js`, never from `SELECT DISTINCT`.**
  Production is a subset of the domain the code handles — 4 policy branches have
  no production row that reaches them. This does not breach the parent spec's
  fidelity rule, which covers a sandbox wider than production, not a production
  narrower than its own code.

### The spec's model facts are stale — see A9

Checked against `main` on 2026-09-23, after last week's query-rewrite and
attendance changes. The snapshot anchors no longer exist, so the manifest's
anchor cells and their null-rule exemption are both gone from this part; what
takes their place is below. Several other counts moved. The full list is in
[A9](#a9--the-specs-cube-model-facts-checked-against-main).

### What replaces the anchor rule

The anchors are gone because the fact is now dense: it carries a row for every
calendar day a student was enrolled, break days included, so any date resolves
and no anchor flag is needed or available. Point-in-time questions pin
`attendance_date` instead.

The hazard did not go with them. It changed shape, and the model documents the
new form in its own comments — each of these is a query that **compiles, runs,
and returns a plausible wrong number**, which is the class the anchor cells
existed to expose. Three replacement cells, all read off traps the model already
names rather than invented here:

| Cell                          | What the sandbox must make visible                                  |
| ----------------------------- | ------------------------------------------------------------------- |
| Unpinned cumulative measures  | A date range must give a materially higher count than a pinned date |
| The two attendance views      | Day-weighted and student-weighted rates must disagree               |
| School weeks versus ISO weeks | An ISO week grouping must be visibly wrong                          |

- **Unpinned cumulative measures.** `count_chronically_absent`, `count_truants`
  and their rates read a cumulative position the fact re-stamps on every daily
  row, so over an open range they count students who crossed the line on _any_
  day, which runs high. If every fabricated student is either always or never
  chronically absent, the pinned and unpinned numbers match and a kit author
  never learns the pin matters. Fabricate students who cross mid-year.
- **The two attendance views are not interchangeable.** One is day-weighted and
  additive over a range; the other is student-weighted and non-additive across
  periods. Production has them diverging by 0.66 points. A sandbox where they
  agree teaches that either will do.
- **`period_type = 'week'` is the PowerSchool school week, not ISO.** Grouping
  by a native week granularity compiles, does not throw, and silently returns a
  meaningless breakdown, with no query-time guard. School weeks diverge from ISO
  Mondays on roughly 14% of production calendar days, so fabricate school weeks
  that split at month and term boundaries rather than a clean Monday-to-Sunday
  grid.

Part 5 fabricates the data that makes these true; Part 6 decides which also get
a canary.

<!-- CB: comments on Part 4 go here, or inline above. -->

Evidence: [A4](#a4--the-coverage-manifests-null-rule-cannot-work-as-written).

## Part 5 — Piece 3, generator scope and fabrication

### Two steps, two identities, and preferably two systems

Part 3 split the work at the isolation boundary. Naming where each half runs:

| Step              | Reads                                       | Writes                    | Identity    |
| ----------------- | ------------------------------------------- | ------------------------- | ----------- |
| Refresh           | Production `INFORMATION_SCHEMA`             | The snapshot, to the repo | Production  |
| Generate and load | The pinned snapshot, `access.js`, cube YAML | Sandbox tables            | Sandbox key |

The refresh belongs in Dagster, where production credentials already are. The
generate-and-load step needs only committed files and the sandbox key, so it can
run in CI. **Prefer that split.** Neither identity is dangerous alone, and
keeping them in separate systems costs nothing here — putting both in one
Dagster deployment is allowed but is the weaker arrangement, for the same reason
Part 3 builds the isolation check as two checks.

The snapshot lives beside the model it describes, under `src/cube/sandbox/`,
with the coverage manifest. It is committed, diffed in review, and pinned by
revision per Part 4.

### Decision: no codesets, and the values come from the model

The spec reads "schema and codesets" from production. Drop the codesets. The
refresh step then reads no production data at all, only `INFORMATION_SCHEMA`.

Three reasons, in order of weight:

1. **The vocabulary that matters is already elsewhere.** `access.js` settles the
   access-control enums, and the spec already forbids sourcing those from
   production data. Every other value the kit must match is written down in the
   cube YAML — `period_type` is year, month and week; `ada_tier` is Tier 1
   through 4; tardy is the T-prefix codes; out-of-school suspension is OS, OSS,
   OSSP and SHI. A value that matters gets documented, because it has to be.
2. **Real values make the sandbox worse at its job.** A kit author who hardcodes
   a value list taken from the sandbox has written a bug. If the sandbox carries
   production's real values, that bug survives repoint by luck. If the values
   are visibly invented, it fails in the sandbox — which is what the sandbox is
   for.
3. **It removes the only production-data read in the design**, and with it the
   allowlist, the cardinality ceiling and the PII exclusion that existed solely
   to make that read safe. Part 1's privacy argument becomes absolute rather
   than qualified.

The one risk worth naming was a load-bearing value that is **not** in the model,
leaving the kit without it. Cristina confirmed on 2026-09-23 that the cube YAML
always carries the allowlists, and the YAML is where the kit reads them from —
so there is no such category. The concern is closed rather than accepted.

### Derive the table set and order; do not write them down

Piece 3 lists the tables and their dependency tiers explicitly. That list is now
wrong: it names `fct_student_attendance_daily`, which no longer exists, and
misses both `fct_student_attendance_enrollment_periods` and
`dim_staff_reporting_periods`.

It has gone stale twice, so stop maintaining it. The generator derives the table
set from the union Part 4 defines and the order from the model's join edges,
then asserts the counts it found. What stays is the invariant, which does not go
stale: **facts never invent a key — every foreign key is sampled from rows
already generated**, which makes referential integrity hold by construction.

The spine cycle also stays, because it is structural rather than a fact about
today's tables: `dim_student_enrollments` and `dim_student_section_enrollments`
reference each other, so neither can go first. Write enrollments with a null
homeroom key, generate section enrollments against them, then update the
enrollments. Leaving a slice of homeroom keys null is one of the manifest's
required cells, not sloppiness. This is the most likely place to produce a
dataset that loads cleanly and fails at query time, because a broken cycle shows
up as a join returning nothing rather than as an error.

### Scale, re-measured 2026-09-23

| Table                                       | Rows       | In the spec         |
| ------------------------------------------- | ---------- | ------------------- |
| `fct_student_attendance_enrollment_daily`   | 29,791,485 | 12,603,269, renamed |
| `fct_assessment_scores_enrollment_scoped`   | 15,080,518 | 13,504,949          |
| `fct_student_attendance_enrollment_periods` | 4,402,039  | Absent              |
| `dim_dates`                                 | 2,921,940  | 2,921,940           |
| `dim_students`                              | 31,297     | 31,194              |
| `dim_staff_work_history`                    | 30,116     | —                   |
| `dim_staff_reporting_chain`                 | 9,310      | —                   |

Generate at that scale. Pagination and query-timeout behaviour is what the
partner is meant to discover here rather than at repoint, and the biggest fact
is now 2.4 times what the spec sized for. Bound `dim_dates` to the real
academic-year range: production's spine runs to the year 9999, and an unbounded
date dimension is what drove the partitioned pre-aggregation incident (#4460).

**The latency fidelity break is smaller than the spec says.** It claimed 12 of
20 tables were production views the sandbox would flatten, making the sandbox
systematically faster. Today 9 of 21 are views, and the three that became
physical include the largest fact. The gap remains and still runs in the
direction the fidelity rule forbids, so keep telling the partner in writing that
sandbox latency must not be used to size timeouts, page sizes or caching — but
it is no longer the dominant effect.

### What the fabricated data must make true

Beyond the coverage manifest's cells, four things the generator must produce on
purpose, because a plausible dataset would omit all four:

- **Students whose cumulative position crosses mid-year**, so an unpinned date
  range returns a materially higher count than a pinned date (Part 4).
- **Day-weighted and student-weighted rates that disagree**, so the two
  attendance views are visibly not interchangeable (Part 4).
- **School weeks that split at month and term boundaries**, so an ISO week
  grouping is visibly wrong (Part 4).
- **Two distinct non-`none` `staff_benefits_scope` values**, plus `none`. One
  would let a kit author write `scope === 'all_in_scope'` and pass every test,
  freezing an equality check where `access.js` does a non-`none` check
  ([A5](#a5--staff_benefits_scope-is-answerable-from-evidence)). Take the
  siblings' vocabulary from `access.js` and the view policies, not from
  production rows.

Nothing here is anonymized: no real row enters the generator at any point, and
with codesets dropped, nothing reads production data either.

### What is open

- **Persona coverage needs regenerating, not editing.** Piece 3's personas are
  specified against seven scope columns and there are now five
  ([A9](#a9--the-specs-cube-model-facts-checked-against-main)).

<!-- CB: comments on Part 5 go here, or inline above. -->

Evidence: [A5](#a5--staff_benefits_scope-is-answerable-from-evidence),
[A9](#a9--the-specs-cube-model-facts-checked-against-main).

## Part 6 — Piece 3, adversarial canaries

The review keeps this piece unchanged and calls it the most valuable one. Most
of this part is therefore confirmation rather than decision — except for one
conflict it exposes with Part 9, and one question Part 4 handed forward.

### The distinction the whole piece rests on

`canaries.yml` holds entries shaped `{persona, query_shape, expect}`, where
`expect` is `BLOCKED`, `ROWS` or `ZERO`. `BLOCKED` asserts the real denial text
— for the SQL API, `Table or CTE with name '<view>' not found`.

**A quiet zero rows against a `BLOCKED` canary is a failure, not a pass.** That
one rule is what mechanically forces sign-off in production mode: a dev-mode
runner fails its own canaries immediately rather than reporting a falsely benign
matrix. Without it the entire suite can go green while enforcing nothing.

The Cube Cloud form of that criterion: run the canaries against the sandbox's
**production environment**, never a Dev Mode one.

The work is small because the runner exists.
[`scripts/cube_rls_matrix.py`](../../../scripts/cube_rls_matrix.py) already
emulates one viewer per connection; adding an `--expect <canaries.yml>` flag and
a non-zero exit turns a human-read matrix into an assertion runner. Do not
recreate the script.

Both tiers run the same files. KTAF CI owns them, because KTAF owns the dbt
marts and the `access_policy` blocks and must break first when a policy changes.
MasterBorn's kit suite runs them unmodified as its acceptance gate.

### The personas must live on `@apps.teamschools.org`

`cube_rls_matrix.py` connects over the **SQL API** — it is a `psycopg` client,
verified 2026-09-23. So persona switching goes through `canSwitchSqlUser`, which
only switches to `@apps.teamschools.org` addresses and must not be broadened.

**This rules out Part 9's synthetic domain for any persona a canary exercises.**
A `ktaf-sandbox.invalid` address cannot be switched to, so every canary using
one would fail for the wrong reason. Fabricated personas need addresses on the
real domain, made non-colliding by a reserved prefix such as `sandbox-`. Part 9
settles the prefix; it no longer gets to settle the domain.

### Poison pills: cut, and free instead

The spec seeds two assessment scopes with deliberately incomparable ranges so a
wrong cross-scope `avg_scale_score` pooling produces an absurd number. The
review cuts it as separate work, and is right: **realistic ranges already do
it.** SAT at 400–1600 beside ACT at 1–36 pools into a number nobody can read as
plausible, with no special seeding.

Keep the reasoning, which the cut does not remove. This is the one failure no
assertion catches — scope-bound measures recompute correctly at any grain and
are simply meaningless across incomparable scopes. Only a person noticing
catches it, so the error has to announce itself in a screenshot.

### What Part 4's hazards get instead of canaries

Part 4 named three queries that compile, run and return a plausible wrong
number. None fits the `BLOCKED`/`ROWS`/`ZERO` shape, because none is an access
failure — the caller is allowed to run them and gets an answer.

They need a second, smaller file of **divergence assertions**: pairs of queries
a careless kit would treat as equivalent, asserted to return materially
different numbers.

| Pair                                          | Asserted to differ |
| --------------------------------------------- | ------------------ |
| Pinned versus unpinned cumulative count       | Materially         |
| Daily view rate versus periods view rate      | Materially         |
| School-week grouping versus ISO-week grouping | Materially         |

If any pair converges, the fabricated data has lost the property Part 5 built
in, and the sandbox has quietly stopped teaching that lesson.

**They go in their own file, not in `canaries.yml`.** The reason is not tidiness
— it is whose gate fails. MasterBorn runs `canaries.yml` unmodified as their
acceptance gate, and a canary going red means the access model broke. A
divergence assertion going red means KTAF's generator regressed. Merge the two
and MasterBorn's gate fails for something MasterBorn cannot fix, which is how a
gate starts getting overridden.

Two smaller reasons agree. The row shapes differ: a canary is one query and an
expected outcome, a divergence assertion is two queries and a relation between
their results. And the two failures have different owners and different urgency.

One runner still serves both — it takes a path either way.

### Mutation testing is the only honest measure

A canary that would still pass with the policy deleted proves nothing. Perturb
one `access_policy` block or one persona's scope value and require at least one
canary to flip red. Report uncaught mutations as a percentage.

This applies to the divergence assertions too: perturb the generator so a pair
converges, and the assertion must fail.

### One thing this part depends on

`canSwitchSqlUser` rejects `@kippmiami.org`, so no Miami persona can be emulated
over the SQL API — 166 of the 1573 rows in `dim_staff_cube_access`, measured
2026-09-23. Until [#5517](https://github.com/TEAMSchools/teamster/issues/5517)
lands, the canary suite cannot cover Miami, and a green suite means less than it
appears to.

### Nothing here is open

<!-- CB: comments on Part 6 go here, or inline above. -->

Evidence: [A9](#a9--the-specs-cube-model-facts-checked-against-main).

## Part 7 — Piece 4, drift gate

The review cuts most of this piece, and the snapshot decision in Part 3 removes
the rest of its reason to exist. What is left is two small checks and one
signal, none of them a fingerprint.

### The question A6 left, answered

**What does the `/meta` check do between a landed snapshot refresh and the
rebuild that follows it?** Nothing, and that is the point. It compares against
the catalog at the **pinned** revision, so a refresh landing on `main` moves
nothing it looks at. A check that went red on every production change would be
overridden inside a month, which is the review's own objection to the
fingerprint gate.

### What the `/meta` check proves

`/meta` is generated by `CubeToMetaTransformer.compile()` — it serializes the
compiled data model and never touches the warehouse, verified 2026-09-23. So it
proves the deployed model is the pinned model, and nothing about the data.

That is still worth having. Piece 5 deploys by running a command against a
tagged checkout, and a mis-deploy, or a deploy that silently did not take, is
exactly the failure nobody notices. But it is a deploy-integrity check, not a
drift gate, and naming it accurately matters — an earlier draft of this part
claimed it left a data-side hole, which pinning already closes.

### Why pinning closes the data-side hole

`/meta` genuinely cannot see a column that the model references and the sandbox
lacks. Under pinning that state cannot arise:

1. CI asserts every column model@R references exists in snapshot@R.
2. The generator writes exactly the columns in snapshot@R.
3. So the model's columns are present in the sandbox, by construction.

**This holds only if one pin covers all three artifacts.** A bump moves a single
revision, and the model, the snapshot and the catalog move together. Pin them
separately and step 1 compares the wrong pair, which puts the hole back without
anything looking wrong.

The one place the chain can still break is a **partial load** — the generator
writes some tables and fails on a later one, leaving the sandbox short of the
snapshot it was built from. So the load ends by asserting the sandbox's columns
equal snapshot@R's columns. That is a completeness check on the generator, not a
drift check, and it is the only data-side assertion this piece needs.

### The check that replaces the fingerprint

Assert that **every column the cube model references exists in the pinned
snapshot**. It is a set difference between two committed files, so it needs no
credentials, no cloud, and no warehouse read. It runs in CI on every pull
request, and it blocks the generator the way the isolation check does.

That is stronger than the fingerprint it replaces, on three counts:

- It runs **before** anything is generated or deployed, rather than comparing
  two deployed states afterwards.
- It catches the case that actually happens: a model change that outran the
  snapshot. The reverse case, production dropping a column the model needs, is
  caught earlier still — the refresh comes up short and the shortfall shows up
  as a diff in a reviewed pull request.
- It cannot cry wolf, because both inputs are pinned. Nothing it reads moves on
  its own.

### Drift is a signal, not a gate

The spec wanted Piece 4 to measure how far the deployed model has drifted from
production. Keep that, and keep it soft: report the distance between the pinned
snapshot and the newest one on `main`, as the diff a bump would ship.

It is a release note waiting to be written, not a failure. Nobody is paged
because a pin is three weeks old. Piece 5 decides whether a distance ever
compels a bump.

### What is cut, and why nothing replaces it

| Cut                         | Why nothing replaces it                                |
| --------------------------- | ------------------------------------------------------ |
| The schema fingerprint      | Both inputs are pinned files; compare them directly    |
| The blocking asset check    | The CI check above blocks earlier and cheaper          |
| `ADD COLUMN` repair patches | A rebuild from a pinned snapshot cannot drift          |
| The GCS run manifest        | Seed, commit SHA and pinned snapshot determine the run |

The manifest is worth one extra line, because the review cut it for a reason
that was briefly wrong. Its justification — "a seeded generator plus its commit
SHA already makes every run reproducible" — failed while live production schema
was a generator input. Pinning the snapshot restored it, so the cut stands on
its original reasoning.

### Nothing here is open

<!-- CB: comments on Part 7 go here, or inline above. -->

Evidence: [A6](#a6--the-piece-4-cut-and-how-big-the-addition-is).

## Part 8 — Piece 5, deploy mode and cadence

### Deploy with CLI, on one reason rather than two

The spec gives two reasons to prefer CLI mode over Git mode. The second is
disproven: staging environments do not auto-create from a repository connection
or a push, so there is no per-branch noise to avoid
([A7](#a7--the-specs-second-reason-for-cli-mode-is-wrong)).

The surviving reason still decides it. **Under CLI mode nothing deploys until
someone runs the command. Under Git mode a push to the tracked branch deploys
immediately**, so deliberateness rests on branch discipline.

That is the same trade the design has now refused three times — a templated
dataset name, role-scoped Cube seats, and a production account writing to the
sandbox were all rejected for replacing a structural guarantee with a procedural
one. Branch discipline is procedural, and the surface in question is handed to
an outside party.

The costs are real and worth stating rather than minimising. CLI mode needs a
deploy token stored somewhere, which is one more credential to manage, and it
needs an explicit exception to a repo rule. Neither outweighs a mistaken push
deploying to MasterBorn.

### There is no sandbox branch

Worth stating plainly, because the spec's framing invites the opposite reading.
Three things differ between the sandbox deployment and production, and only one
of them needs a mechanism:

| What                 | Sandbox versus production                            |
| -------------------- | ---------------------------------------------------- |
| Model files          | **Identical.** Forking them breaks the kit's premise |
| Revision             | Older — a tagged commit on `main`'s own history      |
| Deployment variables | `CUBEJS_DB_BQ_PROJECT_ID` and its credentials        |

The sandbox is not a fork. Every `sql_table:` is project-unqualified, so the
same model files read a different warehouse purely from the deployment variable
— that single-variable repoint is what the whole design rests on. If the sandbox
YAML ever diverged from production YAML, the kit would stop building against the
production semantic layer.

So the sandbox needs a **revision**, not a branch. `sandbox-YYYY.MM.DD` tags a
commit that is already on `main`, and CLI mode deploys exactly that checkout.

A branch appears only inside the Git-mode alternative, because Git mode tracks a
branch head, and a long-lived branch is the only way it can express "an older
commit of `main`." That is an artifact of the mechanism, not something the
design wants.

### The web UI check is about a mechanism we are declining

The one question left for the Cube Cloud web UI — can a Git-mode deployment
point its production environment at a branch other than `main` — only matters if
Git mode is on the table. It is not, for the reason above and for the
deploy-on-push reason before it.

Either answer gives the same outcome: CLI by preference, or CLI by default.
**The check is a note for the record, not a blocker.** Do it when convenient.

### One repo rule needs scoping, not breaking

[`src/cube/CLAUDE.md`](../../../src/cube/CLAUDE.md) says "No manual deploy
command. Production redeploys are triggered by merges to `main` in Cube Cloud;
do not propose a deploy step." That rule is about the production deployment.

Scope it to production explicitly rather than leaving the sandbox quietly
contradicting it. A rule with a silent exception stops being followed.

### Cadence: the review is scheduled, the bump is not

Part 7 hands one question here: does drift distance ever compel a bump?

**No.** A threshold that forces a bump is tracking `main` with extra steps, and
it reopens the exact failure this design rejected — MasterBorn's in-flight build
moving under them without anyone deciding. It also turns Part 7's soft signal
into a gate, which is what Part 7 declined to make it.

So split the two:

- **Scheduled: read the drift report.** Monthly is enough. It says what a bump
  would ship.
- **Deliberate: bump.** Triggered by MasterBorn asking, or by KTAF having a
  reason — the kit needs a member that does not exist yet, or the pin has gone
  far enough that someone judges the repoint is getting worse.

Analytics engineering owns the bump. The drift report informs that conversation;
it never starts it on its own.

### Each bump

1. Move the single pin — model, snapshot and catalog together, per
   [Part 7](#why-pinning-closes-the-data-side-hole).
2. Regenerate the catalog and commit it, so the move is a reviewable diff.
3. Tag the commit `sandbox-YYYY.MM.DD`.
4. Take the member-level diff of additions, removals and retypes as the release
   note. Part 4 makes this a by-product rather than a written document.
5. Send that note to MasterBorn **before** deploying, not after.
6. Deploy that checkout to the sandbox deployment.
7. Re-run the coverage, canary and divergence suites against the new state.

Step 5 moved ahead of the deploy. A release note that arrives after the surface
changed is a changelog, not a warning, and the entire reason for not tracking
`main` was to give warning.

### Nothing here is open

<!-- CB: comments on Part 8 go here, or inline above. -->

Evidence: [A7](#a7--the-specs-second-reason-for-cli-mode-is-wrong).

## Part 9 — Sign-offs

Both items here exist for one property: **anyone looking at a row can tell it is
fabricated.** The spec calls it proof by glance. It matters because fabricated
rows and real rows will be looked at by the same people, and because a synthetic
persona that reads as real is how a test address ends up receiving mail.

### The domain is decided for us, and it is the weaker option

The spec proposes `ktaf-sandbox.invalid`. That is a good choice on its merits:
`.invalid` is reserved by the IETF and can never resolve, so the address cannot
collide with a real account and mail to it cannot be delivered. The guarantee is
structural.

It does not survive contact with the canary runner.
[Part 6](#the-personas-must-live-on-appsteamschoolsorg) establishes that the
runner goes through the SQL API, so persona switching passes `canSwitchSqlUser`,
which accepts only `@apps.teamschools.org`. A `.invalid` address cannot be
switched to, so every canary using one fails for the wrong reason.

So personas use `@apps.teamschools.org` with a reserved prefix. Say plainly what
that costs: the addresses now live on a **real, routable domain**, and the
guarantee drops from structural to procedural.

### Proof by glance now rests on two conventions

| Convention            | Covers                 | Non-collision               |
| --------------------- | ---------------------- | --------------------------- |
| The `sandbox-` prefix | Email addresses        | A promise                   |
| Coined surnames       | Name fields on any row | Inherent, by being invented |

Both are needed. The prefix covers addresses; the surnames cover `dim_students`
and `dim_staff` name columns, where no address appears.

They are not equally strong, and the difference is worth keeping. Nobody is
named Quillamber, so a coined surname cannot collide with a real person no
matter what anyone does later. A `sandbox-` address on a routable domain only
stays non-colliding while KTAF keeps a promise.

The prefix is free today: **0 of 1573** addresses in `dim_staff_cube_access`
start with `sandbox`, measured 2026-09-24. Note that 4 real addresses already
use a hyphenated prefix, so the shape is not distinctive — the word is. Two
commitments follow, and they are commitments rather than mechanisms:

- KTAF never provisions a real account beginning `sandbox-`.
- The generator asserts, before it writes, that no fabricated address collides
  with a real one.

### #5517 is the lever that makes this structural again

[#5517](https://github.com/TEAMSchools/teamster/issues/5517) replaces
`canSwitchSqlUser`'s single `endsWith` with an allowlist of accepted domains, so
Miami staff can be emulated.

**Make that allowlist per-deployment.** Production's list then holds the real
network domains, and the sandbox deployment's list holds one synthetic domain
that resolves nowhere. Personas go back to `ktaf-sandbox.invalid`, proof by
glance returns to structural, and the routable-domain risk above disappears.

This is a follow-on, not a prerequisite. The design works with the prefix; it is
simply better with the domain.

### What `reserved_names.yml` is, since it is on no branch

It was written, then deleted. Commit `aaa57b7222`, "reserve a synthetic-person
namespace, add the starter set", added `src/cube/sandbox/reserved_names.yml`
with 40 coined surnames and 31 given names. The revert that made this branch
specs-only removed it with everything else built before the plan. It is
recoverable from git history and is not on `main`.

What it holds, and why each half is shaped the way it is:

- **Coined surnames** — Fennworth, Quillamber, Bramblehyde. Every fabricated
  person takes a surname from the list, and nothing else uses those words. The
  file's own argument is the right one: a closed list of _plausible_ names would
  prove only provenance, since a real student could be called Jayden Rodriguez
  too. An invented surname makes the **appearance** of the name the proof.
- **Realistic given names**, each tagged with the character class it exercises —
  accents, apostrophes, and the rest of what breaks layout and sorting. The
  tagging lets the coverage script assert every class is present rather than
  hoping a random sample caught the hard ones.

So it is a list KTAF already made and will restore from the plan, not one still
to be invented. Writing names is not the work left.

### The decision: restore it, agree it once, publish it

Coinage makes a surname unique; it does not make anyone recognise it. The second
half is what is missing, and it is the only part that needs a decision.

1. **Restore the file from `aaa57b7222`.** The names are fine and the work is
   done. Re-inventing 40 surnames would produce a different list with no more
   authority than the one already written.
2. **Review the set once and agree it.** This is the sign-off, and it belongs to
   the data team rather than to whoever restores the file. A set inherited with
   its "starter set for review" label intact stays a draft forever.
3. **Publish it** in `docs/reference/` and in the partner handoff, and replace
   the file's header: it stops being a proposal and becomes the reservation,
   pointing at where it is published.

**The contract goes in the spec, not only in the file.** Why the surnames are
coined and why each given name carries a character class currently exists only
as comments inside `reserved_names.yml` — a file that has already been deleted
once, taking the reasoning with it. The spec carries the rule; the file carries
the list.

### Nothing here is open

<!-- CB: comments on Part 9 go here, or inline above. -->

## Part 10 — Out of scope, kit enforcement

### Why it leaves this build

The spec files "should the kit be the only sanctioned path to Cube for internal
apps?" as needing a decision before Pieces 3 to 5. It does not.

It changes the `cube-sandbox` token-exchange service, which is Deliverable 1 of
the parent spec. The generator, the coverage contract, the canaries, the drift
checks and the deploy mechanism are all indifferent to the answer. Nothing in
Parts 3 through 9 would be written differently either way.

It is also a policy question rather than an engineering one, and holding an
engineering build behind a policy decision is how the build stalls.

### What the issue says

Enough that it can be opened without re-deriving the argument:

- **The problem.** The kit is a third access-control surface. Every internal app
  inherits its defaults for token lifetime, result caching and the audit
  `surface` value.
- **Why a contract does not reach it.** The parent spec's 3 partner obligations
  are contract terms because MasterBorn sits outside KTAF. In a kit world those
  obligations move inside KTAF and multiply by the number of internal apps,
  where no contract term applies.
- **The alternative.** Make the kit the enforcement point: the exchange service
  refuses any client that does not present a kit-issued app identity. That
  scales with app count rather than degrading with it.
- **What it would change.** Deliverable 1 only.

### One thing this build must not foreclose

Enforcement stays available only if the exchange service can tell a kit-issued
client from any other. Do not build it accepting any caller that holds a valid
credential, because retrofitting an identity requirement onto clients already in
production is a migration rather than a change.

No decision now. An exchange service that records which client called it costs
almost nothing and keeps both answers open.

### A second issue, not a section of the first

MasterBorn queries the sandbox with its API secret and SQL password directly
([Part 2](#decision-masterborn-gets-no-cube-cloud-account-and-no-web-ui-access)).
KTAF internal apps in production reach Cube through the token-exchange service.
**So the kit's production authentication path is never exercised in the
sandbox.**

That touches the same seam as enforcement, which makes it tempting to file
together. Do not. Enforcement is a policy decision; this is a testing hole.
Bundling them makes the testing hole wait on the policy call — the same failure
this part just avoided for the build, one level down.

Both are Deliverable 1's, not this build's. Two issues, cross-referenced.

### Nothing here is open

<!-- CB: comments on Part 10 go here, or inline above. -->

Evidence: [A8](#a8--kit-enforcement-does-not-gate-the-build).

## When all 10 parts are approved

1. Rewrite `2026-09-11-cube-sandbox-build-design.md` to match every decision
   here, including the stale model facts in
   [A9](#a9--the-specs-cube-model-facts-checked-against-main).
2. Delete this file. It is repair scaffolding, and two documents holding the
   same fact is how the spec drifted in the first place.
3. Run `superpowers:writing-plans` to produce the implementation plan under
   `docs/superpowers/plans/`.
4. Rewrite the PR body on
   [#5267](https://github.com/TEAMSchools/teamster/pull/5267), which still
   describes the removed files and says Piece 2 is built.
5. Open the two issues described in
   [Part 10](#part-10--out-of-scope-kit-enforcement): kit enforcement, and the
   untested production authentication path.

## Appendix — evidence

Filed under the part it belongs to. Each entry is here so a proposal can be
checked, not because it needs reading now.

### A1 — Cube Cloud account isolation is unaddressed

Belongs to Part 2, and **closed by the decision there on 2026-09-23**: no
MasterBorn account, so there is no seat to scope. Kept as the record of what the
review found, since the review called it the largest gap in the design.

GCP isolation does nothing about two deployments sharing one Cube Cloud account.
If MasterBorn gets web UI seats for the sandbox, their reach into the production
deployment depends on their Cube Cloud role, and deployment-scoped roles are
custom roles, which are Enterprise-only.

Three options, per the review: API access only (the sandbox's own API secret and
SQL password, no seats), deployment-scoped custom roles, or a separate Cube
Cloud account. This is partly a procurement question.

### A2 — The backstop is an IAM deny policy

Belongs to Part 3.

Piece 1 prefers a structural refusal over a role assignment but records that an
Organization Policy constraint may be unavailable, because `teamster-332318`
shows no organization. The review supplies a mechanism that works either way: an
IAM deny policy attaches to a project, targets every service account in another
project through a `principalSet` identifier, covers the BigQuery read and
job-creation permissions, and overrides any allow. A later well-meaning grant
cannot reopen the read.

So the resource-hierarchy question stops gating Piece 1.

**Implemented 2026-09-23** as `deny-sandbox-bigquery` on `teamster-332318`, by
the engineer who created the sandbox project. That answers the one item this
entry left unchecked: the role needed to create a deny policy is one he holds
and the analytics side does not — see Part 3 on what that means for the
scheduled check.

### A3 — The sandbox GCP project does not exist yet

**Closed 2026-09-23: the project now exists and Cristina holds credentials.**
Kept because the sequencing conclusion below still shapes the plan.

The original blocker: Cristina lacked `roles/resourcemanager.projectCreator`, so
the project was with an engineer. That gated the load step and the deployment,
but not the generator or the coverage contract, both of which run on local files
and read-only introspection.

The plan should still separate "builds and verifies with no cloud resources"
from "needs the sandbox project" — not to work around a wait that is now over,
but because the first group stays runnable in CI and on any laptop without
handing out sandbox credentials.

### A4 — The coverage manifest's null rule cannot work as written

Belongs to Part 4.

The rule requires at least one null per column unless the column is declared
not-nullable. Every one of the 230 columns reports `NULLABLE` in BigQuery, so
the exemption never fires and the rule forces nulls into join keys and RLS
columns — which would break the very personas the sandbox exists to exercise.

Two candidate fixes: exempt keys and policy-referenced columns, or require a
null only where production actually has one. Part 4 picks.

### A5 — `staff_benefits_scope` is answerable from evidence

Belongs to Part 5. The spec calls this a decision the generator must invent. It
is not.

[`access.js:109-111`](../../../src/cube/access.js) branches on `!== "none"`,
never on a value list:

<!-- markdownlint-disable MD040 -->

    for (const { scope, group } of STAFF_SENSITIVE_TIERS) {
      if (row[scope] && row[scope] !== "none") groups.push(group);
    }

<!-- markdownlint-enable MD040 -->

So any non-`none` string emits `staff-benefits`. Re-checked on 2026-09-23: the
loop is at `access.js:109-110`, still branches on `!== "none"`, and
`staff_benefits_scope` is one of three `STAFF_SENSITIVE_TIERS` alongside
`staff_compensation_scope` and `staff_observations_scope`. Those siblings settle
the vocabulary, but Part 5 should read their live value set rather than carry it
from the spec — two other scope columns were removed since it was written, per
[A9](#a9--the-specs-cube-model-facts-checked-against-main).

Proposed for Part 5: the generator emits **two** distinct non-`none` values plus
`none`. Two rather than one on purpose — a single non-`none` value lets a kit
author write `scope === 'all_in_scope'` and pass every test, freezing an
equality check where the code does a non-`none` check. Two values make that
mistake fail in the sandbox, which is the entire point of Piece 3.

### A6 — The Piece 4 cut, and how big the addition is

Belongs to Part 7. This is the one blocker, and it has been asked twice without
an answer, so here is the material rather than the question.

**What the review cuts.** Have the generator read production's
`INFORMATION_SCHEMA` for the Cube-referenced columns and `CREATE OR REPLACE` the
sandbox tables every run. A sandbox rebuilt each time cannot drift, so the
schema fingerprint, the blocking asset check, and the `ADD COLUMN` repair
patches all have nothing to do. Keep the `/meta`-versus-committed-catalog check.
The review separately cuts the GCS run manifest, because "a seeded generator
plus its commit SHA already makes every run reproducible."

**What the cut changes.** It does not remove the failure, it moves who notices.
Before: production changes, the sandbox stays put, the gate goes red, KTAF sees
it. After: production changes, the sandbox follows silently.

**Verified 2026-09-23.** Cube's `/meta` is generated by
`CubeToMetaTransformer.compile()` in `packages/cubejs-schema-compiler` — it
serializes the compiled data model and makes no warehouse round-trip. So a
dropped or retyped production column stays in `/meta` and surfaces to MasterBorn
at query time rather than to KTAF as a red check. The kept `/meta` leg does not
cover this.

**Not verified.** The sandbox runs its own refresh worker and builds the
`student_assessment_scores` pre-aggregation, and a pre-aggregation build runs
real SQL against the warehouse. A drop inside that pre-aggregation's column
subset would likely fail the refresh worker. That is partial coverage at best —
wrong subset, and it surfaces as a Cube Cloud refresh error, not a KTAF check.
Inferred from how pre-aggregation builds work, not tested.

**Why the addition is smaller than it first looks.** To scope its read to the
Cube-referenced columns, the generator must already hold both the list of
columns Cube references and what production actually returned. "Every
Cube-referenced column still exists" is a set difference on two values already
in memory — the generator not discarding a short read, rather than a new check
bolted on afterward. Roughly 5 lines.

**One item the review could not have seen.** Cutting the GCS manifest was
justified by seed-plus-SHA reproducibility. Under the same review's cut, live
production schema becomes a generator input, so seed plus SHA no longer
determines the output. Logging the schema fingerprint each run reads restores
the claim. Roughly 2 lines, and independent of the item above.

**Superseded in part on 2026-09-23 by Part 3.** The isolation boundary means no
identity can read production and write the sandbox in one run, so the generator
reads a committed schema snapshot rather than live `INFORMATION_SCHEMA`. That
changes both items above:

- The short-read assert moves to the snapshot **refresh** step, which is the
  only step that talks to production. Same check, earlier, and a person reviews
  its diff before it reaches the sandbox.
- Fingerprint logging is no longer needed to restore reproducibility. A
  committed snapshot plus seed plus commit SHA determines the run outright,
  which is what the review assumed all along.

So the review's cut stands and needs no addition. Part 7's remaining question is
narrower: what the `/meta`-versus-committed-catalog check does when the snapshot
refresh has landed a change the sandbox has not been rebuilt for yet.

Proposed for Part 7 before this: take the cut plus both additions, at about 7
lines. Kept for the record; the snapshot decision is the better answer.

### A7 — The spec's second reason for CLI mode is wrong

Belongs to Part 8.

The spec says connecting a GitHub repository auto-syncs non-production branches
into staging environments regardless of deploy mode, meaning a staging
environment per repo branch on the sandbox deployment. Checked against the
vendor documentation on 2026-09-23:

> Staging environments are activated automatically for specific source code
> branches **when a branch is switched to in the Cube Cloud UI**.

The trigger is a person switching branches in that deployment's web UI. Not a
push, and not the act of connecting the repository. There is a toggle, but it
governs availability rather than creation.

This confirms the repo's own note, which has said the same thing since
2026-05-07 and was never checked against the claim:

> **Branch schema validation is manual.** Cube Cloud Staging Environments don't
> auto-create from pushes.
> ([`.claude/rules/cube-authoring.md`](../../../.claude/rules/cube-authoring.md))

The concern fails twice over. Activation is not automatic, and the action that
does trigger it — opening Dev Mode on the sandbox deployment — is one nobody has
a reason to take there. Model development happens against production.

Proposed for Part 8: delete the paragraph and keep CLI mode on its first reason
alone, which is that nothing deploys until someone runs the command. Say plainly
that the margin over Git mode is one reason rather than two.

Also for Part 8: three web UI checks collapse to one, and the survivor decides
whether Git mode is even available. **Can a Git-mode deployment point its
production environment at a branch other than `main`?** The documentation
describes the production environment as running "the data model from the main
branch". The Git-mode alternative depends on pointing the sandbox at a
deliberately fast-forwarded release branch. If Cube Cloud hardcodes `main`, Git
mode is not an option and CLI wins by default rather than on preference.

### A8 — Kit enforcement does not gate the build

Belongs to Part 10.

"Should the kit be the only sanctioned path to Cube for internal apps?" is filed
as needing a decision before Pieces 3 to 5. It changes the `cube-sandbox`
token-exchange Cloud Run service, which is Deliverable 1 of the parent spec. The
generator, the drift gate, and the deploy mechanism are all indifferent to it.

Proposed for Part 10: it moves to its own issue.

### A9 — The spec's Cube model facts, checked against `main`

Belongs to Parts 4 to 6. Checked on 2026-09-23 against the working tree, which
is level with `origin/main`, after last week's query-rewrite and attendance
changes. Column counts re-measured against production `INFORMATION_SCHEMA`.

| Spec claim                                            | Reality on `main`                       |
| ----------------------------------------------------- | --------------------------------------- |
| 4 snapshot anchors                                    | **Gone.** No `is_*_record` in the model |
| 7 `*_scope` columns                                   | **5**                                   |
| 230 columns across 20 tables                          | **243 across 21**                       |
| Table-set union has 20 members                        | **21**                                  |
| `sql_table:` yields 19 tables                         | **20 distinct, 21 declarations**        |
| 129 YAML files under `src/cube/model/`                | **30** (24 cubes, 6 views)              |
| 6 views                                               | 6, but 2 attendance view names are new  |
| Every column `NULLABLE`, none nested                  | Confirmed: 0 not-nullable, 0 nested     |
| `dim_staff_reporting_chain` invisible to `sql_table:` | Confirmed, `cube.js:145`                |
| `cube.js` refs at :51, :59, :137, :145, :221          | All five exact                          |
| `access.js:109-111` branches on `!== "none"`          | Correct, now at 109-110                 |
| `hasRemit` / `hasChain` in `buildGroups`              | Both present                            |
| `student_assessment_scores` pre-aggregation           | Present                                 |
| `scripts/cube_rls_matrix.py` on `main`                | Present                                 |

Two changes carry design weight rather than just a number:

- **The anchors are gone.** Piece 2 required a true/false mix on
  `is_latest_record`, `is_month_end_record`, `is_week_end_record` and
  `is_current_record`, to stop a uniformly-true flag making anchored measures
  look additive to the kit. That hazard was real; whether the query-rewrite
  change removed it or moved it is the open question in Part 4.
- **`staff_location_scope` and `staff_department_scope` no longer exist.** The
  remaining five are `student_location_scope`, `staff_pii_scope`,
  `staff_compensation_scope`, `staff_observations_scope` and
  `staff_benefits_scope`. Piece 2's persona coverage is specified against the
  old seven, so those cells need regenerating rather than editing.

Separately, **`docs/reference/cube-catalog-meta.json` does not exist on `main`,
and the copies that do exist are stale.** It lives on the unmerged branch
`cristinabaldor/feat/claude-cube-api-key-access`, with a copy in
`.claude/scratch/masterborn-handoff/`. That copy, checked 2026-09-23:

| Marker                                       | Occurrences |
| -------------------------------------------- | ----------- |
| `is_latest_record`                           | 11          |
| `is_month_end_record`                        | 6           |
| `staff_department_scope`                     | 2           |
| `student_attendance_enrollment_periods_view` | 0           |
| `fct_student_attendance_enrollment_periods`  | 0           |

The first three were removed from the model; the last two were added. The
catalog describes a model that no longer exists, so it must be regenerated
rather than carried forward from a branch or from scratch. Part 4 covers what
follows from that.
