# Cube Internal User Emulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give an admin-gated data-team caller a sanctioned way to resolve
another internal user's real security context — on the REST/MCP surface and on
Cube Cloud — so each pilot user's row-level security (RLS) can be validated
before access is granted.

**Architecture:** One pure decision function (`resolveEmulationTarget` in
`access.js`) decides _whose_ context to build, from the caller's own identity
only; two thin surface adapters feed it (a REST JWT's `email`/`act_as`, and Cube
Cloud's injected `cubeCloud.username`/`email`). Both then call the existing
unchanged `resolveAccess(target)`, so every view's `access_policy` works with no
view changes. Non-impersonators are silently held to their own scope.

**Tech Stack:** Cube 1.6.x (`@cubejs-backend/server`), Node CommonJS,
`jsonwebtoken`, `node --test` (`npm test` in `src/cube`), BigQuery
(`@google-cloud/bigquery`), Python 3 + `psycopg` 3 for the SQL-API validation
tool, `uv` for all Python execution.

## Global Constraints

- **Design spec:**
  [`docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md`](../specs/2026-07-23-cube-internal-user-emulation-design.md).
  Issue [#4526](https://github.com/TEAMSchools/teamster/issues/4526).
- **The emulation decision is made on the caller's own resolved identity only.**
  A non-impersonator supplying a target gets their own scope — never the
  target's. This is the single most important invariant; it has a dedicated
  negative test in every task that touches a hook.
- **Fail closed.** An absent, unknown, or unresolvable caller or target resolves
  to the empty default-deny context, never to a broader one.
- **Never rewrite the email handed to `resolveAccess`** — not case, not
  whitespace. It runs `WHERE google_email = @email` and keys its cache on the
  raw string, and `checkSqlAuth` passes the connecting user through verbatim, so
  any normalization here silently desyncs the two auth paths. Compare
  case-insensitively where you must (impersonator membership, the self-check);
  pass the original value downstream. All 1,614 `dim_staff_cube_access` rows are
  lowercase today, but the model applies no `lower()` and the column's only test
  is `not_null` — that is an incidental property of the upstream source, not an
  invariant to build on.
- **Impersonator source v1 is the `CUBE_IMPERSONATORS` deployment variable**
  (comma-separated emails). The warehouse-column source
  (`dim_staff_cube_access.is_cube_impersonator`) is explicitly out of scope;
  keep `parseImpersonators` as the only place that reads the variable so it can
  be swapped later without touching the resolver or the adapters.
- **Read the variable per call, not at module load.** `cube.js` already reads
  `CUBEJS_API_SECRET` / `CUBE_GROUP_MAP` / `NODE_ENV` per call, and
  `src/cube/cube.test.js` depends on that (its `test.beforeEach` mutates them).
- **Do not broaden `canSwitchSqlUser`** (`src/cube/cube.js:406-408`). The SQL
  super-user impersonation guard stays exactly as is.
- **Group namespaces stay strictly separate.** Emulation only ever resolves
  internal context via `resolveAccess` (`student-*` / `staff-*`). `external-*`
  groups (#4455 / #4501) are never emitted by this path.
- **Keep `checkAuth` token routing shaped so #4501's `resolveApiKey` can drop in
  as a sibling branch** without reworking the emulation branch.
- **No PII in committed files.** Viewer emails are staff PII. The validation
  tool takes them as arguments or from a gitignored local file; never hardcode
  them, and never put them in a commit message, PR body, or issue comment.
- **Pure logic goes in `access.js`, impure wiring in `cube.js`** — the existing
  split in this directory. `access.js` is unit-tested; `cube.js` owns BigQuery
  reads, caching, and the hooks.
- **All Python via `uv run`.** Never bare `python`.
- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation`.
  Use `git -C <worktree>` on every git call and run `npm`/`uv` with that
  directory as cwd.

---

## Current State

Phase 0 of the spec is **complete and committed** on this branch — do not redo
it:

| Commit                                | Delivered                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------- |
| `ad3af5448`, `c89e8d68a`, `8a76c9013` | the design spec, plus the `maxAge` and Cube Cloud injected-context findings           |
| `af7d10303`                           | the `resolveAccess` ADC fallback in `src/cube/cube.js`                                |
| `b907c5f33`                           | `docs/guides/cube.md` local-validation walkthrough + `src/cube/CLAUDE.md` corrections |

Established facts this plan builds on (all verified in the 2026-07-23 session —
do **not** re-derive):

- `checkAuth` **does** run in Cube developer mode. The local REST Playground
  resolves a pasted `{"email": ...}`.
- Cube Cloud **bypasses `checkAuth`** and injects its own unenriched context:
  `{ email: <target>, cubeCloud: { username: <caller>, roles: [...] }, iss: "cubecloud", exp: <ts> }`
  — with **no `iat`**. `contextToGroups` finds no top-level `groups`, returns
  `[]`, and every gated view default-denies (`WHERE (1 = 0)`, views hidden).
- The local SQL API resolves per-connection identity correctly across the whole
  viewer matrix (network / region / school / none / unresolved).
- `src/cube/cube.test.js` already exists and already covers `maxAge`,
  forged-claim rejection, `checkSqlAuth`, and `resolveAccess` fail-closed. It
  stubs identity with `CUBE_GROUP_MAP` so tests never touch BigQuery.

---

## File Structure

| File                                                                       | Responsibility                                   | Change                                                                                                                     |
| -------------------------------------------------------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| `src/cube/access.js`                                                       | pure access + emulation logic (no I/O)           | add the impersonator parse/check, the shared `resolveEmulationTarget`, and the two surface adapters                        |
| `src/cube/access.test.js`                                                  | unit tests for the pure logic                    | add emulation cases, including the critical negative case                                                                  |
| `src/cube/cube.js`                                                         | auth hooks, BigQuery identity reads, caching     | wire `act_as` into `checkAuth`; add the audit log helper; (conditionally) enrich Cube Cloud's context in `contextToGroups` |
| `src/cube/cube.test.js`                                                    | hook-level tests via the `CUBE_GROUP_MAP` stub   | add emulation hook cases; extend `test.beforeEach` to reset `CUBE_IMPERSONATORS`                                           |
| `scripts/cube_rls_matrix.py`                                               | committed per-viewer RLS matrix over the SQL API | create (promotes the local scratch tool; PII stays out)                                                                    |
| `src/cube/CLAUDE.md`                                                       | Cube domain conventions for future work          | document the emulation path and the impersonator source                                                                    |
| `docs/guides/cube.md`                                                      | human-facing walkthrough                         | document how to emulate, and the matrix tool                                                                               |
| `docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md` | the design record                                | record the spike answers against the Open Questions                                                                        |

---

## Task 1: Pure emulation decision logic

The whole security model of this feature lives in this task. It has no I/O, so
it is fully unit-testable and both surfaces reduce to calling it.

**Files:**

- Modify: `src/cube/access.js` (append before `module.exports` at line 197, and
  extend that export block)
- Test: `src/cube/access.test.js`

**Interfaces:**

- Consumes: nothing from other tasks.
- Produces, all exported from `access.js`:
  - `parseImpersonators(raw: string | undefined) -> Set<string>` — lowercased,
    trimmed, empties dropped.
  - `isImpersonator(email: string | null, impersonators: Set<string>) -> boolean`
  - `resolveEmulationTarget({ callerEmail, requestedTarget, impersonators }) -> { caller: string | null, target: string | null, emulating: boolean }`
  - `emulationInputsFromToken(payload) -> { callerEmail, requestedTarget }`
  - `emulationInputsFromCubeCloud(securityContext) -> { callerEmail, requestedTarget }`

- [ ] **Step 1: Write the failing tests**

Append to `src/cube/access.test.js`:

```javascript
// --- Internal user emulation (#4526) ---------------------------------------

test("parseImpersonators: trims, lowercases, and drops empty entries", () => {
  const set = a.parseImpersonators(" Admin@Apps.Teamschools.Org , ,b@x.org ");
  assert.deepEqual([...set].sort(), ["admin@apps.teamschools.org", "b@x.org"]);
});

test("parseImpersonators: an unset variable yields an empty set", () => {
  assert.equal(a.parseImpersonators(undefined).size, 0);
  assert.equal(a.parseImpersonators("").size, 0);
});

test("isImpersonator: membership is case-insensitive; absent email is false", () => {
  const set = a.parseImpersonators("admin@x.org");
  assert.equal(a.isImpersonator("ADMIN@x.org", set), true);
  assert.equal(a.isImpersonator("someone@x.org", set), false);
  assert.equal(a.isImpersonator(null, set), false);
});

test("resolveEmulationTarget: an impersonator resolves the requested target", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: "teacher@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, {
    caller: "admin@x.org",
    target: "teacher@x.org",
    emulating: true,
  });
});

