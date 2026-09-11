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
| **Pin the sandbox model to a git tag, not `main`**           | **Changed from the parent spec**    |
| Local Cube Core container as the daily surface               | Considered and declined, 2026-09-11 |

### The one change: pin a tag, do not track `main`

The parent spec says the sandbox deployment tracks `main`, reasoning that a
tracking sandbox matches production's catalog by construction. That is the wrong
default for a consumer outside KTAF. Matching production _instantly_ means a
model change merged on a Tuesday afternoon breaks MasterBorn's in-flight build
with no warning and no changelog.

Deploy the sandbox from a tag named `sandbox-YYYY.MM.DD` instead. Bumping it is
a deliberate act by the analytics-engineering team, and each bump ships a diff
report of added, removed, and retyped members as a release note. The sandbox
still matches a known production state exactly — just a state both sides agreed
to move to.

The drift gate in Piece 4 is what makes this safe rather than stale: it measures
the distance between the pinned tag and current production, so a pin that has
drifted too far is visible rather than silent.

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

Prefer a **GCP Organization Policy constraint** denying cross-project IAM
bindings over a bare absence of role grants. An absence is undone by one
well-meaning IAM edit six months from now; a constraint refuses the edit. The
design's strength is that it does not depend on the policies being correct, and
a structural refusal keeps that property true over time.

Acceptance: a test confirms the sandbox service account cannot read
`teamster-332318.kipptaf_marts` at all.

## Piece 2 — declare the coverage contract before generating data

Write the manifest generator first. Not the data generator — the thing that says
what the data must contain.

`scripts/sandbox_coverage_manifest.py` reads `INFORMATION_SCHEMA.COLUMNS` for
the 20 `kipptaf_marts` tables, parses the 6 views' `access_policy` blocks, reads
`SENSITIVE_TIERS` in [`access.js`](../../../src/cube/access.js), and emits
`src/cube/sandbox/coverage_manifest.yml` with every required cell listed and
marked `uncovered`.

### Required cells

- **Every column**: at least 1 null row and 1 non-null row, unless the column is
  declared not-nullable. 229 columns, so this is the bulk of the manifest.
- **Every view crossed with every `*_scope` enum value**: at least 1 fabricated
  `dim_staff_cube_access` row. 6 views against the six scope enums.
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

## Piece 3 — generate the data, and make it adversarial

Seeded RNG, parameterized, production scale, per the parent spec. Commit the
persona fixtures: they are fabricated, so they are not PII.

Two mechanisms make the data an instrument rather than a stand-in.

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

## Piece 5 — pin the model version

Deploy the sandbox from a tag named `sandbox-YYYY.MM.DD`. The rationale is in
[The one change](#the-one-change-pin-a-tag-do-not-track-main) above.

Each bump:

1. Regenerate the catalog and commit it, so the move is a reviewable diff.
1. Generate a member-level diff report of additions, removals, and retypes.
1. Send that report to MasterBorn as a release note.
1. Bump the tag on the sandbox deployment.
1. Re-run the coverage and canary suites against the new pin.

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

Inherited from the parent spec and still open: which features query when the
user is absent, whether MasterBorn will commit in writing that results are never
cached across users, how external users are provisioned in the Cube Cloud SAML
tenant, and whether the product wants REST or MCP.

## Testing strategy

- **Isolation proof**: the sandbox service account cannot read
  `teamster-332318.kipptaf_marts`. Runs before any data exists.
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
