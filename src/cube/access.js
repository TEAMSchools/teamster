"use strict";

// Pure access-resolution helpers for cube.js. No I/O — unit-tested with
// `node --test src/cube/access.test.js`. cube.js owns the BigQuery reads +
// cache and calls these to translate a cached access row into Cube groups and
// per-query filters.
// See docs/superpowers/specs/2026-06-03-cube-security-redesign.md (refold-c):
//   - The staff directory and aggregate summary are OPEN to every staff viewer.
//   - Only sensitive staff fields are gated, by the shared remit
//     (staff_location_scope ∩ staff_department_scope) plus a per-field scope
//     enum. The remit constrains rows ONLY when a sensitive field is queried.
//   - Students have a single location-scoped tier: a viewer with a non-none
//     student_location_scope sees every student view and all fields, PII
//     included. Location is the only axis (no summary/detail or PII split).

// A query member is "<view>.<member>"; the domain is the leading token.
const isStudentMember = (member) => member.startsWith("student");
const isStaffMember = (member) => member.startsWith("staff");

// Sensitive staff-detail leaf → the access row's scope column that gates it.
// PII columns are live (staff_detail view exists). Compensation/observation/
// benefits members are registered here now (forward-compat) but gate nothing
// until their cubes + views are built — no access_policy consumes them yet.
const STAFF_SENSITIVE_SCOPE_BY_MEMBER = {
  personal_email: "staff_pii_scope",
  personal_cell_phone: "staff_pii_scope",
  birth_date: "staff_pii_scope",
  gender_identity: "staff_pii_scope",
  race: "staff_pii_scope",
  is_hispanic: "staff_pii_scope",
  salary: "staff_compensation_scope",
};

// The six sensitive columns excluded from the open staff directory tier (the
// access_policy excludes on staff_detail) and gated to staff-pii.
const STAFF_PII_MEMBERS = Object.keys(STAFF_SENSITIVE_SCOPE_BY_MEMBER);

// One column-visibility tier per forward-compat sensitive staff scope.
// buildGroups emits the tier when its scope is anything other than "none".
// These stay flat (unscoped) — no cubes/views consume them yet. staff_pii is
// handled explicitly in buildGroups as a scope-specific group.
const STAFF_SENSITIVE_TIERS = [
  { scope: "staff_compensation_scope", group: "staff-compensation" },
  { scope: "staff_observations_scope", group: "staff-observations" },
  { scope: "staff_benefits_scope", group: "staff-benefits" },
];

function queryMembers(query) {
  return [
    ...(query.dimensions ?? []),
    ...(query.measures ?? []),
    ...(query.timeDimensions ?? []).map((td) => td.dimension).filter(Boolean),
    ...(query.filters ?? []).map((f) => f.member).filter(Boolean),
  ];
}

// Column-visibility tiers the views gate on. The staff directory + summary are
// open to every staff viewer (any resolved row), so a single staff-directory
// tier covers both staff views; a sensitive tier is added per *_scope != none.
function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  // Student: one scope-specific group per non-none location scope
  // (student-region / student-school / student-network). Cube's canonical
  // group-based RLS — the group IS the row-level tier; each maps 1:1 to a view
  // access_policy. none → no group → default-deny.
  if (row.student_location_scope && row.student_location_scope !== "none") {
    groups.push(`student-${row.student_location_scope}`);
  }

  // Open staff directory for every resolved staff viewer.
  groups.push("staff-directory");

  // Staff PII: one scope-specific group per non-none pii scope, each carrying
  // its own row_level remit in staff_pii.yml.
  if (row.staff_pii_scope && row.staff_pii_scope !== "none") {
    groups.push(`staff-pii-${row.staff_pii_scope}`);
  }

  // Forward-compat sensitive tiers (no view consumes these yet) stay flat.
  for (const { scope, group } of STAFF_SENSITIVE_TIERS) {
    if (row[scope] && row[scope] !== "none") groups.push(group);
  }
  return groups;
}

// The set of school abbreviations a viewer may see staff/students at, given
// their location scope. `universe` = [{ abbreviation, region_key }, ...] (all
// locations). network → every abbreviation; region → abbreviations in the
// viewer's region; school → just the viewer's school; none/other → [] (deny).
function computeAllowedAbbreviations(
  locationScope,
  regionKey,
  locationAbbreviation,
  universe,
) {
  const all = universe ?? [];
  switch (locationScope) {
    case "network":
      return all.map((l) => l.abbreviation);
    case "region":
      return all
        .filter((l) => l.region_key === regionKey)
        .map((l) => l.abbreviation);
    case "school":
      return locationAbbreviation ? [locationAbbreviation] : [];
    default:
      return [];
  }
}

// The department groups a viewer may see, given their department scope.
// `universe` = all distinct department_group values. all → every group;
// own_group → just the viewer's group; none/other → [] (deny).
function computeAllowedDepartmentGroups(
  deptScope,
  departmentGroup,
  deptUniverse,
) {
  switch (deptScope) {
    case "all":
      return deptUniverse ?? [];
    case "own_group":
      return departmentGroup ? [departmentGroup] : [];
    default:
      return [];
  }
}

// Flattens the cached access row + reporting chain into the shape the
// policies interpolate. Pure and null-safe: an unresolved viewer (no cached
// row) gets empty groups/chain, not a thrown error. `email` is not a column on
// the access row — the caller (resolveAccess) adds it to the context.
// `allowedAbbreviations` / `allowedDepartmentGroups` are precomputed by the
// caller (resolveAccess) via computeAllowedAbbreviations /
// computeAllowedDepartmentGroups — domain-agnostic allow-lists later
// interpolated into access_policy row_level filters (Task 5b).
function buildSecurityContext(
  row,
  reporteeStaffKeys,
  allowedAbbreviations,
  allowedDepartmentGroups,
) {
  return {
    groups: buildGroups(row),
    student_location_scope: row?.student_location_scope ?? "none",
    staff_pii_scope: row?.staff_pii_scope ?? "none",
    region_key: row?.region_key ?? null,
    location_abbreviation: row?.location_abbreviation ?? null,
    department_group: row?.department_group ?? null,
    job_function_level: row?.job_function_level ?? null,
    reportee_staff_keys: reporteeStaffKeys ?? [],
    allowed_abbreviations: allowedAbbreviations ?? [],
    allowed_department_groups: allowedDepartmentGroups ?? [],
  };
}

module.exports = {
  isStudentMember,
  isStaffMember,
  queryMembers,
  buildGroups,
  buildSecurityContext,
  computeAllowedAbbreviations,
  computeAllowedDepartmentGroups,
  STAFF_PII_MEMBERS,
  STAFF_SENSITIVE_SCOPE_BY_MEMBER,
};
