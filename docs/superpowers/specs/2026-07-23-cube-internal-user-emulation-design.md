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
build is gated behind a cheap verification spike — the spike may show that no
new server code is needed for the Cube Cloud surface.

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
  (HS256 against `CUBEJS_API_SECRET`), reads the `email` claim, and sets
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
email, there is no way to say "act as user X." Every native emulation surface
falls to default-deny:

| Surface                         | Hook           | State      | Why                                                                                                                                                       |
| ------------------------------- | -------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local SQL API                   | `checkSqlAuth` | **Works**  | Connect as the viewer email in `user`; runs even in dev mode                                                                                              |
| Cube Cloud Playground / Explore | `checkAuth`    | **Denied** | Requests arrive with no resolvable `email` → empty context → views hidden (`/meta` empty, only source tables show) and queries compile to `WHERE (1 = 0)` |
| Local Playground (REST)         | `checkAuth`    | **Denied** | Cube dev mode skips `checkAuth` entirely → default-deny for every gated view                                                                              |

### Validated facts from the 2026-07-23 session

- The **local SQL API matrix works end to end**: connecting as a `network`,
  `region`, `school`, `none`, and unresolved viewer returned exactly the right
  scope (all regions / one region / one school / zero / zero). This is the
  current ground-truth validation tool.
- The **REST `checkAuth` + email-JWT path resolves correctly on prod Cube
  Cloud**: the `cube` MCP mints an `email`-claim JWT and gets full network
  scope. So `checkAuth` is not broken — the Cloud Playground/Explore UI simply
  is not putting an `email` into its requests.
- A **local-dev blocker was found and patched (scaffold)**: with
  `CUBEJS_DB_BQ_CREDENTIALS` unset ("uses ADC locally"), `resolveAccess`'s
  hand-rolled BigQuery client runs `JSON.parse("")` at `cube.js:99`, throws, and
  fail-closes to deny-all for every viewer. The driver itself falls back to ADC;
  `resolveAccess` does not. This must be fixed for any local emulation to work.

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
   `docs/guides/cube.md`.

This alone lets the team sign off each pilot user's scope, so **the pilot is not
blocked on the phases below**.

### Phase 1 — Cube Cloud verification spike (before any `act_as` build)

Reuse #4501 Part 2.3 verbatim (shared work). Run against a live staging
deployment; do not assert third-party behavior:

1. Does **"Enable Cloud Auth Integration"** (Settings → Configuration) make
   Explore/Playground pass the logged-in console user's identity to our custom
   hooks?
1. What SQL `user` does **Explore** connect as? (If not the console user's
   `@apps.teamschools.org` email, that is the denial cause.)
1. Does `__user` impersonation work in Explore for `CUBEJS_SQL_SUPER_USER`,
   given `canSwitchSqlUser` limits the target to `@apps.teamschools.org`?
1. Does a **Playground security-context paste** of `{"email": "<target>"}` get
   signed with `CUBEJS_API_SECRET` so our `jwt.verify` accepts it and
   `resolveAccess` runs?

**Decision gate:** if Q4 (and/or Q1) is yes, internal cloud emulation is solved
with **zero new server code** — a self-serve viewer sets/pastes an email and
sees that user's scope. Phase 2 then shrinks to just the Explore SQL pane, or
drops entirely. Only a proven gap justifies building `act_as`.

### Phase 2 — admin-gated `act_as` (conditional on the spike)

Add an explicit impersonation path to the REST hook.

**`checkAuth` flow:**

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
  `can_impersonate`. HR-governed, consistent with the model; migrate post-pilot.
  The `isImpersonator(email, ctx)` signature accommodates both so the migration
  is internal.

**SQL API / Explore:** impersonation there is already expressible via the
existing `canSwitchSqlUser` super-user + `__user` mechanism; no change unless
the spike shows Explore needs more. Do **not** broaden `canSwitchSqlUser`.

**MCP:** the current `cube` MCP mints an `email`-only JWT. Emulation via MCP
would require it to pass an `act_as` claim — noted as a follow-up, not v1.

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
  `staff-pii` behavior unchanged.
- **Local RLS:** the SQL API viewer-loop matrix (ground truth), plus a
  REST-auth-on run (`NODE_ENV=production`) exercising `act_as`.
- **Cloud:** per the Phase 1 spike outcome — either document the paste/console
  path or smoke-test `act_as` over REST against staging.

## Invariants preserved

- Cubes private, views public; fail-closed default-deny.
- Real end-users cannot self-elevate — `act_as` is honored only for an already
  admin-gated caller.
- Internal identity resolution and existing internal view policies are
  unchanged.
- `canSwitchSqlUser` unchanged.
- The external group namespace is untouched by internal emulation.

## Alternatives considered

- **Test-persona API keys (from #4501 Part 2.2).** They emulate the
  **external-\*** path only (explicit school list, no staff PII, no network), so
  they cannot reproduce an internal user's real HR-derived scope. Complementary,
  not a substitute for internal emulation.
- **Paste a full `securityContext` in the dev Playground.** Works in dev mode
  (which skips `checkAuth`) but requires hand-crafting groups + `region_key` +
  allow-lists — error-prone and not faithful. The context-dump-from-email helper
  is a milder version; superseded if the Phase 1 spike shows email-paste
  resolves.
- **Non-prod-only emulation.** Rejected: the chosen trust model is admin-gated
  on **any** deployment, so emulation must be able to run against prod for a
  trusted admin.

## Open questions / verification items

- The four Cube Cloud config questions in Phase 1 (spike) — gate Phase 2.
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
  security redesign this builds on.
- [#4333](https://github.com/TEAMSchools/teamster/issues/4333) /
  [#4460](https://github.com/TEAMSchools/teamster/pull/4460) — assessment
  materialization + `proficiency_rollup` pre-agg (the RLS validation that
  surfaced this gap).
- `#4466` — the `resolveAccess` BigQuery-client project pin that the ADC
  fallback extends.
