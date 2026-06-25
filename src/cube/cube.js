const access = require("./access");

const groupCache = new Map(); // email → { groups, row, reporteeStaffKeys, expiresAt }

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

// All access-resolution logic (isStudentMember / isStaffMember, group building,
// per-surface row filters) lives in access.js (pure, unit-tested). cube.js owns
// only the BigQuery identity reads + cache below.

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

  contextToGroups: async ({ securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    if (!email) return [];

    // Local dev only: CUBE_GROUP_MAP bypasses the BigQuery reads, supplying the
    // column-visibility tiers directly. row stays null, so the queryRewrite
    // row filters default-deny — unset CUBE_GROUP_MAP to exercise real
    // row-level scoping against kipptaf_marts. Never set in Cube Cloud
    // (see docs/guides/cube.md).
    if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
      try {
        const map = JSON.parse(process.env.CUBE_GROUP_MAP);
        const groups = map[email] ?? [];
        groupCache.set(email, {
          groups,
          row: null,
          reporteeStaffKeys: [],
          expiresAt: nextMidnightEastern(),
        });
        return groups;
      } catch (err) {
        console.error("CUBE_GROUP_MAP is not valid JSON:", err.message);
        return [];
      }
    }

    const cached = groupCache.get(email);
    if (cached && cached.expiresAt > Date.now()) return cached.groups;

    // HR-derived access: resolve the viewer's email to their current-role
    // access row (dim_staff_cube_access) and their reporting chain
    // (dim_staff_reporting_chain). access.js turns these into Cube groups +
    // queryRewrite filters. No Google Admin Directory API.
    try {
      const { BigQuery } = require("@google-cloud/bigquery");
      const bq = new BigQuery();

      // 1. email → access row (one active+primary row, keyed on staff_key).
      const [accessRows] = await bq.query({
        query: `
          SELECT
            staff_key,
            region_key,
            location_abbreviation,
            department_group,
            job_function_level,
            student_summary_location_scope,
            student_detail_location_scope,
            student_pii_scope,
            staff_location_scope,
            staff_department_scope,
            staff_pii_scope,
            staff_compensation_scope,
            staff_observations_scope,
            staff_benefits_scope
          FROM kipptaf_marts.dim_staff_cube_access
          WHERE google_email = @email
          LIMIT 1`,
        params: { email },
      });
      const row = accessRows[0] ?? null;

      // 2. reporting chain (direct + indirect reports, incl. the depth-0 self
      //    pair) keyed on the resolved staff_key.
      let reporteeStaffKeys = [];
      if (row?.staff_key) {
        const [reporteeRows] = await bq.query({
          query: `
            SELECT reportee_staff_key
            FROM kipptaf_marts.dim_staff_reporting_chain
            WHERE manager_staff_key = @staffKey`,
          params: { staffKey: row.staff_key },
        });
        reporteeStaffKeys = reporteeRows.map((r) => r.reportee_staff_key);
      }

      const groups = access.buildGroups(row);
      groupCache.set(email, {
        groups,
        row,
        reporteeStaffKeys,
        expiresAt: nextMidnightEastern(),
      });
      return groups;
    } catch (err) {
      console.error(`contextToGroups failed for ${email}:`, err);
      return []; // default deny on failure
    }
  },

  queryRewrite: (query, { securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    const cached = email ? groupCache.get(email) : null;
    const fresh = cached && cached.expiresAt > Date.now() ? cached : null;
    const row = fresh?.row ?? null;
    const reporteeStaffKeys = fresh?.reporteeStaffKeys ?? [];
    const groups = fresh?.groups ?? [];

    // Strip student members entirely when the viewer has no student access.
    const hasStudentAccess =
      groups.includes("student-detail") || groups.includes("student-summary");
    if (!hasStudentAccess) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter(
          (d) => !access.isStudentMember(d),
        ),
        measures: (query.measures ?? []).filter(
          (m) => !access.isStudentMember(m),
        ),
      };
    }

    const members = access.queryMembers(query);
    const surface = access.surfaceOf(query);
    const filters = [...(query.filters ?? [])];

    if (members.some(access.isStudentMember)) {
      filters.push(...access.studentRowFilters(row, surface));
    }
    if (members.some(access.isStaffMember)) {
      filters.push(
        ...access.staffSensitiveFilters(query, row, reporteeStaffKeys),
      );
    }

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
