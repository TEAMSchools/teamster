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

// Naming convention drives security — no lists to maintain.
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
function withSyntheticGroups(cubeGroups) {
  const result = [...cubeGroups];
  if (cubeGroups.some((g) => g.endsWith("-detail")))
    result.push("detail-access");
  if (cubeGroups.some((g) => g.endsWith("-detail") || g.endsWith("-summary")))
    result.push("summary-access");
  return result;
}

module.exports = {
  driverFactory: () => ({
    type: "bigquery",
    database: "kipptaf_marts",
  }),

  contextToGroups: async ({ securityContext }) => {
    // Pass-through for JWT-embedded groups. Used in Cube Cloud playground
    // testing before the Directory API is configured. Remove once Directory
    // API is live and JWTs no longer carry group claims.
    const jwtGroups = securityContext?.groups;
    if (Array.isArray(jwtGroups) && jwtGroups.length > 0) {
      return jwtGroups.filter((g) => g.startsWith("cube-"));
    }

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
      return withSyntheticGroups(cubeGroups);
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

    // Org-hierarchy filter: inject segment defined in staff cube YAML.
    // Staff cubes and the reporting_chain segment are added in the follow-up
    // spec (blocked on #3729 — dim_staff_work_assignments.staff_key fix).
    const touchesStaffCube = [
      ...(query.dimensions ?? []),
      ...(query.measures ?? []),
    ].some((m) => isStaffMember(m));
    if (touchesStaffCube && !groups.includes("cube-access-staff-all")) {
      query = {
        ...query,
        segments: [...(query.segments ?? []), "staff.reporting_chain"],
      };
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === process.env.CUBEJS_SQL_SUPER_USER &&
    new_user.endsWith("@apps.teamschools.org"),
};
