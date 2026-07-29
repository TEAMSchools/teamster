"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const jwt = require("jsonwebtoken");

const SECRET = "test-secret-for-jwt-expiry-spec";

// cube.js reads CUBEJS_API_SECRET / CUBE_GROUP_MAP / NODE_ENV per-call (not
// cached at module load), so a fresh require per test isn't required — but we
// still reset the env vars each test to keep them independent.
const cube = require("./cube");

function sign(payload) {
  return jwt.sign(payload, SECRET, { algorithm: "HS256" });
}

// Captures the cube_emulation audit lines a call emits. The audit trail is the
// compliance half of emulation, so it is asserted rather than eyeballed.
async function capturedEmulationLog(fn) {
  const lines = [];
  const original = console.log;
  console.log = (...args) => lines.push(args.join(" "));
  try {
    await fn();
  } finally {
    console.log = original;
  }
  return lines.filter((line) => line.includes("cube_emulation"));
}

test.beforeEach(() => {
  process.env.CUBEJS_API_SECRET = SECRET;
  delete process.env.CUBE_GROUP_MAP;
  delete process.env.NODE_ENV; // dev bypass in resolveAccess requires !== "production"
  delete process.env.CUBEJS_SQL_PASSWORD;
  delete process.env.CUBE_IMPERSONATORS;
});

// resolveAccess caches per-email at module scope (until midnight ET) and the
// cache isn't exported, so tests that assert on the resolved context use a
// UNIQUE email each to avoid a cross-test cache hit.

test("checkAuth: a fresh token resolves via the CUBE_GROUP_MAP dev bypass", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "viewer@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "viewer@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
});

test("checkAuth: no Authorization token resolves to the default-deny context", async () => {
  const req = {};
  await cube.checkAuth(req, undefined);
  assert.deepEqual(req.securityContext.groups, []);
});

test("checkAuth: a token past the 12h maxAge is rejected even when exp is still valid", async () => {
  const now = Math.floor(Date.now() / 1000);
  const thirteenHoursAgo = now - 13 * 60 * 60;
  // iat is 13h old (exceeds the 12h maxAge) but exp is far in the future —
  // isolates the maxAge check from the pre-existing exp check below.
  const token = sign({
    email: "leaked@apps.teamschools.org",
    iat: thirteenHoursAgo,
    exp: now + 300,
  });

  const req = {};
  await assert.rejects(
    () => cube.checkAuth(req, token),
    (err) => {
      assert.equal(err.status, 403);
      return true;
    },
  );
});

test("checkAuth: an exp-expired token is rejected", async () => {
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "expired@apps.teamschools.org",
    iat: now - 600,
    exp: now - 60,
  });

  const req = {};
  await assert.rejects(
    () => cube.checkAuth(req, token),
    (err) => {
      assert.equal(err.status, 403);
      return true;
    },
  );
});

test("checkAuth: a token with no iat is rejected (maxAge requires iat)", async () => {
  const now = Math.floor(Date.now() / 1000);
  // A token minted without `iat` (e.g. a hand-rolled token bypassing
  // mcp/server.py's _mint_token) must fail closed once maxAge is enforced,
  // rather than being accepted forever the way a bare `exp`-less/iat-less
  // token would have been before this change. jsonwebtoken's `sign()` adds
  // `iat` automatically unless `noTimestamp` is set — pass it explicitly to
  // reconstruct a token that truly omits the claim.
  const token = jwt.sign(
    { email: "no-iat@apps.teamschools.org", exp: now + 300 },
    SECRET,
    { algorithm: "HS256", noTimestamp: true },
  );

  const req = {};
  await assert.rejects(
    () => cube.checkAuth(req, token),
    (err) => {
      assert.equal(err.status, 403);
      return true;
    },
  );
});

test("checkAuth: a valid token within maxAge resolves normally", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "fresh@apps.teamschools.org": ["staff-directory", "student-network"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "fresh@apps.teamschools.org",
    iat: now - 60, // 1 minute old — well within the 12h ceiling
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, [
    "staff-directory",
    "student-network",
  ]);
});

test("checkAuth: a token expired within clockTolerance still resolves (clock skew)", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "skew@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "skew@apps.teamschools.org",
    iat: now - 60,
    exp: now - 10, // expired 10s ago — within the 30s clockTolerance
  });

  const req = {};
  await cube.checkAuth(req, token);

  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
});

