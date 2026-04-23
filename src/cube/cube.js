const dbtCloudExtension = process.env.DBT_CLOUD_TOKEN
  ? require("@cubejs-backend/dbt-schema-extension-dbt-cloud")
  : null;

const groupCache = new Map(); // email → { groups, expiresAt }
const CACHE_TTL_MS = 5 * 60 * 1000;

module.exports = {
  ...(dbtCloudExtension ? { schemaExtensions: [dbtCloudExtension] } : {}),

  schemaVersion: ({ securityContext }) =>
    securityContext?.schemaVersion ?? "v1",

  contextToGroups: async ({ securityContext }) => {
    const email = securityContext?.email;
    if (!email) return [];

    // Local dev: CUBE_GROUP_MAP bypasses Directory API
    if (process.env.CUBE_GROUP_MAP) {
      const map = JSON.parse(process.env.CUBE_GROUP_MAP);
      return (map[email] ?? []).filter((g) => g.startsWith("cube-"));
    }

    // Check cache
    const cached = groupCache.get(email);
    if (cached && cached.expiresAt > Date.now()) return cached.groups;

    // Call Admin Directory API
    const { google } = require("googleapis");
    const auth = new google.auth.GoogleAuth({
      credentials: JSON.parse(
        Buffer.from(process.env.GOOGLE_DIRECTORY_SA_KEY, "base64").toString(),
      ),
      scopes: [
        "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
      ],
      clientOptions: { subject: "admin@apps.teamschools.org" },
    });
    const admin = google.admin({ version: "directory_v1", auth });

    let groups = [];
    let pageToken;
    do {
      const res = await admin.groups.list({ userKey: email, pageToken });
      groups = groups.concat(
        (res.data.groups ?? []).map((g) => g.email.split("@")[0]),
      );
      pageToken = res.data.nextPageToken;
    } while (pageToken);

    const cubeGroups = groups.filter((g) => g.startsWith("cube-"));
    groupCache.set(email, {
      groups: cubeGroups,
      expiresAt: Date.now() + CACHE_TTL_MS,
    });
    return cubeGroups;
  },

  queryRewrite: (query, { securityContext }) => {
    const groups = securityContext?.groups ?? [];

    // Location scope — evaluate in priority order
    const networkGroup = groups.find((g) => g.startsWith("cube-network-"));
    const regionGroup = groups.find((g) => /^cube-region-[^-]+-/.test(g));
    const schoolGroup = groups.find((g) => /^cube-school-[^-]+-/.test(g));

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
    const STAFF_CUBES = [
      "dim_staff",
      "fct_staff_attrition",
      "fct_staff_observations",
    ];
    const touchesStaffCube = [
      ...(query.dimensions ?? []),
      ...(query.measures ?? []),
    ].some((m) => STAFF_CUBES.some((c) => m.startsWith(c)));
    if (touchesStaffCube && !groups.includes("cube-access-staff-all")) {
      query.segments = [...(query.segments ?? []), "dim_staff.reporting_chain"];
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === "cube-superset-service" &&
    new_user.endsWith("@apps.teamschools.org"),
};
