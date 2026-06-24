"use strict";

// Pure access-resolution helpers for cube.js. No I/O — unit-tested with
// `node --test src/cube/access.test.js`. cube.js owns the BigQuery reads +
// cache and calls these to translate a cached access row into Cube groups and
// per-surface query filters. See docs/superpowers/specs/2026-06-03-cube-security-redesign.md.

// A query member is "<view>.<member>"; the domain is the leading token.
const isStudentMember = (member) => member.startsWith("student");
const isStaffMember = (member) => member.startsWith("staff");

// Default-deny: an empty IN () matches no rows. Routed through the locations
// join present on every view.
const DENY_FILTER = {
  member: "locations.abbreviation",
  operator: "equals",
  values: [],
};

// Staff PII members gated by staff_pii_scope (the only sensitive staff columns
// in v1; comp/observation members slot in here when those cubes are built).
const STAFF_PII_MEMBERS = [
  "personal_email",
  "personal_cell_phone",
  "birth_date",
  "gender_identity",
  "race",
  "is_hispanic",
];

function queryMembers(query) {
  return [
    ...(query.dimensions ?? []),
    ...(query.measures ?? []),
    ...(query.timeDimensions ?? []).map((td) => td.dimension).filter(Boolean),
    ...(query.filters ?? []).map((f) => f.member).filter(Boolean),
  ];
}

// "detail" | "summary" | null — by the view-name suffix on the query's members.
function surfaceOf(query) {
  for (const m of queryMembers(query)) {
    const view = m.split(".")[0];
    if (view.endsWith("_detail")) return "detail";
    if (view.endsWith("_summary")) return "summary";
  }
  return null;
}

// Column-visibility tiers the views gate on. One student + one staff tier set.
function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  if (row.student_detail_location_scope !== "none") {
    groups.push("cube-access-student-detail", "cube-access-student-summary");
  } else if (row.student_summary_location_scope !== "none") {
    groups.push("cube-access-student-summary");
  }
  if (row.student_pii_scope === "all") groups.push("cube-access-student-pii");

  // Staff detail exists whenever the org gate grants anything (the downline is
  // unioned regardless of location, so even a no-location manager sees detail).
  if (row.staff_detail_org_gate && row.staff_detail_org_gate !== "none") {
    groups.push("cube-access-staff-detail", "cube-access-staff-summary");
  } else if (row.staff_summary_location_scope !== "none") {
    groups.push("cube-access-staff-summary");
  }
  if (row.staff_pii_scope && row.staff_pii_scope !== "none") {
    groups.push("cube-access-staff-pii");
  }
  return groups;
}

// { filter } (push it) | { open: true } (no filter) | { deny: true } (none).
function locationScopeFilter(level, regionKey, abbreviation) {
  switch (level) {
    case "network":
      return { open: true };
    case "region":
      return {
        filter: {
          member: "locations.region_key",
          operator: "equals",
          values: [regionKey],
        },
      };
    case "school":
      return {
        filter: {
          member: "locations.abbreviation",
          operator: "equals",
          values: [abbreviation],
        },
      };
    default:
      return { deny: true };
  }
}

function departmentScopeFilter(scope, departmentGroup) {
  if (scope === "all") return { open: true };
  if (scope === "own_group")
    return {
      filter: {
        member: "staff.department_group",
        operator: "equals",
        values: [departmentGroup],
      },
    };
  return { deny: true };
}

function studentRowFilters(row, surface) {
  if (!row) return [DENY_FILTER];
  const level =
    surface === "detail"
      ? row.student_detail_location_scope
      : row.student_summary_location_scope;
  const loc = locationScopeFilter(
    level,
    row.region_key,
    row.location_abbreviation,
  );
  if (loc.deny) return [DENY_FILTER];
  return loc.open ? [] : [loc.filter];
}

function staffSummaryFilters(row) {
  const loc = locationScopeFilter(
    row.staff_summary_location_scope,
    row.region_key,
    row.location_abbreviation,
  );
  const dep = departmentScopeFilter(
    row.staff_summary_department_scope,
    row.department_group,
  );
  if (loc.deny || dep.deny) return [DENY_FILTER];
  const filters = [];
  if (!loc.open) filters.push(loc.filter);
  if (!dep.open) filters.push(dep.filter);
  return filters;
}

function staffDetailFilters(row, reporteeStaffKeys) {
  const gate = row.staff_detail_org_gate;
  const includeScope =
    gate === "all_in_scope" || gate === "below_rank_or_downline";
  const includeDownline =
    gate === "downline_only" || gate === "below_rank_or_downline";
  const branches = [];

  if (includeScope) {
    const loc = locationScopeFilter(
      row.staff_detail_location_scope,
      row.region_key,
      row.location_abbreviation,
    );
    const dep = departmentScopeFilter(
      row.staff_detail_department_scope,
      row.department_group,
    );
    if (!loc.deny && !dep.deny) {
      const and = [];
      if (!loc.open) and.push(loc.filter);
      if (!dep.open) and.push(dep.filter);
      if (gate === "below_rank_or_downline") {
        and.push({
          member: "staff.job_function_level",
          operator: "gt",
          values: [String(row.job_function_level)],
        });
      }
      // Unrestricted scope (e.g. all_in_scope + network + all-dept) → all rows.
      if (and.length === 0) return [];
      branches.push(and.length === 1 ? and[0] : { and });
    }
  }

  if (includeDownline && reporteeStaffKeys.length) {
    branches.push({
      member: "staff.staff_key",
      operator: "equals",
      values: reporteeStaffKeys,
    });
  }

  if (branches.length === 0) return [DENY_FILTER];
  if (branches.length === 1) return [branches[0]];
  return [{ or: branches }];
}

function staffRowFilters(row, reporteeStaffKeys, surface) {
  if (!row) return [DENY_FILTER];
  return surface === "detail"
    ? staffDetailFilters(row, reporteeStaffKeys ?? [])
    : staffSummaryFilters(row);
}

// Row-conditional column visibility: when a sensitive staff column scoped to
// reporting_chain / teaching_staff is requested, narrow the query's rows.
function staffColumnNarrowing(query, row, reporteeStaffKeys) {
  if (!row) return [];
  const requestsPii = queryMembers(query).some((m) =>
    STAFF_PII_MEMBERS.includes(m.split(".").pop()),
  );
  if (!requestsPii) return [];
  if (row.staff_pii_scope === "reporting_chain") {
    return (reporteeStaffKeys ?? []).length
      ? [
          {
            member: "staff.staff_key",
            operator: "equals",
            values: reporteeStaffKeys,
          },
        ]
      : [DENY_FILTER];
  }
  if (row.staff_pii_scope === "teaching_staff") {
    return [
      {
        member: "staff.job_function_code",
        operator: "equals",
        values: ["TEACH", "TIR"],
      },
    ];
  }
  return [];
}

module.exports = {
  isStudentMember,
  isStaffMember,
  queryMembers,
  surfaceOf,
  buildGroups,
  studentRowFilters,
  staffRowFilters,
  staffColumnNarrowing,
  STAFF_PII_MEMBERS,
  DENY_FILTER,
};
