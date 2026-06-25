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
//   - Students keep location-scoped detail/summary + a PII tier.

// A query member is "<view>.<member>"; the domain is the leading token.
const isStudentMember = (member) => member.startsWith("student");
const isStaffMember = (member) => member.startsWith("staff");

// Default-deny: an empty IN () matches no rows. Routed through the locations
// join present on every view (student and staff alike).
const DENY_FILTER = {
  member: "locations.abbreviation",
  operator: "equals",
  values: [],
};

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

// One column-visibility tier per sensitive staff scope. buildGroups emits the
// tier when its scope is anything other than "none". v1 only has PII columns +
// the staff-pii tier wired into a view; the compensation/observations/benefits
// tiers are emitted here too (forward-compat) but gate nothing until their
// cubes + views exist (no access_policy consumes them yet).
const STAFF_SENSITIVE_TIERS = [
  { scope: "staff_pii_scope", group: "staff-pii" },
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

// "detail" | "summary" | null — by the view-name suffix on the query's members.
function surfaceOf(query) {
  for (const m of queryMembers(query)) {
    const view = m.split(".")[0];
    if (view.endsWith("_detail")) return "detail";
    if (view.endsWith("_summary")) return "summary";
  }
  return null;
}

// Column-visibility tiers the views gate on. The staff directory + summary are
// open to every staff viewer (any resolved row), so a single staff-directory
// tier covers both staff views; a sensitive tier is added per *_scope != none.
function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  if (row.student_detail_location_scope !== "none") {
    groups.push("student-detail", "student-summary");
  } else if (row.student_summary_location_scope !== "none") {
    groups.push("student-summary");
  }
  if (row.student_pii_scope === "all") groups.push("student-pii");

  // Open staff directory + summary for every staff viewer.
  groups.push("staff-directory");
  for (const { scope, group } of STAFF_SENSITIVE_TIERS) {
    if (row[scope] && row[scope] !== "none") groups.push(group);
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

// The shared staff sensitive remit: location ∩ department. Returns
// { deny: true } when either axis denies, else { filters: [...] } (possibly []).
function staffRemit(row) {
  const loc = locationScopeFilter(
    row.staff_location_scope,
    row.region_key,
    row.location_abbreviation,
  );
  const dep = departmentScopeFilter(
    row.staff_department_scope,
    row.department_group,
  );
  if (loc.deny || dep.deny) return { deny: true };
  const filters = [];
  if (!loc.open) filters.push(loc.filter);
  if (!dep.open) filters.push(dep.filter);
  return { deny: false, filters };
}

// The row filter for a single sensitive scope value. Returns an array of
// filters to AND into the query ([] = no restriction; [DENY_FILTER] = deny).
function staffScopeFilter(scope, row, reporteeStaffKeys) {
  const chain = reporteeStaffKeys ?? [];
  const chainFilter = chain.length
    ? { member: "staff.staff_key", operator: "equals", values: chain }
    : null;

  switch (scope) {
    case "all_in_scope": {
      const remit = staffRemit(row);
      return remit.deny ? [DENY_FILTER] : remit.filters;
    }
    case "teaching_staff": {
      const remit = staffRemit(row);
      if (remit.deny) return [DENY_FILTER];
      return [
        ...remit.filters,
        {
          member: "staff.job_function_code",
          operator: "equals",
          values: ["TEACH", "TIR"],
        },
      ];
    }
    case "reporting_chain":
      return chainFilter ? [chainFilter] : [DENY_FILTER];
    case "reporting_chain_or_below_rank": {
      // (in scope ∩ ranked below me) ∪ my reporting chain. The reporting chain
      // is unbounded by location/department, so it survives even a deny remit.
      const branches = [];
      const remit = staffRemit(row);
      if (!remit.deny && row.job_function_level != null) {
        const and = [
          ...remit.filters,
          {
            member: "staff.job_function_level",
            operator: "gt",
            values: [String(row.job_function_level)],
          },
        ];
        branches.push(and.length === 1 ? and[0] : { and });
      }
      if (chainFilter) branches.push(chainFilter);
      if (!branches.length) return [DENY_FILTER];
      return [branches.length === 1 ? branches[0] : { or: branches }];
    }
    case "none":
    default:
      return [DENY_FILTER];
  }
}

// Row-conditional gating for the OPEN staff surface: a directory-only or
// summary query gets no filter; a staff_detail query touching sensitive
// field(s) is narrowed by the per-field scope of every requested sensitive
// field (intersection — most-restrictive wins). Summary-view occurrences of a
// sensitive leaf (e.g. staff_summary.race) are open aggregate breakdowns and
// are never gated.
function staffSensitiveFilters(query, row, reporteeStaffKeys) {
  const scopeCols = new Set();
  for (const m of queryMembers(query)) {
    const parts = m.split(".");
    const view = parts[0];
    const leaf = parts[parts.length - 1];
    if (!isStaffMember(m) || !view.endsWith("_detail")) continue;
    const scopeCol = STAFF_SENSITIVE_SCOPE_BY_MEMBER[leaf];
    if (scopeCol) scopeCols.add(scopeCol);
  }
  if (!scopeCols.size) return [];
  if (!row) return [DENY_FILTER];

  // Collect filters per scope column, then dedupe by JSON key so two scope
  // columns that resolve to the same remit filter (e.g. PII + compensation both
  // at all_in_scope school/all) don't inject the same location filter twice.
  const seen = new Set();
  const filters = [];
  for (const col of scopeCols) {
    for (const f of staffScopeFilter(row[col], row, reporteeStaffKeys)) {
      const key = JSON.stringify(f);
      if (!seen.has(key)) {
        seen.add(key);
        filters.push(f);
      }
    }
  }
  return filters;
}

module.exports = {
  isStudentMember,
  isStaffMember,
  queryMembers,
  surfaceOf,
  buildGroups,
  studentRowFilters,
  staffSensitiveFilters,
  STAFF_PII_MEMBERS,
  STAFF_SENSITIVE_SCOPE_BY_MEMBER,
  DENY_FILTER,
};
