"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const a = require("./access");

// Member names a staff view file lists. The views are YAML and no parser is
// installed (src/cube depends only on the Cube server + driver, and the suite
// must run without node_modules), so match the bare `- <member>` sequence
// entries — that covers both the `includes:` blocks and the meta.folders
// lists, and skips `- group:` / `- name:` / `- join_path:` mapping entries.
// Enough to assert a member is absent from a view file entirely, which is the
// property the open staff-directory tier depends on.
function viewMembers(file) {
  const text = fs.readFileSync(
    path.join(__dirname, "model", "views", "staff", file),
    "utf8",
  );
  return new Set(
    text
      .split("\n")
      .map((line) => /^\s+- ([a-z0-9_]+)\s*$/.exec(line))
      .filter((m) => m !== null)
      .map((m) => m[1]),
  );
}

// Refold-c access row: open staff directory + summary, sensitive staff fields
// gated by the shared remit (staff_location_scope ∩ staff_department_scope) plus
// a per-field scope enum. SL = a school leader (school location, all-dept remit,
// all_in_scope PII).
const SL = {
  staff_key: "self",
  is_employee: true,
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
  // remit, so the all_in_scope PII group is emitted. The student tier is now
  // driven by the precomputed allowedStudentAbbreviations array (5th arg),
  // not a row field — pass SL's own school to simulate her base scope.
  const g = a.buildGroups(SL, ["ABC"], ["Ops"], [], ["ABC"]);
  assert.ok(g.includes("student"));
  // No scope-specific tiers or old summary/detail/pii split — one flat tier.
  assert.ok(!g.includes("student-school"));
  assert.ok(!g.includes("student-region"));
  assert.ok(!g.includes("student-network"));
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

test("buildGroups: directory is open to every employee, even full-deny", () => {
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

test("buildGroups: empty allowedStudentAbbreviations → no student tier", () => {
  // Omitting the 5th arg defaults it to [] — the empty-array guard (same
  // rationale as staff-pii-* below: Cube hard-errors on `equals []` rather
  // than compiling to zero rows).
  const g = a.buildGroups(SL);
  assert.ok(!g.some((x) => x.startsWith("student")));
  assert.ok(g.includes("staff-directory"));
});

test("buildGroups: a non-empty allowedStudentAbbreviations emits the student tier even when the base scope alone would deny", () => {
  // Proves the array, not a row field, drives the tier — this is what lets an
  // individual-exception grant add student access for a viewer whose base
  // student_location_scope is none/absent.
  const g = a.buildGroups({ staff_key: "s1" }, [], [], [], ["KIPP_LIFE"]);
  assert.ok(g.includes("student"));
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
    is_employee: true,
    staff_pii_scope: "reporting_chain_or_below_rank",
    region_key: "R1",
    location_abbreviation: "ABC",
    department_group: "Operations",
    job_function_level: 5,
  };
  const ctx = a.buildSecurityContext(row, ["k1", "k2"], [], [], ["A", "B"]);
  assert.strictEqual(ctx.region_key, "R1");
  assert.strictEqual(ctx.job_function_level, 5);
  assert.deepEqual(ctx.reportee_staff_keys, ["k1", "k2"]);
  assert.deepEqual(ctx.allowed_student_abbreviations, ["A", "B"]);
  assert.ok(ctx.groups.includes("staff-directory"));
  // Single flat student group, driven by allowed_student_abbreviations —
  // there is no student_location_scope key on the returned context anymore.
  assert.ok(ctx.groups.includes("student"));
  assert.strictEqual(ctx.student_location_scope, undefined);
  assert.ok(ctx.groups.includes("staff-pii-reporting_chain_or_below_rank"));
});

test("buildSecurityContext is null-safe for an unresolved viewer", () => {
  const ctx = a.buildSecurityContext(null, []);
  assert.deepEqual(ctx.groups, []);
  assert.deepEqual(ctx.reportee_staff_keys, []);
});

test("buildSecurityContext defaults allowed_abbreviations/allowed_department_groups/allowed_student_abbreviations to [] when omitted", () => {
  const ctx = a.buildSecurityContext(null, []);
  assert.deepEqual(ctx.allowed_abbreviations, []);
  assert.deepEqual(ctx.allowed_department_groups, []);
  assert.deepEqual(ctx.allowed_student_abbreviations, []);
});

test("buildSecurityContext passes through the precomputed allow-lists", () => {
  const ctx = a.buildSecurityContext(
    { staff_pii_scope: "all_in_scope" },
    ["k1"],
    ["A", "B"],
    ["talent"],
    ["C", "D"],
  );
  assert.deepEqual(ctx.allowed_abbreviations, ["A", "B"]);
  assert.deepEqual(ctx.allowed_department_groups, ["talent"]);
  assert.deepEqual(ctx.allowed_student_abbreviations, ["C", "D"]);
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
    { staff_key: "s1", is_employee: true, staff_pii_scope: "all_in_scope" },
    [],
    ["Ops"],
    [],
  );
  assert.ok(!g.includes("staff-pii-all_in_scope"));
  assert.ok(g.includes("staff-directory")); // directory stays open to employees
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

test("unionAdditionalGrants: no grants returns the base list unchanged", () => {
  assert.deepEqual(
    a.unionAdditionalGrants(["A"], [], LOCATION_UNIVERSE, { axis: "staff" }),
    ["A"],
  );
  assert.deepEqual(
    a.unionAdditionalGrants(["A"], undefined, LOCATION_UNIVERSE, {
      axis: "staff",
    }),
    ["A"],
  );
});

test("unionAdditionalGrants: a missing or unrecognized axis unions nothing (fails closed)", () => {
  const grants = [
    {
      location_scope: "network",
      region_key: null,
      location_abbreviation: null,
      includes_student_data: true,
      includes_staff_data: true,
    },
  ];
  // No axis at all, and a typo'd axis, both return the base list untouched
  // rather than widening the wrong axis.
  assert.deepEqual(a.unionAdditionalGrants(["A"], grants, LOCATION_UNIVERSE), [
    "A",
  ]);
  assert.deepEqual(
    a.unionAdditionalGrants(["A"], grants, LOCATION_UNIVERSE, {
      axis: "students",
    }),
    ["A"],
  );
});

test("unionAdditionalGrants: a school grant adds exactly that one abbreviation, dedup'd against the base", () => {
  const grants = [
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "B",
      includes_student_data: false,
      includes_staff_data: true,
    },
  ];
  assert.deepEqual(
    a
      .unionAdditionalGrants(["A"], grants, LOCATION_UNIVERSE, {
        axis: "staff",
      })
      .sort(),
    ["A", "B"],
  );
  // Granting a school already in the base list doesn't duplicate it.
  assert.deepEqual(
    a.unionAdditionalGrants(["B"], grants, LOCATION_UNIVERSE, {
      axis: "staff",
    }),
    ["B"],
  );
});

test("unionAdditionalGrants: two school grants for the same person both union in (Example D)", () => {
  const grants = [
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "B",
      includes_student_data: true,
      includes_staff_data: true,
    },
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "C",
      includes_student_data: false,
      includes_staff_data: true,
    },
  ];
  assert.deepEqual(
    a
      .unionAdditionalGrants([], grants, LOCATION_UNIVERSE, { axis: "staff" })
      .sort(),
    ["B", "C"],
  );
  // The student axis reads includes_student_data, so only the first grant.
  assert.deepEqual(
    a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, {
      axis: "student",
    }),
    ["B"],
  );
});

