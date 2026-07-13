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
});

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
