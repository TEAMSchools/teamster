"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const a = require("./access");

const SL = {
  region_key: "R1",
  location_abbreviation: "ABC",
  department_group: "Ops",
  job_function_level: 4,
  student_summary_location_scope: "network",
  student_detail_location_scope: "school",
  student_pii_scope: "all",
  staff_summary_location_scope: "network",
  staff_summary_department_scope: "all",
  staff_detail_location_scope: "school",
  staff_detail_department_scope: "all",
  staff_detail_org_gate: "below_rank_or_downline",
  staff_pii_scope: "all",
  staff_compensation_scope: "none",
  staff_observations_scope: "none",
  staff_benefits_scope: "none",
};

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

test("buildGroups: SL gets detail+summary+pii for both domains", () => {
  const g = a.buildGroups(SL);
  assert.ok(g.includes("cube-access-student-detail"));
  assert.ok(g.includes("cube-access-student-summary"));
  assert.ok(g.includes("cube-access-student-pii"));
  assert.ok(g.includes("cube-access-staff-detail"));
  assert.ok(g.includes("cube-access-staff-summary"));
  assert.ok(g.includes("cube-access-staff-pii"));
});

test("buildGroups: summary-only student viewer gets no student-detail", () => {
  const g = a.buildGroups({
    ...SL,
    student_detail_location_scope: "none",
    student_pii_scope: "none",
  });
  assert.ok(g.includes("cube-access-student-summary"));
  assert.ok(!g.includes("cube-access-student-detail"));
  assert.ok(!g.includes("cube-access-student-pii"));
});

test("buildGroups: null row → no groups", () => {
  assert.deepEqual(a.buildGroups(null), []);
});

test("studentRowFilters: detail=school → abbreviation filter", () => {
  const f = a.studentRowFilters(SL, "detail");
  assert.deepEqual(f, [
    { member: "locations.abbreviation", operator: "equals", values: ["ABC"] },
  ]);
});

test("studentRowFilters: summary=network → no filter", () => {
  assert.deepEqual(a.studentRowFilters(SL, "summary"), []);
});

test("studentRowFilters: none → deny", () => {
  const f = a.studentRowFilters(
    { ...SL, student_detail_location_scope: "none" },
    "detail",
  );
  assert.deepEqual(f, [a.DENY_FILTER]);
});

test("staffRowFilters summary: network ∩ all-dept → no filter", () => {
  assert.deepEqual(a.staffRowFilters(SL, [], "summary"), []);
});

test("staffRowFilters detail below_rank_or_downline: OR(scope∧rank, downline)", () => {
  const f = a.staffRowFilters(SL, ["k1", "k2"], "detail");
  assert.equal(f.length, 1);
  assert.ok(f[0].or, "top-level OR");
  const [scope, downline] = f[0].or;
  assert.ok(scope.and.some((c) => c.member === "locations.abbreviation"));
  assert.ok(
    scope.and.some(
      (c) =>
        c.member === "staff.job_function_level" &&
        c.operator === "gt" &&
        c.values[0] === "4",
    ),
  );
  assert.deepEqual(downline, {
    member: "staff.staff_key",
    operator: "equals",
    values: ["k1", "k2"],
  });
});

test("staffRowFilters detail downline_only: just the downline IN", () => {
  const f = a.staffRowFilters(
    { ...SL, staff_detail_org_gate: "downline_only" },
    ["k1"],
    "detail",
  );
  assert.deepEqual(f, [
    { member: "staff.staff_key", operator: "equals", values: ["k1"] },
  ]);
});

test("staffRowFilters detail all_in_scope + network → no filter (all in scope)", () => {
  const exec = {
    ...SL,
    staff_detail_org_gate: "all_in_scope",
    staff_detail_location_scope: "network",
    staff_detail_department_scope: "all",
  };
  assert.deepEqual(a.staffRowFilters(exec, [], "detail"), []);
});

test("staffRowFilters detail org_gate none → deny", () => {
  assert.deepEqual(
    a.staffRowFilters({ ...SL, staff_detail_org_gate: "none" }, [], "detail"),
    [a.DENY_FILTER],
  );
});

test("staffColumnNarrowing: reporting_chain PII request narrows to downline", () => {
  const row = { ...SL, staff_pii_scope: "reporting_chain" };
  const q = { dimensions: ["staff_detail.personal_email"] };
  const f = a.staffColumnNarrowing(q, row, ["k1"]);
  assert.deepEqual(f, [
    { member: "staff.staff_key", operator: "equals", values: ["k1"] },
  ]);
});

test("staffColumnNarrowing: teaching_staff PII request narrows to TEACH/TIR", () => {
  const row = { ...SL, staff_pii_scope: "teaching_staff" };
  const q = { dimensions: ["staff_detail.race"] };
  const f = a.staffColumnNarrowing(q, row, []);
  assert.deepEqual(f, [
    {
      member: "staff.job_function_code",
      operator: "equals",
      values: ["TEACH", "TIR"],
    },
  ]);
});

test("staffColumnNarrowing: pii_scope=all → no extra filter", () => {
  const q = { dimensions: ["staff_detail.personal_email"] };
  assert.deepEqual(a.staffColumnNarrowing(q, SL, ["k1"]), []);
});
