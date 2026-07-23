# Cube internal user emulation for RLS validation — design

- **Issue:** [#4526](https://github.com/TEAMSchools/teamster/issues/4526)
- **Status:** Design (brainstorming output; feeds `superpowers:writing-plans`)
- **Date:** 2026-07-23
- **Author:** cristinabaldor (with Claude)

## Summary

Give the data team a sanctioned, admin-gated way to see **exactly what an
internal user sees** in the Cube semantic layer — for row-level-security (RLS)
validation ahead of an internal-customer pilot — without letting real end-users
self-elevate on production.

The work is deliberately **separated from the external-vendor API-key layer**
([#4455](https://github.com/TEAMSchools/teamster/issues/4455) /
[#4501](https://github.com/TEAMSchools/teamster/pull/4501)); this spec is
internal emulation only. It stays source-compatible with that external layer
(shared `checkAuth` dispatch, strictly separate group namespaces) so the vendor
work can fold in later without rework.

The design is **staged** so the pilot-critical piece ships first. The 2026-07-23
session ran the verification spike, and it showed the two blocked surfaces fail
for **different** reasons: the local Playground on the `checkAuth` `maxAge`
token-age cap (fixable with a fresh token), and Cube Cloud because it injects
its own **unenriched** security context that never runs through `resolveAccess`.

## Background — current architecture (post PR #4269)

Authentication and RLS flow through one identity-agnostic pipeline:

```text
checkAuth (REST/MCP)  ─┐
                       ├─→ resolveAccess(email) ─→ buildSecurityContext ─→ groups ─→ per-view access_policy
checkSqlAuth (SQL API)─┘
```

Everything downstream reads only the _shape_ of the security context, not how it
was produced. Grounded in code:

- [`cube.js`](../../../src/cube/cube.js) `checkAuth` verifies the bearer token
  (HS256 against `CUBEJS_API_SECRET`, with a `maxAge: "12h"` cap on the token's
  `iat`), reads the `email` claim, and sets
  `req.securityContext = await resolveAccess(email)`. It **ignores any
  caller-supplied context** — the entire context is rebuilt from the email.
- `checkSqlAuth` resolves identity from the connecting SQL `user` (or
  `CUBE_SQL_DEV_EMAIL` outside production), and `canSwitchSqlUser` lets the SQL
  super-user (`cube-superset-service`) impersonate `@apps.teamschools.org`
  accounts via `__user`.
- `resolveAccess(email)` reads one row from `dim_staff_cube_access` plus
  reportees from `dim_staff_reporting_chain`, computes allow-lists, and calls
  `access.buildSecurityContext(...)`. It fails **closed** (empty default-deny
  context) on any error.
- [`access.js`](../../../src/cube/access.js) holds the pure, unit-tested logic
  (`buildGroups`, `buildSecurityContext`, `computeAllowedAbbreviations`,
  `computeAllowedDepartmentGroups`).

**The gap:** because the context is derived only from the caller's own resolved
email, there is no first-class "act as user X" path, and each blocked surface
fails differently:

| Surface                         | Hook                 | State                           | Notes                                                                                                                                                                                                                                                                  |
| ------------------------------- | -------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local SQL API                   | `checkSqlAuth`       | **Works**                       | Connect as the viewer email in `user`; runs even in dev mode. Ground-truth validation surface                                                                                                                                                                          |
| Local Playground (REST)         | `checkAuth`          | **Works (fresh token)**         | `checkAuth` runs in dev mode (Cube 1.6.59); paste `{"email": "target"}` into the Security Context editor. Earlier "denied" was the `maxAge` cap rejecting a stale cached token                                                                                         |
| Cube Cloud Playground / Explore | `checkAuth` bypassed | **Denied (unenriched context)** | Cube Cloud injects its own context (top-level `email` = target, `cubeCloud.username` = caller, `iss: "cubecloud"`) **directly** — `resolveAccess` never runs, so `contextToGroups` finds no `groups` and `row_level` fields are absent → `WHERE (1 = 0)`, views hidden |

### Validated facts from the 2026-07-23 session

- The **local SQL API matrix works end to end**: connecting as a `network`,
  `region`, `school`, `none`, and unresolved viewer returned exactly the right
  scope (all regions / one region / one school / zero / zero). This is the
  current ground-truth validation tool.
- The **REST `checkAuth` + email-JWT path resolves correctly on prod Cube
  Cloud**: the `cube` MCP mints an `email`-claim JWT and gets full network
  scope.
- A **local-dev blocker was found and patched (scaffold)**: with
  `CUBEJS_DB_BQ_CREDENTIALS` unset ("uses ADC locally"), `resolveAccess`'s
  hand-rolled BigQuery client runs `JSON.parse("")` at `cube.js:99`, throws, and
  fail-closes to deny-all for every viewer. The driver itself falls back to ADC;
  `resolveAccess` does not. Fixed by an ADC fallback (Phase 0).
- **Local Playground: `checkAuth` runs in dev mode; the blocker was a stale
  token hitting `maxAge`.** A stack trace on `/cubejs-api/v1/meta` showed
  `checkAuth` firing in dev mode and throwing
  `TokenExpiredError: maxAge exceeded` (`cube.js:227`) on a cached Playground
  token whose `iat` was ~5 weeks old. Pasting `{"email": "target"}` with a
  freshly minted token then resolves the target correctly. So the CLAUDE.md "dev
  mode skips checkAuth" note is **wrong for this version**, and local
  email-emulation works.
- **Cube Cloud injects its own unenriched context and bypasses `checkAuth`.**
  The query security context on Cube Cloud reads
  `{ "email": "<target>", "cubeCloud": { "username": "<caller>", "roles": ["Developer"], ... }, "iss": "cubecloud", "exp": ... }`
  — a top-level `email` (the target typed into the Security Context box), the
  real console user under `cubeCloud.username`, and **no `iat`**. It produced
  `WHERE (1=0)`, **not** a 403 — proving `checkAuth` did not process it (a
  missing-`iat` token would have thrown under `maxAge`). Cube Cloud injects the
  object directly; `contextToGroups` finds no top-level `groups` → default-deny.
  This is a **different** blocker from the local `maxAge` one, and it is the
  real reason Explore/Playground deny on Cube Cloud. Usefully, it hands us both
  identities for `act_as`: the caller in `cubeCloud.username`, the target in the
  top-level `email`.

## Goals

- The data team can emulate any internal user (by email) to validate RLS before
  the pilot, on the surfaces the pilot actually uses.
- Emulation is **admin-gated** and honored on **any deployment** (local, branch
  staging, prod), per the chosen trust model — real end-users can never
  self-elevate.
- Emulation is **faithful**: it resolves the target's real HR-derived context
  (groups, `region_key`, allow-lists, reporting chain), not a hand-crafted stub.
- Source-compatible with the external-vendor API-key layer (#4455 / #4501).

## Non-goals (this spec)

- External-vendor API keys / `resolveApiKey` — deferred to #4501 / #4455.
- Changing `canSwitchSqlUser` or the SQL super-user model.
- Self-serve emulation for non-admins; a partner/emulation UI.
- A durable warehouse audit sink (v1 uses Cube Cloud logs plus a structured log
  line; see Audit).

## Design

### Phase 0 — pilot-critical, ship now (low risk)

1. **Make the `resolveAccess` ADC fallback permanent.** When
   `CUBEJS_DB_BQ_CREDENTIALS` is set, parse it as today; when it is unset, build
   the client with `projectId` only and let Application Default Credentials
   resolve (exactly what the BigQuery driver already does). Keep the `projectId`
   pin so ADC bills `teamster-332318` (preserves the #4466 fix). This turns the
   session scaffold into real code.

   ```js
   const bqOptions = { projectId: process.env.CUBEJS_DB_BQ_PROJECT_ID };
   if (process.env.CUBEJS_DB_BQ_CREDENTIALS) {
     bqOptions.credentials = JSON.parse(
       Buffer.from(process.env.CUBEJS_DB_BQ_CREDENTIALS, "base64").toString(
         "utf8",
       ),
     );
   }
   const bq = new BigQuery(bqOptions);
   ```

1. **Document the local validation surfaces** as the official pre-pilot tools:
   the SQL API matrix (`.claude/scratch/rls_matrix.py` pattern — reconnect per
   viewer email, assert scope) and the local Playground `{email}`-paste method.
   Capture in `src/cube/CLAUDE.md` and `docs/guides/cube.md`.

This alone lets the team sign off each pilot user's scope, so **the pilot is not
blocked on the phases below**.

### Phase 1 — verification spike (answered 2026-07-23)

The spike asked how each surface delivers identity. Answered:

- **Local Playground:** `checkAuth` runs in dev mode; a fresh `{email}` token
  resolves the target; a stale token trips `maxAge`.
- **Cube Cloud:** `checkAuth` is bypassed; Cube Cloud injects an unenriched
  context (top-level `email` = target, `cubeCloud.username` = caller,
  `iss: "cubecloud"`, no `iat`) → `contextToGroups` returns `[]` → deny.

Remaining Cube Cloud items to confirm on staging:

1. Does **"Enable Cloud Auth Integration"** (Settings → Configuration) change
   how the context is injected (e.g. route it through our hooks)?
1. What SQL `user` does **Explore** connect as, and does `__user` impersonation
   work for `CUBEJS_SQL_SUPER_USER` (given `canSwitchSqlUser`)?
1. Can `contextToGroups` **mutate** the securityContext (populate `region_key` /
   allow-lists), or is a dedicated context-transform hook required?

**Decision gate:** the fixes are now surface-specific — local needs the `maxAge`
decision, Cube Cloud needs server-side **enrichment** of the injected context.
Both are Phase 2.

### Phase 2 — enrichment + `maxAge` + admin-gated `act_as`

Two surface-specific fixes over one shared resolver.

**(a) Cube Cloud context enrichment (the cloud blocker).** Cube Cloud delivers
both identities in the injected context: the authenticated caller in
`cubeCloud.username`, the emulation target in the top-level `email`. The
deployment must **enrich** this context server-side — gate on
`cubeCloud.username` ∈ the impersonator set, then `resolveAccess(email)` and
populate the resulting `groups` + `region_key` + allow-lists onto the security
context the policies read. Leading seam: `contextToGroups` (runs on Cube Cloud,
receives the context) — confirm it can **mutate** the securityContext, not just
return groups; else use a context-transform hook. Any path that runs the
`cubecloud` token through `jwt.verify` must **not** impose `maxAge` (no `iat`).

**(b) The `maxAge` control (the local blocker).** `checkAuth`'s `maxAge: "12h"`
(`cube.js:227`) rejects any token whose `iat` is over 12h old — which breaks the
Playground (stale cached token). A security decision, not a snap change; options
to weigh with the analytics-engineer code owners (against the #4269 rationale
that a compromised minter cannot extend life via `exp` alone):

- Raise/remove `maxAge` and rely on the token's own `exp`.
- Scope `maxAge` to only the short-lived MCP-minted tokens (which set a 5-min
  `exp`), exempting interactive Playground/console tokens.
- Keep it and document a "re-mint a fresh token" step per surface — fragile.

**(c) Admin-gated `act_as` (API/MCP + explicit gating).** For the REST/MCP
surface, add an impersonation path:

```js
const callerEmail = payload.email;
const actAs = payload.act_as; // optional target
const callerCtx = await resolveAccess(callerEmail);
req.securityContext =
  actAs && isImpersonator(callerEmail, callerCtx)
    ? await resolveAccess(actAs) // faithful emulation of the target
    : callerCtx; // own scope; act_as ignored for non-impersonators
```

The Cube Cloud path (a) is the same gate expressed through `cubeCloud.username`;
the REST/MCP path uses an `act_as` claim. The impersonation decision is made on
the **caller's real resolved identity**, so it is unforgeable.

**Where "who may impersonate" lives:**

- **v1 — `CUBE_IMPERSONATORS` environment variable** (comma-separated data-team
  emails). Ships without a dbt change; fits the pilot deadline.
- **Later — warehouse column** (`is_cube_impersonator` in
  `dim_staff_cube_access`), surfaced by `buildSecurityContext` as
  `can_impersonate`. HR-governed; migrate post-pilot. The
  `isImpersonator(email, ctx)` signature accommodates both.

**SQL API / Explore:** impersonation there is already expressible via the
existing `canSwitchSqlUser` super-user + `__user` mechanism; do **not** broaden
it.

**MCP:** the `cube` MCP mints an `email`-only JWT; `act_as` support there is a
follow-up, not v1.

### Audit

Impersonation moves PII visibility, so it needs a trail. The enrichment/`act_as`
path emits a structured log line when a caller resolves as a different target
(`caller`, `act_as`/`email`, timestamp — no row data) into Cube Cloud logs. A
durable sink is a future add if compliance requires retention.

## External-compatibility constraint (kept in mind, not built)

- The `checkAuth` token-routing must be shaped so #4501's `resolveApiKey`
  (key-prefix branch) drops in as a sibling without reworking the `act_as`
  branch.
- **Group namespaces stay strictly separate:** `act_as` / Cube Cloud enrichment
  only ever resolves **internal** context via `resolveAccess` (`student-*` /
  `staff-*`); `external-*` groups are never emitted by `resolveAccess`. The two
  never cross.

## Testing strategy

- **Unit** (`node --test src/cube/access.test.js` + a `cube.js` harness for the
  hook): impersonator + `act_as`/`cubeCloud.username` → target context;
  **non-impersonator + `act_as` → own context, not target** (the critical
  negative case); unknown/unresolvable target → fail-closed; `isImpersonator`
  membership; enrichment populates `groups` **and** `region_key`/allow-lists.
- **Regression:** the internal `resolveAccess` path is unchanged when no
  `act_as` is present; existing `student-*` / `staff-directory` / `staff-pii`
  behavior unchanged. Confirm any `maxAge` change still rejects an expired
  short-lived MCP token.
- **Local RLS:** the SQL API viewer-loop matrix (ground truth), plus a
  Playground `{email}`-paste check.
- **Cloud:** on staging, confirm the enrichment resolves the injected context
  and scopes correctly, and that out-of-scope rows are absent.

## Invariants preserved

- Cubes private, views public; fail-closed default-deny.
- Real end-users cannot self-elevate — impersonation is honored only for an
  admin-gated caller (`CUBE_IMPERSONATORS` / `cubeCloud.username`).
- Internal identity resolution and existing internal view policies are
  unchanged.
- `canSwitchSqlUser` unchanged.
- The external group namespace is untouched by internal emulation.

## Alternatives considered

- **Test-persona API keys (from #4501 Part 2.2).** They emulate the
  **external-\*** path only (explicit school list, no staff PII, no network), so
  they cannot reproduce an internal user's real HR-derived scope. Complementary,
  not a substitute.
- **Full-`securityContext` paste helper**
  (`.claude/scratch/dump_security_context.js`). Superseded for the local
  Playground (a plain `{email}` paste resolves). May still matter on Cube Cloud
  if enrichment is not wired, since Cube Cloud uses the injected context —
  verify during Phase 2. Also a useful offline resolver cross-check.
- **Non-prod-only emulation.** Rejected: the chosen trust model is admin-gated
  on **any** deployment, so emulation must be able to run against prod for a
  trusted admin.

## Open questions / verification items

- The `maxAge` control decision (raise / scope-to-MCP / keep) — needs code-owner
  sign-off.
- Whether `contextToGroups` can mutate the securityContext, or a
  context-transform hook is required for Cube Cloud enrichment.
- The remaining Cube Cloud config items (Cloud Auth Integration, Explore's SQL
  `user`, `__user`), and whether Cube Cloud console access is already scoped to
  the intended admin set (if so, console access itself is part of the gate).
- Final impersonator source for v1 (`CUBE_IMPERSONATORS` list assumed; confirm
  the data-team email set).
- Native Cube Cloud audit capability and log retention.
- Whether the pilot's customer-facing surface is Cube Cloud Explore, a BI tool
  over the SQL API, or both — narrows which surface the fix must cover.

## Out of scope / future

- External-vendor API-key layer (#4455 / #4501).
- `act_as` support in the `cube` MCP.
- Migrating the impersonator flag from an environment variable to a warehouse
  column.
- A durable (BigQuery/GCS) impersonation-audit sink.

## Related

- [#4526](https://github.com/TEAMSchools/teamster/issues/4526) — this issue.
- [#4455](https://github.com/TEAMSchools/teamster/issues/4455) /
  [#4501](https://github.com/TEAMSchools/teamster/pull/4501) — external-vendor
  API-key access + cloud emulation (sibling; folds in later).
- [#4269](https://github.com/TEAMSchools/teamster/pull/4269) — the HR-derived
  security redesign this builds on (added the `maxAge` cap).
- [#4333](https://github.com/TEAMSchools/teamster/issues/4333) /
  [#4460](https://github.com/TEAMSchools/teamster/pull/4460) — assessment
  materialization + `proficiency_rollup` pre-agg (the RLS validation that
  surfaced this gap).
- `#4466` — the `resolveAccess` BigQuery-client project pin that the ADC
  fallback extends.