test("unionAdditionalGrants: the two axes are independent — a student-only grant does not widen staff", () => {
  const grants = [
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "B",
      includes_student_data: true,
      includes_staff_data: false,
    },
  ];
  assert.deepEqual(
    a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, {
      axis: "student",
    }),
    ["B"],
  );
  assert.deepEqual(
    a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, { axis: "staff" }),
    [],
  );
});

test("unionAdditionalGrants: a network grant adds every abbreviation", () => {
  assert.deepEqual(
    a
      .unionAdditionalGrants(
        [],
        [
          {
            location_scope: "network",
            region_key: null,
            location_abbreviation: null,
            includes_student_data: true,
            includes_staff_data: true,
          },
        ],
        LOCATION_UNIVERSE,
        { axis: "staff" },
      )
      .sort(),
    ["A", "B", "C"],
  );
});

test("unionAdditionalGrants: a region grant adds that region's abbreviations only", () => {
  assert.deepEqual(
    a
      .unionAdditionalGrants(
        [],
        [
          {
            location_scope: "region",
            region_key: "R2",
            location_abbreviation: null,
            includes_student_data: false,
            includes_staff_data: true,
          },
        ],
        LOCATION_UNIVERSE,
        { axis: "staff" },
      )
      .sort(),
    ["C"],
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
    "status_reason",
  ]);
});

