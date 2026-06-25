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
  student_summary_location_scope: "network",
  student_detail_location_scope: "school",
  student_pii_scope: "all",
  staff_location_scope: "school",
  staff_department_scope: "all",
  staff_pii_scope: "all_in_scope",
  staff_compensation_scope: "none",
  staff_observations_scope: "none",
  staff_benefits_scope: "none",
};

test("isStudentMember / isStaffMember key off the view prefix", () => {
  assert.ok(a.isStudentMember("student_attendance_detail.x"));
  assert.ok(!a.isStudentMember("staff_detail.x"));
  assert.ok(a.isStaffMember("staff_summary.race"));
  assert.ok(!a.isStaffMember("student_enrollments_detail.x"));
});

test("surfaceOf reads the view suffix", () => {
  assert.equal(
    a.surfaceOf({ dimensions: ["staff_detail.full_name"] }),
    "detail",
  );
  assert.equal(
    a.surfaceOf({ measures: ["staff_summary.count_employees"] }),
    "summary",
  );
  assert.equal(a.surfaceOf({ dimensions: ["dates.date_day"] }), null);
});

test("buildGroups: SL gets student detail+summary+pii and staff directory+pii", () => {
  const g = a.buildGroups(SL);
  assert.ok(g.includes("student-detail"));
  assert.ok(g.includes("student-summary"));
  assert.ok(g.includes("student-pii"));
  assert.ok(g.includes("staff-directory"));
  assert.ok(g.includes("staff-pii"));
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
    student_summary_location_scope: "none",
    student_detail_location_scope: "none",
    student_pii_scope: "none",
    staff_location_scope: "none",
    staff_department_scope: "none",
    staff_pii_scope: "none",
  };
  assert.deepEqual(a.buildGroups(denied), ["staff-directory"]);
});

test("buildGroups: staff_pii_scope none → directory but no pii tier", () => {
  const g = a.buildGroups({ ...SL, staff_pii_scope: "none" });
  assert.ok(g.includes("staff-directory"));
  assert.ok(!g.includes("staff-pii"));
});

test("buildGroups: summary-only student viewer gets no student-detail", () => {
  const g = a.buildGroups({
    ...SL,
    student_detail_location_scope: "none",
    student_pii_scope: "none",
  });
  assert.ok(g.includes("student-summary"));
  assert.ok(!g.includes("student-detail"));
  assert.ok(!g.includes("student-pii"));
});

test("buildGroups: null row → no groups", () => {
  assert.deepEqual(a.buildGroups(null), []);
});

test("studentRowFilters: detail=school → abbreviation filter", () => {
  assert.deepEqual(a.studentRowFilters(SL, "detail"), [
    { member: "locations.abbreviation", operator: "equals", values: ["ABC"] },
  ]);
});

test("studentRowFilters: summary=network → no filter", () => {
  assert.deepEqual(a.studentRowFilters(SL, "summary"), []);
});

test("studentRowFilters: none → deny", () => {
  assert.deepEqual(
    a.studentRowFilters(
      { ...SL, student_detail_location_scope: "none" },
      "detail",
    ),
    [a.DENY_FILTER],
  );
});

// ---- staffSensitiveFilters: the open directory + per-field gating ----

test("staffSensitiveFilters: directory-only staff query → no filter", () => {
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.full_name"] }, SL, []),
    [],
  );
});

test("staffSensitiveFilters: staff_summary demographic is an open aggregate (no gate)", () => {
  // race is a STAFF_PII_MEMBER leaf, but on the summary view it is an open
  // aggregate breakdown — only staff_detail occurrences are gated.
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_summary.race"] }, SL, []),
    [],
  );
});

test("staffSensitiveFilters: all_in_scope + school/all → school filter", () => {
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.personal_email"] },
      SL,
      [],
    ),
    [{ member: "locations.abbreviation", operator: "equals", values: ["ABC"] }],
  );
});

test("staffSensitiveFilters: all_in_scope + network/all → no filter", () => {
  const exec = {
    ...SL,
    staff_location_scope: "network",
    staff_department_scope: "all",
  };
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.race"] }, exec, []),
    [],
  );
});

test("staffSensitiveFilters: all_in_scope + region/own_group → region ∩ dept", () => {
  const r = {
    ...SL,
    staff_location_scope: "region",
    staff_department_scope: "own_group",
  };
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.birth_date"] }, r, []),
    [
      { member: "locations.region_key", operator: "equals", values: ["R1"] },
      { member: "staff.department_group", operator: "equals", values: ["Ops"] },
    ],
  );
});

test("staffSensitiveFilters: reporting_chain → chain IN only", () => {
  const r = { ...SL, staff_pii_scope: "reporting_chain" };
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.personal_email"] },
      r,
      ["k1", "k2"],
    ),
    [{ member: "staff.staff_key", operator: "equals", values: ["k1", "k2"] }],
  );
});

