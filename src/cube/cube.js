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
    const bq = new BigQuery();
    const [rows] = await bq.query({
      query:
        "SELECT * FROM `kipptaf_marts.dim_staff_cube_access` WHERE google_email = @email LIMIT 1",
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

module.exports = {
  driverFactory: () => ({
    type: "bigquery",
    database: "kipptaf_marts",
  }),

  contextToGroups: async ({ securityContext }) => securityContext?.groups ?? [],

  checkAuth: async (req, auth) => {
    // `auth` is the raw bearer token STRING (a custom checkAuth replaces Cube's
    // default JWT verify+decode). Verify the HS256 signature against
    // CUBEJS_API_SECRET ourselves, then resolve identity from the email claim.
    // An invalid/expired token → clean 403 (see catch below). A request with no
    // Authorization header resolves to the empty default-deny context.
    let email;
    if (auth) {
      try {
        // maxAge is a defense-in-depth cap independent of the token's own
        // `exp`: it derives from `iat` (issued-at) instead, so a compromised
        // or misconfigured minter can't extend a token's life by inflating
        // `exp` alone — jsonwebtoken rejects any token missing `iat` once
        // maxAge is set (fails closed). `mcp/server.py`'s `_mint_token` sets
        // both `iat` and a 5-minute `exp`, so this 12h ceiling is a backstop,
        // not the primary control.
        const payload = jwt.verify(auth, process.env.CUBEJS_API_SECRET, {
          algorithms: ["HS256"],
          maxAge: "12h",
        });
        email = payload?.email;
      } catch (err) {
        // Mirror Cube's default checkAuth: a bad/expired token is a clean 403,
        // not a bare-Error 500 (only CubejsHandlerError carries a status).
        throw new CubejsHandlerError(403, "Forbidden", "Invalid token", err);
      }
    }
    req.securityContext = await resolveAccess(email);
  },

  checkSqlAuth: async (req, user, password) => {
    const email =
      (process.env.NODE_ENV !== "production" &&
        process.env.CUBE_SQL_DEV_EMAIL) ||
      user;
    // Cube validates the presented password against the RETURNED one — returning
    // null rejects every connection (Task 1 verdict). Return the server-known
    // SQL password (Cube's canonical checkSqlAuth pattern); RLS identity comes
    // from securityContext.email, not the SQL user. `password` (the presented
    // value) is absent on SET-USER re-auth flows, so do not compare against it.
    return {
      password: process.env.CUBEJS_SQL_PASSWORD,
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
