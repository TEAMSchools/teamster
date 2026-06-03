const groupCache = new Map(); // email → { groups, expiresAt }

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

// Naming convention drives security — no static lists to maintain.
// student cubes: name starts with "student" (students, student_attendance, etc.)
// staff cubes:   name starts with "staff"   (staff, staff_attrition, etc.)
// conformed dims: bare business name (dates, locations, regions, terms, school_calendars)
function isStudentMember(m) {
  return m.startsWith("student");
}
function isStaffMember(m) {
  return m.startsWith("staff");
}

// Emit synthetic access groups so view access_policy blocks can gate on
// detail vs summary independently of the specific school/region group.
// These are NOT cached — derived fresh from the cached real groups on each
// contextToGroups call so the cache stays clean for queryRewrite lookups.
//
// Tier is derived from the SAME effective scope group that queryRewrite uses
// (network > region > school). A lower-priority detail group cannot escalate
// access beyond what the effective scope grants.
function withSyntheticGroups(cubeGroups) {
  const result = [...cubeGroups];
  const effectiveScope =
    cubeGroups.find((g) => g.startsWith("cube-network-")) ??
    cubeGroups.find((g) =>
      /^cube-region-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    ) ??
    cubeGroups.find((g) =>
      /^cube-school-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    );
  if (effectiveScope?.endsWith("-detail")) result.push("detail-access");
  if (
    effectiveScope?.endsWith("-detail") ||
    effectiveScope?.endsWith("-summary")
  )
    result.push("summary-access");
  return result;
}

// Convention for snapshot cubes: cumulative daily flags that overcount without
// a point-in-time anchor. All snapshot cubes expose these three dimensions.
const SNAPSHOT_ANCHOR_DIMENSIONS = {
  default: "is_latest_record",
  month: "is_month_end_record",
  week: "is_week_end_record",
};
const SNAPSHOT_SELF_ANCHORED_SUFFIXES = [
  "_year_end",
  "_month_end",
  "_week_end",
];

// Add a cube name here when it exposes is_latest_record / is_month_end_record
// / is_week_end_record and its measures need the anchor guard. Also add the
// cube's snapshot measure stems to SNAPSHOT_MEASURE_STEMS below — both arrays
// must stay in sync or the guard won't match the new cube's measures.
const SNAPSHOT_CUBES = ["student_attendance"];

