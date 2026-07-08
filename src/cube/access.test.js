"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const a = require("./access");

// Refold-c access row: open staff directory + summary, sensitive staff fields
// gated by the shared remit (staff_location_scope ∩ staff_department_scope) plus
// a per-field scope enum. SL = a school leader (school location, all-dept remit,
// all_in_scope PII).
const SL = {
  staff_key: "self",
  region_key: "R1",
  location_abbreviation: "ABC",
  department_group: "Ops",
  job_function_level: 4,
  student_location_scope: "school",
  staff_location_scope: "school",
  staff_department_scope: "all",
  staff_pii_scope: "all_in_scope",
  staff_compensation_scope: "none",
  staff_observations_scope: "none",
  staff_benefits_scope: "none",
};

test("buildGroups: SL gets the single student tier and staff directory+pii", () => {
  const g = a.buildGroups(SL);
  assert.ok(g.includes("student-school"));
  // No summary/detail/pii split — one student tier.
  assert.ok(!g.includes("student-detail"));
  assert.ok(!g.includes("student-summary"));
  assert.ok(!g.includes("student-pii"));
  assert.ok(g.includes("staff-directory"));
  assert.ok(g.includes("staff-pii-all_in_scope"));
  // No detail/summary split on the open staff surface.
  assert.ok(!g.includes("staff-detail"));
  assert.ok(!g.includes("staff-summary"));
  // SL has none-valued comp/obs/benefits scopes → those tiers are not emitted.
  assert.ok(!g.includes("staff-compensation"));
  assert.ok(!g.includes("staff-observations"));
  assert.ok(!g.includes("staff-benefits"));
});

test("buildGroups: a sensitive tier is emitted per scope != none", () => {
  const g = a.buildGroups({
    ...SL,
    staff_compensation_scope: "reporting_chain",
    staff_observations_scope: "all_in_scope",
    staff_benefits_scope: "none",
  });
  assert.ok(g.includes("staff-compensation"));
  assert.ok(g.includes("staff-observations"));
  assert.ok(!g.includes("staff-benefits"));
});

test("buildGroups: directory is open to every staff viewer, even full-deny", () => {
  const denied = {
    ...SL,
    student_location_scope: "none",
    staff_location_scope: "none",
    staff_department_scope: "none",
    staff_pii_scope: "none",
  };
  assert.deepEqual(a.buildGroups(denied), ["staff-directory"]);
});

test("buildGroups: staff_pii_scope none → directory but no pii tier", () => {
  const g = a.buildGroups({ ...SL, staff_pii_scope: "none" });
  assert.ok(g.includes("staff-directory"));
  assert.ok(!g.some((x) => x.startsWith("staff-pii")));
});

test("buildGroups: student_location_scope none → no student tier", () => {
  const g = a.buildGroups({ ...SL, student_location_scope: "none" });
  assert.ok(!g.some((x) => x.startsWith("student")));
  assert.ok(g.includes("staff-directory"));
});

test("buildGroups: null row → no groups", () => {
  assert.deepEqual(a.buildGroups(null), []);
});

test("buildSecurityContext flattens the access row + chain", () => {
  const row = {
    student_location_scope: "region",
    staff_pii_scope: "reporting_chain_or_below_rank",
    region_key: "R1",
    location_abbreviation: "ABC",
    department_group: "Operations",
    job_function_level: 5,
  };
  const ctx = a.buildSecurityContext(row, ["k1", "k2"]);
  assert.strictEqual(ctx.region_key, "R1");
  assert.strictEqual(ctx.job_function_level, 5);
  assert.deepEqual(ctx.reportee_staff_keys, ["k1", "k2"]);
  assert.ok(ctx.groups.includes("staff-directory"));
  // Scope-specific student group (canonical group-based RLS), not "student".
  assert.ok(ctx.groups.includes("student-region"));
  assert.ok(ctx.groups.includes("staff-pii-reporting_chain_or_below_rank"));
});

test("buildSecurityContext is null-safe for an unresolved viewer", () => {
  const ctx = a.buildSecurityContext(null, []);
  assert.deepEqual(ctx.groups, []);
  assert.deepEqual(ctx.reportee_staff_keys, []);
});

