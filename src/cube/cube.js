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

// STUDENT_CUBES: cubes that require cube-access-student-data.
// TODO: populate full list during YAML implementation (follow-up to PR #3715).
const STUDENT_CUBES = [
  "fct_student_attendance_daily",
  "fct_student_attendance_interventions",
];

const STAFF_CUBES = [
  "dim_staff",
  "fct_staff_attrition",
  "fct_staff_observations",
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

    // Users without cube-access-student-data see no student cubes.
    // STUDENT_CUBES list is a placeholder — full list added during YAML implementation.
    if (!groups.includes("cube-access-student-data")) {
      query = {
        ...query,
        dimensions: (query.dimensions ?? []).filter(
          (d) => !STUDENT_CUBES.some((c) => d.startsWith(c)),
        ),
        measures: (query.measures ?? []).filter(
          (m) => !STUDENT_CUBES.some((c) => m.startsWith(c)),
        ),
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
        member: "dim_locations.region_key",
        operator: "equals",
        values: [region],
      };
    } else if (schoolGroup) {
      const slug = schoolGroup
        .replace(/^cube-school-/, "")
        .replace(/-(?:detail|summary)$/, "");
      locationFilter = {
        member: "dim_locations.abbreviation",
        operator: "equals",
        values: [slug],
      };
    } else {
      // Default deny — no scope group
      return {
        ...query,
        filters: [
          {
            member: "dim_locations.abbreviation",
            operator: "equals",
            values: [],
          },
        ],
      };
    }

    const filters = [...(query.filters ?? [])];
    if (locationFilter) filters.push(locationFilter);

    // Org-hierarchy filter: inject segment defined in staff cube YAML.
    // Staff cubes and the reporting_chain segment are added in the follow-up
    // spec (blocked on #3729 — dim_staff_work_assignments.staff_key fix).
    const touchesStaffCube = [
      ...(query.dimensions ?? []),
      ...(query.measures ?? []),
    ].some((m) => STAFF_CUBES.some((c) => m.startsWith(c)));
    if (touchesStaffCube && !groups.includes("cube-access-staff-all")) {
      query = {
        ...query,
        segments: [...(query.segments ?? []), "dim_staff.reporting_chain"],
      };
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === process.env.CUBEJS_SQL_SUPER_USER &&
    new_user.endsWith("@apps.teamschools.org"),
};