// Measure-name stems that mark a snapshot (cumulative-daily-flag) measure
// family — chronic absence, ADA tiers, and truancy. Only these need the
// period-end anchor guard. Additive measures on the same cube
// (avg_daily_attendance, count_students, pct_tardy, pct_ontime,
// count_absent_days) are point-in-time safe and must be left untouched, so the
// guard must NOT match every measure that starts with a snapshot cube name.
const SNAPSHOT_MEASURE_STEMS = [
  "chronically_absent",
  "tier_1_2",
  "tier_3",
  "truant",
];

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

    // Local dev only: CUBE_GROUP_MAP bypasses BigQuery lookup.
    // Must never be set in Cube Cloud — see docs/guides/cube.md.
    if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
      try {
        const map = JSON.parse(process.env.CUBE_GROUP_MAP);
        const groups = (map[email] ?? []).filter((g) => g.startsWith("cube-"));
        groupCache.set(email, {
          groups,
          location_scope: "network",
          location_scope_key: null,
          expiresAt: nextMidnightEastern(),
        });
        return withSyntheticGroups(groups);
      } catch (err) {
        console.error("CUBE_GROUP_MAP is not valid JSON:", err.message);
        return [];
      }
    }

    // Check cache
    const cached = groupCache.get(email);
    if (cached && cached.expiresAt > Date.now())
      return withSyntheticGroups(cached.groups);

    // Query BigQuery for access config from dim_staff_cube_access.
    // Replaces Google Admin Directory API — see spec 2026-06-03-cube-security-redesign.
    try {
      const { BigQuery } = require("@google-cloud/bigquery");
      const bq = new BigQuery();
      const [rows] = await bq.query({
        query: `
          SELECT
            student_access_level,
            staff_access_level,
            student_pii,
            staff_pii,
            staff_compensation,
            staff_benefits,
            location_scope,
            location_scope_key
          FROM kipptaf_marts.dim_staff_cube_access
          WHERE staff_google_email = @email
          LIMIT 1
        `,
        params: { email },
        types: { email: "STRING" },
      });

      const row = rows[0] ?? null;
      const groups = [];

      if (row) {
        if (row.student_access_level === "detail")
          groups.push("cube-access-student-detail");
        else if (row.student_access_level === "summary")
          groups.push("cube-access-student-summary");

        if (row.staff_access_level === "detail")
          groups.push("cube-access-staff-detail");
        else if (row.staff_access_level === "summary")
          groups.push("cube-access-staff-summary");

        if (row.student_pii) groups.push("cube-access-student-pii");
        if (row.staff_pii) groups.push("cube-access-staff-pii");
        if (row.staff_compensation)
          groups.push("cube-access-staff-compensation");
        if (row.staff_benefits) groups.push("cube-access-staff-benefits");
      }

      groupCache.set(email, {
        groups,
        location_scope: row?.location_scope ?? null,
        location_scope_key: row?.location_scope_key ?? null,
        expiresAt: nextMidnightEastern(),
      });

      return withSyntheticGroups(groups);
    } catch (err) {
      console.error(`contextToGroups failed for ${email}:`, err);
      return []; // default deny on lookup failure
    }
  },

  queryRewrite: (query, { securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    const cached = email ? groupCache.get(email) : null;
    const groups = cached?.expiresAt > Date.now() ? cached.groups : [];
    const locationScope =
      cached?.expiresAt > Date.now() ? cached.location_scope : null;
    const locationKey =
      cached?.expiresAt > Date.now() ? cached.location_scope_key : null;

    // Student domain gate — strip student members for users without student access.
    if (
      !groups.includes("cube-access-student-detail") &&
      !groups.includes("cube-access-student-summary")
    ) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter((d) => !isStudentMember(d)),
        measures: (query.measures ?? []).filter((m) => !isStudentMember(m)),
      };
    }

    // Staff domain gate — strip staff members for users without staff access.
    if (
      !groups.includes("cube-access-staff-detail") &&
      !groups.includes("cube-access-staff-summary")
    ) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter((d) => !isStaffMember(d)),
        measures: (query.measures ?? []).filter((m) => !isStaffMember(m)),
      };
    }

    // Location scope — read from cache populated by contextToGroups.
    let locationFilter = null;

    if (!locationScope) {
      // User not in dim_staff_cube_access — default deny.
      return {
        ...query,
        filters: [
          {
            member: "locations.abbreviation",
            operator: "equals",
            values: [],
          },
        ],
      };
    } else if (locationScope === "region") {
      locationFilter = {
        member: "locations.region_key",
        operator: "equals",
        values: [locationKey],
      };
    } else if (locationScope === "school") {
      locationFilter = {
        member: "locations.abbreviation",
        operator: "equals",
        values: [locationKey],
      };
    }
    // locationScope === 'network' → no filter

    const filters = [...(query.filters ?? [])];
    if (locationFilter) filters.push(locationFilter);

    // Snapshot anchor guard: for cubes with cumulative daily flags, inject
    // the appropriate period-end anchor when the query has none.
    // Named measures (_year_end, _month_end, _week_end) have anchors baked in
    // but require matching granularity — _month_end without grouping by month
    // returns "CA at any month-end during the range," which is meaningless.
    for (const cubePrefix of SNAPSHOT_CUBES) {
      const measures = (query.measures ?? []).filter(
        (m) =>
          m.startsWith(cubePrefix) &&
          SNAPSHOT_MEASURE_STEMS.some((stem) => m.includes(stem)),
      );
      if (!measures.length) continue;

      const dateDayTd = (query.timeDimensions ?? []).find((td) =>
        td.dimension?.endsWith("dates_date_day"),
      );
      const granularity = dateDayTd?.granularity ?? null;

      // Named period-end measures must be grouped by the matching granularity.
      // Without it, the result is "CA at any period-end during the range."
      for (const [suffix, required] of [
        ["_month_end", "month"],
        ["_week_end", "week"],
      ]) {
        if (
          measures.some((m) => m.endsWith(suffix)) &&
          granularity !== required
        ) {
          throw new Error(
            `${suffix} measures must be grouped by ${required} — add ` +
              `timeDimensions with granularity: "${required}". Without it, ` +
              `the result counts students across all ${required}-ends in the ` +
              `date range, not a per-${required} breakdown.`,
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

      if (granularity === "day") continue;

      const anchorDimension =
        SNAPSHOT_ANCHOR_DIMENSIONS[granularity] ??
        SNAPSHOT_ANCHOR_DIMENSIONS.default;
      const anchorMember = `${cubePrefix}.${anchorDimension}`;

      const alreadyAnchored =
        filters.some(
          (f) =>
            Object.values(SNAPSHOT_ANCHOR_DIMENSIONS).some((d) =>
              f.member?.endsWith(d),
            ) &&
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
