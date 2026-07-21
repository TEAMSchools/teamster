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

test.beforeEach(() => {
  process.env.CUBEJS_API_SECRET = SECRET;
  delete process.env.CUBE_GROUP_MAP;
  delete process.env.NODE_ENV; // dev bypass in resolveAccess requires !== "production"
  delete process.env.CUBEJS_SQL_PASSWORD;
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

test("checkAuth: forged groups/securityContext claims are ignored (only email is trusted)", async () => {
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