test("checkAuth: an alg:none (unsigned) token is rejected", async () => {
  const now = Math.floor(Date.now() / 1000);
  // An attacker strips the signature and sets alg:none. jwt.verify pins HS256,
  // so this must be rejected — never treated as a valid identity.
  const token = jwt.sign(
    { email: "attacker@apps.teamschools.org", iat: now, exp: now + 300 },
    "",
    { algorithm: "none" },
  );

  const req = {};
  await assert.rejects(
    () => cube.checkAuth(req, token),
    (err) => {
      assert.equal(err.status, 403);
      return true;
    },
  );
});

test("checkAuth: a token signed with the wrong secret is rejected", async () => {
  const now = Math.floor(Date.now() / 1000);
  const token = jwt.sign(
    { email: "attacker@apps.teamschools.org", iat: now, exp: now + 300 },
    "not-the-real-secret",
    { algorithm: "HS256" },
  );

  const req = {};
  await assert.rejects(
    () => cube.checkAuth(req, token),
    (err) => {
      assert.equal(err.status, 403);
      return true;
    },
  );
});

test("checkAuth: forged groups/securityContext claims are ignored (email and act_as are the only claims read)", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "forged@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  // A validly-signed token that also smuggles attacker-controlled group claims.
  const token = sign({
    email: "forged@apps.teamschools.org",
    groups: ["staff-pii-all_in_scope", "student-network"],
    securityContext: { groups: ["staff-pii-all_in_scope"] },
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  // Resolved from the email claim only — the forged group claims never reach
  // the security context.
  assert.deepEqual(req.securityContext.groups, ["staff-directory"]);
});

test("checkSqlAuth: an unset SQL password rejects the connection (fail-closed)", async () => {
  delete process.env.CUBEJS_SQL_PASSWORD;
  const res = await cube.checkSqlAuth({}, "sqlnopw@apps.teamschools.org", "x");
  // password: null makes Cube reject every connection; context is default-deny.
  assert.equal(res.password, null);
  assert.deepEqual(res.securityContext.groups, []);
});

test("checkSqlAuth: a set SQL password is returned and identity resolves from the connecting user", async () => {
  process.env.CUBEJS_SQL_PASSWORD = "server-known-pw";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "sqlviewer@apps.teamschools.org": ["staff-directory"],
  });
  const res = await cube.checkSqlAuth(
    {},
    "sqlviewer@apps.teamschools.org",
    "presented-value-ignored",
  );
  assert.equal(res.password, "server-known-pw");
  assert.deepEqual(res.securityContext.groups, ["staff-directory"]);
});

test("resolveAccess (production path) fails closed to default-deny when BigQuery errors", async () => {
  process.env.NODE_ENV = "production"; // skip the CUBE_GROUP_MAP dev bypass
  process.env.CUBEJS_SQL_PASSWORD = "server-known-pw";
  // @google-cloud/bigquery exposes BigQuery as a getter-only property, so swap
  // the whole cached module exports (resolveAccess does a lazy require).
  const bqPath = require.resolve("@google-cloud/bigquery");
  require("@google-cloud/bigquery"); // ensure it is in the require cache
  const cached = require.cache[bqPath];
  const origExports = cached.exports;
  cached.exports = {
    BigQuery: class {
      async query() {
        throw new Error("simulated BigQuery failure");
      }
    },
  };
  try {
    const res = await cube.checkSqlAuth(
      {},
      "prodfail@apps.teamschools.org",
      "server-known-pw",
    );
    // The production path hits BigQuery, which throws -> the try/catch in
    // resolveAccess returns an empty default-deny context (never throws, stays
    // available) rather than granting anything.
    assert.deepEqual(res.securityContext.groups, []);
    assert.equal(res.password, "server-known-pw");
  } finally {
    cached.exports = origExports;
  }
});

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
  // The critical negative case. act_as is attacker-controlled here: the caller
  // signed their own valid token and asked for a broader identity.
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

test("checkAuth: a real emulation emits exactly one audit line, identities only", async () => {
  process.env.CUBE_IMPERSONATORS = "admin8@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "target8@apps.teamschools.org": ["student-network"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin8@apps.teamschools.org",
    act_as: "target8@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const lines = await capturedEmulationLog(() => cube.checkAuth({}, token));

  assert.equal(lines.length, 1);
  const entry = JSON.parse(lines[0]);
  assert.equal(entry.event, "cube_emulation");
  assert.equal(entry.surface, "rest");
  assert.equal(entry.caller, "admin8@apps.teamschools.org");
  assert.equal(entry.target, "target8@apps.teamschools.org");
  // Identities and a timestamp ONLY — never groups, scopes, or row data.
  assert.deepEqual(Object.keys(entry).sort(), [
    "at",
    "caller",
    "event",
    "surface",
    "target",
  ]);
});

