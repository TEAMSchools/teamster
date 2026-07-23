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

The design is **staged** so the pilot-critical piece ships first and the larger
build is gated behind a cheap verification spike — the 2026-07-23 session
already answered most of that spike (see below): the true cross-surface blocker
is the `checkAuth` `maxAge` token-age cap, not a dev-mode auth-skip.

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
email, there is no first-class "act as user X" path, and two mechanics get in
the way of even self-emulation:

| Surface                         | Hook           | State                        | Notes                                                                                                                                                                                                    |
| ------------------------------- | -------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local SQL API                   | `checkSqlAuth` | **Works**                    | Connect as the viewer email in `user`; runs even in dev mode. Ground-truth validation surface                                                                                                            |
| Local Playground (REST)         | `checkAuth`    | **Works**                    | `checkAuth` DOES run in dev mode (Cube 1.6.59); paste `{"email": "target"}` with a **freshly minted** token. Earlier "denied" was the `maxAge` cap rejecting a stale cached token, not an auth-skip      |
| Cube Cloud Playground / Explore | `checkAuth`    | **Denied (likely `maxAge`)** | Same `checkAuth` runs; denial is the `maxAge` cap rejecting the console-minted token and/or no resolvable `email` → empty context → views hidden (`/meta` empty, only source tables) and `WHERE (1 = 0)` |

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
- **`checkAuth` runs in dev mode (Cube 1.6.59), and the real Playground/Explore
  blocker is the `maxAge` cap.** A stack trace on `/cubejs-api/v1/meta` showed
  `checkAuth` firing in dev mode and throwing
  `TokenExpiredError: maxAge exceeded` (`cube.js:227`) on a Playground token
  whose `iat` was ~5 weeks stale. Pasting `{"email": "target"}` into the
  Playground Security Context with a freshly minted token then resolves the
  target correctly. So: (a) the CLAUDE.md "dev mode skips checkAuth" note is
  **wrong for this version**; (b) **local email-emulation works** via a fresh
  `{email}` paste — no full-context helper needed; (c) the cross-surface blocker
  is the `maxAge: "12h"` cap (added in #4269), not auth-skip or a missing email.

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

1. **Document the local SQL API validation matrix** as the official pre-pilot
   tool (the `.claude/scratch/rls_matrix.py` harness pattern: reconnect per
   viewer email, assert scope). Capture it in `src/cube/CLAUDE.md` and
   `docs/guides/cube.md`, alongside the local-Playground `{email}`-paste method.

This alone lets the team sign off each pilot user's scope, so **the pilot is not
blocked on the phases below**.

### Phase 1 — verification spike (mostly answered on 2026-07-23)

The original spike (reused from #4501 Part 2.3) asked whether `checkAuth` runs
and whether an `{email}` paste resolves. The local repro answered the core of
it:

- **Answered:** `checkAuth` runs in dev mode; an `{email}` paste with a fresh
  token resolves the target; the wall is the `maxAge` cap. The full-context
  helper is therefore unnecessary for the Playground.
- **Still to verify on Cube Cloud (staging):**
  1. Does **"Enable Cloud Auth Integration"** (Settings → Configuration) pass
     the logged-in console user's identity to our hooks?
  1. What SQL `user` does **Explore** connect as? (If not the console user's
     `@apps.teamschools.org` email, that is a denial cause.)
  1. Does `__user` impersonation work in Explore for `CUBEJS_SQL_SUPER_USER`,
     given `canSwitchSqlUser` limits the target to `@apps.teamschools.org`?
  1. Confirm the **`maxAge` cap** is what rejects the console-minted token
     (strongly expected, matching the local repro) and whether the console token
     is short- or long-lived.

**Decision gate:** because `checkAuth` already resolves `{email}`, fixing the
`maxAge` control (below) most likely unblocks cloud emulation with **no new
resolver code** — a data-team console admin sets/pastes the target email and
sees that scope. Explicit `act_as` is then needed only where there is no console
(API/MCP) or where emulation must be gated **more tightly** than Cube Cloud
console access.

### Phase 2 — the `maxAge` control + admin-gated `act_as`

**The `maxAge` control (primary blocker; a security decision, not a snap
change).** `checkAuth`'s `maxAge: "12h"` (`cube.js:227`) rejects any token whose
`iat` is over 12h old — which breaks the Playground (stale cached token) and,
almost certainly, Cube Cloud Explore (console-minted token). Options, to decide
with the analytics-engineer code owners:

- Raise/remove `maxAge` and rely on the token's own `exp`.
- Scope `maxAge` to only the short-lived MCP-minted tokens (which set a 5-min
  `exp`), exempting interactive Playground/console tokens.
- Keep it and document a "re-mint a fresh token" step per surface — fragile, and
  does not fix Cloud if the console token is long-lived.

Weigh against the #4269 rationale for `maxAge` (a compromised minter cannot
extend a token's life by inflating `exp` alone).

**Admin-gated `act_as` (for the API/MCP surface and tighter gating).** Add an
explicit impersonation path to the REST hook:

```js
const callerEmail = payload.email;
const actAs = payload.act_as; // optional target
const callerCtx = await resolveAccess(callerEmail);
req.securityContext =
  actAs && isImpersonator(callerEmail, callerCtx)
    ? await resolveAccess(actAs) // faithful emulation of the target
    : callerCtx; // own scope; act_as ignored for non-impersonators
```

The impersonation decision is made on the **caller's real resolved identity**,
so it is unforgeable — a token cannot self-assign impersonator rights.

**Where "who may impersonate" lives:**

- **v1 — `CUBE_IMPERSONATORS` environment variable** (comma-separated data-team
  emails). Ships without a dbt change; fits the pilot deadline.
  `isImpersonator(email)` = membership test.
- **Later — warehouse column** (`is_cube_impersonator` in
  `dim_staff_cube_access`), surfaced by `buildSecurityContext` as
  `can_impersonate`. HR-governed; migrate post-pilot. The
  `isImpersonator(email, ctx)` signature accommodates both.

**SQL API / Explore:** impersonation there is already expressible via the
existing `canSwitchSqlUser` super-user + `__user` mechanism; do **not** broaden
`canSwitchSqlUser`.

**MCP:** the `cube` MCP mints an `email`-only JWT; `act_as` support there is a
follow-up, not v1.

### Audit

Impersonation moves PII visibility, so it needs a trail. `checkAuth` emits a
structured log line when `act_as` is honored (`caller`, `act_as`, timestamp — no
row data) into Cube Cloud logs. A durable sink is a future add if compliance
requires retention.

## External-compatibility constraint (kept in mind, not built)

- The `checkAuth` token-routing must be shaped so #4501's `resolveApiKey`
  (key-prefix branch) drops in as a sibling without reworking the `act_as`
  branch.
- **Group namespaces stay strictly separate:** `act_as` only ever resolves
  **internal** context via `resolveAccess` (`student-*` / `staff-*`);
  `external-*` groups are never emitted by `resolveAccess`. The two never cross.

## Testing strategy

- **Unit** (`node --test src/cube/access.test.js` + a `cube.js` harness for the
  hook): impersonator + `act_as` → target context; **non-impersonator + `act_as`
  → own context, not target** (the critical negative case); unknown/unresolvable
  `act_as` → fail-closed; `isImpersonator` membership.
- **Regression:** the internal `resolveAccess` path is byte-for-byte unchanged
  when no `act_as` is present; existing `student-*` / `staff-directory` /
  `staff-pii` behavior unchanged. Confirm any `maxAge` change does not accept an
  expired short-lived MCP token.
- **Local RLS:** the SQL API viewer-loop matrix (ground truth), plus a
  Playground `{email}`-paste check and a REST-auth-on run
  (`NODE_ENV=production`) exercising `act_as`.
- **Cloud:** per the Phase 1 items — confirm the `maxAge` fix unblocks the
  console, then smoke-test scope on staging.

## Invariants preserved

- Cubes private, views public; fail-closed default-deny.
- Real end-users cannot self-elevate — `act_as` is honored only for an already
  admin-gated caller, and cloud console emulation is gated by console access.
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
  (`.claude/scratch/dump_security_context.js`). **Superseded** for the
  Playground: since `checkAuth` runs in dev mode and resolves `{email}`, a plain
  `{email}` paste is enough. The helper remains useful only as an offline
  resolver cross-check.
- **Non-prod-only emulation.** Rejected: the chosen trust model is admin-gated
  on **any** deployment, so emulation must be able to run against prod for a
  trusted admin.

## Open questions / verification items

- The `maxAge` control decision (raise / scope-to-MCP / keep) — gates the cloud
  fix; needs code-owner sign-off.
- The remaining Cube Cloud config items in Phase 1 (Cloud Auth Integration,
  Explore's SQL `user`, `__user`), and whether Cube Cloud console access is
  already scoped to the intended admin set (if so, console `{email}` paste is
  the admin-gated cloud emulation and `act_as` shrinks to API/MCP only).
- Final impersonator source for v1 (`CUBE_IMPERSONATORS` list assumed; confirm
  the data-team email set).
- Native Cube Cloud audit capability and log retention.
- Whether the pilot's customer-facing surface is Cube Cloud Explore, a BI tool
  over the SQL API, or both — narrows which surface `act_as` must cover.

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
