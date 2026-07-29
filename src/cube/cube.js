const access = require("./access");
const jwt = require("jsonwebtoken");
// CubejsHandlerError carries an HTTP status Cube's api-gateway honors; a bare
// Error from checkAuth becomes a 500. Resolved transitively from the bundled
// @cubejs-backend/server (not pinned in package.json, to avoid version skew).
const { CubejsHandlerError } = require("@cubejs-backend/api-gateway");

const groupCache = new Map(); // email → { ctx, expiresAt }

// Global (not per-email) cache of the "universes" computeAllowedAbbreviations
// / computeAllowedDepartmentGroups need: every location abbreviation+region
// and every distinct department_group. Same midnight-ET expiry as
// groupCache — one shared entry, not one per viewer.
let universeCache = null; // { data: { locations: [...], deptGroups: [...] }, expiresAt }

function nextMidnightEastern() {
  const now = new Date();
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hour12: false,
    })
      .formatToParts(now)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value }) => [type, +value]),
  );
  const msElapsedToday =
    (parts.hour * 3600 + parts.minute * 60 + parts.second) * 1000 +
    now.getMilliseconds();
  return now.getTime() + (24 * 60 * 60 * 1000 - msElapsedToday);
}

// All pure access-resolution logic (buildGroups, buildSecurityContext, the
// allow-list computations) lives in access.js (unit-tested). cube.js owns only
// the BigQuery identity reads + cache below.

// Fetches the domain-agnostic "universes" (all location abbreviations+regions,
// all distinct department groups) that access.computeAllowedAbbreviations /
// computeAllowedDepartmentGroups turn into per-viewer allow-lists. Cached
// globally (not per-email) until next midnight ET.
async function loadUniverses(bq) {
  if (universeCache && universeCache.expiresAt > Date.now())
    return universeCache.data;
  const [locs] = await bq.query({
    query: "SELECT abbreviation, region_key FROM `kipptaf_marts.dim_locations`",
  });
  // A NULL department_group can't be in the universe, and `department_group IN
  // (...)` never matches NULL — so a staff member with a NULL department_group
  // is invisible to every remit-scoped PII policy (fail-closed). Zero such rows
  // today; if that changes, backfill a sentinel group upstream.
  const [deps] = await bq.query({
    query:
      "SELECT DISTINCT department_group FROM `kipptaf_marts.dim_staff_cube_access` WHERE department_group IS NOT NULL",
  });
  const data = {
    locations: locs.map((r) => ({
      abbreviation: r.abbreviation,
      region_key: r.region_key,
    })),
    deptGroups: deps.map((r) => r.department_group),
  };
  universeCache = { data, expiresAt: nextMidnightEastern() };
  return data;
}

