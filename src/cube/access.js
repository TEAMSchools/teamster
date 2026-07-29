"use strict";

// Pure access-resolution helpers for cube.js. No I/O — unit-tested with
// `node --test src/cube/access.test.js`. cube.js does the BigQuery reads +
// caching and calls these to translate a resolved access row into the Cube
// groups + flat securityContext that per-view access_policy interpolates.
// Row-level security lives in the view access_policy blocks (see
// src/cube/CLAUDE.md "View access policies"), NOT here — this file only shapes
// identity into groups + allow-list arrays. Model:
//   - Students are location-scoped: a single `student` group is emitted
//     whenever the viewer's allowed_student_abbreviations array is non-empty;
//     the matching view policy filters rows with an abbreviation IN that
//     array. The array is the viewer's base student_location_scope UNIONED
//     with every individual-exception grant that has includes_student_data
//     (see unionAdditionalGrants) — this is what lets an exception grant a
//     single extra school, not just a whole network/region tier.
//   - The staff directory is OPEN (staff-directory group, every resolved
//     viewer); sensitive staff PII is gated in the staff_pii view per
//     staff_pii_scope (staff-pii-<scope>), scoped by a location ∩ department
//     remit precomputed into allowed_abbreviations / allowed_department_groups.
//     allowed_abbreviations is likewise the base staff_location_scope UNIONED
//     with every individual-exception grant — unconditionally, regardless of
//     includes_student_data (a location grant always widens staff visibility;
//     includes_student_data only decides whether it ALSO widens student
//     visibility).

// Sensitive staff leaf → the access-row scope column that gates it. The PII
// members live in the staff_pii view; compensation is registered here
// (forward-compat) but gates nothing until its cube + view are built.
const STAFF_SENSITIVE_SCOPE_BY_MEMBER = {
  personal_email: "staff_pii_scope",
  personal_cell_phone: "staff_pii_scope",
  birth_date: "staff_pii_scope",
  gender_identity: "staff_pii_scope",
  race: "staff_pii_scope",
  is_hispanic: "staff_pii_scope",
  salary: "staff_compensation_scope",
};

// The sensitive staff columns kept out of the open staff_directory view. Each
// maps to its gating scope column in STAFF_SENSITIVE_SCOPE_BY_MEMBER — the six
// PII fields to staff_pii_scope (surfaced in staff_pii), salary to
// staff_compensation_scope (forward-compat; no view yet). Not PII-only, so not
// named *_PII_*.
const STAFF_SENSITIVE_MEMBERS = Object.keys(STAFF_SENSITIVE_SCOPE_BY_MEMBER);

// One column-visibility tier per forward-compat sensitive staff scope.
// buildGroups emits the tier when its scope is anything other than "none".
// These stay flat (unscoped) — no cubes/views consume them yet. staff_pii is
// handled explicitly in buildGroups as a scope-specific group.
const STAFF_SENSITIVE_TIERS = [
  { scope: "staff_compensation_scope", group: "staff-compensation" },
  { scope: "staff_observations_scope", group: "staff-observations" },
  { scope: "staff_benefits_scope", group: "staff-benefits" },
];

// Column-visibility tiers the views gate on. The staff directory is open to
// every resolved staff identity, so a single staff-directory tier covers it; a
// sensitive tier is added per *_scope != none.
function buildGroups(
  row,
  allowedAbbreviations = [],
  allowedDepartmentGroups = [],
  reporteeStaffKeys = [],
  allowedStudentAbbreviations = [],
) {
  // Gate on a real identity: a row with no staff_key (a stray {} or an
  // object-shaped lookup miss) is not a resolved viewer and must get no groups
  // — default-deny. staff_key is the not-null PK, so every genuine row has one.
  if (!row?.staff_key) return [];
  const groups = [];

  // Student: a single `student` group, gated on the precomputed
  // allowed_student_abbreviations array being non-empty — same empty-array
  // guard as staff-pii-* below (Cube (Tesseract) throws "Values required for
  // filter" on an `equals []` row_level filter rather than compiling to zero
  // rows, #4269), not three separate tier groups. This is what lets an
  // individual-exception grant add one specific extra school for a viewer
  // whose base student_location_scope is narrower (or none) — a tier group
  // could only ever express "my whole region/network," never "my region plus
  // this one other school."
  if (allowedStudentAbbreviations.length > 0) {
    groups.push("student");
  }

  // Open staff directory for every resolved staff viewer.
  groups.push("staff-directory");

  // Staff PII: emit the scope-specific group ONLY when the securityContext
  // arrays its staff_pii.yml access_policy interpolates are non-empty. Cube
  // (Tesseract) throws "Values required for filter" on an `equals []` row_level
  // filter — it does NOT compile it to IN () / zero rows (verified empirically,
  // #4269). So a scope whose remit/chain resolved empty must not emit its group;
  // the viewer then takes the clean no-group → default-deny path instead of
  // hitting a hard query error. Empty remit is a resolution bug (a dbt test
  // guards it), so this is defense-in-depth, not expected state.
  const hasRemit =
    allowedAbbreviations.length > 0 && allowedDepartmentGroups.length > 0;
  const hasChain = reporteeStaffKeys.length > 0;
  switch (row.staff_pii_scope) {
    case "all_in_scope":
    case "teaching_staff":
      // Policies AND both remit axes with no fallback.
      if (hasRemit) groups.push(`staff-pii-${row.staff_pii_scope}`);
      break;
    case "reporting_chain":
      // Policy filters staff_key IN reportee_staff_keys — empty chain errors.
      if (hasChain) groups.push("staff-pii-reporting_chain");
      break;
    case "reporting_chain_or_below_rank":
      // OR of (remit + rank) and the staff_key chain — emit if either side is
      // satisfiable. TODO(#4403): a non-empty chain with an empty remit still
      // injects an empty `equals []` into the OR's nested AND-branch, which may
      // itself error; nested empty-array behavior is unverified. Revisit if that
      // mixed state becomes reachable (no such viewer in current data).
      if (hasRemit || hasChain) {
        groups.push("staff-pii-reporting_chain_or_below_rank");
      }
      break;
    default:
      break; // none / unrecognized → no staff-pii group (default-deny)
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
      // A null regionKey must not match locations whose region_key is also null
      // (=== would treat null === null as a match). No region → no abbreviations.
      return regionKey == null
        ? []
        : all
            .filter((l) => l.region_key === regionKey)
            .map((l) => l.abbreviation);
    case "school":
      return locationAbbreviation ? [locationAbbreviation] : [];
    default:
      return [];
  }
}