test("staffSensitiveFilters: reporting_chain + empty chain → deny", () => {
  const r = { ...SL, staff_pii_scope: "reporting_chain" };
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.race"] }, r, []),
    [a.DENY_FILTER],
  );
});

test("staffSensitiveFilters: reporting_chain_or_below_rank → OR(scope∧rank, chain)", () => {
  const r = { ...SL, staff_pii_scope: "reporting_chain_or_below_rank" };
  const f = a.staffSensitiveFilters({ dimensions: ["staff_detail.race"] }, r, [
    "k1",
  ]);
  assert.equal(f.length, 1);
  assert.ok(f[0].or, "top-level OR");
  const [scope, chain] = f[0].or;
  assert.ok(scope.and.some((c) => c.member === "locations.abbreviation"));
  assert.ok(
    scope.and.some(
      (c) =>
        c.member === "staff.job_function_level" &&
        c.operator === "gt" &&
        c.values[0] === "4",
    ),
  );
  assert.deepEqual(chain, {
    member: "staff.staff_key",
    operator: "equals",
    values: ["k1"],
  });
});

test("staffSensitiveFilters: reporting_chain_or_below_rank, network scope, no chain → rank only", () => {
  const r = {
    ...SL,
    staff_pii_scope: "reporting_chain_or_below_rank",
    staff_location_scope: "network",
    staff_department_scope: "all",
  };
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.race"] }, r, []),
    [{ member: "staff.job_function_level", operator: "gt", values: ["4"] }],
  );
});

test("staffSensitiveFilters: teaching_staff → remit ∩ TEACH/TIR", () => {
  const r = { ...SL, staff_pii_scope: "teaching_staff" };
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.personal_cell_phone"] },
      r,
      [],
    ),
    [
      { member: "locations.abbreviation", operator: "equals", values: ["ABC"] },
      {
        member: "staff.job_function_code",
        operator: "equals",
        values: ["TEACH", "TIR"],
      },
    ],
  );
});

test("staffSensitiveFilters: scope none → deny", () => {
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.race"] },
      { ...SL, staff_pii_scope: "none" },
      [],
    ),
    [a.DENY_FILTER],
  );
});

test("staffSensitiveFilters: null row + sensitive request → deny", () => {
  assert.deepEqual(
    a.staffSensitiveFilters({ dimensions: ["staff_detail.race"] }, null, []),
    [a.DENY_FILTER],
  );
});

test("staffSensitiveFilters: two PII fields share one scope → not doubled", () => {
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.personal_email", "staff_detail.race"] },
      SL,
      [],
    ),
    [{ member: "locations.abbreviation", operator: "equals", values: ["ABC"] }],
  );
});

test("staffSensitiveFilters: null row + non-sensitive field → no filter", () => {
  // full_name is not in STAFF_SENSITIVE_SCOPE_BY_MEMBER — directory-only field.
  // A null row must not deny when no sensitive field is requested.
  assert.deepEqual(
    a.staffSensitiveFilters(
      { dimensions: ["staff_detail.full_name"] },
      null,
      [],
    ),
    [],
  );
});

test("staffSensitiveFilters: PII + compensation simultaneously → both scope filters ANDed", () => {
  // birth_date → staff_pii_scope; salary → staff_compensation_scope.
  // A viewer with all_in_scope PII (school/all remit) but no compensation
  // access should get a location filter for PII AND a deny for compensation.
  // The two are independent scope columns — staffSensitiveFilters must emit
  // filters for both, not collapse them into one.
  const piiOnlyViewer = { ...SL, staff_compensation_scope: "none" };
  const filters = a.staffSensitiveFilters(
    { dimensions: ["staff_detail.birth_date", "staff_detail.salary"] },
    piiOnlyViewer,
    [],
  );
  // compensation deny fires → whole filter set includes DENY_FILTER
  assert.ok(
    filters.some(
      (f) => f.member === "locations.abbreviation" && f.values.length === 0,
    ),
    "DENY_FILTER present for compensation scope=none",
  );
});

test("staffSensitiveFilters: PII + compensation both granted → both scope filters emitted without deny", () => {
  // A viewer with both PII and compensation access (school/all remit for both)
  // should get a location filter for PII and no deny for compensation.
  const bothGranted = {
    ...SL,
    staff_pii_scope: "all_in_scope",
    staff_compensation_scope: "all_in_scope",
  };
  const filters = a.staffSensitiveFilters(
    { dimensions: ["staff_detail.birth_date", "staff_detail.salary"] },
    bothGranted,
    [],
  );
  assert.ok(
    !filters.some(
      (f) => f.member === "locations.abbreviation" && f.values.length === 0,
    ),
    "no DENY_FILTER when both scopes are granted",
  );
  // Both scope columns resolve to the same school remit → one location filter
  // (the Set dedup collapses two calls to the same scope column result).
  assert.deepEqual(filters, [
    { member: "locations.abbreviation", operator: "equals", values: ["ABC"] },
  ]);
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