// status_reason is the leave type (Medical / Family / Disability) or the
// termination reason behind a period's status. It used to sit on the open
// staff_directory view, so every resolved viewer — including one whose every
// scope is "none" — could read it for all staff network-wide. It is now a
// staff_pii_scope-gated member of staff_pii.
test("status_reason is gated by staff_pii_scope", () => {
  assert.equal(
    a.STAFF_SENSITIVE_SCOPE_BY_MEMBER.status_reason,
    "staff_pii_scope",
  );
});

test("a full-deny viewer holds no group exposing status_reason", () => {
  const directory = viewMembers("staff_directory.yml");
  const pii = viewMembers("staff_pii.yml");
  // Guard against a path/regex regression making the assertions vacuous.
  assert.ok(directory.has("status_name") && pii.has("status_name"));

  const denied = {
    ...SL,
    student_location_scope: "none",
    staff_location_scope: "none",
    staff_department_scope: "none",
    staff_pii_scope: "none",
  };
  // The only tier this viewer holds is the open directory...
  assert.deepEqual(a.buildGroups(denied), ["staff-directory"]);
  // ...which no longer exposes status_reason at all — the member moved to
  // staff_pii, whose every policy requires a staff-pii-<scope> group.
  assert.ok(!directory.has("status_reason"));
  assert.ok(pii.has("status_reason"));
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

// A non-employee grantee (contractor) as dim_staff_cube_access now emits one:
// a real staff_key off the exceptions sheet, but NULL for every role- and
// org-derived attribute, so all five scopes sit at 'none' and the only thing
// granting anything is additional_location_grants. is_employee false is what
// keeps the open staff directory off them until a grant reaches the staff axis.
const CONTRACTOR = {
  staff_key: "non-employee-hash",
  is_employee: false,
  region_key: null,
  location_abbreviation: null,
  department_group: null,
  job_function_level: null,
  student_location_scope: "none",
  staff_location_scope: "none",
  staff_department_scope: "none",
  staff_pii_scope: "none",
  staff_compensation_scope: "none",
  staff_observations_scope: "none",
  staff_benefits_scope: "none",
};

test("contractor: a 'none' base scope resolves to no abbreviations on either axis", () => {
  // Nothing about the row itself grants a location — that is the whole point of
  // the non-employee leg. Both axes start empty and only grants can fill them.
  assert.deepEqual(
    a.computeAllowedAbbreviations(
      CONTRACTOR.staff_location_scope,
      CONTRACTOR.region_key,
      CONTRACTOR.location_abbreviation,
      LOCATION_UNIVERSE,
    ),
    [],
  );
  assert.deepEqual(
    a.computeAllowedAbbreviations(
      CONTRACTOR.student_location_scope,
      CONTRACTOR.region_key,
      CONTRACTOR.location_abbreviation,
      LOCATION_UNIVERSE,
    ),
    [],
  );
});

test("contractor: one school grant with student data yields exactly that school on both axes", () => {
  const grants = [
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "B",
      includes_student_data: true,
      includes_staff_data: true,
    },
  ];
  const staff = a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, {
    axis: "staff",
  });
  const student = a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, {
    axis: "student",
  });
  assert.deepEqual(staff, ["B"]);
  assert.deepEqual(student, ["B"]);

  // staff_department_scope is 'none', so the remit's department axis is empty
  // and no staff-pii group is emitted — but the student group is, because the
  // grant filled allowedStudentAbbreviations.
  const g = a.buildGroups(CONTRACTOR, staff, [], [], student);
  assert.ok(g.includes("student"));
  assert.ok(g.includes("staff-directory"));
  assert.ok(!g.some((x) => x.startsWith("staff-pii-")));
});

