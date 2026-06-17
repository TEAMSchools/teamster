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

// Domain membership is derived from the cube-name prefix, not a static array —
// a query member is "<cube>.<member>", so the cube name is the prefix. Adding a
// new domain cube requires no cube.js change as long as it follows the naming
// convention: student-domain cube names start with "student", staff-domain with
// "staff" (see src/cube/CLAUDE.md naming rules).
const isStudentMember = (member) => member.startsWith("student");
const isStaffMember = (member) => member.startsWith("staff");

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

    // Local dev only: CUBE_GROUP_MAP bypasses Directory API.
    // Must never be set in Cube Cloud — see docs/guides/cube.md.
    if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
      try {
        const map = JSON.parse(process.env.CUBE_GROUP_MAP);
        const groups = (map[email] ?? []).filter((g) => g.startsWith("cube-"));
        groupCache.set(email, { groups, expiresAt: nextMidnightEastern() });
        return groups;
      } catch (err) {
        console.error("CUBE_GROUP_MAP is not valid JSON:", err.message);
        return [];
      }
    }

    // Check cache
    const cached = groupCache.get(email);
    if (cached && cached.expiresAt > Date.now()) return cached.groups;

    // Call Admin Directory API.
    // GOOGLE_DIRECTORY_SA_KEY: base64-encoded service account JSON with
    //   domain-wide delegation granted by GOOGLE_DIRECTORY_SA_SUBJECT.
    // GOOGLE_DIRECTORY_SA_SUBJECT: email of the Workspace admin that granted
    //   delegation (must be a super-admin in apps.teamschools.org).
    try {
      const { google } = require("googleapis");
      const auth = new google.auth.GoogleAuth({
        credentials: JSON.parse(
          Buffer.from(process.env.GOOGLE_DIRECTORY_SA_KEY, "base64").toString(),
        ),
        scopes: [
          "https://www.googleapis.com/auth/admin.directory.group.readonly",
        ],
        clientOptions: {
          subject: process.env.GOOGLE_DIRECTORY_SA_SUBJECT,
        },
      });
      const admin = google.admin({ version: "directory_v1", auth });

      let groups = [];
      let pageToken;
      do {
        const res = await admin.groups.list({ userKey: email, pageToken });
        groups = groups.concat(
          (res.data.groups ?? []).map((g) => (g.email ?? "").split("@")[0]),
        );
        pageToken = res.data.nextPageToken;
      } while (pageToken);

      const cubeGroups = groups.filter((g) => g.startsWith("cube-"));
      groupCache.set(email, {
        groups: cubeGroups,
        expiresAt: nextMidnightEastern(),
      });
      return cubeGroups;
    } catch (err) {
      console.error(`contextToGroups failed for ${email}:`, err);
      return []; // default deny on API failure
    }
  },

  queryRewrite: (query, { securityContext }) => {
    const email =
      securityContext?.email ??
      securityContext?.cubeCloud?.userAttributes?.email;
    const cached = email ? groupCache.get(email) : null;
    const groups = cached?.expiresAt > Date.now() ? cached.groups : [];

    if (!groups.includes("cube-access-student-data")) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter((d) => !isStudentMember(d)),
        measures: (query.measures ?? []).filter((m) => !isStudentMember(m)),
      };
    }

    // Location scope — evaluate in priority order
    const networkGroup = groups.find((g) => g.startsWith("cube-network-"));
    const regionGroup = groups.find((g) =>
      /^cube-region-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    );
    const schoolGroup = groups.find((g) =>
      /^cube-school-[a-z0-9][a-z0-9-]*-(?:detail|summary)$/.test(g),
    );

    let locationFilter = null;

    if (networkGroup) {
      // No location filter
    } else if (regionGroup) {
      const region = regionGroup
        .replace(/^cube-region-/, "")
        .replace(/-(?:detail|summary)$/, "");
      locationFilter = {
        member: "locations.region_key",
        operator: "equals",
        values: [region],
      };
    } else if (schoolGroup) {
      const slug = schoolGroup
        .replace(/^cube-school-/, "")
        .replace(/-(?:detail|summary)$/, "");
      locationFilter = {
        member: "locations.abbreviation",
        operator: "equals",
        values: [slug],
      };
    } else {
      // Default deny — no scope group
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
    }

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

    if (!groups.includes("cube-access-staff-data")) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter((d) => !isStaffMember(d)),
        measures: (query.measures ?? []).filter((m) => !isStaffMember(m)),
      };
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === process.env.CUBEJS_SQL_SUPER_USER &&
    new_user.endsWith("@apps.teamschools.org"),
};
