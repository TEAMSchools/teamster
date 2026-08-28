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
  // SL is school-scoped with an all-department remit → a non-empty resolved
  // remit, so the all_in_scope PII group is emitted.
  const g = a.buildGroups(SL, ["ABC"], ["Ops"]);
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

test("buildGroups: an object with no staff_key gets no groups (not even staff-directory)", () => {
  // Defense-in-depth: a lookup miss shaped as {} must not be treated as a
  // resolved viewer. The wired caller passes null, but gate on a real identity.
  assert.deepEqual(a.buildGroups({}), []);
  assert.deepEqual(a.buildGroups({ staff_pii_scope: "all_in_scope" }), []);
});

test("buildSecurityContext flattens the access row + chain", () => {
  const row = {
    staff_key: "s1",
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

// Empty-remit hardening: Cube (Tesseract) throws "Values required for filter" on
// an `equals []` row_level filter (verified #4269) rather than compiling it to
// zero rows, so a staff-pii scope whose remit/chain resolved empty must not emit
// its group — the viewer takes the clean no-group default-deny path instead.
test("buildGroups: all_in_scope with a full remit emits the group", () => {
  const g = a.buildGroups(
    { staff_key: "s1", staff_pii_scope: "all_in_scope" },
    ["A"],
    ["Ops"],
    [],
  );
  assert.ok(g.includes("staff-pii-all_in_scope"));
});

test("buildGroups: all_in_scope with an empty location remit does NOT emit the group", () => {
  const g = a.buildGroups(
    { staff_key: "s1", staff_pii_scope: "all_in_scope" },
    [],
    ["Ops"],
    [],
  );
  assert.ok(!g.includes("staff-pii-all_in_scope"));
  assert.ok(g.includes("staff-directory")); // directory tier stays open
});

test("buildGroups: all_in_scope with an empty department remit does NOT emit the group", () => {
  const g = a.buildGroups(
    { staff_key: "s1", staff_pii_scope: "all_in_scope" },
    ["A"],
    [],
    [],
  );
  assert.ok(!g.includes("staff-pii-all_in_scope"));
});

test("buildGroups: reporting_chain with no reportees does NOT emit the group", () => {
  const g = a.buildGroups(
    { staff_key: "s1", staff_pii_scope: "reporting_chain" },
    [],
    [],
    [],
  );
  assert.ok(!g.includes("staff-pii-reporting_chain"));
});

test("buildGroups: reporting_chain with reportees emits the group", () => {
  const g = a.buildGroups(
    { staff_key: "s1", staff_pii_scope: "reporting_chain" },
    [],
    [],
    ["k1"],
  );
  assert.ok(g.includes("staff-pii-reporting_chain"));
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

test("STAFF_SENSITIVE_MEMBERS lists all gated sensitive columns", () => {
  assert.deepEqual(a.STAFF_SENSITIVE_MEMBERS.sort(), [
    "birth_date",
    "gender_identity",
    "is_hispanic",
    "personal_cell_phone",
    "personal_email",
    "race",
    "salary",
  ]);
});

// --- Internal user emulation (#4526) ---------------------------------------

test("parseImpersonators: trims, lowercases, and drops empty entries", () => {
  const set = a.parseImpersonators(" Admin@Apps.Teamschools.Org , ,b@x.org ");
  assert.deepEqual([...set].sort(), ["admin@apps.teamschools.org", "b@x.org"]);
});

test("parseImpersonators: an unset variable yields an empty set", () => {
  assert.equal(a.parseImpersonators(undefined).size, 0);
  assert.equal(a.parseImpersonators("").size, 0);
});

test("isImpersonator: membership is case-insensitive; absent email is false", () => {
  const set = a.parseImpersonators("admin@x.org");
  assert.equal(a.isImpersonator("ADMIN@x.org", set), true);
  assert.equal(a.isImpersonator("someone@x.org", set), false);
  assert.equal(a.isImpersonator(null, set), false);
});

test("resolveEmulationTarget: an impersonator resolves the requested target", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: "teacher@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, {
    caller: "admin@x.org",
    target: "teacher@x.org",
    emulating: true,
  });
});

test("resolveEmulationTarget: a NON-impersonator gets their OWN scope, not the target", () => {
  // The critical negative case: supplying a target must never elevate.
  const r = a.resolveEmulationTarget({
    callerEmail: "teacher@x.org",
    requestedTarget: "superintendent@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.target, "teacher@x.org");
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: the returned emails keep their original case", () => {
  // resolveAccess queries `WHERE google_email = @email` and keys its cache on
  // the raw string, so lowercasing here would change resolution for every
  // request. Membership matching is case-insensitive; the value passed
  // downstream is not rewritten.
  const r = a.resolveEmulationTarget({
    callerEmail: "Admin@X.org",
    requestedTarget: "Teacher@X.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.caller, "Admin@X.org");
  assert.equal(r.target, "Teacher@X.org");
  assert.equal(r.emulating, true);
});

test("resolveEmulationTarget: a non-emulated caller is passed through unchanged", () => {
  // The regression guard for every ordinary request: the email reaching
  // resolveAccess must be byte-identical to the one in the token.
  const r = a.resolveEmulationTarget({
    callerEmail: "MixedCase@Apps.Teamschools.Org",
    requestedTarget: null,
    impersonators: a.parseImpersonators(""),
  });
  assert.equal(r.target, "MixedCase@Apps.Teamschools.Org");
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: no requested target is not an emulation", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: null,
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, {
    caller: "admin@x.org",
    target: "admin@x.org",
    emulating: false,
  });
});

test("resolveEmulationTarget: targeting yourself is not an emulation", () => {
  // Keeps the audit log free of no-op self-emulation lines.
  const r = a.resolveEmulationTarget({
    callerEmail: "admin@x.org",
    requestedTarget: "ADMIN@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.equal(r.emulating, false);
});

test("resolveEmulationTarget: an absent caller can never emulate", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: null,
    requestedTarget: "superintendent@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, { caller: null, target: null, emulating: false });
});

test("emulationInputsFromToken: caller is `email`, target is `act_as`", () => {
  assert.deepEqual(
    a.emulationInputsFromToken({ email: "admin@x.org", act_as: "t@x.org" }),
    { callerEmail: "admin@x.org", requestedTarget: "t@x.org" },
  );
  assert.deepEqual(a.emulationInputsFromToken(undefined), {
    callerEmail: null,
    requestedTarget: null,
  });
});

test("emulationInputsFromCubeCloud: caller is cubeCloud.username, target is email", () => {
  assert.deepEqual(
    a.emulationInputsFromCubeCloud({
      email: "teacher@x.org",
      cubeCloud: { username: "admin@x.org" },
      iss: "cubecloud",
    }),
    { callerEmail: "admin@x.org", requestedTarget: "teacher@x.org" },
  );
});

test("emulationInputsFromCubeCloud: falls back to userAttributes.email for the target", () => {
  // Cube Cloud mirrors a pasted Security Context under cubeCloud.userAttributes
  // as well as merging it into the top level, and 1.7.14 has been observed
  // presenting only the mirror on follow-up requests within a session.
  assert.deepEqual(
    a.emulationInputsFromCubeCloud({
      cubeCloud: {
        username: "admin@x.org",
        userAttributes: { email: "target@x.org" },
      },
      iss: "cubecloud",
    }),
    { callerEmail: "admin@x.org", requestedTarget: "target@x.org" },
  );
});

test("emulationInputsFromCubeCloud: a top-level email wins over the mirror", () => {
  assert.deepEqual(
    a.emulationInputsFromCubeCloud({
      email: "toplevel@x.org",
      cubeCloud: {
        username: "admin@x.org",
        userAttributes: { email: "mirror@x.org" },
      },
    }),
    { callerEmail: "admin@x.org", requestedTarget: "toplevel@x.org" },
  );
});

test("emulationInputsFromCubeCloud: with no pasted context the console user is the target", () => {
  // Cube Cloud with nothing typed into Security Context: the caller resolves as
  // themselves, which is what fixes plain (non-emulated) Explore.
  const inputs = a.emulationInputsFromCubeCloud({
    cubeCloud: { username: "admin@x.org" },
    iss: "cubecloud",
  });
  const r = a.resolveEmulationTarget({
    ...inputs,
    impersonators: a.parseImpersonators(""),
  });
  assert.equal(r.target, "admin@x.org");
  assert.equal(r.emulating, false);
});

// --- Non-string identities from a pasted Cube Cloud context -----------------
// On Cube Cloud the target (and, less commonly, the caller identity feeding
// this function) is a pasted JSON value, so it can be an object or an array
// just as easily as a string. A bare `.toLowerCase()` on a non-string used to
// throw a TypeError out of contextToGroups — a 500 instead of a clean
// decision. Coercing anything non-string to null treats "no usable identity"
// as "no emulation," which fails closed without erroring. Verified this
// throws under the old `callerEmail ?? null` / `requestedTarget ?? null`
// coercion (temporarily reverted locally, restored — not committed).

test("resolveEmulationTarget: a non-string requestedTarget from an impersonator caller yields no emulation, not a throw", () => {
  const impersonators = a.parseImpersonators("admin@x.org");
  for (const requestedTarget of [{ email: { a: 1 } }, ["x"], 42]) {
    const r = a.resolveEmulationTarget({
      callerEmail: "admin@x.org",
      requestedTarget,
      impersonators,
    });
    assert.deepEqual(r, {
      caller: "admin@x.org",
      target: "admin@x.org",
      emulating: false,
    });
  }
});

test("resolveEmulationTarget: a non-string callerEmail resolves to no caller and no target", () => {
  const r = a.resolveEmulationTarget({
    callerEmail: { username: "admin@x.org" },
    requestedTarget: "target@x.org",
    impersonators: a.parseImpersonators("admin@x.org"),
  });
  assert.deepEqual(r, { caller: null, target: null, emulating: false });
});