// Resolves a viewer's email to an enriched securityContext (access.js
// buildSecurityContext output, including `groups`). Shared by checkAuth
// (REST/MCP) and checkSqlAuth (SQL API) so both auth paths populate the same
// shape. Cached per-email until next midnight ET.
async function resolveAccess(email) {
  if (!email) return access.buildSecurityContext(null, []);
  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.ctx;

  // Local dev bypass (unchanged intent): CUBE_GROUP_MAP supplies groups only.
  if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
    const map = JSON.parse(process.env.CUBE_GROUP_MAP);
    const ctx = {
      ...access.buildSecurityContext(null, []),
      groups: map[email] ?? [],
    };
    groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
    return ctx;
  }

  try {
    const { BigQuery } = require("@google-cloud/bigquery");
    // Cube's data driver is configured via CUBEJS_DB_BQ_* and runs jobs in
    // teamster-332318. This hand-rolled client inherits none of that: a bare
    // `new BigQuery()` defaults to the Cube Cloud host project (cubejs-cloud),
    // where this identity has no bigquery.jobs.create — so every identity read
    // throws, resolveAccess fails closed, and the whole network is denied
    // (#4466). Pin the project + credentials to the driver's own config.
    // When CUBEJS_DB_BQ_CREDENTIALS is unset (e.g. local dev on ADC), fall back
    // to ADC like the BigQuery driver does, instead of JSON.parse("") throwing
    // and failing closed — which denies every viewer (#4526). Keep the projectId
    // pin so ADC bills teamster-332318, not the ambient Cube Cloud host project
    // (#4466).
    const bqOptions = { projectId: process.env.CUBEJS_DB_BQ_PROJECT_ID };
    if (process.env.CUBEJS_DB_BQ_CREDENTIALS) {
      bqOptions.credentials = JSON.parse(
        Buffer.from(process.env.CUBEJS_DB_BQ_CREDENTIALS, "base64").toString(
          "utf8",
        ),
      );
    }
    const bq = new BigQuery(bqOptions);
    const [rows] = await bq.query({
      query:
        "SELECT * FROM `kipptaf_marts.dim_staff_cube_access` WHERE google_email = @email ORDER BY staff_key LIMIT 1",
      params: { email },
    });
    const row = rows[0] ?? null;
    let reporteeStaffKeys = [];
    if (row?.staff_key) {
      const [rc] = await bq.query({
        query:
          "SELECT reportee_staff_key FROM `kipptaf_marts.dim_staff_reporting_chain` WHERE manager_staff_key = @k",
        params: { k: row.staff_key },
      });
      reporteeStaffKeys = rc.map((r) => r.reportee_staff_key);
    }
    const universes = await loadUniverses(bq);
    const allowedAbbreviations = access.computeAllowedAbbreviations(
      row?.staff_location_scope,
      row?.region_key,
      row?.location_abbreviation,
      universes.locations,
    );
    const allowedDepartmentGroups = access.computeAllowedDepartmentGroups(
      row?.staff_department_scope,
      row?.department_group,
      universes.deptGroups,
    );
    const ctx = access.buildSecurityContext(
      row,
      reporteeStaffKeys,
      allowedAbbreviations,
      allowedDepartmentGroups,
    );
    groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
    return ctx;
  } catch (err) {
    console.error(`resolveAccess failed for ${email}:`, err);
    return access.buildSecurityContext(null, []); // fail closed, stay available
  }
}

// Convention for snapshot cubes: cumulative daily flags that overcount without
// a point-in-time anchor. All snapshot cubes expose these three dimensions.
const SNAPSHOT_ANCHOR_DIMENSIONS = {
  default: "is_latest_record",
  month: "is_month_end_record",
  week: "is_week_end_record",
};

// Per-cube override of the no-granularity default anchor. Enrollment's default
// is the per-school period-end-as-of-now flag (is_current_record), not the
// per-student-last-day flag (is_latest_record = "served"). Falls back to
// SNAPSHOT_ANCHOR_DIMENSIONS for any cube not listed here, so attendance's
// resolved anchor map is byte-for-byte unchanged.
const SNAPSHOT_ANCHOR_OVERRIDES = {
  student_enrollments: { default: "is_current_record" },
};
const SNAPSHOT_SELF_ANCHORED_SUFFIXES = [
  "_year_end",
  "_month_end",
  "_week_end",
];

// Add a cube name here when it exposes is_latest_record / is_month_end_record
// / is_week_end_record and its measures need the anchor guard. Also add the
// cube's snapshot measure stems under the same key in SNAPSHOT_MEASURE_STEMS
// below — a cube in this list with no stems entry matches nothing (guard no-op).
const SNAPSHOT_CUBES = ["student_attendance", "student_enrollments"];

// Per-cube measure-name stems that mark a snapshot measure needing the
// period-end anchor guard. Keyed per cube (like SNAPSHOT_ANCHOR_OVERRIDES) so a
// stem matches ONLY its own cube — a flat shared list substring-matches across
// cubes (e.g. "count_students" would wrongly catch student_attendance's
// count_students too). Which measures need the guard, by cube:
//   student_attendance: chronic absence / ADA tiers / truancy are cumulative
//     daily flags (re-stamped each row) — count_distinct over a range without an
//     anchor overcounts. Its ADDITIVE measures (avg_daily_attendance,
//     count_students, pct_tardy, pct_ontime, count_absent_days) are NOT listed —
//     they are point-in-time safe and must stay unanchored.
//   student_enrollments: count_students is count_distinct(student_key) over the
//     attendance daily fact; a student enrolled across N in-session days appears
//     in N rows, so an unanchored count over a range overcounts — needs the guard.
// Both cubes' weekly trends are driven by a school_week_start_date grouping
// (PowerSchool school weeks), not Cube's ISO granularity: "week".
const SNAPSHOT_MEASURE_STEMS = {
  student_attendance: ["chronically_absent", "tier_1_2", "tier_3", "truant"],
  student_enrollments: ["count_students"],
};