test("resolveEmulationTarget: the returned emails keep their original case", () => {
  // resolveAccess queries `WHERE google_email = @email` and keys its cache on
  // the raw string, so lowercasing here would change resolution for every
  // request and fail-close any non-lowercase google_email. Membership matching
  // is case-insensitive; the value passed downstream is not rewritten.
  const r = a.resolveEmulationTarget({
    callerEmail: "Admin@X.org",
    requestedTarget: "Teacher@X.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.caller, "Admin@X.org");
  assert.equal(r.target, "Teacher@X.org");
  assert.equal(r.emulating, true);
});

test("resolveEmulationTarget: a non-emulated caller is passed through unchanged", () => {
  // The regression guard for every ordinary request: the email reaching
  // resolveAccess must be byte-identical to the one in the token.
  const r = a.resolveEmulationTarget({
    callerEmail: "MixedCase@Apps.Teamschools.Org",
    requestedTarget: null,
    impersonators: a.parseImpersonators(""),
  });
  assert.equal(r.target, "MixedCase@Apps.Teamschools.Org");
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: a NON-impersonator gets their OWN scope, not the target", () => {
  // The critical negative case: supplying a target must never elevate.
  const r = a.resolveEmulationTarget({
    callerEmail: "teacher@x.org",
    requestedTarget: "superintendent@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.target, "teacher@x.org");
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: no requested target is not an emulation", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: null,
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, {
    caller: "admin@x.org",
    target: "admin@x.org",
    emulating: false,
  });
});

test("resolveEmulationTarget: targeting yourself is not an emulation", () => {
  // Keeps the audit log free of no-op self-emulation lines.
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: "ADMIN@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: an absent caller can never emulate", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: null,
    requestedTarget: "superintendent@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, { caller: null, target: null, emulating: false });
});

test("emulationInputsFromToken: caller is `email`, target is `act_as`", () => {
  assert.deepEqual(
    a.emulationInputsFromToken({ email: "admin@x.org", act_as: "t@x.org" }),
    { callerEmail: "admin@x.org", requestedTarget: "t@x.org" },
  );
  assert.deepEqual(a.emulationInputsFromToken(undefined), {
    callerEmail: null,
    requestedTarget: null,
  });
});

test("emulationInputsFromCubeCloud: caller is cubeCloud.username, target is email", () => {
  assert.deepEqual(
    a.emulationInputsFromCubeCloud({
      email: "teacher@x.org",
      cubeCloud: { username: "admin@x.org" },
      iss: "cubecloud",
    }),
    { callerEmail: "admin@x.org", requestedTarget: "teacher@x.org" },
  );
});

test("emulationInputsFromCubeCloud: with no pasted context the console user is the target", () => {
  // Cube Cloud with nothing typed into Security Context: the caller resolves as
  // themselves, which is what fixes plain (non-emulated) Explore.
  const inputs = a.emulationInputsFromCubeCloud({
    cubeCloud: { username: "admin@x.org" },
    iss: "cubecloud",
  });
  const r = a.resolveEmulationTarget({
    ...inputs,
    impersonators: a.parseImpersonators(""),
  });
  assert.equal(r.target, "admin@x.org");
  assert.equal(r.emulating, false);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: FAIL — `a.parseImpersonators is not a function` (and the same for the
other four new names).

- [ ] **Step 3: Write the implementation**

Insert into `src/cube/access.js` immediately before `module.exports` (line 197):

```javascript
// --- Internal user emulation (#4526) ---------------------------------------
// Admin-gated emulation lets a data-team caller resolve another internal user's
// real context for RLS validation. All of the security reasoning lives in
// resolveEmulationTarget below; the surface adapters are dumb field maps.

// Who may emulate. v1 source is the CUBE_IMPERSONATORS deployment variable
// (comma-separated emails). A warehouse-column source
// (dim_staff_cube_access.is_cube_impersonator) can replace THIS FUNCTION ONLY,
// later, without touching the resolver or either adapter.
function parseImpersonators(raw) {
  return new Set(
    String(raw ?? "")
      .split(",")
      .map((entry) => entry.trim().toLowerCase())
      .filter(Boolean),
  );
}

function isImpersonator(email, impersonators) {
  if (!email) return false;
  return impersonators.has(String(email).toLowerCase());
}

// The single decision point shared by both emulation surfaces. Returns the
// caller, the email whose context must actually be resolved, and whether that
// is an emulation (for the audit line).
//
// The decision reads ONLY the caller's own identity, so a non-impersonator who
// supplies a target — in an `act_as` claim they signed, or a spoofed cubeCloud
// block — gets their OWN scope, never the target's. Fail-closed: no caller
// means no emulation and a null target, which resolveAccess turns into the
// empty default-deny context.
//
// CASE IS PRESERVED on the returned emails, deliberately. Comparisons here are
// case-insensitive, but `target` is handed to resolveAccess, which queries
// `WHERE google_email = @email` and keys its cache on the raw string. Returning
// a lowercased email would change resolution for EVERY request (not just
// emulated ones), silently fail-closing any staff row whose google_email is not
// already lowercase, and desyncing this path from checkSqlAuth, which passes
// the connecting user through verbatim.
function resolveEmulationTarget({
  callerEmail,
  requestedTarget,
  impersonators,
}) {
  const caller = callerEmail ?? null;
  const requested = requestedTarget ?? null;
  // No target, or the caller's own email: an ordinary request, not an emulation
  // (also keeps no-op self-emulation out of the audit log).
  const isSelf =
    caller && requested && requested.toLowerCase() === caller.toLowerCase();
  if (!requested || isSelf) return { caller, target: caller, emulating: false };
  if (!isImpersonator(caller, impersonators))
    return { caller, target: caller, emulating: false };
  return { caller, target: requested, emulating: true };
}

// Surface adapter — REST/MCP. The signed JWT carries the caller in `email` and
// an optional emulation target in `act_as`.
function emulationInputsFromToken(payload) {
  return {
    callerEmail: payload?.email ?? null,
    requestedTarget: payload?.act_as ?? null,
  };
}

// Surface adapter — Cube Cloud. Cube Cloud injects its own context: the console
// user in `cubeCloud.username`, and the emulation target as a top-level `email`
// when a Security Context is pasted. With nothing pasted there is no top-level
// email, so the console user resolves as themselves.
function emulationInputsFromCubeCloud(securityContext) {
  return {
    callerEmail: securityContext?.cubeCloud?.username ?? null,
    requestedTarget: securityContext?.email ?? null,
  };
}
```

Then extend the export block so it reads:

```javascript
module.exports = {
  buildGroups,
  buildSecurityContext,
  computeAllowedAbbreviations,
  computeAllowedDepartmentGroups,
  emulationInputsFromCubeCloud,
  emulationInputsFromToken,
  isImpersonator,
  parseImpersonators,
  resolveEmulationTarget,
  STAFF_SENSITIVE_MEMBERS,
  STAFF_SENSITIVE_SCOPE_BY_MEMBER,
};
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: PASS — all new tests plus every pre-existing `access.test.js` and
`cube.test.js` test.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/access.js src/cube/access.test.js </dev/null
```

Expected: `No issues`. `--force` is required or committed files are skipped.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git add src/cube/access.js src/cube/access.test.js
git commit -m "feat(cube): add admin-gated emulation target resolution

Pure, unit-tested decision logic shared by both emulation surfaces. The
target is chosen from the caller's own identity only, so a non-impersonator
supplying a target keeps their own scope.

Refs #4526"
```

---

## Task 2: Wire `act_as` into `checkAuth` (REST / MCP surface)

**Files:**

- Modify: `src/cube/cube.js:208-245` (`checkAuth`), plus a new module-level
  `logEmulation` helper above `module.exports` (line 200)
- Test: `src/cube/cube.test.js`

**Interfaces:**

- Consumes: `access.resolveEmulationTarget`, `access.emulationInputsFromToken`,
  `access.parseImpersonators` from Task 1.
- Produces:
  `logEmulation(surface: string, caller: string, target: string) -> void` —
  module-local in `cube.js`, reused by Task 6.

- [ ] **Step 1: Write the failing tests**

First extend the existing `test.beforeEach` in `src/cube/cube.test.js` (line 17)
so the new variable cannot leak between tests — add one line:

```javascript
test.beforeEach(() => {
  process.env.CUBEJS_API_SECRET = SECRET;
  delete process.env.CUBE_GROUP_MAP;
  delete process.env.NODE_ENV; // dev bypass in resolveAccess requires !== "production"
  delete process.env.CUBEJS_SQL_PASSWORD;
  delete process.env.CUBE_IMPERSONATORS;
});
```

Then append the new tests. Each uses a unique email because `resolveAccess`
caches per email at module scope:

```javascript
// --- Admin-gated emulation, REST surface (#4526) ----------------------------

test("checkAuth: an impersonator's act_as resolves the TARGET's context", async () => {
  process.env.CUBE_IMPERSONATORS = "admin1@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "admin1@apps.teamschools.org": ["staff-directory"],
    "target1@apps.teamschools.org": ["student-network", "staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin1@apps.teamschools.org",
    act_as: "target1@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, [
    "student-network",
    "staff-directory",
  ]);
});

test("checkAuth: a NON-impersonator's act_as is ignored — own scope, not the target's", async () => {
  // The critical negative case. Note act_as is attacker-controlled here: the
  // caller signed their own valid token and asked for a broader identity.
  process.env.CUBE_IMPERSONATORS = "admin2@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "teacher2@apps.teamschools.org": ["staff-directory"],
    "target2@apps.teamschools.org": [
      "student-network",
      "staff-pii-all_in_scope",
    ],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "teacher2@apps.teamschools.org",
    act_as: "target2@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
  assert.ok(!req.securityContext.groups.includes("staff-pii-all_in_scope"));
});

test("checkAuth: an impersonator with no act_as resolves their own context", async () => {
  process.env.CUBE_IMPERSONATORS = "admin3@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "admin3@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin3@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
});

test("checkAuth: act_as for an unresolvable target fails closed to default-deny", async () => {
  process.env.CUBE_IMPERSONATORS = "admin4@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "admin4@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin4@apps.teamschools.org",
    act_as: "nobody4@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  // Emulating a non-existent viewer must NOT fall back to the caller's scope.
  assert.deepEqual(req.securityContext.groups, []);
});

test("checkAuth: the impersonator list tolerates spacing and case", async () => {
  process.env.CUBE_IMPERSONATORS =
    " ADMIN5@Apps.Teamschools.Org , other@x.org ";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "admin5@apps.teamschools.org": ["staff-directory"],
    "target5@apps.teamschools.org": ["student-network"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin5@apps.teamschools.org",
    act_as: "target5@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["student-network"]);
});

test("checkAuth: with no impersonators configured, act_as is inert", async () => {
  // The production default until the variable is set: emulation is off.
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "caller6@apps.teamschools.org": ["staff-directory"],
    "target6@apps.teamschools.org": ["student-network"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "caller6@apps.teamschools.org",
    act_as: "target6@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: the impersonator tests FAIL (the resolved groups are the caller's,
because `act_as` is not read yet). The negative-case tests (`NON-impersonator`,
`no impersonators configured`) already PASS — that is correct and expected; they
are regression guards, and they must still pass after Step 3.

- [ ] **Step 3: Write the implementation**

Add the audit helper to `src/cube/cube.js`, immediately before `module.exports`
(line 200):

```javascript
// Emulation moves PII visibility, so every emulated request leaves a trail in
// the deployment logs. Identities and a timestamp only — never row data.
function logEmulation(surface, caller, target) {
  console.log(
    JSON.stringify({
      event: "cube_emulation",
      surface,
      caller,
      target,
      at: new Date().toISOString(),
    }),
  );
}
```

Then replace the body of `checkAuth` from `let email;` (line 218) through
`req.securityContext = await resolveAccess(email);` (line 244) with:

```javascript
let payload;
if (auth) {
  try {
    // maxAge is a defense-in-depth cap independent of the token's own
    // `exp`: it derives from `iat` (issued-at) instead, so a compromised
    // or misconfigured minter can't extend a token's life by inflating
    // `exp` alone — jsonwebtoken rejects any token missing `iat` once
    // maxAge is set (fails closed). `mcp/server.py`'s `_mint_token` sets
    // both `iat` and a 5-minute `exp`, so this 12h ceiling is a backstop,
    // not the primary control.
    payload = jwt.verify(auth, process.env.CUBEJS_API_SECRET, {
      algorithms: ["HS256"],
      maxAge: "12h",
      // Absorb minor minter/server clock skew so a short-lived (5-min) token
      // isn't spuriously 403'd near its edges. Small relative to the token
      // life, and it fails closed — an expired token past the tolerance is
      // still rejected.
      clockTolerance: 30,
    });
  } catch (err) {
    // Mirror Cube's default checkAuth: a bad/expired token is a clean 403,
    // not a bare-Error 500 (only CubejsHandlerError carries a status).
    throw new CubejsHandlerError(403, "Forbidden", "Invalid token", err);
  }
}
// Admin-gated emulation (#4526): an approved impersonator may pass an
// `act_as` claim and get that target's real HR-derived context. For anyone
// else `act_as` is ignored and they keep their own scope. The gate reads the
// SIGNED `email` claim, so it is unforgeable. A future API-key branch
// (#4501) slots in beside this one — it resolves a different context source,
// not a different emulation rule.
const { caller, target, emulating } = access.resolveEmulationTarget({
  ...access.emulationInputsFromToken(payload),
  impersonators: access.parseImpersonators(process.env.CUBE_IMPERSONATORS),
});
if (emulating) logEmulation("rest", caller, target);
req.securityContext = await resolveAccess(target);
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: PASS, all tests. Confirm specifically that the pre-existing
`checkAuth: forged groups/securityContext claims are ignored (only email is trusted)`
test still passes — `act_as` is now honored for impersonators, but forged
`groups` / `securityContext` claims must remain ignored for everyone.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/cube.js src/cube/cube.test.js </dev/null
```

Expected: `No issues`.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git add src/cube/cube.js src/cube/cube.test.js
git commit -m "feat(cube): honor act_as for approved impersonators in checkAuth

An approved caller may pass an act_as claim and resolve that target's real
context; everyone else keeps their own scope. Emulated requests emit a
structured audit line carrying identities only.

Refs #4526"
```

---

## Task 3: Commit the per-viewer RLS matrix as a real tool

The scratch prototype is the ground-truth pre-pilot validation tool, but it
embeds real viewer emails. The committed version must take them as input.

**Files:**

- Create: `scripts/cube_rls_matrix.py`
- Modify: `docs/guides/cube.md` (the `## Testing row-level security locally`
  section — replace the inline region-isolation `psycopg2` heredoc with a
  pointer to the tool)

**Interfaces:**

- Consumes: nothing from other tasks. It exercises the shipped `checkSqlAuth`
  path.
- Produces: a CLI invoked as
  `uv run scripts/cube_rls_matrix.py --viewers a@x.org b@x.org`; exit code 0 on
  success, 1 if any connection or query fails.

- [ ] **Step 1: Create the tool**

`psycopg` **3** is already a project dependency (`pyproject.toml:27`), so prefer
it over adding `psycopg2`. But **verify it actually works against Cube's SQL API
before building on it**: the scratch prototype was proven with `psycopg2`, and
psycopg 3 uses the extended query protocol and auto-prepares repeated
statements, while Cube's SQL API is only a partial Postgres implementation.

Smoke-test the connection first, with one viewer:

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
uv run python -c "
import psycopg
with psycopg.connect(host='127.0.0.1', port=15432, user='you@apps.teamschools.org',
                     password='<local sql password>', dbname='cube') as c, c.cursor() as cur:
    cur.execute('SELECT MEASURE(count_employees) FROM staff_directory')
    print(cur.fetchall())
"
```

If that errors on the protocol rather than on auth or SQL, fall back to the
proven path — `import psycopg2` plus
`uv run --with psycopg2-binary scripts/cube_rls_matrix.py` — and say so in the
module docstring so the next person does not "upgrade" it back. Do not spend
time debugging psycopg 3 against a partial Postgres implementation; the tool's
job is validating RLS, not exercising a driver.

```python
"""Validate Cube row-level security by emulating each viewer over the SQL API.

Ground-truth pre-pilot check. Cube's `checkSqlAuth` resolves identity from the
connecting SQL user, so one connection per viewer email runs the SAME query
under a different security context — any difference in the result is
attributable to access policy alone.

Viewer emails are staff PII: pass them as arguments or in a local file (e.g.
under `.claude/scratch/`, which is gitignored). Never commit a viewer list.

Requires the local Cube dev server with the SQL API enabled
(`CUBEJS_PG_SQL_PORT`, `CUBEJS_SQL_USER`, `CUBEJS_SQL_PASSWORD`); see
`docs/guides/cube.md`.

Usage:
    uv run scripts/cube_rls_matrix.py --viewers a@x.org b@x.org
    uv run scripts/cube_rls_matrix.py --viewers-file .claude/scratch/viewers.txt
    uv run scripts/cube_rls_matrix.py --viewers a@x.org --query "SELECT ..."
"""

import argparse
import os
import sys
from pathlib import Path

import psycopg

# Region breakdown of student attendance: additive year-round (unlike
# student_enrollments.count_students, which anchors to is_current_record and
# reads 0 off-season), so a scope difference is visible any time of year.
DEFAULT_QUERY = (
    "SELECT regions_region_name, MEASURE(count_students) "
    "FROM student_attendance_view GROUP BY 1 ORDER BY 1"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--viewers", nargs="+", help="viewer emails to emulate, space-separated"
    )
    source.add_argument(
        "--viewers-file",
        type=Path,
        help="file with one viewer email per line (blank lines and # ignored)",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="SQL to run per viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=15432)
    parser.add_argument("--dbname", default="cube")
    parser.add_argument(
        "--password",
        default=os.environ.get("CUBEJS_SQL_PASSWORD"),
        help="local Cube SQL API password (defaults to the CUBEJS_SQL_PASSWORD value)",
    )
    return parser.parse_args()


def load_viewers(args: argparse.Namespace) -> list[str]:
    if args.viewers:
        return args.viewers
    lines = args.viewers_file.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def run_for_viewer(
    viewer: str, args: argparse.Namespace
) -> tuple[list[tuple], str | None]:
    """Return (rows, error). Identity is the connecting user, so one connection
    per viewer is what switches the security context."""
    try:
        with psycopg.connect(
            host=args.host,
            port=args.port,
            user=viewer,
            password=args.password,
            dbname=args.dbname,
        ) as conn, conn.cursor() as cur:
            cur.execute(args.query)
            return cur.fetchall(), None
    except Exception as err:  # noqa: BLE001 - report and continue the matrix
        return [], str(err)


def main() -> int:
    args = parse_args()
    if not args.password:
        print(
            "No SQL password given: pass --password or set the CUBEJS_SQL_PASSWORD"
            " value in your shell.",
            file=sys.stderr,
        )
        return 1

    viewers = load_viewers(args)
    if not viewers:
        print("No viewer emails to test.", file=sys.stderr)
        return 1

    failures = 0
    for viewer in viewers:
        rows, error = run_for_viewer(viewer, args)
        if error:
            failures += 1
            print(f"{viewer}: CONNECTION/QUERY FAILED - {error}")
            continue
        if not rows:
            print(f"{viewer}: 0 rows (default-deny or no scope)")
            continue
        print(f"{viewer}: {len(rows)} group(s)")
        for row in rows:
            print(f"    {row}")

    print(f"\n{len(viewers)} viewer(s) checked, {failures} failed.")
    print(
        "Interpret: a uniform 0 rows across EVERY viewer (including a"
        " network-scoped one) means the identity read failed, not that policies"
        " denied - check the dev-server log for 'resolveAccess failed for'."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against a real viewer matrix**

Requires the **Cube: Dev Server** VS Code task running with the SQL API enabled.
Write a local, gitignored viewer list first (one email per line) — include a
network-scoped, a region-scoped, a school-scoped, a `none`-scope, and a
deliberately unresolvable viewer:

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
uv run scripts/cube_rls_matrix.py --viewers-file /workspaces/teamster/.claude/scratch/viewers.txt
```

Expected: the network viewer returns all four regions; the region viewer only
its own; the school viewer a subset of that region; the `none` and unresolvable
viewers 0 rows. **Do not paste this output into a commit, PR, or issue** — it
contains viewer emails. Record the verdict as "matrix passed, 5 viewers" only.

- [ ] **Step 3: Point the guide at the tool**

In `docs/guides/cube.md`, in the `## Testing row-level security locally`
section, replace the inline region-isolation heredoc (the second `psycopg2`
example, the one looping over three viewer emails) with:

````markdown
For the full viewer matrix, use the committed tool rather than an ad-hoc script
— it takes the viewer list as input so no PII lands in the repo:

```bash
uv run scripts/cube_rls_matrix.py --viewers-file .claude/scratch/viewers.txt
```

Expect a network viewer to return all four regions, a region-scoped viewer only
their own region, and a `none`-scope or unresolvable viewer no rows at all. A
uniform zero across _every_ viewer means the identity read failed rather than
the policies denying.
````

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix scripts/cube_rls_matrix.py docs/guides/cube.md </dev/null
```

Expected: `No issues`. If ruff flags the broad `except Exception`, keep the
behavior (one bad viewer must not abort the matrix) and suppress with
`# trunk-ignore(ruff/BLE001): report per-viewer failure and continue` on the
line immediately above.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git add scripts/cube_rls_matrix.py docs/guides/cube.md
git commit -m "feat(cube): commit the per-viewer RLS matrix as a real tool

Promotes the local scratch prototype. Viewer emails are supplied as arguments
or a local file, so no PII enters the repo.

Refs #4526"
```

---

## Task 4: Push the branch and stand it up in Cube Cloud

Every remaining task needs a live Cube Cloud deployment of this branch — the
spike, the enrichment, and the emulation validation. Cube Cloud can only reach a
branch that exists on the remote, and **branch environments do not create
themselves on push**, so this is a real prerequisite rather than a formality.

**Files:**

- No file changes. This is a push plus Cube Cloud console configuration.

**Interfaces:**

- Consumes: the committed work from Tasks 1-3.
- Produces: a live per-branch Cube Cloud environment with `CUBE_IMPERSONATORS`
  set, reachable at two endpoints:
  - **Dev Mode** — `/user/<urlencoded-email>/<id>/cubejs-api/v1`. The only
    surface that shows server `console.log`, so this is where `cube.js` code
    paths and the `cube_emulation` audit line get observed.
  - **Branch staging** — `/staging/<branch>/cubejs-api/v1`. Stable, redeploys on
    push.

- [ ] **Step 1: Push the branch**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git push -u origin cristinabaldor/feat/claude-cube-internal-emulation
```

Do **not** open the PR yet — that is Task 9. A push with no PR does not start
`claude-review` (it only fires on PR `opened` / `ready_for_review`), and this
branch changes no dbt models, so dbt Cloud CI has nothing to build either way.

- [ ] **Step 2: Add the branch in Cube Cloud**

Cube Cloud → Data Model → Dev Mode → add the branch **by name**. Adding it here
is what spins up the per-branch staging environment; a push alone does not.

- [ ] **Step 3: Verify the branch environment's configuration**

Branch environments do **not** fully inherit production configuration. Confirm
on the branch environment:

1. `CUBEJS_DB_TYPE`, `CUBEJS_DB_BQ_PROJECT_ID`, and `CUBEJS_DB_BQ_CREDENTIALS`
   are set. Without them every identity read fails and `resolveAccess`
   fail-closes to deny-all for **every** viewer — indistinguishable from an
   access-policy bug, and the single most likely way to waste an hour here.
1. `CUBE_IMPERSONATORS` is set to your own email. Emulation is inert until it
   is. That is the correct production default, but it also means "nothing
   happened" is the _expected_ result if this step is skipped.
1. `CUBE_GROUP_MAP` is **absent**. It is a dev bypass that supplies groups only,
   and it would mask real resolution.

- [ ] **Step 4: Confirm the model is live, as yourself**

Do this over REST, not the Cube Cloud Playground: the Playground is the broken
surface, so an empty view list there is ambiguous — it means either "model did
not deploy" or "every view is access-hidden," and you cannot tell which. REST
runs through `checkAuth`, which works.

Mint a token with the **branch environment's** `CUBEJS_API_SECRET` (from its API
Credentials panel — not necessarily production's) and call the branch endpoint.
The `Authorization` header takes the raw token with **no `Bearer` prefix**:

```bash
tok=$(node -e "const j=require('jsonwebtoken');console.log(j.sign({email:'you@apps.teamschools.org'},process.env.CUBEJS_API_SECRET,{algorithm:'HS256'}))")
curl -s -H "Authorization: $tok" -H 'Content-Type: application/json' \
  -X POST --data '{"query":{"measures":["staff_directory.count_employees"]}}' \
  https://<deployment>.cubecloud.dev/staging/<branch>/cubejs-api/v1/load
```

Expected: a real count. If instead every view is missing, compile the same query
through `/sql` — it compiles against `public: false` members and ignores access
hiding, so a successful compile proves the model deployed and points at access
rather than the deployment.

---

## Task 5: Cube Cloud spike and cloud emulation validation (requires console access)

Two jobs on the live branch deployment: prove the Task 1-2 emulation path
actually works in the cloud on the surface that already routes through our
hooks, and answer the open questions that decide whether Task 6 is a code change
or a configuration change. **Claude cannot reach the Cube Cloud console or mint
against the branch secret; this task is run by the user.**

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md`
  (record answers under `## Open questions / verification items`)

**Interfaces:**

- Consumes: the live branch environment from Task 4; the `act_as` path from
  Task 2.
- Produces: (a) confirmation that emulation works end-to-end on a real
  deployment, and (b) a decision — **Variant A** (enrich in `contextToGroups`)
  or **Variant B** (Cloud Auth Integration routes Cube Cloud through
  `checkAuth`) — which selects the branch of Task 6.

- [ ] **Step 1: Validate emulation on the branch deployment over REST**

This is the real proof that Tasks 1-2 work, and it does not depend on the Cube
Cloud console problem at all — REST goes through `checkAuth`, which Cube Cloud's
Explore bypasses. Mint two tokens against the branch environment's
`CUBEJS_API_SECRET` and compare.

First, as yourself with an `act_as` for a **region-scoped** viewer:

```bash
tok=$(node -e "const j=require('jsonwebtoken');console.log(j.sign({email:'you@apps.teamschools.org',act_as:'a-region-scoped-viewer@apps.teamschools.org'},process.env.CUBEJS_API_SECRET,{algorithm:'HS256'}))")
curl -s -H "Authorization: $tok" -H 'Content-Type: application/json' \
  -X POST --data '{"query":{
    "measures":["student_attendance_view.count_students"],
    "dimensions":["student_attendance_view.regions_region_name"]
  }}' \
  https://<deployment>.cubecloud.dev/staging/<branch>/cubejs-api/v1/load
```

Expected: **only that viewer's region** comes back, not all four — even though
you are network-scoped. That is emulation working: your own scope would have
returned every region.

Then run the same request with `CUBE_IMPERSONATORS` **removed** from the branch
environment (redeploy takes a moment). Expected: all four regions — `act_as`
ignored, your own scope applied. Restore the variable afterward.

Finally, have a **non-impersonator** colleague mint a token with an `act_as` for
someone broader, or simulate it by setting `CUBE_IMPERSONATORS` to an unrelated
email while keeping your own `act_as` request. Expected: your own scope, never
the target's. This is the negative case the unit tests assert; confirming it
once against a real deployment is worth the five minutes.

Cross-check the Dev Mode logs panel for exactly one `cube_emulation` line per
emulated request, carrying only the two identities and a timestamp — no row
data.

- [ ] **Step 2: Experiment 1 — does Cloud Auth Integration route through our
      hooks?**

On the branch staging deployment (not production):

1. Cube Cloud → Settings → Configuration → enable **Cloud Auth Integration**.
1. Open Explore as yourself, with **nothing** pasted into Security Context, and
   query `staff_directory`.
1. Check the Dev Mode logs panel (only Dev Mode surfaces server `console.log`;
   staging has no log UI).

Expected if it routes through `checkAuth`: gated views become visible and a
`resolveAccess` log line appears for your email → **Variant B**, and Task 2
already covers Cube Cloud. Expected if not: views stay hidden → **Variant A**.

- [ ] **Step 3: Experiment 2 — can `contextToGroups` mutate the
      securityContext?**

Only needed if Experiment 1 (Step 2) says Variant A. In Dev Mode, temporarily
add to `contextToGroups` in `src/cube/cube.js` (uncommitted scaffold):

```javascript
  contextToGroups: async ({ securityContext }) => {
    console.log("SPIKE injected context:", JSON.stringify(securityContext));
    if (securityContext?.iss === "cubecloud") {
      securityContext.region_key = "SPIKE-REGION";
      securityContext.groups = ["student-region"];
    }
    return securityContext?.groups ?? [];
  },
```

Then query `student_enrollments_view` and read the compiled SQL via `/sql`.

Expected if mutation propagates: the compiled SQL contains
`region_key = 'SPIKE-REGION'` (not `WHERE (1 = 0)`), proving the `row_level`
filters read the mutated object → Variant A is implementable in
`contextToGroups`. If it still compiles to `WHERE (1 = 0)` while `console.log`
shows the mutation happened, `contextToGroups` cannot mutate — **stop and
re-brainstorm the cloud seam**; do not proceed to Task 6.

- [ ] **Step 4: Answer the two remaining console questions**

1. What SQL `user` does Cube Cloud **Explore** connect as, and does `__user`
   impersonation work for `CUBEJS_SQL_SUPER_USER`? (Needed by Task 7; do **not**
   change `canSwitchSqlUser` either way.)
1. Is Cube Cloud console access already restricted to the intended admin set? If
   yes, console access is itself part of the gate and `CUBE_IMPERSONATORS` is
   defense-in-depth rather than the sole control.

- [ ] **Step 5: Record the answers and revert the scaffold**

Replace each answered bullet under `## Open questions / verification items` in
the spec with the finding. Then confirm the spike scaffold is gone:

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git diff --stat && grep -n SPIKE src/cube/cube.js
```

Expected: no `SPIKE` matches, and `git diff` shows only the spec file.

- [ ] **Step 6: Commit and push**

Record the Step 1 emulation-validation result here too — it is the first
end-to-end proof the feature works, and the PR body should cite it.

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git add docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md
git commit -m "docs(cube): record Cube Cloud emulation spike answers

Refs #4526"
git push
```

Pushing redeploys the branch environment, so the next task starts against
current code.

---

## Task 6: Cube Cloud enrichment

> **OUTCOME (2026-07-29): shipped, and neither variant as written.** Kept below
> as the record of what was planned versus what 1.7.14 actually required.
>
> The spike answered Variant B in the negative: Cloud Auth Integration was
> enabled and Explore stayed dark, so it does not route through our hooks.
> Variant A was therefore the path, and Cube's own source confirmed it works
> before any code was written — `CompilerApi.getApplicablePolicies` passes the
> same `context` object to `contextToGroups` and then to `evaluateNestedFilter`,
> so mutation reaches `row_level` interpolation.
>
> Three things the plan did not anticipate:
>
> 1. **1.7.14 injects no top-level `email`** until a Security Context is pasted.
>    The context is
>    `{ cubeCloud: { username, groups, roles, userAttributes, meta, userCredentials }, iss, exp }`.
>    A pasted target is merged into the top level and mirrored at
>    `cubeCloud.userAttributes.email`, so the enrichment reads both.
> 2. **That merge was a live privilege-escalation vector, predating this
>    issue.** Because the old `contextToGroups` read
>    `securityContext?.groups ?? []` straight off the merged object, any console
>    user could paste `groups` and scope values and have them honored. Fixed by
>    always re-deriving and overwriting; a `!securityContext.groups` guard here
>    IS the bypass. Production was affected.
> 3. **Self-resolution matters more than emulation.** Enriching from
>    `cubeCloud.username` is what makes Explore work for real pilot users, needs
>    no admin gate, and carries no escalation surface. Emulation layered on top
>    after the target channel was known.
>
> Landed in `4d0f96ed4` (enrichment), `c2212537a` (paste fix plus emulation),
> with the observation probes in `c8a47b7df` / `87e96fbd6` and a first probe
> reverted in `e4d044719` after a security review correctly flagged it for
> privilege injection and PII in logs.

Implement **only the variant Task 5 selected.** Both variants reuse Task 1's
resolver, so the security rule is identical across surfaces.

**Files:**

- Variant A — Modify: `src/cube/cube.js:206` (`contextToGroups`); Test:
  `src/cube/cube.test.js`
- Variant B — Modify: `src/cube/CLAUDE.md` and `docs/guides/cube.md` only (no
  `cube.js` change); the deployment setting is applied in the Cube Cloud console

**Interfaces:**

- Consumes: `access.resolveEmulationTarget`,
  `access.emulationInputsFromCubeCloud`, `access.parseImpersonators` (Task 1);
  `logEmulation` (Task 2).
- Produces: an enriched `securityContext` on Cube Cloud carrying `groups` plus
  the `row_level` interpolation values (`region_key`, `allowed_abbreviations`,
  `allowed_department_groups`, `reportee_staff_keys`).

### Variant A — enrich in `contextToGroups`

- [ ] **Step A1: Write the failing tests**

Append to `src/cube/cube.test.js`:

```javascript
// --- Cube Cloud injected-context enrichment (#4526) -------------------------

test("contextToGroups: an impersonator's Cube Cloud context resolves the target", async () => {
  process.env.CUBE_IMPERSONATORS = "cloudadmin1@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudtarget1@apps.teamschools.org": ["student-region"],
  });
  const securityContext = {
    email: "cloudtarget1@apps.teamschools.org",
    cubeCloud: { username: "cloudadmin1@apps.teamschools.org" },
    iss: "cubecloud",
  };

  const groups = await cube.contextToGroups({ securityContext });

  assert.deepEqual(groups, ["student-region"]);
  // The policies read the context object, not the return value — enrichment
  // must land ON the object.
  assert.deepEqual(securityContext.groups, ["student-region"]);
  assert.ok("allowed_abbreviations" in securityContext);
});

test("contextToGroups: a NON-impersonator's Cube Cloud context resolves only themselves", async () => {
  process.env.CUBE_IMPERSONATORS = "cloudadmin2@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudviewer2@apps.teamschools.org": ["staff-directory"],
    "cloudtarget2@apps.teamschools.org": ["student-network"],
  });
  const securityContext = {
    email: "cloudtarget2@apps.teamschools.org",
    cubeCloud: { username: "cloudviewer2@apps.teamschools.org" },
    iss: "cubecloud",
  };

  const groups = await cube.contextToGroups({ securityContext });

  assert.deepEqual(groups, ["staff-directory"]);
});

test("contextToGroups: a Cube Cloud context with nothing pasted resolves the console user", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudself3@apps.teamschools.org": ["staff-directory"],
  });
  const securityContext = {
    cubeCloud: { username: "cloudself3@apps.teamschools.org" },
    iss: "cubecloud",
  };

  const groups = await cube.contextToGroups({ securityContext });

  assert.deepEqual(groups, ["staff-directory"]);
});

test("contextToGroups: an already-enriched context is passed through untouched", async () => {
  // The REST path enriches in checkAuth; contextToGroups must not re-resolve.
  const securityContext = { groups: ["student-network"], region_key: "R1" };
  const groups = await cube.contextToGroups({ securityContext });
  assert.deepEqual(groups, ["student-network"]);
  assert.equal(securityContext.region_key, "R1");
});

test("contextToGroups: a non-Cube-Cloud context with no groups stays default-deny", async () => {
  const securityContext = { email: "someone@apps.teamschools.org" };
  assert.deepEqual(await cube.contextToGroups({ securityContext }), []);
});
```

- [ ] **Step A2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: the Cube Cloud tests FAIL with `[]` returned (no enrichment yet). The
last two PASS already and are regression guards.

- [ ] **Step A3: Write the implementation**

Replace `contextToGroups` in `src/cube/cube.js` (line 206) with:

```javascript
  contextToGroups: async ({ securityContext }) => {
    // Cube Cloud bypasses checkAuth and injects its own UNENRICHED context
    // (iss: "cubecloud", the console user in cubeCloud.username, the pasted
    // emulation target as a top-level email, and no iat). resolveAccess never
    // runs on that path, so enrich here: same admin gate as the REST act_as
    // branch, then populate the fields the access_policy row_level filters
    // interpolate. Mutating the object is required — the policies read the
    // context, not this return value (verified by the Task 5 spike).
    if (securityContext?.iss === "cubecloud" && !securityContext.groups) {
      const { caller, target, emulating } = access.resolveEmulationTarget({
        ...access.emulationInputsFromCubeCloud(securityContext),
        impersonators: access.parseImpersonators(process.env.CUBE_IMPERSONATORS),
      });
      if (emulating) logEmulation("cubecloud", caller, target);
      Object.assign(securityContext, await resolveAccess(target));
    }
    return securityContext?.groups ?? [];
  },
```

- [ ] **Step A4: Run the tests to verify they pass**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation/src/cube && npm test
```

Expected: PASS, all tests including every pre-existing one.

- [ ] **Step A5: Verify in Cube Cloud Explore on the branch**

The branch environment is already standing with `CUBE_IMPERSONATORS` set (Task 4
Step 3) — push this commit so it redeploys, then in **Explore** paste
`{"email": "a-region-scoped-viewer@apps.teamschools.org"}` into Security Context
and query `student_enrollments_view`.

This is the surface Task 5 could not fix, so it is the one that proves the
enrichment worked. Expected: gated views are now **visible** at all (previously
you saw only source tables); results cover only that viewer's region; `/sql`
shows the region predicate rather than `WHERE (1 = 0)`; and the Dev Mode log
shows exactly one `cube_emulation` line.

Then repeat with `CUBE_IMPERSONATORS` **unset** on that environment and confirm
the pasted target is ignored — you resolve as yourself, and a viewer who is not
an approved impersonator cannot elevate through the console. Restore the
variable afterward.

- [ ] **Step A6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/cube.js src/cube/cube.test.js </dev/null
git add src/cube/cube.js src/cube/cube.test.js
git commit -m "feat(cube): enrich the Cube Cloud injected security context

Cube Cloud bypasses checkAuth and injects an unenriched context, so gated
views default-denied for every console user. Enrich it in contextToGroups
behind the same admin gate as the REST path.

Refs #4526"
```

### Variant B — Cloud Auth Integration

- [ ] **Step B1: Confirm the token reaches `checkAuth` with an `iat`**

A Cube Cloud-issued token carries **no `iat`**, and `checkAuth`'s
`maxAge: "12h"` rejects any token without one — so if Cloud Auth Integration
routes a `cubecloud`-issued token through `jwt.verify`, it will 403 and Task 8
becomes a hard blocker rather than an optional cleanup. Check the Dev Mode log
for the request outcome.

Expected: a `resolveAccess` line for your email (the token was accepted and
carries an `iat`) → proceed to Step B2. A 403 / `maxAge exceeded` → **stop**:
this needs the Task 8 decision plus code-owner sign-off first, because the only
fix is relaxing `maxAge` for a token whose `iss` is read _before_ verification,
which weakens the #4269 control.

- [ ] **Step B2: Document the configuration**

Add to `src/cube/CLAUDE.md`, in the `## Testing row-level security locally`
section, replacing the `**Cube Cloud emulation is not fixed yet (#4526).**`
bullet:

```markdown
- **Cube Cloud emulation goes through `checkAuth`** once **Cloud Auth
  Integration** is enabled (Settings → Configuration). With it off, Cube Cloud
  injects its own unenriched context (top-level `email`, `cubeCloud.username`,
  `iss: "cubecloud"`, no `iat`) and default-denies every gated view. With it on,
  the request reaches `checkAuth` and the admin-gated `act_as` path applies —
  emulation requires the caller's email in `CUBE_IMPERSONATORS`.
```

And update the `### 4. Test in Cube Cloud` section of `docs/guides/cube.md` to
replace the "row-level security cannot be validated there yet" paragraph with
the working instructions.

- [ ] **Step B3: Verify and commit**

Repeat the Step A5 staging verification (paste a target, confirm scoping, then
unset `CUBE_IMPERSONATORS` and confirm the paste is ignored), then:

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/CLAUDE.md docs/guides/cube.md </dev/null
git add src/cube/CLAUDE.md docs/guides/cube.md
git commit -m "docs(cube): document Cloud Auth Integration as the Cube Cloud emulation path

Refs #4526"
```

---

## Task 7: Validate and document both pilot surfaces

The pilot covers Cube Cloud Explore **and** a BI tool over the SQL API. SQL-API
scoping already works through the untouched `checkSqlAuth` + `canSwitchSqlUser`
/ `__user` mechanism; this task proves both end to end and writes down the
sign-off procedure.

**Files:**

- Modify: `docs/guides/cube.md` (a new `### Signing off a pilot user's scope`
  subsection under `## Testing row-level security locally`)
- Modify: `src/cube/CLAUDE.md` (the `## cube.js security model` section)

**Interfaces:**

- Consumes: `scripts/cube_rls_matrix.py` (Task 3); the working emulation path
  (Task 2 and Task 6).
- Produces: no code interface — a documented, repeatable procedure, plus the
  production configuration decision below.

- [ ] **Step 1: Decide whether to enable emulation in production — explicitly**

Every step up to here ran against the **branch** environment. Emulating a real
pilot user against real production data requires `CUBE_IMPERSONATORS` set on the
**production** deployment, and nothing earlier in this plan does that. Do not
treat it as a config detail that follows automatically from merging.

What enabling it means: the listed emails gain the ability to resolve any
internal user's full context on production, including student PII and the six
sensitive staff fields, for as long as they are listed. What it does not mean:
no new data leaves the network, no view or policy changes, and the ability is
unforgeable — a caller who is not listed keeps their own scope.

Bring it to the analytics-engineer code owners as its own decision, with the
list of emails and the reason (pre-pilot scope sign-off). Two live options:

- **Enable on production**, scoped to the smallest possible data-team list, and
  agree when it gets removed — after pilot sign-off, or on a fixed date.
- **Leave production off** and sign off scopes on the branch environment, which
  reads production `kipptaf_marts` anyway (so the identity data is real even
  though the deployment is not). Slower for the pilot, and it means the exact
  production surface is never itself exercised.

Record the decision and the agreed removal date in the PR before merge. If
production stays off, say so in the guide too, so the next person does not spend
an afternoon wondering why the documented procedure returns their own scope.

- [ ] **Step 2: Run the matrix against the real pilot viewer set**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
uv run scripts/cube_rls_matrix.py --viewers-file /workspaces/teamster/.claude/scratch/pilot-viewers.txt
```

Expected: every pilot user's returned scope matches their intended scope. Keep
the output local — record only "N viewers checked, all scopes as intended".

- [ ] **Step 3: Confirm the Explore surface for one pilot user**

Using the Task 6 path, emulate one pilot user in Cube Cloud Explore and confirm
the same scope the matrix reported for them, and that a member outside their
tier is absent rather than erroring.

- [ ] **Step 4: Document the sign-off procedure**

Add to `docs/guides/cube.md` under `## Testing row-level security locally`:

```markdown
### Signing off a pilot user's scope

Before granting a new internal user access, confirm what they will actually see
on the surface they will use:

1. Put their email in a local, gitignored viewer file and run
   `uv run scripts/cube_rls_matrix.py --viewers-file <file>`. This is ground
   truth — it exercises the same `checkSqlAuth` path a BI tool uses.
1. Compare the returned scope against their intended scope. A mismatch is an
   HR-data problem in `dim_staff_cube_access`, not a Cube problem — fix it
   upstream rather than in a policy.
1. If they will use Cube Cloud Explore, emulate them there too: your email must
   be in `CUBE_IMPERSONATORS`, then supply their email as the emulation target.
   Confirm the same scope appears.
1. Record the sign-off without the emails — viewer identities are staff PII.

A BI tool over the SQL API scopes per user through the existing SQL super-user
mechanism (`canSwitchSqlUser` plus `__user`); emulation does not change or
broaden it.
```

- [ ] **Step 5: Update the domain notes**

In `src/cube/CLAUDE.md`, `## cube.js security model`, add one bullet after the
`contextToGroups` bullet:

```markdown
- **Emulation (#4526)** is admin-gated and decided in
  `access.resolveEmulationTarget` from the CALLER's identity only — a
  non-impersonator supplying a target keeps their own scope. Impersonators come
  from the `CUBE_IMPERSONATORS` deployment variable via
  `access.parseImpersonators` (the only place that reads it; swap it for a
  `dim_staff_cube_access.is_cube_impersonator` column later). REST/MCP passes
  the target in an `act_as` claim; Cube Cloud supplies caller and target in its
  injected context. Every emulated request logs a `cube_emulation` line
  (identities only).
```

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/guides/cube.md src/cube/CLAUDE.md </dev/null
git add docs/guides/cube.md src/cube/CLAUDE.md
git commit -m "docs(cube): add the pilot-user scope sign-off procedure

Refs #4526"
```

---

## Task 8: The `maxAge` decision (code-owner gated, non-blocking)

> **OUTCOME (2026-07-29): resolved a third way — `c6796e7c8`.** `maxAge` stays
> at 12h, so #4269's property is intact. What changed is that the rejection is
> now legible: `jwtRejectionReason` distinguishes too-old-from-`iat` (with the
> re-mint step), expired-past-`exp`, a bad signature pointing at the
> deployment's `CUBEJS_API_SECRET`, and a missing `iat`. Same 403 status.
>
> The reframing came from hitting it for real: a branch environment with no
> `CUBEJS_API_SECRET` returned `403 "Invalid token"` for every token, identical
> to a stale one and to a wrong secret, and it cost an hour to diagnose. The
> trap was never the rejection — it was that one message covered every cause.
> Fixing the diagnostics removes the trap without touching the control, which
> beats both "raise it" and "keep it and document a workaround."

**Recommendation: change nothing.** `maxAge: "12h"` only breaks the _local_ REST
Playground with a stale cached token, which Phase 0 already documented as a
one-click fix (clear `localhost` local storage). Neither pilot surface depends
on it. Weakening a #4269 security control for a documented developer-ergonomics
issue is the wrong trade — so this task exists to get that recorded, not to
change code by default.

Do **not** implement an alternative unless the analytics-engineer code owners
ask for it, or unless Task 6 Variant B Step B1 proved a `cubecloud` token gets
403'd for having no `iat` (in which case the cloud surface genuinely needs it).

**Files:**

- Modify (only if a change is approved): `src/cube/cube.js:228-236`,
  `src/cube/cube.test.js:51-113`
- Modify:
  `docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md`
  (record the decision)

**Interfaces:**

- Consumes: nothing.
- Produces: nothing consumed by other tasks. If a change is approved, three
  existing tests change meaning — see Step 2.

- [ ] **Step 1: Put the decision to the code owners**

Ask the `src/cube/` CODEOWNERS (analytics-engineers) on the PR, presenting: the
#4269 rationale (a compromised minter cannot extend a token's life by inflating
`exp` alone, because `maxAge` derives from `iat` and rejects tokens with no
`iat`); the one real cost (a stale Playground token denies every view, fixed by
re-minting); and the recommendation to keep it.

- [ ] **Step 2: If a change IS approved, know what it breaks first**

Three existing tests encode today's behavior and would have to change:

- `src/cube/cube.test.js:51` — "a token past the 12h maxAge is rejected even
  when exp is still valid"
- `src/cube/cube.test.js:90` — "a token with no iat is rejected (maxAge requires
  iat)"
- `src/cube/cube.test.js:72` — "an exp-expired token is rejected" (must keep
  passing under any option; it is the remaining control)

The spec's testing strategy also requires confirming that any change still
rejects an expired short-lived MCP token (`mcp/server.py`'s `_mint_token` sets
`iat` plus a 5-minute `exp`).

Do not relax `maxAge` based on an `iss` value read from an **unverified**
`jwt.decode` — that lets anyone who can sign a token opt out of the cap, which
is exactly the threat `maxAge` exists for. If the cloud surface needs it, gate
on the _transport_ (a separate hook or endpoint) rather than on token-supplied
content.

- [ ] **Step 3: Record the decision**

In the spec, replace the `maxAge` bullet under
`## Open questions / verification items` with the decision and its rationale.

- [ ] **Step 4: Commit**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git add docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md
git commit -m "docs(cube): record the maxAge decision for emulation

Refs #4526"
```

---

## Task 9: Open the pull request

**Files:**

- Reference: `.github/pull_request_template.md`

**Interfaces:**

- Consumes: every prior task.
- Produces: a PR against `main`, squash-merge, awaiting analytics-engineer
  review (CODEOWNERS covers `src/dbt/` and `src/cube/`).

- [ ] **Step 1: Merge main and run everything**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git fetch origin main && git merge origin/main
cd src/cube && npm test
```

Expected: merge clean, all tests pass.

- [ ] **Step 2: Lint every changed file**

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only origin/main...HEAD | while read -r f; do [ -f "$f" ] && printf '%s ' "$f"; done) </dev/null
```

Expected: `No issues`. The existing-file filter matters — `--force` hard-errors
on a deleted path.

- [ ] **Step 3: Push the remaining commits and open the PR**

The branch has been on the remote since Task 4 (Cube Cloud needed it), so this
is just catching up the tail:

```bash
cd /workspaces/teamster/.worktrees/cristinabaldor/feat/claude-cube-internal-emulation
git push
```

Then open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md` as the body, with `Closes #4526`. Keep viewer
emails and matrix output out of the body. Note in the body that
`CUBE_IMPERSONATORS` must be set on the deployment for emulation to do anything
— unset means the feature is inert, which is the safe default.

- [ ] **Step 4: Verify CI on both surfaces**

Check the dbt Cloud commit _status_ and the Trunk / CodeQL / `claude` _check
runs_ — they are disjoint surfaces. `claude-review` only fires on `opened` /
`ready_for_review`, so do not wait for a re-review after a fix push.

---

## Out of Scope

Carried forward from the spec and the 2026-07-23 session; do **not** absorb
these into this plan:

- External-vendor API-key layer (#4455 / #4501) — sibling work. This plan only
  keeps the `checkAuth` branch shaped so `resolveApiKey` drops in later.
- `act_as` support in the `cube` MCP (it mints an `email`-only JWT).
- Migrating the impersonator flag from the deployment variable to
  `dim_staff_cube_access.is_cube_impersonator`.
- A durable (BigQuery/GCS) impersonation-audit sink. v1 is deployment logs.
- Any change to `canSwitchSqlUser` or the SQL super-user model.
- `staff_directory.count_employees` missing a date filter, and the fact that
  `staff_directory` is an open tier (no `row_level`) so every resolved viewer
  sees all business units network-wide. Real findings, separate issue.
- At least one region-scope viewer in `dim_staff_cube_access` has a NULL
  `region_key` and fail-safes to 0 rows. Not a leak; an upstream data-quality
  follow-up. Identify the rows with
  `where student_location_scope = 'region' and region_key is null` rather than
  recording an email here — viewer identities are PII and do not belong in a
  committed file.

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: Phase 0 items 1-2 →
already committed (`af7d10303`, `b907c5f33`); Phase 1 spike remainder → Task 5;
Phase 2(a) cloud enrichment → Task 6; Phase 2(b) `maxAge` → Task 8; Phase 2(c)
admin-gated `act_as` → Tasks 1-2; "where impersonators live" → Task 1
(`parseImpersonators`); Audit → Task 2 (`logEmulation`, reused in Task 6);
external-compatibility constraint → Global Constraints plus the `checkAuth`
comment in Task 2; testing strategy (unit, regression, local RLS, cloud) → Tasks
1, 2, 3, 5 and 6; invariants → Global Constraints. The spec's "turn the matrix
into a committed tool" line → Task 3.

**Gap found and closed (1):** the spec's testing strategy asks for a `cube.js`
harness; one already exists (`src/cube/cube.test.js`), and it contains a
`forged groups/securityContext claims are ignored (only email is trusted)` test
whose premise `act_as` modifies. Task 2 Step 4 explicitly re-checks it, and Task
2 Step 1 extends `test.beforeEach` so `CUBE_IMPERSONATORS` cannot leak across
tests.

**Gap found and closed (2):** the first draft of this plan deferred pushing the
branch to the final PR task, yet the spike and both verification steps require a
live Cube Cloud deployment — which cannot exist for an unpushed branch, and does
not auto-create even after a push. Task 4 now stands the branch up explicitly
(push → add the branch in Dev Mode → verify that environment's own configuration
→ confirm the model is live over REST) before any console work. It also captures
the two failure modes that otherwise masquerade as access bugs: unset BigQuery
connection variables on the branch environment deny every viewer, and an unset
`CUBE_IMPERSONATORS` makes emulation silently inert.

**Gap found and closed (3):** nothing in the first draft proved the `act_as`
path worked anywhere but in unit tests. Task 5 Step 1 now validates it against
the real branch deployment over REST — which works today, because REST goes
through `checkAuth` while only Explore bypasses it — including the negative case
with `CUBE_IMPERSONATORS` removed. That separates "emulation works" from "Cube
Cloud Explore works", so a failure in the harder cloud surface can no longer be
mistaken for the feature being broken.

**Type and name consistency.** `resolveEmulationTarget` returns
`{ caller, target, emulating }` in Task 1 and is destructured with exactly those
names in Task 2 and Task 6. `parseImpersonators` returns a `Set` and
`isImpersonator` calls `.has()` on it. `logEmulation(surface, caller, target)`
is defined in Task 2 and called with `"rest"` there and `"cubecloud"` in Task 6.
The adapters return `{ callerEmail, requestedTarget }`, matching
`resolveEmulationTarget`'s parameter names, so the spread in both hooks
resolves.

**Gap found and closed (4):** the first draft's `resolveEmulationTarget`
lowercased the emails it returned, and Task 2 feeds that value straight into
`resolveAccess` — which matches `google_email` exactly and caches on the raw
string. That would have changed resolution for **every** request, not only
emulated ones, and left `checkSqlAuth` on the un-normalized value. Verified
against the warehouse: all 1,614 rows are already lowercase, so it was latent
rather than live — but the model applies no `lower()` and tests only `not_null`,
so the property is incidental. Case is now preserved, with a dedicated
regression test asserting a non-emulated caller passes through byte-identical.

**Gap found and closed (5):** Task 3 originally switched the matrix tool from
the `psycopg2` the prototype was proven with to `psycopg` 3, purely because 3
was already a dependency. psycopg 3 uses the extended query protocol against
what is only a partial Postgres implementation, so the plan now smoke-tests the
connection first and names `psycopg2-binary` via `uv run --with` as the
documented fallback.

**Gap found and closed (6):** nothing in the plan enabled `CUBE_IMPERSONATORS`
on **production**, yet Task 7 asks you to sign off real pilot users. Task 7 Step
1 is now an explicit decision — enable on production with a named list and an
agreed removal date, or sign off on the branch environment (which reads
production `kipptaf_marts`, so the identity data is real) and say so in the
guide.

**Sequencing note.** Tasks 1-3 are unblocked and entirely local. Task 4 is the
hinge: it needs one push (Claude can do that) plus Cube Cloud console
configuration (the user must do that), and everything after it depends on the
live branch environment. Task 5 then both validates emulation and picks the Task
6 variant, so Task 6 cannot start before it. Task 8 is deliberately last and
non-blocking, except in the one Variant B case flagged in Step B1, where it
becomes a hard prerequisite.

**Emulation is proved twice, on purpose.** Task 5 Step 1 proves it over REST on
a real deployment (works today), and Task 6 Step A5 proves it in Cube Cloud
Explore (the surface that needs the fix). Both include the
un-set-`CUBE_IMPERSONATORS` negative check, because "it returned data" is not
evidence the gate is closed.
