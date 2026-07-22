# Cube external API-key access + cloud emulation — design

- **Issue:** [#4455](https://github.com/TEAMSchools/teamster/issues/4455)
- **Status:** Design (brainstorming output; feeds `superpowers:writing-plans`)
- **Date:** 2026-07-22
- **Author:** cristinabaldor (with Claude)

## Summary

Add an API-key access layer to the Cube semantic layer so a **contracted
external vendor** (operating as a FERPA "school official" under a written
data-sharing agreement) can query Cube over REST/MCP with **row-level,
location-scoped access** — without ever holding the deployment master secret
(`CUBEJS_API_SECRET`).

The same work resolves a second, related need: **emulating users in Cube Cloud**
for testing. The two share a resolver core (identity → security context) but use
different auth-hook front-ends, so this spec treats them as one design with two
parts.

## Background — current architecture (post PR #4269)

Authentication and row-level security flow through one identity-agnostic
pipeline:

```text
checkAuth (REST/MCP)  ─┐
                       ├─→ resolveAccess(email) ─→ buildSecurityContext ─→ groups ─→ per-view access_policy
checkSqlAuth (SQL API)─┘
```

Everything downstream of the resolver only reads the _shape_ of the security
context, not how it was produced. Key facts grounded in code:

- [`cube.js`](../../../src/cube/cube.js) `checkAuth` receives the raw bearer
  token, verifies HS256 against `CUBEJS_API_SECRET`, reads the `email` claim,
  and sets `req.securityContext = await resolveAccess(email)`.
- `resolveAccess(email)` reads one row from `dim_staff_cube_access` plus
  reportees from `dim_staff_reporting_chain`, computes allow-lists, and calls
  `access.buildSecurityContext(...)`. Fail-closed to an empty (default-deny)
  context on any error. Cached per-email until next midnight ET.
- [`access.js`](../../../src/cube/access.js) holds the pure, unit-tested logic
  (`buildGroups`, `buildSecurityContext`, `computeAllowedAbbreviations`,
  `computeAllowedDepartmentGroups`).
- Row-level security lives entirely in per-view `access_policy` blocks.

The problem: access is derived from an `email` resolved against HR data. An
external email not in `dim_staff_cube_access` authenticates but default-denies
(zero rows). Handing out `CUBEJS_API_SECRET` is unacceptable — it is the master
key for the REST path and can mint a token for any email, including a full-PII
network account.

## Goals

- A scoped, revocable credential for a contracted external vendor over
  **REST/MCP only** (v1).
- Row-level access scoped to an **explicit list of schools** named in the DPA.
- Vendor sees **student data** (the collapsed student views) and a
  **location-scoped staff directory** (no staff PII).
- A working, documented way to **emulate/impersonate a user in Cube Cloud** for
  testing, plus re-verification of the local emulation backup.

## Non-goals (v1)

- SQL API access for external keys (key-in-password slot is awkward; deferred).
- Staff PII for external vendors (`staff_pii` view is out of scope).
- Aggregate / de-identified tiers (not this vendor's need; blocked separately by
  small-cell suppression #4237).
- Self-serve key management / partner portal.
- A durable warehouse audit sink (v1 uses Cube Cloud logs; see Audit).

## Design — Part 1: External API-key access layer

### 1.1 Resolver dispatch

Add `resolveApiKey(key)` in [`cube.js`](../../../src/cube/cube.js) as a sibling
to `resolveAccess(email)`. `checkAuth` gains one routing branch keyed on a
**key-prefix convention**:

- Token starts with the key prefix (`cbk_...`) → `resolveApiKey(key)`.
- Otherwise → the existing JWT path (`jwt.verify` → `email` → `resolveAccess`),
  unchanged.

`resolveApiKey(key)`:

1. Compute `sha256(key)`. Keys are 256-bit random, so a plain fast hash is
   correct — no bcrypt/argon2 (those defend low-entropy passwords).
1. Look up the hash in the in-memory registry (parsed once from the env var).
1. Miss / `active:false` / past `expires_at` → empty default-deny context (fail
   closed, same as `resolveAccess`).
1. Hit → build the security context from the registry entry's explicit
   allow-list and emit the `external-*` groups (below).

API keys are **opaque bearer tokens, not JWTs** — compared by hash. They do not
depend on `CUBEJS_API_SECRET`, so rotating the secret never disturbs keys, and
revoking a key never touches the secret. HTTPS-only.

### 1.2 Registry — Cube Cloud environment variable (JSON)

A single env var `CUBE_API_CLIENTS` holds the whole registry as a JSON object,
**keyed by each key's hash**:

```json
{
  "<sha256-of-key>": {
    "client_name": "acme-analytics",
    "allowed_abbreviations": ["KCNA", "KHNA"],
    "expires_at": "2026-12-31",
    "active": true
  }
}
```

`resolveApiKey` runs `JSON.parse(process.env.CUBE_API_CLIENTS)` once and looks
up `sha256(presented_key)`. For a handful of vendors this is a small string.
Only **hashed** keys and scope config are stored; raw keys are stored nowhere.

The entry carries an **explicit `allowed_abbreviations` list** rather than the
person-relative `student_location_scope` enum, because `school`/`region` mean
"the one school/region on your HR row" — an external vendor has no roster row,
so scope must be stated explicitly and can span an arbitrary set of schools.

### 1.3 External groups and view policies

This is a small, **additive** change (correcting the initial "zero view changes"
assumption). `access.js` gains external-group emission; two new group namespaces
are emitted **only** by `resolveApiKey`, never by the internal `resolveAccess`
path:

- `external-student` — an additive `access_policy` block on each covered student
  view, filtering `locations_abbreviation` (bare `abbreviation` on the
  assessment view — per-view authoring detail) with the array-`IN` form:
  `values: "{ securityContext.allowed_abbreviations }"`, mirroring the proven
  `staff_pii` remit pattern.
- `external-staff-directory` — a **new** `row_level` block on `staff_directory`
  filtering the same list. The internal `staff-directory` group stays open and
  untouched; `staff_directory` already exposes `locations_abbreviation`, so this
  is expressible.

Member visibility: both external groups use `member_level: { includes: "*" }`.
So `external-student` exposes the **full student field set, including student
PII** (names, `student_number`, `date_of_birth`, ...) — scoped by location,
matching the internal `student-*` tiers — because the vendor's need is
row-level-with-PII under the DPA. `external-staff-directory` exposes the
directory's fields, which by construction carry **no staff PII** (personal
contact, DOB, and demographics live only in `staff_pii`, which is out of scope).
If a future DPA needs a narrower student field set, switch `external-student` to
an explicit `includes`/`excludes` list — but that is not v1.

Empty `allowed_abbreviations` → no group emitted → clean default-deny (mirrors
the existing `staff_pii` empty-array guard; Cube throws "Values required for
filter" on an empty `IN`, so the group must not be emitted).

Covered student views for v1: the collapsed student views
(`student_enrollments_view`, `student_attendance_view`,
`student_assessment_scores_view`, `student_section_enrollments_view`) — trim to
the specific views the DPA names if narrower.

### 1.4 Key lifecycle — data-team script

A script (`scripts/cube-api-key.py`, run via `uv run`):

- **Generate:** mint a random key, format `cbk_<base32>`, print it **once**, and
  print the JSON entry (hash + scope) to paste into `CUBE_API_CLIENTS`. The raw
  key is handed to the vendor over a secure channel — never logged, committed,
  or put in a ticket.
- **Validate:** reject an empty `allowed_abbreviations`, reject unknown
  abbreviations, and require `expires_at` (no non-expiring external key).
- **Revoke / rotate:** set `active:false` or remove the entry, then redeploy
  (env-var change → Cube Cloud redeploy, ~minutes). Rotate =
  add-new-then-remove-old.

### 1.5 Guardrails (DPA-matched)

- **No network scope** — external access requires a non-empty explicit school
  list; there is no "all locations" external key.
- **No staff PII** — no `external-*` policy is added to `staff_pii`.
- **Mandatory expiry** — enforced by the generator and `resolveApiKey`.
- **Governance/activation gate** — an entry lands in the live env var only after
  the DPA is executed and People Ops / legal sign off. Process, not code;
  documented in the runbook. (Engineering does not remove the need for the DPA.)
- **Blast radius** — a leaked key sees only its own entry's scope.

### 1.6 Audit

PII leaving KTAF wants a per-client trail. v1: `resolveApiKey` emits a
structured log line per request (`client_name`, timestamp — no PII) into Cube
Cloud logs; Cube Cloud query history covers query detail. A durable sink
(BigQuery/GCS) is a future add if retention/compliance requires it. Verify what
Cube Cloud offers natively for audit before finalizing.

## Design — Part 2: Emulation and Cube Cloud config

### 2.1 State of each emulation surface

| Surface                 | Hook           | Works today      | Path                                                                      |
| ----------------------- | -------------- | ---------------- | ------------------------------------------------------------------------- |
| Local SQL API (backup)  | `checkSqlAuth` | Yes              | psycopg2, connect as viewer email in `user`; runs even in dev mode        |
| Cloud Playground (REST) | `checkAuth`    | Auth-on only     | Staging/prod (not dev mode) + "Edit Security Context" `{"email": target}` |
| Cloud Explore (SQL)     | `checkSqlAuth` | No (the blocker) | Depends on what `user` Explore connects as + Cube Cloud config            |

Dev Mode skips `checkAuth` entirely, so the Playground default-denies every
gated view unless auth is on — this is why the local Playground "worked" only
with auth on, and why the SQL API is the truer local path.

### 2.2 API keys as cloud emulation (the unified bonus)

Because we are building `resolveApiKey`, we get deterministic cloud emulation
for the external path for free: create internal **test-persona keys** scoped
like a real vendor, and present the key via REST/MCP to see exactly that scope
anywhere auth is on — no dependence on console quirks. Split:

- Test **external** access → present an external test key (REST; works in
  cloud).
- Test **internal** RLS → local SQL API (ground truth) or cloud Playground
  paste.

### 2.3 Cube Cloud config — verification spike

Verify against a live staging deployment before writing the emulation runbook.
Do not assert third-party behavior:

1. Does **"Enable Cloud Auth Integration"** (Settings → Configuration) make
   Explore/Playground pass the logged-in console user's identity to our custom
   hooks?
1. What SQL `user` does **Explore** actually connect as? (If not the console
   user's `@apps.teamschools.org` email, that is the denial cause.)
1. Does `__user` impersonation work in Explore for `CUBEJS_SQL_SUPER_USER`
   (already `cube-superset-service`), given our `canSwitchSqlUser` guard limits
   the target to `@apps.teamschools.org`?
1. Does the Playground security-context paste trigger `resolveAccess` on
   prod/staging (i.e. does Cube Cloud sign it with `CUBEJS_API_SECRET` so our
   `jwt.verify` accepts it)?

## Testing strategy

- **Unit** (`node --test src/cube/access.test.js`): external-group emission;
  `resolveApiKey` hash lookup, expiry, `active:false`, fail-closed on miss.
- **Local RLS:** existing SQL-API viewer-loop, plus REST-auth-on
  (`NODE_ENV=production`) with an external test key in the `Authorization`
  header. Re-verify the local SQL emulation backup still works.
- **Cloud:** staging deployment; present an external test key via `curl`;
  confirm scoped rows and that out-of-scope schools return zero.
- **Regression:** confirm internal `student-*` / `staff-directory` / `staff-pii`
  behavior is unchanged (external groups are additive, never emitted by
  `resolveAccess`).

## Invariants preserved

- Cubes private, views public; fail-closed default-deny.
- No change to internal identity resolution or existing internal view policies
  (external policies are additive, separate group namespace).
- Never store raw keys; keys are bearer credentials (HTTPS only).
- `canSwitchSqlUser` unchanged (SQL super-user impersonation guard).
- A leaked key's blast radius is limited to its own scope.

## Open questions / verification items

- The four Cube Cloud config questions in 2.3 (spike).
- Native Cube Cloud audit capability and log retention (affects whether a
  durable sink is needed sooner).
- Exact per-view filter member name on each covered student view
  (`locations_abbreviation` vs bare `abbreviation`).
- Confirm the covered student view list against the DPA scope.

## Out of scope / future

- SQL API surface for external keys.
- Staff PII, aggregate, and de-identified external tiers.
- Self-serve key management / partner portal.
- Migrating the registry from an env var to a BigQuery table if client count
  grows beyond a handful or self-serve is needed.
- Per-key rate limiting (evaluate what Cube Cloud offers per identity).

## Related

- PR #4269 — the HR-derived security redesign this builds on.
- #4237 — small-cell suppression (blocks aggregate demographic exposure).
- #4268 — `queryRewrite` member-strip (out-of-tier field handling).
- #4342 — post-#4269 follow-ups.
