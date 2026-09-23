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
| 4   | Piece 2 — coverage contract               | **Drafted — needs you** |
| 5   | Piece 3 — generator scope and fabrication | Not drafted             |
| 6   | Piece 3 — adversarial canaries            | Not drafted             |
| 7   | Piece 4 — drift gate                      | Not drafted, unblocked  |
| 8   | Piece 5 — deploy mode and cadence         | Not drafted             |
| 9   | Sign-offs — reserved names, domain        | Not drafted             |
| 10  | Out of scope — kit enforcement            | Not drafted             |

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

Only two things are read from production: **schema and codesets** — column
names, types, nullability, and the distinct values of categorical fields such as
`race` and `enrollment_status`. No rows, ever. The privacy argument is one
sentence long, and it is structural rather than statistical.

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

### One hard rule on the snapshot, because it goes into git

The snapshot carries schema **and codesets** — the distinct values of
categorical fields, per Part 1. Git history is permanent, so the codeset half
needs a rule rather than a judgment call each time:

- Codesets are pulled only for columns on an explicit allowlist, each a genuine
  low-cardinality enumeration such as `race` or `enrollment_status`.
- A cardinality ceiling, so a column that is not really an enumeration fails the
  pull instead of dumping its values.
- Never from free-text columns or anything naming a person. A distinct-values
  pull on the wrong column writes student data to git permanently.

Part 5 settles the allowlist and the ceiling. The rule itself is not Part 5's to
reopen.

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

Not drafted. Decides what the generator reads, what it invents, and in what
order. See [A5](#a5--staff_benefits_scope-is-answerable-from-evidence).

Carried here from Part 3, which raised them but does not settle them:

- **Where the schema snapshot lives and what shape it takes**, alongside the
  codeset allowlist and cardinality ceiling that Part 3 made a hard rule.
- **What runs the refresh step.** A Dagster asset in `teamster-332318` is the
  obvious home, since that is where production credentials already are.

## Part 6 — Piece 3, adversarial canaries

Not drafted. Decides the must-be-empty canaries and how they are verified. The
review keeps these as-is and calls them the most valuable piece.

## Part 7 — Piece 4, drift gate

Not drafted, and **no longer blocked**. The review cuts most of Piece 4, and
Part 3's committed-snapshot decision settles the question of whether that cut
needed an addition: it does not. What remains for this part is narrower — what
the `/meta`-versus-committed-catalog check does between a landed snapshot
refresh and the sandbox rebuild that follows it. See
[A6](#a6--the-piece-4-cut-and-how-big-the-addition-is).

## Part 8 — Piece 5, deploy mode and cadence

Not drafted. Decides CLI versus Git deploy mode and the bump cadence. See
[A7](#a7--the-specs-second-reason-for-cli-mode-is-wrong).

## Part 9 — Sign-offs

Not drafted. Reserved surnames and the synthetic email domain for fabricated
personas.

## Part 10 — Out of scope, kit enforcement

Not drafted. Says what moves to its own issue and what that issue contains. See
[A8](#a8--kit-enforcement-does-not-gate-the-build).

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