test("contractor: a location grant WITHOUT student data grants no student access", () => {
  const grants = [
    {
      location_scope: "school",
      region_key: null,
      location_abbreviation: "B",
      includes_student_data: false,
      includes_staff_data: true,
    },
  ];
  const student = a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, {
    axis: "student",
  });
  assert.deepEqual(student, []);
  // Empty student array → no `student` group → default-deny on every student
  // view, rather than an `equals []` filter Cube would hard-error on (#4269).
  const g = a.buildGroups(
    CONTRACTOR,
    a.unionAdditionalGrants([], grants, LOCATION_UNIVERSE, { axis: "staff" }),
    [],
    [],
    student,
  );
  assert.ok(!g.includes("student"));
});

test("contractor: a grantee whose grants widen nothing is denied everything", () => {
  // The inert sheet row — both axes 'none', every remit 'inherit' — still
  // mints a viewer, because the grant-reaches-a-viewer dbt test requires every
  // live row to resolve. That viewer must hold NO group at all: staff_directory
  // carries no row_level filter, so a staff-directory group here would hand a
  // contractor the whole unfiltered network directory.
  const g = a.buildGroups(CONTRACTOR, [], [], [], []);
  assert.deepEqual(g, []);
});

test("contractor: a staff-axis grant is what opens the directory to them", () => {
  // The complement of the test above — non-empty allowedAbbreviations means
  // some grant of theirs reached the staff axis, which is the condition.
  const g = a.buildGroups(CONTRACTOR, ["B"], [], [], []);
  assert.deepEqual(g, ["staff-directory"]);
});

test("employee: an empty staff allow-list still keeps the open directory", () => {
  // 4 employees resolve to staff_location_scope 'none' in prod today. The
  // directory is open to staff by policy, so is_employee — not the allow-list
  // — is what gates it; keying on the list alone would silently deny them.
  const g = a.buildGroups(
    { staff_key: "s1", is_employee: true },
    [],
    [],
    [],
    [],
  );
  assert.deepEqual(g, ["staff-directory"]);
});

test("buildGroups: a row missing is_employee falls to the grant check, not open access", () => {
  // Fail-closed on schema skew: if Cube deploys before the mart carries the
  // column, an unknown is_employee must not read as employee.
  assert.deepEqual(a.buildGroups({ staff_key: "s1" }, [], [], [], []), []);
  assert.deepEqual(a.buildGroups({ staff_key: "s1" }, ["B"], [], [], []), [
    "staff-directory",
  ]);
});

// --- resolveAccessDataset (I1) ---------------------------------------------
// The override redirects identity resolution, so its gates are a security
// boundary, not a convenience. Both must hold for a value to be honored.

test("resolveAccessDataset: unset reads prod", () => {
  assert.equal(a.resolveAccessDataset(undefined, false), "kipptaf_marts");
  assert.equal(a.resolveAccessDataset("", false), "kipptaf_marts");
});

test("resolveAccessDataset: a dev schema is honored on the local ADC path", () => {
  assert.equal(
    a.resolveAccessDataset("zz_someone_kipptaf_marts", false),
    "zz_someone_kipptaf_marts",
  );
});

test("resolveAccessDataset: deployment credentials override any value", () => {
  // Every working deployment sets CUBEJS_DB_BQ_CREDENTIALS (#4466), so this is
  // what makes the override unreachable on a deployment. Without it, a zz_
  // value set in prod config would let a developer grant themselves whatever
  // their own writable copy says.
  assert.equal(
    a.resolveAccessDataset("zz_someone_kipptaf_marts", true),
    "kipptaf_marts",
  );
  assert.equal(
    a.resolveAccessDataset("zz_stg_kipptaf_marts", true),
    "kipptaf_marts",
  );
});

test("resolveAccessDataset: a non-dev dataset is refused even locally", () => {
  for (const raw of [
    "kipptaf_marts_other",
    "kipptaf_google_sheets",
    "ZZ_UPPER_CASE",
    "zz_bad-chars",
    "../kipptaf_marts",
  ]) {
    assert.equal(a.resolveAccessDataset(raw, false), "kipptaf_marts", raw);
  }
});