test("checkAuth: an IGNORED act_as emits no audit line", async () => {
  // A line here would assert an emulation that did not happen — worse than no
  // trail, because it would implicate a caller who never gained the target's
  // scope.
  process.env.CUBE_IMPERSONATORS = "admin9@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "teacher9@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "teacher9@apps.teamschools.org",
    act_as: "admin9@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const lines = await capturedEmulationLog(() => cube.checkAuth({}, token));

  assert.deepEqual(lines, []);
});

test("checkAuth: act_as pointing at yourself emits no audit line", async () => {
  // Self-targeting is a no-op, not an emulation — keeps the trail free of noise.
  process.env.CUBE_IMPERSONATORS = "admin10@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "admin10@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin10@apps.teamschools.org",
    act_as: "ADMIN10@apps.teamschools.org",
    iat: now,
    exp: now + 300,
  });

  const lines = await capturedEmulationLog(() => cube.checkAuth({}, token));

  assert.deepEqual(lines, []);
});

test("checkAuth: the target email reaches resolveAccess with its case intact", async () => {
  // resolveAccess matches google_email exactly and keys its cache on the raw
  // string, so the hook must not normalize what it forwards.
  process.env.CUBE_IMPERSONATORS = "admin7@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "MixedTarget7@Apps.Teamschools.Org": ["student-network"],
    "mixedtarget7@apps.teamschools.org": ["staff-directory"],
  });
  const now = Math.floor(Date.now() / 1000);
  const token = sign({
    email: "admin7@apps.teamschools.org",
    act_as: "MixedTarget7@Apps.Teamschools.Org",
    iat: now,
    exp: now + 300,
  });

  const req = {};
  await cube.checkAuth(req, token);

  // The mixed-case key resolved, not the lowercased one.
  assert.deepEqual(req.securityContext.groups, ["student-network"]);
});

// --- Cube Cloud injected-context enrichment (#4526) --------------------------
// Cube Cloud bypasses checkAuth and injects a context with no top-level
// `groups`, so contextToGroups enriches it from the console identity. Shapes
// below match what 1.7.14 actually injects: no top-level email, and the console
// user under cubeCloud.username.

test("contextToGroups: a Cube Cloud context resolves the console user's own scope", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "console1@apps.teamschools.org": ["student-network", "staff-directory"],
  });
  const securityContext = {
    cubeCloud: {
      username: "console1@apps.teamschools.org",
      roles: ["Developer"],
    },
    iss: "cubecloud",
    exp: 1790000000,
  };

  const groups = await cube.contextToGroups({ securityContext });

  assert.deepEqual(groups, ["student-network", "staff-directory"]);
  // The access policies read the context object, not this return value, so the
  // enrichment has to land ON it.
  assert.deepEqual(securityContext.groups, [
    "student-network",
    "staff-directory",
  ]);
  assert.ok("allowed_abbreviations" in securityContext);
  // Cube Cloud's own keys survive enrichment.
  assert.equal(
    securityContext.cubeCloud.username,
    "console1@apps.teamschools.org",
  );
});

test("contextToGroups: enrichment is idempotent (re-entry is a no-op)", async () => {
  // Cube caches selected policies under a hash taken BEFORE this hook, so the
  // same input context must always yield the same groups.
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "console2@apps.teamschools.org": ["staff-directory"],
  });
  const securityContext = {
    cubeCloud: { username: "console2@apps.teamschools.org" },
    iss: "cubecloud",
  };

  const first = await cube.contextToGroups({ securityContext });
  const second = await cube.contextToGroups({ securityContext });

  assert.deepEqual(first, second);
  assert.deepEqual(securityContext.groups, ["staff-directory"]);
});

test("contextToGroups: a Cube Cloud context with no username stays default-deny", async () => {
  const securityContext = {
    cubeCloud: { roles: ["Developer"] },
    iss: "cubecloud",
  };
  assert.deepEqual(await cube.contextToGroups({ securityContext }), []);
  assert.ok(!("groups" in securityContext));
});

test("contextToGroups: an unresolvable console user stays default-deny", async () => {
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "someone-else@apps.teamschools.org": ["student-network"],
  });
  const securityContext = {
    cubeCloud: { username: "nobody3@apps.teamschools.org" },
    iss: "cubecloud",
  };
  assert.deepEqual(await cube.contextToGroups({ securityContext }), []);
});

