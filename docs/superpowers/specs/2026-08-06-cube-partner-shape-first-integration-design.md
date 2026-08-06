# Cube partner integration — build against the shape, then repoint

- **Issue:** [#4455](https://github.com/TEAMSchools/teamster/issues/4455)
- **Status:** Design (brainstorming output; feeds `superpowers:writing-plans`)
- **Date:** 2026-08-06
- **Author:** cristinabaldor (with Claude)
- **Supersedes:** `2026-07-22-cube-external-api-key-access-design.md`, deleted
  in this change

## Summary

A contracted software-development agency is building a product on top of the
Cube semantic layer. **They do not need our data. They need the shape of it.**

So the deliverable is a **catalog their code can consume** plus a **behaviorally
faithful sandbox holding no real records**. They build against the shape; we
repoint at production `kipptaf_marts`; it works.

Zero real-data egress in v1. The production identity model is designed for but
deferred, because it turns on a question only the partner can answer.

The partner is **MasterBorn**, a custom software-development agency.

## The conceit that was wrong

The superseded spec framed this as **external API access**: a hashed-key
registry granting an outside party row-level student records, scoped to schools
named in a data-sharing agreement, gated behind legal sign-off.

That is the right design for a data recipient and the wrong design for a
development agency. It answers "how does an outside party read our warehouse"
when the actual question is "how does a team build software against our semantic
layer."

Three consequences follow from the correction:

- **The primary deliverable is a catalog, not a credential.** What unblocks an
  engineer on day one is knowing what they can ask for and what comes back.
- **Real data is not required, and not wanted.** A credential carrying
  production PII creates an egress problem that the work does not need to have.
- **The migration event is a repoint, not a promotion.** Their integration is
  written once, against a stable contract, and swapped to production data by
  configuration.

## What "the shape" means concretely

Building an integration splits into three kinds of work, and each needs
something different from us. Skipping any one of them just moves the discovery
later.

| Layer          | What it needs                               | Deliverable      |
| -------------- | ------------------------------------------- | ---------------- |
| Write the code | The contract: members, grains, envelopes    | Catalog bundle   |
| Run the code   | Something that responds to every code path  | Sandbox          |
| Trust the code | Real error shapes, denials, anchoring rules | Sandbox fidelity |

A document alone covers the first layer. Their engineers hit the second within
about a day of starting.

## Current architecture (grounded in code)

Authentication and row-level security flow through one identity-agnostic
pipeline. Everything downstream of the resolver reads only the _shape_ of the
security context, never how it was produced — which is exactly why a repoint is
a configuration change rather than a rewrite.

```text
checkAuth       (REST/MCP)    ─┐
checkSqlAuth    (SQL API)     ─┼─→ resolveAccess(email) ─→ buildSecurityContext
contextToGroups (Cube Cloud)  ─┘                                    │
                                                                    ▼
                                              groups + flat scope values
                                                                    │
                                                                    ▼
                                                   per-view access_policy
```

- [`cube.js`](../../../src/cube/cube.js) `checkAuth` receives the raw bearer
  token string, verifies HS256 against `CUBEJS_API_SECRET`, reads the `email`
  claim, and sets `req.securityContext = await resolveAccess(email)`.
- `resolveAccess(email)` reads one row from `dim_staff_cube_access` plus
  reportees from `dim_staff_reporting_chain`, loads the location and department
  universes, and calls `access.buildSecurityContext(...)`. Fail-closed to an
  empty default-deny context on any error. Cached per-email until next midnight
  ET.
- [`access.js`](../../../src/cube/access.js) holds the pure, unit-tested logic.
- Row-level security lives entirely in per-view `access_policy` blocks.
- [`mcp/server.py`](../../../src/cube/mcp/server.py) on Cloud Run verifies a
  WorkOS AuthKit JWT against JWKS (`JWKSTokenVerifier`), extracts the verified
  `email` claim, and mints a 5-minute HS256 Cube token whose entire payload is
  `{email, iat, exp}`.

### The callable-service answer

The partner asked whether the authorization logic is a callable service and what
would need to be passed to enforce the security derivation.

**It is callable and already deployed.** `mcp/server.py` on Cloud Run is a
token-exchange shim: an OIDC identity in, a short-lived Cube token out, with
`CUBEJS_API_SECRET` never leaving KTAF infrastructure.

**What gets passed is an end-user identity assertion** — not a scope, not a
school list, not a key. Why that is the correct boundary:

- Scope derives from HR data per query, so it tracks reassignments, role
  changes, and departures with no action by the partner.
- Nothing for the partner to revoke. Removing the HR row removes the access.
- An identity absent from `dim_staff_cube_access` resolves to the empty
  default-deny context — fail-closed by construction, not by policy.
- Internal staff resolve through the same derivation. One model, not two.

**The limit:** it only covers identities KTAF HR data knows. That limit is the
deferred decision, and it is the one thing that can make the repoint fail.

## Decisions

| Decision                   | Choice                                                             |
| -------------------------- | ------------------------------------------------------------------ |
| Framing                    | Shape-first: catalog and sandbox, then repoint                     |
| Production caller identity | **Not scoped yet** — deferred, designed toward pass-through        |
| Developer data posture     | Synthetic only; no real records leave KTAF in v1                   |
| Sandbox runtime            | Second Cube Cloud deployment (Enterprise: unlimited)               |
| New views and metrics      | Partner requests, KTAF analytics engineers implement               |
| Audit                      | KTAF-owned sink; Cube Cloud's audit log does not cover data access |

## Scope of the implementation plan

**In scope for the plan this spec feeds:** the catalog bundle, the sandbox
deployment and its synthetic dataset, the `cube-sandbox` Cloud Run service and
deployment-scoped console access, the audit emit path with its BigQuery sink,
and the intake issue template.

**Out of scope, each needing its own spec:** the production identity
pass-through (blocked on the partner's answer), the de-identified mirror and its
re-identification-risk threshold, and small-cell suppression
([#4237](https://github.com/TEAMSchools/teamster/issues/4237)).

## Deliverable 1 — the catalog bundle

The thing that gets into their code. Ordered by usefulness to an engineer.

**A committed `/meta` snapshot.** Cube's own metadata payload: every view, its
dimensions and measures, types, grains, and descriptions. Machine-readable, and
already the shape a Cube client consumes. **It contains no data rows.**

**A generated human-readable page** in the `mkdocs.yml` nav, for orientation and
for brainstorming what the product should do.

**Sample `/load` request and response pairs** — five to ten realistic queries
with their responses. This is what lets them stand up a local mock and start
writing parsing code on day one, before the sandbox exists.

**A written gotchas note.** Cheap to produce and it saves days:

- The `Authorization` header takes the **raw token — no `Bearer` prefix**.
- A query requesting one member outside the caller's tier **fails entirely**
  rather than dropping that member
  ([#4268](https://github.com/TEAMSchools/teamster/issues/4268)).
- Snapshot measures reject some measure-and-granularity combinations by design,
  and weekly trends must group by `dates_school_week_start_date` rather than
  Cube's ISO `granularity: "week"`.
- `count_students` on `student_enrollments` anchors to `is_current_record`, so
  it reads 0 outside the school year.

**Optionally, generated TypeScript types** from the snapshot. High leverage for
a typed codebase: view and member names become compile-time checked instead of
string literals discovered at runtime.

### How it is produced

A script (`scripts/cube_catalog_export.py`, run via `uv run`) calls `/meta` with
a data-team token and writes the artifacts. **Commit the output.**

Committing it buys a property worth more than the artifact: a model change shows
up as a reviewable diff, which closes the loop with the intake process below.
The partner sees what changed without being told.

One trap to design around: **`/meta` returns `{"cubes": []}` for a
default-denied identity.** Access policies hide every cube when no group
matches, so an empty catalog is indistinguishable from an unpopulated
deployment. The export must run as a full-scope identity, and the script should
fail loudly on an empty result rather than committing it.

### Scope: give them the whole catalog

Export the **full** model, including views and members the product will not be
granted, and mark those clearly.

The alternative — exporting a pre-scoped catalog — hides the surface and makes
the intake process blind. They cannot file an informed request for something
they cannot see exists. Marking a field as present-but-gated is more useful than
omitting it, and the catalog carries no data either way.

## Deliverable 2 — the sandbox

### Why a separate Cube Cloud deployment, not a branch

**Empirically confirmed in the Cube Cloud console (2026-08-06):**

| Variable                          | Scope                                        | Set by                  |
| --------------------------------- | -------------------------------------------- | ----------------------- |
| `CUBEJS_API_SECRET`               | Deployment-wide, shared by every environment | Cube Cloud generates it |
| `CUBEJS_DB_BQ_*` and other config | Per environment, editable on a branch        | Us                      |

That asymmetry is a trap, and it closes the branch route. A token minted for a
branch staging environment is verified by production's `checkAuth` using the
same secret, so it is **mechanically a production credential** — a holder can
claim any `email` and read all of `kipptaf_marts`. The bypass happens at
signature verification, before `resolveAccess` runs and before any
`access_policy` is consulted, so no view or policy change mitigates it.

The natural inference — "a branch has its own variables, so a branch is an
isolated environment, so it is safe to expose" — is true for the data connection
and false for the credential. Getting it backwards hands out a production key.

Three secondary reasons, all still true:

- Branch staging suspends after 10 minutes idle unless toggled always-active.
- The branch name is embedded in the endpoint path, so renaming or deleting the
  branch breaks the integration.
- A long-lived branch drifts from `main`, and the sandbox's value depends on its
  catalog matching production exactly.

The useful corollary: pointing a branch environment at a sandbox BigQuery
project is a **legitimate internal technique** for testing the model against
synthetic data. It simply cannot carry its own credential, so it stays
internal-only.

### The mechanism, and why it needs no model changes

Every reference in the Cube model is **project-unqualified**
(`sql_table: kipptaf_marts.dim_staff`, never
`teamster-332318.kipptaf_marts.dim_staff`), and the GCP project comes from
exactly one variable — `CUBEJS_DB_BQ_PROJECT_ID` — read by both the BigQuery
driver and `resolveAccess`'s own hand-rolled client.

So the recipe is:

1. Create a sandbox GCP project containing a dataset also named `kipptaf_marts`.
1. Populate it with synthetic tables using identical table and column names.
1. Point the sandbox deployment's `CUBEJS_DB_BQ_PROJECT_ID` at it.

**No changes to any cube YAML, any view, or `cube.js`.** Identity resolution
comes along for free, because `dim_staff_cube_access`, `dim_locations`, and
`dim_staff_reporting_chain` are read the same project-unqualified way.

An earlier draft proposed templatizing `sql_table` with Jinja. That is
unnecessary and should not be built.

### Blast-radius isolation

The sandbox deployment's service account gets **no IAM whatsoever on
`teamster-332318`**. A total compromise of the sandbox then reaches zero real
records.

This is a stronger guarantee than any policy-level control, because it does not
depend on the access policies being correct.

### Cost shape

Cube Cloud Enterprise allows unlimited deployments; billing is Cube Consumption
Units per hour (roughly 1–2 CCU/hour shared, 4–8 dedicated). Provision the
sandbox as a **Development Instance**, which deallocates after inactivity, so
cost tracks the partner's actual working hours. Cold starts are acceptable in a
development sandbox.

### Synthetic data scope

Measured against production `kipptaf_marts`:

- **20 tables**, 229 columns total, **zero nested or repeated columns**. Widest
  is `fct_student_attendance_daily` at 24 columns.
- **6 views** must resolve: `student_attendance_view`,
  `student_enrollments_view`, `student_section_enrollments_view`,
  `student_assessment_scores_view`, `staff_directory`, `staff_pii`.

```text
dim_assessment_administrations   dim_staff_reporting_chain
dim_assessments                  dim_staff_reporting_periods
dim_course_sections              dim_staff_work_history
dim_courses                      dim_student_enrollment_status
dim_dates                        dim_student_enrollments
dim_locations                    dim_student_section_enrollments
dim_regions                      dim_students
dim_school_calendars             dim_terms
dim_staff                        fct_assessment_scores_enrollment_scoped
dim_staff_cube_access            fct_student_attendance_daily
```

A flat, narrow, un-nested schema is why this is days rather than weeks. The hard
parts of a de-identified mirror — FERPA re-identification analysis,
distributional realism, referential fidelity against live marts — are all absent
when the rows are invented.

### The fidelity rule

**Make the sandbox narrower and messier than production. Never wider or
cleaner.**

Every direction of that asymmetry converts a production surprise into a sandbox
bug, which is the entire point of the sandbox existing. Concretely:

- **Referential integrity must hold** across the join graph, or views fail to
  resolve rather than returning wrong numbers.
- **Include deliberate messiness**: nulls in optional columns, a mid-year
  transfer, a student with no term record, a staff member with no reportees.
- **Populate the snapshot anchor dimensions** (`is_latest_record`,
  `is_month_end_record`, `is_week_end_record`, `is_current_record`) so the
  `queryRewrite` guard behaves as it will in production. If these are uniformly
  true, anchored measures silently look additive and the partner never learns
  the rule.
- **Give the partner the narrowest plausible personas**, not permissive ones. A
  permissive persona hides the whole-query denial in #4268, which is the single
  most likely production surprise.

### Personas are data, not configuration

`dim_staff_cube_access` is 15 flat columns — `staff_key`, `google_email`,
`region_key`, `location_abbreviation`, `department_group`, `entity`,
`job_function_code`, `job_function_level`, and the six `*_scope` enums.

**A persona is one row.** Fabricate a row per test identity and that identity's
scope is set, with no special code path and no deploy. Cover at minimum:

- A `network`, a `region`, and a `school` `student_location_scope`.
- `none` on every axis, to exercise clean default-deny.
- One `staff_pii_scope` of each value the policies gate on.
- One deliberately unresolvable identity, with no row at all.

That full matrix is for KTAF's own validation. The personas actually **handed to
the partner** are a narrow subset, per the fidelity rule above.

Because these personas are fabricated, the persona list is **not PII** and may
be committed as a test fixture — unlike the production viewer list, which must
be passed in at runtime.

## The repoint

The migration event, and the **last** step — not the third thing built. It is
gated on the deferred identity question below. Their integration is written once
and swapped to production data by configuration.

### What ports unchanged

- **Query shapes.** Same view and member names, same JSON envelope. The sandbox
  deployment tracks `main`, so the semantic model is identical by construction.
- **Auth integration code.** Same OAuth flow, same raw `Authorization` header,
  same 403 shapes and messages.
- **Query-shape validation.** `queryRewrite`'s snapshot guard rejects invalid
  measure-and-granularity combinations from the query alone, independent of the
  data, so those errors are learned in the sandbox and never resurface.

### What does not port

Five things, ordered by how badly each bites:

**Who can call it.** The partner's engineers are not in the real
`dim_staff_cube_access`, so at repoint they default-deny. The repoint does not
grant _them_ production access — it grants the **product's end users** access.
Two different populations, and the repoint swaps which one is served. Their
engineers keep using the sandbox after cutover.

**Whether there is an identity to resolve at all.** If the product's end users
are students, families, or community members, they have no HR row and no
Workspace account, and the repoint **fails** rather than degrading. This is the
deferred question, and it is a hard dependency, not a refinement.

**Field-level denials.** `access_policy` blocks the whole query rather than
stripping the member. A permissive sandbox persona hides this entirely.
Mitigated by the fidelity rule above, not by anything at repoint time.

**Volume behavior.** Pagination, query timeouts, and pre-aggregation routing are
all invisible at a few hundred synthetic rows and load-bearing at ten thousand
students. Client code that never had to paginate will not start on its own.

**Number plausibility.** Anything tuned by eye against fabricated values gets
retuned against real ones. Scope-bound measures are the sharp edge here:
`avg_scale_score` and `avg_percent_correct` recompute correctly at any grain but
are only _meaningful_ within a comparable assessment scope, and synthetic data
will not reveal a wrong pooling.

### The repoint checklist

1. Confirm the production identity model (the deferred question) is answered and
   built.
1. Confirm the audit sink is live and receiving records.
1. Point the partner's production integration at the production Cloud Run
   exchange service, not the sandbox one.
1. Re-run their integration test suite and expect failures only in the five
   categories above.
1. Load-test at production volume before any end user sees it.

## Access for the partner's engineers

### The Cloud Run token-exchange service

A second Cloud Run service — `cube-sandbox` — built as a copy of
[`deploy-cube-mcp.yaml`](../../../.github/workflows/deploy-cube-mcp.yaml) with
its own variables, pointing at the sandbox deployment's endpoint and secret.

```text
partner app
  → WorkOS AuthKit sign-in (OIDC)
  → cube-sandbox on Cloud Run
      · JWKSTokenVerifier verifies the AuthKit token, extracts verified `email`
      · mints a 5-minute token signed with the SANDBOX deployment's secret
  → sandbox Cube /load
      · checkAuth verifies signature, resolveAccess(email)
      · reads the SANDBOX project's dim_staff_cube_access → synthetic persona
      · per-view access_policy filters synthetic rows
```

What this buys:

- **Their scope is data KTAF controls.** Edit a persona row, change their
  access.
- **Their auth code is the production code**, which is what makes the repoint a
  configuration change.
- **The Cube endpoint is never exposed to them.** Rate limiting, audit, and
  revocation all live in the Cloud Run service.
- **This is the existing pattern.** `cube-mcp` already runs
  `--allow-unauthenticated` with OAuth at the application layer, serving
  external `claude.ai` connectors today.

There is **no standalone IP allowlisting** in Cube Cloud; network-level
restriction requires the Enterprise Dedicated Infrastructure add-on (VPC
peering, PrivateLink, BYOC). Fronting the endpoint with Cloud Run is therefore
the access control, not a convenience.

### Cube Cloud console access, deployment-scoped

Enterprise **custom roles** can scope a console user to specific deployments.
Grant the partner's engineers a custom role scoped to the sandbox deployment
only, with no visibility into production.

This is the best available answer to "help us understand the shape of your
data": they explore real measure and dimension names interactively, and their
console identity resolves through `contextToGroups` against the sandbox
`dim_staff_cube_access`, so the synthetic persona's scope still applies.

Two deliberate choices required:

- The **data model** permission shows them cube YAML including `access_policy`
  blocks. On a sandbox that is arguably useful, but choose it explicitly rather
  than inheriting it.
- **Environment-level RBAC does not exist** — the scoping unit is the
  deployment. An independent reason the sandbox must be its own deployment.

Cube Cloud SSO is Enterprise SAML. Confirm how external users are provisioned in
the KTAF tenant before promising console access.

### Persona switching needs one small change

`_mint_token(email)` in `mcp/server.py` hardcodes its claims to
`{email, iat, exp}`; no code path sets `act_as`. So emulation does not work
through the Cloud Run path today.

Add an **`act_as` passthrough to the `cube-sandbox` service only**. It is safe
there precisely because the data is fabricated, and it lets the partner switch
personas without KTAF becoming the bottleneck on their testing.

Gate it on a configuration flag (for example `CUBE_ALLOW_ACT_AS`, default off)
rather than forking `server.py` — one codebase serves both deployments, and the
production service simply never sets it.

Do **not** add it to the production `cube-mcp` service as part of this work.

### The shortcut to refuse

Because the sandbox holds no real data, KTAF could hand the partner the sandbox
`CUBEJS_API_SECRET` and let them mint their own tokens. The blast radius is
genuinely fabricated rows, so it is not a data risk.

Refuse it anyway. It trains the partner on the exact pattern production forbids,
their auth code is discarded at cutover — destroying the repoint property this
whole design is built around — and it invites a later request to point the same
approach at production.

## Audit

**Cube Cloud's Audit Log does not record data access.** It covers administrative
events: user management, logins, account and deployment configuration changes,
Git branch management, CI/CD actions. Retention is 30 days with a 10,000-event
cap, and export is a control-plane endpoint (`/api/v1/audit-logs/export`) with
no documented sink connectors.

So the data-access trail is KTAF-built work, not a settings toggle:

- Emit one structured line per resolved request — identity, surface, view,
  timestamp. **Never row values.** `logEmulation` in `cube.js` already
  establishes the shape.
- Sink Cloud Logging into BigQuery for retention KTAF owns.

Build the emit side **alongside the sandbox**, not after. Retrofitting an audit
trail onto a live external integration is strictly worse, and the partner
explicitly asked for audit to be accounted for early.

## Intake for new views and metrics

The partner files a structured request; KTAF analytics engineers implement; the
catalog is regenerated and committed, which surfaces the change as a diff.

- Add an issue template under `.github/ISSUE_TEMPLATE/` capturing grain,
  dimensions, measures, filters, and the consuming product surface.
- **No repo access for the partner.** `/src/cube/` and `/src/dbt/` stay
  CODEOWNERS-gated to `@TEAMSchools/analytics-engineers`.
- PII tagging and grain decisions live in the dbt marts, which is why authorship
  stays with KTAF.
- The queue doubles as the written record of what the product needs — the exact
  input the deferred identity decision requires.

## Deferred — production identity pass-through

Gated on the product being scoped. Prove the chain end to end from outside KTAF
infrastructure with a real staff identity.

- Register the partner's application in WorkOS AuthKit. DCR/CIMD is a
  tenant-wide toggle under Connect → Configuration → MCP Auth.
- Add the partner's public URL to MCP resource indicators (RFC 8707) so issued
  tokens bind to that resource.
- Confirm the AuthKit JWT template emits `email` — it omits it by default.
- Decide the query surface: the MCP service as-is, or a thin REST proxy beside
  it performing the same exchange. A product likely wants REST, not MCP tool
  calls.
- **The load-bearing test is the negative one:** a non-staff identity must
  default-deny.

## Deferred — de-identified mirror

A dbt-built `kipptaf_marts_deid` dataset with identical table and column shapes,
on its own deployment, closing the realism gap listed under
[What does not port](#what-does-not-port).

**De-identification requires its own spec.** Direct identifiers are the easy
half. FERPA's "linked or linkable" standard is the hard half: a row carrying
school, grade level, race, and IEP status is re-identifiable in a small school
with no name present. That forces a stated re-identification-risk threshold —
**the same governance decision blocking
[#4237](https://github.com/TEAMSchools/teamster/issues/4237) small-cell
suppression, so settle both together.**

Scope the mirror to the views the product actually uses, from the intake record.
Do not mirror all of `kipptaf_marts` speculatively.

## Constraints this design must respect

**Every field a policy interpolates must be returned by `buildSecurityContext`**
([#4526](https://github.com/TEAMSchools/teamster/issues/4526)).
`contextToGroups` unconditionally overwrites the Cube Cloud security context
with `resolveAccess` output; a field computed anywhere else is not overwritten,
which reopens the pasted-context bypass for that field alone — silently, and
only on that surface. Any new resolver must route through
`buildSecurityContext`.

**`checkAuth` caps token age at 12h derived from `iat`**, independent of the
token's own `exp`, with 30 seconds of clock tolerance. Any external credential
path inherits that ceiling, and a token carrying no `iat` is rejected outright.

**The `Authorization` header takes the raw token — no `Bearer` prefix.**

**`access_policy` blocks rather than strips**
([#4268](https://github.com/TEAMSchools/teamster/issues/4268), open). Named in
the catalog gotchas note because it is the likeliest single thing to cost the
partner's engineers a day.

## Invariants preserved

- Cubes private, views public; fail-closed default-deny throughout.
- No change to internal identity resolution or existing internal view policies.
- Never store raw credentials.
- `canSwitchSqlUser` unchanged.
- A leaked credential's blast radius is limited to its own scope — and in v1
  that scope contains no real records.

## Non-goals

- SQL API access for external clients.
- Real student or staff PII leaving KTAF infrastructure in v1.
- An API-key registry. Identity pass-through replaces it; revisit only if the
  product turns out to require a service identity.
- Aggregate demographic tiers (blocked by #4237).
- Self-serve credential management or a partner portal.
- Per-key rate limiting inside Cube — the Cloud Run service is the right layer.
- Adding `act_as` to the production `cube-mcp` service.

## Testing strategy

- **Isolation proof:** confirm the sandbox service account cannot read
  `teamster-332318.kipptaf_marts` at all. **The single most important test in
  the plan** — every other guarantee is downstream of it.
- **Catalog export guard:** the export script must fail on an empty `cubes`
  array rather than committing a default-denied snapshot.
- **Sandbox RLS matrix:** run `scripts/cube_rls_matrix.py` against the sandbox
  with the committed synthetic persona fixture. This needs the SQL API enabled
  on the sandbox deployment (`CUBEJS_PG_SQL_PORT`) for KTAF's own validation
  only — the partner's access is REST through Cloud Run, and the SQL API is
  never exposed to them (see Non-goals).
- **Denial shape with auth on:** run the sign-off as
  `NODE_ENV=production CUBEJS_DEV_MODE=false`. Dev mode downgrades an
  out-of-tier denial to a quiet zero rows, which makes a matrix run falsely
  benign ([#4605](https://github.com/TEAMSchools/teamster/issues/4605)).
- **Anchor fidelity:** confirm a snapshot measure over a date range returns the
  anchored count on synthetic data, not the additive one.
- **Unit** (`node --test`): any new `access.js` helper; unchanged internal
  behavior.
- **Regression:** internal `student-*`, `staff-directory`, and `staff-pii`
  behavior unchanged on production.

## Open questions

- **Who are the product's end users?** Gates the repoint. The partner's to
  answer, and the one question that can invalidate the design.
- How are external users provisioned in the KTAF Cube Cloud SAML tenant?
- Does the partner's product want REST or MCP as its query surface?
- Synthetic generation approach: hand-authored dbt seeds, or a generator script?
  Seeds are simpler to review; a generator scales to realistic volume later.
- Do they want generated TypeScript types, or is the raw snapshot enough?
- Re-identification-risk threshold for the de-identified mirror, jointly with
  #4237.

## Related

- [#4455](https://github.com/TEAMSchools/teamster/issues/4455) — this work.
- [#4237](https://github.com/TEAMSchools/teamster/issues/4237) — small-cell
  suppression; shares the de-identification threshold decision.
- [#4268](https://github.com/TEAMSchools/teamster/issues/4268) — `queryRewrite`
  member-strip.
- [#4526](https://github.com/TEAMSchools/teamster/issues/4526) — Cube Cloud
  context enrichment and the pasted-context fix.
- [#4614](https://github.com/TEAMSchools/teamster/pull/4614) — internal
  emulation, which shipped the superseded spec's Part 2.

## Appendix — draft response to the partner

Held here so the outbound message is reviewable alongside the design. Send after
review; adjust timeline language to whatever the team commits to.

---

Thanks — these are the right questions, and two of them changed our plan, so
this was useful.

First, a reframe on our side. We had been thinking about this as giving you API
access to our data. That is the wrong shape. What you need in order to build is
**the shape of our data**, not the data itself. So that is what we are going to
give you, and when the product is built we repoint it at production and it
works.

**Is the authorization logic a callable service? What would need to be passed?**

Yes, and it already exists. We run a small token-exchange service that verifies
an OIDC identity token and returns a short-lived token for our semantic layer.
Our signing secret never leaves our infrastructure.

What you would pass is **an end-user identity, not a scope**. We derive
permissions server-side from HR data at query time — which schools or region
someone covers, whether they can see sensitive staff fields, who reports to
them. You never compute or assert permissions, and you never hold a credential
that could broaden them. When someone changes roles or leaves, their access
changes with no deploy and no action on your side.

One constraint worth knowing now: this derivation only covers people our HR data
knows. If your product's end users are staff, it works exactly as described. If
they are students, families, or community members, we need a different
permission model — which is why the question at the bottom of this note matters.

**How do we ensure safe access for developers testing in non-production,
externally?**

We agree with your de-identified default, and for the first phase we are going
further: **no real records at all.**

We will stand up a separate sandbox with the same schema, the same semantic
model, and the same authentication path as production, reading a **synthetic
dataset** — fabricated rows, no student or staff data. Its service account will
have no access whatsoever to our production warehouse, so the isolation does not
depend on our permission rules being correct.

Three things that matter for your engineers:

- **The auth path is identical to production**, so the integration code you
  write against the sandbox is the code that ships. The cutover is a
  configuration change, not a rewrite.
- **We can give you test personas with different permission scopes**, so you can
  see how the product behaves for a school-level user versus a network-level
  one. Those are just rows in the sandbox, so we can add or change them quickly.
- **We will deliberately make the sandbox stricter and messier than production**
  — narrower permissions, nulls, mid-year transfers. Anything that works there
  works on real data. The reverse is not true, which is why we are biasing this
  way.

Later, once we know which parts of the model your product uses, we can add an
environment with de-identified data at realistic volume. We are deliberately not
building that first, because we would be guessing at what to include.

**What is the process for adding or exposing additional views or metrics?**

You send us a request naming the grain, the dimensions and measures, and the
screen it feeds. Our analytics engineers implement it in the warehouse and the
semantic layer, and we regenerate the catalog.

We are keeping authorship on our side because that is where data-classification
and grain decisions live. We will give you a request template so nothing is lost
in translation, and the catalog is version-controlled, so every change shows up
as a diff you can see.

**What you get first, for getting this into code.**

- A machine-readable catalog of the semantic layer: every view, its dimensions
  and measures, types, grains, and descriptions. No data in it.
- Sample request and response pairs, so you can mock locally and start writing
  parsing code before the sandbox exists.
- A readable version of the same catalog for design and scoping conversations.
- A short gotchas list. The most important one: **if a query asks for a field
  the caller's permissions exclude, we reject the whole query rather than
  dropping that field.** Worth handling early — it is the most common surprise
  for teams integrating with us.
- If it helps, we can generate TypeScript types from the catalog so view and
  field names are compile-time checked. Tell us if you want that.

**Audit logs.**

Agreed, and we checked: our platform's built-in audit log covers administrative
events, not data access. So we are building the data-access trail ourselves —
one record per query with the identity, the view, and a timestamp, never row
values — into our own warehouse with retention we control. That lands alongside
the sandbox rather than after it.

**Rough phasing — please react with your timeline and what you actually need.**

1. **Catalog and samples** — days. Enough to start writing code and scoping
   screens.
1. **Sandbox with synthetic data and your access** — one to two weeks. A real
   endpoint, real auth, test personas, no real records.
1. **Audit trail** — built alongside the sandbox.
1. **Repoint at production data** — weeks, and **blocked on one question from
   you** (below).
1. **De-identified environment at realistic volume** — later, scoped to what
   your product actually uses.

Steps 1 through 3 do not depend on that open question, so we can start now.

Two things we need back from you:

- **Who are your product's end users, and does a query carry a signed-in
  person's identity or your application's own?** This is the single biggest
  driver, and it is the one thing that could change the approach rather than
  just the timeline.
- **When do your engineers need something to call?** If that is sooner than our
  sandbox timeline, say so and we will get you the catalog and sample responses
  first so you can mock against them while we build.