// Turns a jsonwebtoken failure into a message that names the failed check, so a
// 403 is diagnosable without server access. jsonwebtoken reports both the maxAge
// cap and the token's own `exp` as TokenExpiredError, distinguished only by the
// message text — hence the string check rather than a type check.
function jwtRejectionReason(err) {
  if (err?.name === "TokenExpiredError") {
    return String(err.message).includes("maxAge")
      ? "Token too old: exceeds the 12h maxAge cap measured from `iat`. Re-mint it (in the Playground, clear localhost local storage or re-save the security context)."
      : "Token expired: past its own `exp`.";
  }
  if (err?.name === "JsonWebTokenError") {
    // Covers a bad signature, a wrong/absent CUBEJS_API_SECRET on this
    // deployment, a missing `iat` under maxAge, and alg:none. Naming the secret
    // matters: an unset one on a branch environment is the likeliest cause and
    // is otherwise invisible.
    return `Invalid token: ${err.message}. Check the signing secret matches this deployment's CUBEJS_API_SECRET, and that the token carries an \`iat\`.`;
  }
  return "Invalid token";
}

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

module.exports = {
  driverFactory: () => ({
    type: "bigquery",
    database: "kipptaf_marts",
  }),

  contextToGroups: async ({ securityContext }) => {
    // Cube Cloud bypasses checkAuth and injects its own context, so
    // resolveAccess never runs on this path and every gated view default-denied
    // for console users (#4526). Enrich it here.
    //
    // CRITICAL: Cube Cloud MERGES a pasted Security Context into the TOP LEVEL
    // of this object. Every top-level value is therefore caller-supplied and
    // untrusted — including `groups` itself and the `region_key` /
    // `allowed_abbreviations` / `allowed_department_groups` values the
    // access_policy row_level filters interpolate. A console user pasting
    // `{"groups": ["staff-pii-all_in_scope"], "allowed_abbreviations": [...]}`
    // was previously honored verbatim, because the old one-line
    // `securityContext?.groups ?? []` read straight from that merged object.
    //
    // So this ALWAYS re-derives and OVERWRITES, never conditionally on whether
    // `groups` is already present. resolveAccess's output covers every key any
    // policy interpolates, so assigning it over the top neutralizes anything
    // pasted. Do not reintroduce a `!securityContext.groups` guard here — that
    // is exactly the bypass.
    //
    // Emulation: `cubeCloud.username` is the authenticated console user; a
    // pasted target arrives as top-level `email` (also mirrored at
    // `cubeCloud.userAttributes.email`). The same admin gate as the REST
    // `act_as` path applies, so a non-impersonator's pasted email is ignored and
    // they resolve as themselves.
    //
    // TRUST NOTE for code-owner review: `cubeCloud.username` is asserted by Cube
    // Cloud, not verified by our own `jwt.verify`. Before this change console
    // identity was not load-bearing for data access; now Cube Cloud's console
    // authentication establishes identity for RLS. Deliberate, and on par with
    // the trust the SQL API places in the connecting user.
    //
    // Determinism matters: Cube caches the selected policies under a hash of
    // this context computed BEFORE the hook runs
    // (`CompilerApi.hashRequestContext`), so the same input must always produce
    // the same output. Re-deriving unconditionally is deterministic — the
    // per-email cache in resolveAccess makes re-entry cheap.
    const consoleUser = securityContext?.cubeCloud?.username ?? null;
    if (consoleUser) {
      const requestedTarget =
        securityContext.email ??
        securityContext.cubeCloud?.userAttributes?.email ??
        null;
      const { caller, target, emulating } = access.resolveEmulationTarget({
        callerEmail: consoleUser,
        requestedTarget,
        impersonators: access.parseImpersonators(
          process.env.CUBE_IMPERSONATORS,
        ),
      });
      if (emulating) logEmulation("cubecloud", caller, target);
      Object.assign(securityContext, await resolveAccess(target));
    }
    return securityContext?.groups ?? [];
  },

  checkAuth: async (req, auth) => {
    // `auth` is the raw bearer token STRING (a custom checkAuth replaces Cube's
    // default JWT verify+decode). Verify the HS256 signature against
    // CUBEJS_API_SECRET ourselves, then resolve identity from the email claim.
    // An invalid/expired token → clean 403 (see catch below). A request with no
    // Authorization header intentionally resolves to the empty default-deny
    // context (200 + zero rows), NOT a 403: the data is fully protected either
    // way, and this lets an unauthenticated capability probe get a no-access
    // context rather than an error. The 403 is reserved for a token that is
    // present but invalid.
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
        //
        // Say WHICH check failed. A single "Invalid token" for every failure is
        // what makes the maxAge cap a trap rather than a control: a Playground
        // token cached over 12h denies every view, and the symptom is
        // indistinguishable from a wrong secret or a missing one — so it reads as
        // an access-policy bug and costs an hour. The status stays 403 and the
        // control is unchanged; only the message differs. This leaks nothing
        // useful: a caller already knows their own token's age, and learning
        // "too old" versus "bad signature" does not help forge a signature.
        throw new CubejsHandlerError(
          403,
          "Forbidden",
          jwtRejectionReason(err),
          err,
        );
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
  },

  checkSqlAuth: async (req, user, password) => {
    const email =
      (process.env.NODE_ENV !== "production" &&
        process.env.CUBE_SQL_DEV_EMAIL) ||
      user;
    // Fail closed on an unset/blank SQL password: Cube validates the presented
    // password against the RETURNED one, so returning the env var unconditionally
    // would validate presented passwords against `undefined` when it is absent —
    // potentially accepting a blank-password connection. Return null to reject
    // every connection instead (Task 1 verdict: a null password rejects). The
    // REST path already fails closed here because jwt.verify throws on an absent
    // CUBEJS_API_SECRET.
    const sqlPassword = process.env.CUBEJS_SQL_PASSWORD;
    if (!sqlPassword) {
      console.error(
        "checkSqlAuth: CUBEJS_SQL_PASSWORD is not set — rejecting SQL API connection",
      );
      return {
        password: null,
        securityContext: access.buildSecurityContext(null, []),
      };
    }
    // Return the server-known SQL password (Cube's canonical checkSqlAuth
    // pattern). RLS identity is resolved from the connecting `user` (the email),
    // not from the presented password — which is absent on SET-USER re-auth
    // flows, so do not compare against it.
    return {
      password: sqlPassword,
      securityContext: await resolveAccess(email),
    };
  },

  queryRewrite: (query) => {
    const filters = [...(query.filters ?? [])];

    // Snapshot anchor guard: for cubes with cumulative daily flags, inject
    // the appropriate period-end anchor when the query has none.
    // Named measures (_year_end, _month_end, _week_end) have anchors baked in
    // but require matching granularity — _month_end without grouping by month
    // returns "CA at any month-end during the range," which is meaningless.
    for (const cubePrefix of SNAPSHOT_CUBES) {
      const stems = SNAPSHOT_MEASURE_STEMS[cubePrefix] ?? [];
      const measures = (query.measures ?? []).filter(
        (m) =>
          m.startsWith(cubePrefix) && stems.some((stem) => m.includes(stem)),
      );
      if (!measures.length) continue;

      const dateDayTd = (query.timeDimensions ?? []).find((td) =>
        td.dimension?.endsWith("dates_date_day"),
      );
      const granularity = dateDayTd?.granularity ?? null;

      const groupsBySchoolWeek = [
        ...(query.dimensions ?? []),
        ...(query.timeDimensions ?? []).map((td) => td.dimension),
      ].some((m) => m && m.split(".").pop() === "dates_school_week_start_date");

      // School weeks (PowerSchool week_start_monday, via dim_dates) replace Cube's
      // ISO week for snapshot measures: the *_week_end anchors are school-week-based,
      // so weekly trends MUST group by dates_school_week_start_date. Treat that
      // grouping as the "week" period; Cube's native granularity drives only day/month.
      const period = groupsBySchoolWeek ? "week" : granularity;

      if (granularity === "week" && !groupsBySchoolWeek) {
        throw new Error(
          "Weekly snapshot trends use school weeks — group by " +
            '<view>.dates_school_week_start_date, not Cube\'s granularity: "week" ' +
            "(ISO Monday weeks do not match PowerSchool school weeks).",
        );
      }

      // Named period-end measures must be grouped by the matching period.
      // Without it, the result is "CA at any period-end during the range."
      for (const { suffix, ok, hint } of [
        {
          suffix: "_month_end",
          ok: granularity === "month",
          hint: 'timeDimensions granularity: "month"',
        },
        {
          suffix: "_week_end",
          ok: groupsBySchoolWeek,
          hint: "a dates_school_week_start_date grouping",
        },
      ]) {
        if (measures.some((m) => m.endsWith(suffix)) && !ok) {
          throw new Error(
            `${suffix} measures must be grouped by ${hint}. Without it, the ` +
              `result counts students across all period-ends in the date range, ` +
              `not a per-period breakdown.`,
          );
        }
      }

      const hasUnanchoredMeasure = measures.some(
        (m) => !SNAPSHOT_SELF_ANCHORED_SUFFIXES.some((s) => m.endsWith(s)),
      );
      if (!hasUnanchoredMeasure) continue;

      if (granularity && !["day", "week", "month"].includes(granularity)) {
        throw new Error(
          `Snapshot measures (e.g. pct_chronically_absent) do not support ` +
            `"${granularity}" granularity. Use the day-level base measure, ` +
            `or the _week_end / _month_end named measures for week/month ` +
            `trends, or omit timeDimensions for a year-end snapshot.`,
        );
      }

      if (period === "day") continue;

      const anchorMap = {
        ...SNAPSHOT_ANCHOR_DIMENSIONS,
        ...(SNAPSHOT_ANCHOR_OVERRIDES[cubePrefix] ?? {}),
      };
      const anchorDimension = anchorMap[period] ?? anchorMap.default;
      const anchorMember = `${cubePrefix}.${anchorDimension}`;

      const alreadyAnchored =
        filters.some(
          (f) =>
            Object.values(anchorMap).some((d) => f.member?.endsWith(d)) &&
            f.operator === "equals" &&
            [true, "true", "1"].includes(f.values?.[0]),
        ) ||
        filters.some(
          (f) =>
            f.member?.endsWith("dates_date_day") &&
            f.operator === "equals" &&
            Array.isArray(f.values) &&
            f.values.length === 1,
        ) ||
        (query.dimensions ?? []).some((d) => d.endsWith("dates_date_day")) ||
        // A point-in-time pin expressed via timeDimensions counts as anchored
        // only when it is a single day — a single-element dateRange or
        // granularity "day". A wider dateRange with null granularity is NOT
        // anchored (injecting the period-end snapshot is correct there;
        // treating it as anchored would re-open the "ever-CA-in-range"
        // overcount). Reuse dateDayTd found above rather than re-scanning.
        // A single-day dateRange is either one element (["2025-01-15"], which
        // Cube treats as start === end) or two equal elements.
        (dateDayTd &&
          ((Array.isArray(dateDayTd.dateRange) &&
            (dateDayTd.dateRange.length === 1 ||
              dateDayTd.dateRange[0] === dateDayTd.dateRange[1])) ||
            dateDayTd.granularity === "day"));

      if (!alreadyAnchored) {
        filters.push({
          member: anchorMember,
          operator: "equals",
          values: [true],
        });
      }
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === process.env.CUBEJS_SQL_SUPER_USER &&
    new_user.endsWith("@apps.teamschools.org"),
};
