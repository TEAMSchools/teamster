# Cube sandbox — requirements pass

Working document for the design pass that
[2026-09-11-cube-sandbox-build-design.md](2026-09-11-cube-sandbox-build-design.md)
never had. The spec was amended in conversation as gaps surfaced during
implementation, so requirements arrived during the build instead of before it.
This document walks the spec part by part, folds in
[cbini's review](https://github.com/TEAMSchools/teamster/issues/5266#issuecomment-5801479218),
and settles each part before the next is drafted.

Once every part is approved, the design spec is rewritten to match and
`superpowers:writing-plans` produces the implementation plan.

**The branch is specs only.** Everything built before this pass was removed in
`revert(cube): drop everything built before the plan`. Nothing here has to
preserve a prior implementation, and nothing here is constrained by one.

Tracked in [#5266](https://github.com/TEAMSchools/teamster/issues/5266), on
[#5267](https://github.com/TEAMSchools/teamster/pull/5267).

## How to comment

Write `CB:` anywhere in this file — inline, on its own line, or inside an HTML
comment. Everything marked that way gets picked up and answered before the part
is redrafted. Questions are as welcome as corrections; a part is not approved
until it reads right to you.

## Running order

Each part states what the spec says today, what the review changes, and what is
proposed. Parts are drafted one at a time so a correction early does not have to
be chased through everything downstream.

| #   | Part                                              | Review items folded in            | Status                   |
| --- | ------------------------------------------------- | --------------------------------- | ------------------------ |
| 1   | Why a sandbox at all — stakeholder background     | —                                 | Drafted, awaiting review |
| 2   | Deployment shape and Cube Cloud account isolation | Cube Cloud gap 1                  | Not drafted              |
| 3   | Piece 1 — isolation proof                         | IAM deny policy                   | Not drafted              |
| 4   | Piece 2 — coverage contract                       | Null rule                         | Not drafted              |
| 5   | Piece 3 — generator scope, order, fabrication     | Poison-pill ranges                | Not drafted              |
| 6   | Piece 3 — adversarial mechanisms and canaries     | Canaries kept as-is               | Not drafted              |
| 7   | Piece 4 — drift gate                              | Most of Piece 4 cut; manifest cut | Not drafted              |
| 8   | Piece 5 — deploy mode, cadence, ownership         | CLI second reason wrong           | Not drafted              |
| 9   | Sign-offs — reserved surnames, synthetic domain   | —                                 | Not drafted              |
| 10  | Out of scope — kit enforcement                    | Move to its own issue             | Not drafted              |

## Findings that change the Open questions list

These remove questions rather than answering them, so each needs agreement.

### Staging environments do not auto-create, and the spec's reason for CLI mode is wrong

Piece 5 gives two reasons to prefer Deploy with CLI. The second one is false.

The spec says connecting a GitHub repository auto-syncs non-production branches
into staging environments regardless of deploy mode, and that this would mean a
staging environment per repo branch on the sandbox deployment. Checked against
the vendor documentation on 2026-09-23:

> Staging environments are activated automatically for specific source code
> branches **when a branch is switched to in the Cube Cloud UI**.

The trigger is a person switching branches in that deployment's console. Not a
push, and not the act of connecting the repository. There is a toggle, but it
governs availability rather than creation — off, the default, means the
environment is live only while someone is viewing it; on means it stays warm.

This also confirms the repo's own note, which has said the same thing since
2026-05-07 and was never checked against the claim:

> **Branch schema validation is manual.** Cube Cloud Staging Environments don't
> auto-create from pushes.
> ([`.claude/rules/cube-authoring.md`](../../../.claude/rules/cube-authoring.md))

The concern fails twice over. Activation is not automatic, and the action that
does trigger it — opening Dev Mode on the sandbox deployment — is one nobody has
a reason to take there. Model development happens against production.

Proposal: delete the paragraph, and keep CLI mode on its first reason alone,
which is that nothing deploys until someone runs the command. State plainly that
the margin over Git mode is now one reason rather than two.

### One console check replaces three

Piece 5 currently flags the whole deploy mechanism for console confirmation. Two
of the three items are now settled from documentation. What remains is narrower
and it is the item that decides whether Git mode is even available:

**Can a Git-mode deployment point its production environment at a branch other
than `main`?** The documentation describes the production environment as running
"the data model from the main branch". The Git-mode alternative depends on
pointing the sandbox at a deliberately fast-forwarded release branch. If Cube
Cloud hardcodes `main`, Git mode is not an option for the sandbox and CLI wins
by default rather than on preference.

### The isolation backstop is an IAM deny policy, not an Organization Policy constraint

Piece 1 prefers a structural refusal over a role assignment but records that an
Organization Policy constraint may be unavailable, because `teamster-332318`
shows no organization. The review supplies the mechanism that works either way:
an IAM deny policy attaches to a project, targets every service account in
another project through a `principalSet` identifier, covers the BigQuery read
and job-creation permissions, and overrides any allow. So a later well-meaning
grant cannot reopen the read.

Proposal: the resource-hierarchy question stops gating Piece 1. The deny policy
is the backstop, attached to `teamster-332318`, and the isolation test asserts
both the denial and the policy's existence. Still unchecked, and now the only
open item here: which role is needed to create one.

### The coverage manifest's null rule cannot work as written

The rule requires at least one null per column unless the column is declared
not-nullable. Every one of the 230 columns reports `NULLABLE` in BigQuery, so
the exemption never fires and the rule forces nulls into join keys and RLS
columns — which would break the very personas the sandbox exists to exercise.

Proposal: exempt keys and policy-referenced columns, or require a null only
where production actually has one. Part 4 settles which.

### `staff_benefits_scope` is answerable from evidence, not open

The spec calls this a decision the generator must invent. It is not.
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

Proposal: the generator emits **two** distinct non-`none` values —
`all_in_scope` and `reporting_chain` — plus `none`. Two rather than one on
purpose: a single non-`none` value lets a kit author write
`scope === 'all_in_scope'` and pass every test, freezing an equality check where
the code does a non-`none` check. Two values make that mistake fail in the
sandbox, which is the entire point of Piece 3. The handoff states that no
production row carries either value today.

### The kit-enforcement question does not gate the build

"Should the kit be the only sanctioned path to Cube for internal apps?" is filed
as needing a decision before Pieces 3 to 5. It changes the `cube-sandbox`
token-exchange Cloud Run service, which is Deliverable 1 of the parent spec. The
generator, the drift gate, and the deploy mechanism are all indifferent to it.

Proposal: it moves to its own issue. Part 10 covers what that issue says.

### One item is still blocked on a fact, and it blocks less than it looks

**Where the sandbox project lands in the resource hierarchy.** Needs someone
with `roles/resourcemanager.projectCreator` to create it. With the deny policy
replacing the Organization Policy constraint, this no longer decides the
isolation design — it only decides where the project sits.

Nothing blocks the generator or the coverage contract: both run on local files
and read-only production introspection. The project gates the load step and the
deployment.

Proposal: the plan separates "builds and verifies with no cloud resources" from
"needs the sandbox project to exist", so work can start without waiting.

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

"The sandbox" is not Cube's **Playground**. Playground is a console feature in
the existing production deployment, and
[`src/cube/CLAUDE.md`](../../../src/cube/CLAUDE.md) forbids its Models tab
because it overwrites hand-authored YAML. The sandbox is a separate Cube Cloud
deployment pointed at a separate BigQuery project. If a stakeholder says
"playground", that is the thing to correct.

## Parts 2 to 10

Not drafted. Each is written after the previous one is approved.
