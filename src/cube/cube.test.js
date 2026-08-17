"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const jwt = require("jsonwebtoken");
const fs = require("node:fs");
const path = require("node:path");
const access = require("./access");

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

// Same pattern as capturedEmulationLog, for the ADC-fallback breadcrumb, which
// is logged via console.warn (not console.log).
async function capturedWarnLog(fn) {
  const lines = [];
  const original = console.warn;
  console.warn = (...args) => lines.push(args.join(" "));
  try {
    await fn();
  } finally {
    console.warn = original;
  }
  return lines.filter((line) => line.includes("cube_bq_credentials_fallback"));
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

// --- 403 diagnosability (#4526) ----------------------------------------------
// Every jwt failure used to return a bare "Invalid token", which is what turned
// the maxAge cap into a trap: a stale Playground token, a wrong secret, and an
// unset secret all looked identical, and all render as "no data". The status
// stays 403; only the message distinguishes them.

async function rejectionMessage(token) {
  let captured;
  await assert.rejects(
    () => cube.checkAuth({}, token),
    (err) => {
      assert.equal(err.status, 403);
      captured = String(err.message);
      return true;
    },
  );
  return captured;
}

test("checkAuth: a maxAge rejection says the token is too old and to re-mint", async () => {
  const now = Math.floor(Date.now() / 1000);
  const message = await rejectionMessage(
    sign({
      email: "stale-msg@apps.teamschools.org",
      iat: now - 13 * 60 * 60,
      exp: now + 300,
    }),
  );
  assert.match(message, /too old/i);
  assert.match(message, /maxAge/);
  assert.match(message, /re-mint/i);
});

test("checkAuth: an exp rejection is distinguishable from a maxAge one", async () => {
  const now = Math.floor(Date.now() / 1000);
  const message = await rejectionMessage(
    sign({
      email: "exp-msg@apps.teamschools.org",
      iat: now - 600,
      exp: now - 120,
    }),
  );
  assert.match(message, /expired/i);
  // The two must not be confusable - that confusion is the whole bug.
  assert.doesNotMatch(message, /maxAge/);
});

test("checkAuth: a signature rejection points at the deployment's signing secret", async () => {
  const now = Math.floor(Date.now() / 1000);
  const message = await rejectionMessage(
    jwt.sign(
      {
        email: "wrongsecret-msg@apps.teamschools.org",
        iat: now,
        exp: now + 300,
      },
      "not-the-real-secret",
      { algorithm: "HS256" },
    ),
  );
  // The likeliest real cause is a secret that is wrong or unset on a branch
  // environment, which is otherwise invisible from the client side.
  assert.match(message, /signing secret|CUBEJS_API_SECRET/);
  assert.doesNotMatch(message, /too old/i);
});

test("checkAuth: an unset signing secret withholds jsonwebtoken's own message, naming only that verification failed", async () => {
  // jsonwebtoken reports an unset secret as "secret or public key must be
  // provided" — that is deployment state (this environment has no signing
  // secret configured at all), not a fact about the caller's own token. An
  // unauthenticated caller must not learn that from a 403 body.
  delete process.env.CUBEJS_API_SECRET;
  const now = Math.floor(Date.now() / 1000);
  // Signed with an arbitrary secret — irrelevant, since jwt.verify errors
  // before ever checking the signature when its own secretOrPublicKey is
  // missing.
  const token = jwt.sign(
    { email: "unset-secret@apps.teamschools.org", iat: now, exp: now + 300 },
    "whatever",
    { algorithm: "HS256" },
  );
  const message = await rejectionMessage(token);
  assert.match(message, /the server could not verify it/);
  assert.doesNotMatch(message, /secret or public key/);
});

test("checkAuth: a bad-signature rejection still echoes jsonwebtoken's own message text (withholding is narrow, not blanket)", async () => {
  // Every OTHER JsonWebTokenError message stays verbatim — only the unset-
  // secret case above is withheld. This is the non-regression half: a real
  // signature mismatch must still name jsonwebtoken's own diagnostic text.
  const now = Math.floor(Date.now() / 1000);
  const message = await rejectionMessage(
    jwt.sign(
      { email: "badsig@apps.teamschools.org", iat: now, exp: now + 300 },
      "not-the-real-secret",
      { algorithm: "HS256" },
    ),
  );
  assert.match(message, /invalid signature/i);
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

// --- ADC fallback when CUBEJS_DB_BQ_CREDENTIALS is unset --------------------
// The documented local RLS sign-off runs `NODE_ENV=production
// CUBEJS_DEV_MODE=false npm run dev`, so gating the ADC fallback on
// NODE_ENV === "production" would fail-close that exact workflow (the bug a
// prior draft of this change nearly reintroduced). The fallback is
// unconditional; an unset CUBEJS_DB_BQ_CREDENTIALS instead logs a one-time
// console.warn breadcrumb (`cube_bq_credentials_fallback`), latched by a
// module-level flag so it fires once per process, not once per identity
// resolution. These tests re-require "./cube" fresh (via require.cache
// deletion) to get an unlatched module instance, rather than reaching into
// cube.js's internals — the shared top-level `cube` binding used by every
// other test in this file is untouched by that cache deletion.

function stubBigQueryExports(queryImpl) {
  const bqPath = require.resolve("@google-cloud/bigquery");
  require("@google-cloud/bigquery"); // ensure it is in the require cache
  const cached = require.cache[bqPath];
  const origExports = cached.exports;
  cached.exports = {
    BigQuery: class {
      async query(opts) {
        return queryImpl(opts);
      }
    },
  };
  return () => {
    cached.exports = origExports;
  };
}

function freshCubeModule() {
  const cubePath = require.resolve("./cube");
  delete require.cache[cubePath];
  return require("./cube");
}

test("resolveAccess: with CUBEJS_DB_BQ_CREDENTIALS unset, identity resolution falls back to ADC and still resolves — not a fail-closed empty context — in both dev and NODE_ENV=production", async () => {
  delete process.env.CUBEJS_DB_BQ_CREDENTIALS;
  process.env.CUBEJS_SQL_PASSWORD = "server-known-pw";

  const restoreBigQuery = stubBigQueryExports(({ query }) => {
    if (query.includes("dim_staff_reporting_chain")) return [[]];
    if (query.includes("dim_locations")) {
      return [[{ abbreviation: "ABC", region_key: "R1" }]];
    }
    if (query.includes("DISTINCT department_group")) return [[]];
    return [
      [
        {
          staff_key: "adc-fallback-staff",
          student_location_scope: "school",
          staff_pii_scope: "none",
          region_key: "R1",
          location_abbreviation: "ABC",
          department_group: null,
          job_function_level: 2,
          staff_location_scope: "school",
          staff_department_scope: "none",
        },
      ],
    ];
  });

  try {
    for (const nodeEnv of [undefined, "production"]) {
      if (nodeEnv) process.env.NODE_ENV = nodeEnv;
      else delete process.env.NODE_ENV;

      const freshCube = freshCubeModule();
      const email = `adc-fallback-${nodeEnv ?? "dev"}@apps.teamschools.org`;
      const res = await freshCube.checkSqlAuth({}, email, "ignored");

      assert.equal(res.password, "server-known-pw");
      // Populated, HR-derived scope — the opposite of the empty default-deny
      // shape that a fail-closed throw would have produced.
      assert.ok(res.securityContext.groups.includes("staff-directory"));
      assert.equal(res.securityContext.region_key, "R1");
    }
  } finally {
    restoreBigQuery();
    delete require.cache[require.resolve("./cube")];
    delete process.env.NODE_ENV;
  }
});

test("resolveAccess: the ADC-fallback warning is emitted once per process, not once per call", async () => {
  delete process.env.CUBEJS_DB_BQ_CREDENTIALS;
  process.env.CUBEJS_SQL_PASSWORD = "server-known-pw";

  const restoreBigQuery = stubBigQueryExports(() => [[]]);
  const freshCube = freshCubeModule();

  try {
    const lines = await capturedWarnLog(async () => {
      await freshCube.checkSqlAuth({}, "warn-once-a@apps.teamschools.org", "x");
      await freshCube.checkSqlAuth({}, "warn-once-b@apps.teamschools.org", "x");
    });
    assert.equal(lines.length, 1);
    const entry = JSON.parse(lines[0]);
    assert.equal(entry.event, "cube_bq_credentials_fallback");
  } finally {
    restoreBigQuery();
    delete require.cache[require.resolve("./cube")];
  }
});

test("resolveAccess: with CUBEJS_DB_BQ_CREDENTIALS set, no ADC-fallback warning is emitted", async () => {
  process.env.CUBEJS_SQL_PASSWORD = "server-known-pw";
  process.env.CUBEJS_DB_BQ_CREDENTIALS = Buffer.from(
    JSON.stringify({
      client_email: "test@example.iam.gserviceaccount.com",
      private_key: "not-a-real-key",
    }),
  ).toString("base64");

  const restoreBigQuery = stubBigQueryExports(() => [[]]);
  const freshCube = freshCubeModule();

  try {
    const lines = await capturedWarnLog(async () => {
      await freshCube.checkSqlAuth({}, "creds-set@apps.teamschools.org", "x");
    });
    assert.deepEqual(lines, []);
  } finally {
    restoreBigQuery();
    delete process.env.CUBEJS_DB_BQ_CREDENTIALS;
    delete require.cache[require.resolve("./cube")];
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
  // The context is now OVERWRITTEN with the empty default-deny shape rather than
  // left untouched. This assertion used to read `!("groups" in securityContext)`,
  // which encoded the old `if (consoleUser)` gate: a missing username skipped
  // enrichment entirely and left the object alone. Gating on the `cubeCloud` key
  // means a username-less console context is neutralized like any other, so
  // asserting the default-deny VALUES is both the stronger check and the one
  // that matches intent — an absent key proves nothing about what a paste left
  // behind.
  assert.deepEqual(securityContext.groups, []);
  assert.equal(securityContext.region_key, null);
  assert.deepEqual(securityContext.allowed_abbreviations, []);
});

// --- Change A load-bearing negative: the gate must fire on the `cubeCloud`
// KEY, not on `cubeCloud.username` -------------------------------------------
// This is the exact bypass the overwrite exists to close: a console context
// that carries `cubeCloud` but no `username` must still enter the enrichment
// block and resolve to the empty default-deny context — never fall through to
// `securityContext?.groups ?? []` and honor whatever was pasted alongside it.
// Verified this FAILS against the OLD `if (consoleUser)` gate (where
// `consoleUser = securityContext?.cubeCloud?.username ?? null` is null here,
// so the block is skipped and the pasted `groups` + forged allow-lists are
// returned/left in place verbatim) — reverted `cube.js` locally to that gate,
// confirmed the failure, then restored the file (not committed).
test("contextToGroups: a Cube Cloud context with no username is neutralized, not passed through (Change A load-bearing negative)", async () => {
  const pasted = {
    cubeCloud: { roles: ["Developer"] }, // no username
    iss: "cubecloud",
    groups: ["staff-pii-all_in_scope"],
    region_key: "FORGED",
    allowed_abbreviations: ["FORGED"],
    allowed_department_groups: ["FORGED"],
  };

  const lines = await capturedEmulationLog(async () => {
    const groups = await cube.contextToGroups({ securityContext: pasted });
    assert.deepEqual(groups, []);
  });

  assert.ok(!pasted.groups.includes("staff-pii-all_in_scope"));
  assert.notEqual(pasted.region_key, "FORGED");
  assert.notDeepEqual(pasted.allowed_abbreviations, ["FORGED"]);
  assert.notDeepEqual(pasted.allowed_department_groups, ["FORGED"]);
  // No caller identity to resolve (username absent) means no emulation to log.
  assert.deepEqual(lines, []);
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

// --- Change B on the Cube Cloud surface -------------------------------------
// The pasted `email` target is a JSON value the console user fully controls,
// so it is just as likely to be an object/array as a string. Before Change B,
// a bare `.toLowerCase()` on it threw a TypeError out of contextToGroups (a
// 500), not a clean deny. Verified (in access.test.js) that the old
// `?? null` coercion throws here; this test proves the surface-level
// consequence — no throw, no emulation, caller resolves as themselves.
test("contextToGroups: a pasted non-string email target does not throw and resolves the caller as themselves", async () => {
  process.env.CUBE_IMPERSONATORS = "cloudadmin11@apps.teamschools.org";
  process.env.CUBE_GROUP_MAP = JSON.stringify({
    "cloudadmin11@apps.teamschools.org": ["student-network"],
  });
  const securityContext = {
    cubeCloud: { username: "cloudadmin11@apps.teamschools.org" },
    iss: "cubecloud",
    email: { a: 1 }, // a pasted JSON object, not a string
  };

  const lines = await capturedEmulationLog(async () => {
    const groups = await cube.contextToGroups({ securityContext });
    assert.deepEqual(groups, ["student-network"]);
  });

  assert.deepEqual(lines, []);
});

test("contextToGroups: no security context at all is default-deny", async () => {
  assert.deepEqual(
    await cube.contextToGroups({ securityContext: undefined }),
    [],
  );
});

// --- Structural invariant: every securityContext.<field> a policy
// interpolates must be a key access.buildSecurityContext returns -----------
// src/cube/CLAUDE.md states this in prose: it is what makes the Object.assign
// overwrite in contextToGroups a COMPLETE one. A new `row_level` filter that
// interpolates a securityContext field buildSecurityContext doesn't return
// would silently reopen the Cube Cloud paste vector for that field alone —
// Object.assign can't overwrite a pasted value for a key it never sets. Prose
// can't enforce this; this test derives the actual set of interpolated field
// names from the model YAML on disk and checks it against
// buildSecurityContext's real return, so it fails the moment the two drift.

function listYamlFilesRecursive(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...listYamlFilesRecursive(full));
    } else if (entry.isFile() && /\.ya?ml$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

test("structural invariant: every securityContext.<field> interpolated in model/ is returned by access.buildSecurityContext", () => {
  const modelDir = path.join(__dirname, "model");
  const files = listYamlFilesRecursive(modelDir);
  assert.ok(
    files.length > 0,
    `no YAML files found under ${modelDir} — check __dirname resolution before trusting this test`,
  );

  const found = new Set();
  const pattern = /securityContext\.([a-zA-Z_][a-zA-Z0-9_]*)/g;
  // Cube Cloud shorthand identifiers ("Cube Cloud shorthand identifiers" in
  // CubePropContextTranspiler.js: userAttributes / user_attributes / groups)
  // are rewritten, INSIDE an access_policy only, into
  // securityContext.cubeCloud.<name> -- a destination the plain pattern above
  // never sees, since no literal "securityContext.<name>" token appears for
  // it. cubeCloud.* is where a pasted Cube Cloud Security Context is mirrored,
  // and contextToGroups's Object.assign overwrite in cube.js only overwrites
  // TOP-LEVEL keys -- so a row_level filter reading the shorthand's rewritten
  // destination (or reading securityContext.cubeCloud.* directly) would read
  // an attacker-pasted value that nothing overwrites, reopening the paste
  // vector for that field on the Cube Cloud surface alone. Requiring a "{"
  // immediately before the identifier is what keeps this from false-firing on
  // the legitimate "group:" / "groups:" access_policy YAML keys throughout
  // model/ (e.g. staff_pii.yml's "- group: staff-pii-all_in_scope") -- those
  // keys contain no interpolation brace at all, only a hypothetical
  // "{ userAttributes.foo }" does.
  const shorthandPattern = /\{\{?\s*(userAttributes|user_attributes|groups)\b/g;
  const shorthandHits = [];
  const cubeCloudHits = [];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const match of text.matchAll(pattern)) {
      found.add(match[1]);
    }
    for (const match of text.matchAll(shorthandPattern)) {
      shorthandHits.push(
        `${path.relative(modelDir, file)}: ${match[0].trim()}`,
      );
    }
    if (text.includes("securityContext.cubeCloud")) {
      cubeCloudHits.push(path.relative(modelDir, file));
    }
  }

  assert.deepEqual(
    shorthandHits,
    [],
    shorthandHits.length
      ? `Cube Cloud shorthand identifier(s) interpolated in an access_policy: ` +
          `${shorthandHits.join(", ")}. Cube's CubePropContextTranspiler rewrites ` +
          "userAttributes./user_attributes./groups. inside an access_policy into " +
          "securityContext.cubeCloud.<name> - cubeCloud.* is caller-pasted on the Cube " +
          "Cloud surface and is not covered by the Object.assign overwrite in " +
          "contextToGroups, so a policy reading it is a paste vector. Put the value in " +
          "buildSecurityContext and read it from the top level instead."
      : undefined,
  );

  assert.deepEqual(
    cubeCloudHits,
    [],
    cubeCloudHits.length
      ? `model/ reads securityContext.cubeCloud directly in: ${cubeCloudHits.join(", ")}. ` +
          "cubeCloud.* is caller-pasted on the Cube Cloud surface and is not covered by " +
          "the Object.assign overwrite in contextToGroups, so a policy reading it is a " +
          "paste vector. Put the value in buildSecurityContext and read it from the top " +
          "level instead."
      : undefined,
  );

  // A regex that silently matched nothing would make every assertion below
  // vacuously pass. Guard against that explicitly with a floor plausible for
  // the current model, rather than trusting an empty derived set. (Was 6
  // before the flat `student` group replaced tiered student-region/-school/
  // -network groups and dropped `region_key` from view YAML.)
  assert.ok(
    found.size >= 5,
    `expected at least 5 distinct securityContext.<field> tokens under ${modelDir}, ` +
      `found ${found.size}: ${[...found].sort().join(", ")}. Either the model ` +
      "lost its row_level filters, or the extraction regex broke.",
  );

  const contextKeys = new Set(
    Object.keys(access.buildSecurityContext(null, [], [], [])),
  );
  const missing = [...found].filter((key) => !contextKeys.has(key));
  assert.deepEqual(
    missing,
    [],
    missing.length
      ? `securityContext field(s) interpolated in model/ but NOT returned by ` +
          `access.buildSecurityContext: ${missing.join(", ")}. Add the field ` +
          "to buildSecurityContext's return in access.js — otherwise the " +
          "Cube Cloud Object.assign overwrite in contextToGroups cannot " +
          "neutralize a pasted value for it, reopening the paste vector for " +
          "that field alone."
      : undefined,
  );

  // Sanity check against the five fields known today (#4526 / Task 5b; was
  // six with `location_abbreviation` / `region_key` before the flat
  // `student` group replaced tiered student-region/-school/-network groups
  // with `allowed_student_abbreviations`). This is in addition to, not
  // instead of, the derived assertion above — it exists so a reader can see
  // at a glance what the model currently interpolates.
  const expected = [
    "allowed_abbreviations",
    "allowed_department_groups",
    "allowed_student_abbreviations",
    "job_function_level",
    "reportee_staff_keys",
  ];
  assert.deepEqual(
    [...found].sort(),
    expected,
    `model/ now interpolates a different securityContext field set than the five documented ` +
      `here: found ${[...found].sort().join(", ")}, expected ${expected.join(", ")}. If the ` +
      "'missing' assertion above passed, the new/removed field IS already covered by " +
      "buildSecurityContext - this list is a deliberate, human-reviewed sanity check, not a " +
      "second correctness gate. Update it to match once you've confirmed the change is " +
      "intentional.",
  );
});