test("buildSecurityContext defaults allowed_abbreviations/allowed_department_groups to [] when omitted", () => {
  const ctx = a.buildSecurityContext(null, []);
  assert.deepEqual(ctx.allowed_abbreviations, []);
  assert.deepEqual(ctx.allowed_department_groups, []);
});

test("buildSecurityContext passes through the precomputed allow-lists", () => {
  const ctx = a.buildSecurityContext(
    { staff_pii_scope: "all_in_scope" },
    ["k1"],
    ["A", "B"],
    ["talent"],
  );
  assert.deepEqual(ctx.allowed_abbreviations, ["A", "B"]);
  assert.deepEqual(ctx.allowed_department_groups, ["talent"]);
});

const LOCATION_UNIVERSE = [
  { abbreviation: "A", region_key: "R1" },
  { abbreviation: "B", region_key: "R1" },
  { abbreviation: "C", region_key: "R2" },
];

test("computeAllowedAbbreviations: network scope returns every abbreviation", () => {
  assert.deepEqual(
    a.computeAllowedAbbreviations("network", "R1", "A", LOCATION_UNIVERSE),
    ["A", "B", "C"],
  );
});

test("computeAllowedAbbreviations: region scope returns only same-region abbreviations", () => {
  assert.deepEqual(
    a.computeAllowedAbbreviations("region", "R1", null, LOCATION_UNIVERSE),
    ["A", "B"],
  );
  assert.deepEqual(
    a.computeAllowedAbbreviations("region", "R2", null, LOCATION_UNIVERSE),
    ["C"],
  );
});

test("computeAllowedAbbreviations: school scope returns only the viewer's school", () => {
  assert.deepEqual(
    a.computeAllowedAbbreviations("school", "R1", "B", LOCATION_UNIVERSE),
    ["B"],
  );
});

test("computeAllowedAbbreviations: school scope with no location_abbreviation denies", () => {
  assert.deepEqual(
    a.computeAllowedAbbreviations("school", "R1", null, LOCATION_UNIVERSE),
    [],
  );
});

test("computeAllowedAbbreviations: none/undefined scope denies", () => {
  assert.deepEqual(
    a.computeAllowedAbbreviations("none", "R1", "A", LOCATION_UNIVERSE),
    [],
  );
  assert.deepEqual(
    a.computeAllowedAbbreviations(undefined, "R1", "A", LOCATION_UNIVERSE),
    [],
  );
});

test("computeAllowedAbbreviations: empty/undefined universe returns []", () => {
  assert.deepEqual(a.computeAllowedAbbreviations("network", "R1", "A", []), []);
  assert.deepEqual(
    a.computeAllowedAbbreviations("network", "R1", "A", undefined),
    [],
  );
});

const DEPARTMENT_UNIVERSE = ["talent", "finance", "academics"];

test("computeAllowedDepartmentGroups: all scope returns the full universe", () => {
  assert.deepEqual(
    a.computeAllowedDepartmentGroups("all", "talent", DEPARTMENT_UNIVERSE),
    DEPARTMENT_UNIVERSE,
  );
});

test("computeAllowedDepartmentGroups: own_group scope returns just the viewer's group", () => {
  assert.deepEqual(
    a.computeAllowedDepartmentGroups(
      "own_group",
      "talent",
      DEPARTMENT_UNIVERSE,
    ),
    ["talent"],
  );
});

test("computeAllowedDepartmentGroups: none/undefined scope denies", () => {
  assert.deepEqual(
    a.computeAllowedDepartmentGroups("none", "talent", DEPARTMENT_UNIVERSE),
    [],
  );
  assert.deepEqual(
    a.computeAllowedDepartmentGroups(undefined, "talent", DEPARTMENT_UNIVERSE),
    [],
  );
});

test("STAFF_PII_MEMBERS lists all gated sensitive columns", () => {
  assert.deepEqual(a.STAFF_PII_MEMBERS.sort(), [
    "birth_date",
    "gender_identity",
    "is_hispanic",
    "personal_cell_phone",
    "personal_email",
    "race",
    "salary",
  ]);
});
