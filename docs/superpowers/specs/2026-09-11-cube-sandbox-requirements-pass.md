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
| 3   | Piece 1 — isolation proof                 | **Drafted — needs you** |
| 4   | Piece 2 — coverage contract               | Not drafted             |
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
[`cube-catalog-meta.json`](../../reference/cube-catalog-meta.json), and the
query APIs. No Cube Cloud web UI, so no Playground and no data model browser.

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
| 2   | A later grant cannot reopen it                                | `deny-sandbox-bigquery`  | Built    |
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

That gap is small but real, and closing it does not need an invasive test.
Assert that `deny-sandbox-bigquery` exists, as a second assertion alongside the
403, which is what the review asked for in
[A2](#a2--the-backstop-is-an-iam-deny-policy). The scheduled form of this check
should carry both.

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

### What the scheduled check must assert

Two assertions, not one. The second is the gap the passing test leaves:

1. The 403 on production, with the sandbox read succeeding in the same run.
2. That `deny-sandbox-bigquery` still exists on `teamster-332318`.

Reading a deny policy needs `iam.googleapis.com/denypolicies.list` on the
production project, which the codespace's own credentials do not hold. So
whatever runs this check needs an identity that does — a constraint on where the
check lives, and one for the plan rather than for this part.

### Nothing here is open

A2's last unchecked item — which role creates an IAM deny policy — is answered
by the policy existing. The snapshot's file location, its shape, and what runs
the refresh step are Part 5's, and are recorded there.

<!-- CB: comments on Part 3 go here, or inline above. -->

Evidence: [A2](#a2--the-backstop-is-an-iam-deny-policy),
[A3](#a3--the-sandbox-gcp-project-does-not-exist-yet).

## Part 4 — Piece 2, coverage contract

Not drafted. Decides what the generated coverage manifest asserts. See
[A4](#a4--the-coverage-manifests-null-rule-cannot-work-as-written).

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

**Implemented 2026-09-23** as `deny-sandbox-bigquery` on `teamster-332318`,
which also answers the one item this entry left unchecked: the role needed to
create a deny policy was one Cristina held.

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

So any non-`none` string emits `staff-benefits`. The vocabulary is settled by
the sibling columns: `staff_compensation_scope` and `staff_observations_scope`
both use `all_in_scope`, `reporting_chain`, and `reporting_chain_or_below_rank`.

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