// Unions a base allow-list of abbreviations with every individual-exception
// location grant on the row (dim_staff_cube_access.additional_location_grants
// — an array of { location_scope, region_key, location_abbreviation,
// includes_student_data } structs, one per live grant; empty when the person
// has none). Each grant is resolved through the same computeAllowedAbbreviations
// used for the base scope, so a `network` grant contributes every abbreviation,
// a `region` grant contributes that region's abbreviations, and a `school`
// grant contributes just that one school — exactly the mechanism that lets an
// exception add a single specific extra location rather than only widening to
// a whole tier. Pass `studentOnly: true` to only union grants where
// includes_student_data is true (used for the student remit); omit it (the
// staff remit) to union every grant unconditionally — a location grant always
// widens staff visibility regardless of includes_student_data.
function unionAdditionalGrants(
  baseAbbreviations,
  grants,
  universe,
  { studentOnly = false } = {},
) {
  const result = new Set(baseAbbreviations ?? []);
  for (const grant of grants ?? []) {
    if (studentOnly && !grant.includes_student_data) continue;
    for (const abbreviation of computeAllowedAbbreviations(
      grant.location_scope,
      grant.region_key,
      grant.location_abbreviation,
      universe,
    )) {
      result.add(abbreviation);
    }
  }
  return [...result];
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
// row) gets empty groups/chain, not a thrown error. Identity is resolved from
// the connecting user / email claim in cube.js; `email` is intentionally NOT
// stored on the returned context (no access_policy interpolates it — do not add
// a policy referencing securityContext.email without first setting it here).
// `allowedAbbreviations` / `allowedDepartmentGroups` / `allowedStudentAbbreviations`
// are precomputed by the caller (resolveAccess) via computeAllowedAbbreviations /
// computeAllowedDepartmentGroups / unionAdditionalGrants — domain-agnostic
// allow-lists later interpolated into access_policy row_level filters (Task 5b).
// allowedAbbreviations already has every individual-exception grant unioned in
// (unconditionally); allowedStudentAbbreviations has only the grants where
// includes_student_data is true unioned in — see unionAdditionalGrants.
function buildSecurityContext(
  row,
  reporteeStaffKeys,
  allowedAbbreviations,
  allowedDepartmentGroups,
  allowedStudentAbbreviations = [],
) {
  return {
    groups: buildGroups(
      row,
      allowedAbbreviations,
      allowedDepartmentGroups,
      reporteeStaffKeys,
      allowedStudentAbbreviations,
    ),
    staff_pii_scope: row?.staff_pii_scope ?? "none",
    region_key: row?.region_key ?? null,
    location_abbreviation: row?.location_abbreviation ?? null,
    department_group: row?.department_group ?? null,
    job_function_level: row?.job_function_level ?? null,
    reportee_staff_keys: reporteeStaffKeys ?? [],
    allowed_abbreviations: allowedAbbreviations ?? [],
    allowed_department_groups: allowedDepartmentGroups ?? [],
    allowed_student_abbreviations: allowedStudentAbbreviations ?? [],
  };
}

module.exports = {
  buildGroups,
  buildSecurityContext,
  computeAllowedAbbreviations,
  computeAllowedDepartmentGroups,
  unionAdditionalGrants,
  STAFF_SENSITIVE_MEMBERS,
  STAFF_SENSITIVE_SCOPE_BY_MEMBER,
};