test("contextToGroups: a REST context (no cubeCloud) is passed through untouched", async () => {
  // checkAuth already resolved it, and there is no console identity to re-derive
  // from, so this path must be inert - including when groups is legitimately
  // empty (default-deny).
  const rest = { groups: ["staff-directory"], region_key: "R1" };
  assert.deepEqual(await cube.contextToGroups({ securityContext: rest }), [
    "staff-directory",
  ]);
  assert.equal(rest.region_key, "R1");

  const denied = { groups: [] };
  assert.deepEqual(await cube.contextToGroups({ securityContext: denied }), []);
});

test("contextToGroups: PASTED groups and scope values are overwritten, not honored", async () => {
  // Cube Cloud merges a pasted Security Context into the top level, so these are
  // attacker-controlled. Before this fix they were returned verbatim, which let
  // any console user grant themselves staff PII access with a forged remit.
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "console5@apps.teamschools.org": ["staff-directory"],
  });
  const pasted = {
    cubeCloud: { username: "console5@apps.teamschools.org" },
    iss: "cubecloud",
    groups: ["staff-pii-all_in_scope", "student-network"],
    region_key: "FORGED",
    allowed_abbreviations: ["FORGED"],
    allowed_department_groups: ["FORGED"],
  };

  const groups = await cube.contextToGroups({ securityContext: pasted });

  // Only the console user's real HR-derived scope survives.
  assert.deepEqual(groups, ["staff-directory"]);
  assert.ok(!groups.includes("staff-pii-all_in_scope"));
  assert.notEqual(pasted.region_key, "FORGED");
  assert.notDeepEqual(pasted.allowed_abbreviations, ["FORGED"]);
  assert.notDeepEqual(pasted.allowed_department_groups, ["FORGED"]);
});

test("contextToGroups: an impersonator's pasted email resolves the TARGET", async () => {
  process.env.CUBE_IMPERSONATORS = "cloudadmin6@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudadmin6@apps.teamschools.org": ["student-network"],
    "cloudtarget6@apps.teamschools.org": ["student-region"],
  });
  const securityContext = {
    cubeCloud: { username: "cloudadmin6@apps.teamschools.org" },
    iss: "cubecloud",
    email: "cloudtarget6@apps.teamschools.org",
  };

  const lines = await capturedEmulationLog(async () => {
    assert.deepEqual(await cube.contextToGroups({ securityContext }), [
      "student-region",
    ]);
  });

  assert.equal(lines.length, 1);
  const entry = JSON.parse(lines[0]);
  assert.equal(entry.surface, "cubecloud");
  assert.equal(entry.caller, "cloudadmin6@apps.teamschools.org");
  assert.equal(entry.target, "cloudtarget6@apps.teamschools.org");
});

test("contextToGroups: a NON-impersonator's pasted email is ignored - own scope only", async () => {
  // The critical negative on the Explore surface: anyone with console access can
  // type another email into the Security Context editor.
  process.env.CUBE_IMPERSONATORS = "cloudadmin7@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudviewer7@apps.teamschools.org": ["staff-directory"],
    "cloudtarget7@apps.teamschools.org": [
      "student-network",
      "staff-pii-all_in_scope",
    ],
  });
  const securityContext = {
    cubeCloud: { username: "cloudviewer7@apps.teamschools.org" },
    iss: "cubecloud",
    email: "cloudtarget7@apps.teamschools.org",
  };

  const lines = await capturedEmulationLog(async () => {
    assert.deepEqual(await cube.contextToGroups({ securityContext }), [
      "staff-directory",
    ]);
  });

  assert.deepEqual(lines, []);
});

test("contextToGroups: a target mirrored only at userAttributes.email is honored", async () => {
  // Cube Cloud mirrors the pasted context there as well as at the top level.
  process.env.CUBE_IMPERSONATORS = "cloudadmin8@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudadmin8@apps.teamschools.org": ["student-network"],
    "cloudtarget8@apps.teamschools.org": ["student-region"],
  });
  const securityContext = {
    cubeCloud: {
      username: "cloudadmin8@apps.teamschools.org",
      userAttributes: { email: "cloudtarget8@apps.teamschools.org" },
    },
    iss: "cubecloud",
  };

  assert.deepEqual(await cube.contextToGroups({ securityContext }), [
    "student-region",
  ]);
});

test("contextToGroups: no security context at all is default-deny", async () => {
  assert.deepEqual(
    await cube.contextToGroups({ securityContext: undefined }),
    [],
  );
});
