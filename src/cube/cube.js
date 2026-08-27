const access = require("./access");
const jwt = require("jsonwebtoken");
// CubejsHandlerError carries an HTTP status Cube's api-gateway honors; a bare
// Error from checkAuth becomes a 500. Resolved transitively from the bundled
// @cubejs-backend/server (not pinned in package.json, to avoid version skew).
const { CubejsHandlerError } = require("@cubejs-backend/api-gateway");

const groupCache = new Map(); // email → { ctx, expiresAt }

// Global (not per-email) cache of the "universes" computeAllowedAbbreviations
// / computeAllowedDepartmentGroups need: every location abbreviation+region
// and every distinct department_group. Same midnight-ET expiry as
// groupCache — one shared entry, not one per viewer.
// Latched so the ADC-fallback notice is emitted once per process, not once per
// identity-resolution cache miss.
let adcFallbackWarned = false;
let universeCache = null; // { data: { locations: [...], deptGroups: [...] }, expiresAt }

function nextMidnightEastern() {
  const now = new Date();
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hour12: false,
    })
      .formatToParts(now)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value }) => [type, +value]),
  );
  const msElapsedToday =
    (parts.hour * 3600 + parts.minute * 60 + parts.second) * 1000 +
    now.getMilliseconds();
  return now.getTime() + (24 * 60 * 60 * 1000 - msElapsedToday);
}

// All pure access-resolution logic (buildGroups, buildSecurityContext, the
// allow-list computations) lives in access.js (unit-tested). cube.js owns only
// the BigQuery identity reads + cache below.

// Fetches the domain-agnostic "universes" (all location abbreviations+regions,
// all distinct department groups) that access.computeAllowedAbbreviations /
// computeAllowedDepartmentGroups turn into per-viewer allow-lists. Cached
// globally (not per-email) until next midnight ET.
async function loadUniverses(bq) {
  if (universeCache && universeCache.expiresAt > Date.now())
    return universeCache.data;
  const [locs] = await bq.query({
    query: "SELECT abbreviation, region_key FROM `kipptaf_marts.dim_locations`",
  });
  // A NULL department_group can't be in the universe, and `department_group IN
  // (...)` never matches NULL — so a staff member with a NULL department_group
  // is invisible to every remit-scoped PII policy (fail-closed). Zero such rows
  // today; if that changes, backfill a sentinel group upstream.
  const [deps] = await bq.query({
    query:
      "SELECT DISTINCT department_group FROM `kipptaf_marts.dim_staff_cube_access` WHERE department_group IS NOT NULL",
  });
  const data = {
    locations: locs.map((r) => ({
      abbreviation: r.abbreviation,
      region_key: r.region_key,
    })),
    deptGroups: deps.map((r) => r.department_group),
  };
  universeCache = { data, expiresAt: nextMidnightEastern() };
  return data;
}

// Resolves a viewer's email to an enriched securityContext (access.js
// buildSecurityContext output, including `groups`). Shared by checkAuth
// (REST/MCP) and checkSqlAuth (SQL API) so both auth paths populate the same
// shape. Cached per-email until next midnight ET.
async function resolveAccess(email) {
  if (!email) return access.buildSecurityContext(null, []);
  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.ctx;

  // Local dev bypass (unchanged intent): CUBE_GROUP_MAP supplies groups only.
  if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
    const map = JSON.parse(process.env.CUBE_GROUP_MAP);
    const ctx = {
      ...access.buildSecurityContext(null, []),
      groups: map[email] ?? [],
    };
    groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
    return ctx;
  }

  try {
    const { BigQuery } = require("@google-cloud/bigquery");
    // Cube's data driver is configured via CUBEJS_DB_BQ_* and runs jobs in
    // teamster-332318. This hand-rolled client inherits none of that: a bare
    // `new BigQuery()` defaults to the Cube Cloud host project (cubejs-cloud),
    // where this identity has no bigquery.jobs.create — so every identity read
    // throws, resolveAccess fails closed, and the whole network is denied
    // (#4466). Pin the project + credentials to the driver's own config.
    // When CUBEJS_DB_BQ_CREDENTIALS is unset (e.g. local dev on ADC), fall back
    // to ADC like the BigQuery driver does, instead of JSON.parse("") throwing
    // and failing closed — which denies every viewer (#4526). Keep the projectId
    // pin so ADC bills teamster-332318, not the ambient Cube Cloud host project
    // (#4466).
    const bqOptions = { projectId: process.env.CUBEJS_DB_BQ_PROJECT_ID };
    if (process.env.CUBEJS_DB_BQ_CREDENTIALS) {
      bqOptions.credentials = JSON.parse(
        Buffer.from(process.env.CUBEJS_DB_BQ_CREDENTIALS, "base64").toString(
          "utf8",
        ),
      );
    } else if (!adcFallbackWarned) {
      // Falling back to ADC, which is what local dev runs on. Say so once, then
      // stay quiet. The fallback itself is correct, but on a DEPLOYMENT it
      // silently switches identity reads to the ambient Cube Cloud host
      // principal, which lacks bigquery.jobs.create and default-denies every
      // viewer for a reason that looks nothing like the cause (#4466). This line
      // is the breadcrumb that turns that into a two-second diagnosis.
      //
      // NODE_ENV is deliberately NOT the discriminator. The documented local RLS
      // sign-off runs `NODE_ENV=production CUBEJS_DEV_MODE=false npm run dev`,
      // so refusing the fallback under NODE_ENV=production would fail-close the
      // exact workflow the fallback exists for. There is no reliable Cube Cloud
      // marker to gate on, so warn rather than throw.
      adcFallbackWarned = true;
      console.warn(
        JSON.stringify({
          event: "cube_bq_credentials_fallback",
          message:
            "CUBEJS_DB_BQ_CREDENTIALS is unset; identity reads are using ambient ADC. Expected locally. On a deployment, set it on THIS environment — branch environments do not inherit it.",
        }),
      );
    }
    const bq = new BigQuery(bqOptions);
    const [rows] = await bq.query({
      query:
        "SELECT * FROM `kipptaf_marts.dim_staff_cube_access` WHERE google_email = @email ORDER BY staff_key LIMIT 1",
      params: { email },
    });
    const row = rows[0] ?? null;
    let reporteeStaffKeys = [];
    if (row?.staff_key) {
      const [rc] = await bq.query({
        query:
          "SELECT reportee_staff_key FROM `kipptaf_marts.dim_staff_reporting_chain` WHERE manager_staff_key = @k",
        params: { k: row.staff_key },
      });
      reporteeStaffKeys = rc.map((r) => r.reportee_staff_key);
    }
    const universes = await loadUniverses(bq);
    const allowedAbbreviations = access.computeAllowedAbbreviations(
      row?.staff_location_scope,
      row?.region_key,
      row?.location_abbreviation,
      universes.locations,
    );
    const allowedDepartmentGroups = access.computeAllowedDepartmentGroups(
      row?.staff_department_scope,
      row?.department_group,
      universes.deptGroups,
    );
    const ctx = access.buildSecurityContext(
      row,
      reporteeStaffKeys,
      allowedAbbreviations,
      allowedDepartmentGroups,
    );
    groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
    return ctx;
  } catch (err) {
    console.error(`resolveAccess failed for ${email}:`, err);
    return access.buildSecurityContext(null, []); // fail closed, stay available
  }
}

// Convention for snapshot cubes: cumulative daily flags that overcount without
// a point-in-time anchor. All snapshot cubes expose these three dimensions.
const SNAPSHOT_ANCHOR_DIMENSIONS = {
  default: "is_latest_record",
  month: "is_month_end_record",
  week: "is_week_end_record",
};

// Per-cube override of the no-granularity default anchor. Enrollment's default
// is the per-school period-end-as-of-now flag (is_current_record), not the
// per-student-last-day flag (is_latest_record = "served"). Falls back to
// SNAPSHOT_ANCHOR_DIMENSIONS for any cube not listed here, so attendance's
// resolved anchor map is byte-for-byte unchanged.
const SNAPSHOT_ANCHOR_OVERRIDES = {
  student_enrollments: { default: "is_current_record" },
};
const SNAPSHOT_SELF_ANCHORED_SUFFIXES = [
  "_year_end",
  "_month_end",
  "_week_end",
];

// Add a cube name here when it exposes is_latest_record / is_month_end_record
// / is_week_end_record and its measures need the anchor guard. Also add the
// cube's snapshot measure stems under the same key in SNAPSHOT_MEASURE_STEMS
// below — a cube in this list with no stems entry matches nothing (guard no-op).
const SNAPSHOT_CUBES = ["student_attendance"];

// Per-cube measure-name stems that mark a snapshot measure needing the
// period-end anchor guard. Keyed per cube (like SNAPSHOT_ANCHOR_OVERRIDES) so a
// stem matches ONLY its own cube — a flat shared list substring-matches across
// cubes (e.g. a stem defined for one cube could wrongly catch a same-named
// measure on another). Which measures need the guard, by cube:
//   student_attendance: chronic absence / ADA tiers / truancy are cumulative
//     daily flags (re-stamped each row) — count_distinct over a range without an
//     anchor overcounts. Its ADDITIVE measures (avg_daily_attendance,
//     count_students, pct_tardy, pct_ontime, count_absent_days) are NOT listed —
//     they are point-in-time safe and must stay unanchored.
// This cube's weekly trends are driven by a school_week_start_date grouping
// (PowerSchool school weeks), not Cube's ISO granularity: "week".
const SNAPSHOT_MEASURE_STEMS = {
  student_attendance: ["chronically_absent", "tier_1_2", "tier_3", "truant"],
};

// Query member cube-name matching must be boundary-safe. A plain
// `m.startsWith(cubePrefix)` treats ANY cube/view whose name merely extends
// cubePrefix as a substring (e.g. student_attendance_periods /
// student_attendance_periods_view) as if it were student_attendance itself —
// sweeping its measures into this guard and injecting a filter on a cube the
// query never joins ("Can't find join path to join ..."). Match only the two
// real forms in use: the bare cube name (a direct cube query) and
// `<cube>_view` (the collapsed public view, e.g. student_attendance_view).
function memberMatchesSnapshotCube(member, cubePrefix) {
  const memberCube = member.split(".")[0];
  return memberCube === cubePrefix || memberCube === `${cubePrefix}_view`;
}

// Turns a jsonwebtoken failure into a message that names the failed check, so a
// 403 is diagnosable without server access. jsonwebtoken reports both the maxAge
// cap and the token's own `exp` as TokenExpiredError, distinguished only by the
// message text — hence the string check rather than a type check.
function jwtRejectionReason(err) {
  if (err?.name === "TokenExpiredError") {
    return String(err.message).includes("maxAge")
      ? "Token too old: exceeds the 12h maxAge cap measured from `iat`. Re-mint it (in the Playground, clear localhost local storage or re-save the security context)."
      : "Token expired: past its own `exp`.";
  }
  if (err?.name === "JsonWebTokenError") {
    // Covers a bad signature, a wrong/absent CUBEJS_API_SECRET on this
    // deployment, a missing `iat` under maxAge, and alg:none. Naming the secret
    // matters: an unset one on a branch environment is the likeliest cause and
    // is otherwise invisible.
    // One message is withheld. jsonwebtoken reports an UNSET secret as "secret
    // or public key must be provided" — that is deployment state, not a fact
    // about the caller's own token, and an unauthenticated caller learns from it
    // that this deployment has no signing secret at all. Every other message
    // here describes the token they minted, so it stays verbatim.
    const detail = String(err.message).startsWith("secret or public key")
      ? "the server could not verify it"
      : err.message;
    return `Invalid token: ${detail}. Check the signing secret matches this deployment's CUBEJS_API_SECRET, and that the token carries an \`iat\`.`;
  }
  return "Invalid token";
}

// Emulation moves PII visibility, so every emulated request leaves a trail in
// the deployment logs. Identities and a timestamp only — never row data.
function logEmulation(surface, caller, target) {
  console.log(
    JSON.stringify({
      event: "cube_emulation",
      surface,
      caller,
      target,
      at: new Date().toISOString(),
    }),
  );
}

module.exports = {
  driverFactory: () => ({
    type: "bigquery",
    database: "kipptaf_marts",
  }),

  contextToGroups: async ({ securityContext }) => {
    // Cube Cloud bypasses checkAuth and injects its own context, so
    // resolveAccess never runs on this path and every gated view default-denied
    // for console users (#4526). Enrich it here.
    //
    // CRITICAL: Cube Cloud MERGES a pasted Security Context into the TOP LEVEL
    // of this object. Every top-level value is therefore caller-supplied and
    // untrusted — including `groups` itself and the `region_key` /
    // `allowed_abbreviations` / `allowed_department_groups` values the
    // access_policy row_level filters interpolate. A console user pasting
    // `{"groups": ["staff-pii-all_in_scope"], "allowed_abbreviations": [...]}`
    // was previously honored verbatim, because the old one-line
    // `securityContext?.groups ?? []` read straight from that merged object.
    //
    // So this ALWAYS re-derives and OVERWRITES, never conditionally on whether
    // `groups` is already present. resolveAccess's output covers every key any
    // policy interpolates, so assigning it over the top neutralizes anything
    // pasted. Do not reintroduce a `!securityContext.groups` guard here — that
    // is exactly the bypass.
    //
    // Emulation: `cubeCloud.username` is the authenticated console user; a
    // pasted target arrives as top-level `email` (also mirrored at
    // `cubeCloud.userAttributes.email`). The same admin gate as the REST
    // `act_as` path applies, so a non-impersonator's pasted email is ignored and
    // they resolve as themselves.
    //
    // TRUST NOTE for code-owner review: `cubeCloud.username` is asserted by Cube
    // Cloud, not verified by our own `jwt.verify`. Before this change console
    // identity was not load-bearing for data access; now Cube Cloud's console
    // authentication establishes identity for RLS. Deliberate, and on par with
    // the trust the SQL API places in the connecting user.
    //
    // SECOND, SEPARATE ASSUMPTION, load-bearing and worth stating: a paste
    // cannot REPLACE the `cubeCloud` key itself. Cube Cloud must apply its own
    // block after the paste (`{...paste, cubeCloud: realBlock}`), or a console
    // user could paste `{"cubeCloud": {"username": "<anyone>"}}` and resolve that
    // person's real context — which would collapse this whole design, not just
    // the gate below. Tested on a Cube Cloud Dev Mode deployment: a
    // network-scoped caller pasting a school-scoped viewer's email as
    // `cubeCloud.username` still got their own four-region scope, so the injected
    // block wins — including against a FALSY paste. Pasting
    // `{"cubeCloud": null, "groups": ["student-region"], "region_key": "<a region>"}`
    // returned the caller's own four-region scope, not the single pasted region:
    // the gate still fired (so `cubeCloud: null` did not survive the merge) and
    // the pasted `groups` + `region_key` were both overwritten. That is the merge
    // order this gate needs, `{...paste, cubeCloud: realBlock}`, which makes the
    // pasted VALUE irrelevant.
    //
    // Empirical, not guaranteed: Cube Cloud's merge is closed-source and the OSS
    // tree carries no reference to `cubeCloud`, so re-confirm after a Cube Cloud
    // upgrade rather than treating it as settled.
    //
    // Determinism matters: Cube caches the selected policies under a hash of
    // this context computed BEFORE the hook runs
    // (`CompilerApi.hashRequestContext`), so the same input must always produce
    // the same output. Re-deriving unconditionally is deterministic — the
    // per-email cache in resolveAccess makes re-entry cheap.
    // Gate on the `cubeCloud` KEY, not on `cubeCloud.username`. A Cube Cloud
    // context whose username is absent must still be neutralized: falling
    // through to the `securityContext?.groups` return below would honor a pasted
    // `groups`, which is the exact bypass the overwrite exists to close. The
    // body needs no null handling for it — emulationInputsFromCubeCloud yields a
    // null caller, resolveEmulationTarget fails closed to a null target, and
    // resolveAccess(null) returns the empty default-deny context. So a missing
    // username denies cleanly instead of passing the paste through.
    if (securityContext?.cubeCloud) {
      const { caller, target, emulating } = access.resolveEmulationTarget({
        // Same shape as the REST branch above, via the surface adapter — the
        // caller/target extraction lives in access.js so both paths and their
        // unit tests exercise one implementation.
        ...access.emulationInputsFromCubeCloud(securityContext),
        impersonators: access.parseImpersonators(
          process.env.CUBE_IMPERSONATORS,
        ),
      });
      if (emulating) logEmulation("cubecloud", caller, target);
      Object.assign(securityContext, await resolveAccess(target));
    }
    return securityContext?.groups ?? [];
  },

  checkAuth: async (req, auth) => {
    // `auth` is the raw bearer token STRING (a custom checkAuth replaces Cube's
    // default JWT verify+decode). Verify the HS256 signature against
    // CUBEJS_API_SECRET ourselves, then resolve identity from the email claim.
    // An invalid/expired token → clean 403 (see catch below). A request with no
    // Authorization header intentionally resolves to the empty default-deny
    // context (200 + zero rows), NOT a 403: the data is fully protected either
    // way, and this lets an unauthenticated capability probe get a no-access
    // context rather than an error. The 403 is reserved for a token that is
    // present but invalid.
    let payload;
    if (auth) {
      try {
        // maxAge is a defense-in-depth cap independent of the token's own
        // `exp`: it derives from `iat` (issued-at) instead, so a compromised
        // or misconfigured minter can't extend a token's life by inflating
        // `exp` alone — jsonwebtoken rejects any token missing `iat` once
        // maxAge is set (fails closed). `mcp/server.py`'s `_mint_token` sets
        // both `iat` and a 5-minute `exp`, so this 12h ceiling is a backstop,
        // not the primary control.
        payload = jwt.verify(auth, process.env.CUBEJS_API_SECRET, {
          algorithms: ["HS256"],
          maxAge: "12h",
          // Absorb minor minter/server clock skew so a short-lived (5-min) token
          // isn't spuriously 403'd near its edges. Small relative to the token
          // life, and it fails closed — an expired token past the tolerance is
          // still rejected.
          clockTolerance: 30,
        });
      } catch (err) {
        // Mirror Cube's default checkAuth: a bad/expired token is a clean 403,
        // not a bare-Error 500 (only CubejsHandlerError carries a status).
        //
        // Say WHICH check failed. A single "Invalid token" for every failure is
        // what makes the maxAge cap a trap rather than a control: a Playground
        // token cached over 12h denies every view, and the symptom is
        // indistinguishable from a wrong secret or a missing one — so it reads as
        // an access-policy bug and costs an hour. The status stays 403 and the
        // control is unchanged; only the message differs. This leaks nothing
        // useful: a caller already knows their own token's age, and learning
        // "too old" versus "bad signature" does not help forge a signature.
        throw new CubejsHandlerError(
          403,
          "Forbidden",
          jwtRejectionReason(err),
          err,
        );
      }
    }
    // Admin-gated emulation (#4526): an approved impersonator may pass an
    // `act_as` claim and get that target's real HR-derived context. For anyone
    // else `act_as` is ignored and they keep their own scope. The gate reads the
    // SIGNED `email` claim, so it is unforgeable. A future API-key branch
    // (#4501) slots in beside this one — it resolves a different context source,
    // not a different emulation rule.
    const { caller, target, emulating } = access.resolveEmulationTarget({
      ...access.emulationInputsFromToken(payload),
      impersonators: access.parseImpersonators(process.env.CUBE_IMPERSONATORS),
    });
    if (emulating) logEmulation("rest", caller, target);
    req.securityContext = await resolveAccess(target);
  },

  checkSqlAuth: async (req, user, password) => {
    const email =
      (process.env.NODE_ENV !== "production" &&
        process.env.CUBE_SQL_DEV_EMAIL) ||
      user;
    // Fail closed on an unset/blank SQL password: Cube validates the presented
    // password against the RETURNED one, so returning the env var unconditionally
    // would validate presented passwords against `undefined` when it is absent —
    // potentially accepting a blank-password connection. Return null to reject
    // every connection instead (Task 1 verdict: a null password rejects). The
    // REST path already fails closed here because jwt.verify throws on an absent
    // CUBEJS_API_SECRET.
    const sqlPassword = process.env.CUBEJS_SQL_PASSWORD;
    if (!sqlPassword) {
      console.error(
        "checkSqlAuth: CUBEJS_SQL_PASSWORD is not set — rejecting SQL API connection",
      );
      return {
        password: null,
        securityContext: access.buildSecurityContext(null, []),
      };
    }
    // Return the server-known SQL password (Cube's canonical checkSqlAuth
    // pattern). RLS identity is resolved from the connecting `user` (the email),
    // not from the presented password — which is absent on SET-USER re-auth
    // flows, so do not compare against it.
    return {
      password: sqlPassword,
      securityContext: await resolveAccess(email),
    };
  },

  queryRewrite: (query) => {
    const filters = [...(query.filters ?? [])];

    // Snapshot anchor guard: for cubes with cumulative daily flags, inject
    // the appropriate period-end anchor when the query has none.
    // Named measures (_year_end, _month_end, _week_end) have anchors baked in
    // but require matching granularity — _month_end without grouping by month
    // returns "CA at any month-end during the range," which is meaningless.
    for (const cubePrefix of SNAPSHOT_CUBES) {
      const stems = SNAPSHOT_MEASURE_STEMS[cubePrefix] ?? [];
      const measures = (query.measures ?? []).filter(
        (m) =>
          memberMatchesSnapshotCube(m, cubePrefix) &&
          stems.some((stem) => m.includes(stem)),
      );
      if (!measures.length) continue;

      const dateDayTd = (query.timeDimensions ?? []).find((td) =>
        td.dimension?.endsWith("dates_date_day"),
      );
      const granularity = dateDayTd?.granularity ?? null;

      const groupsBySchoolWeek = [
        ...(query.dimensions ?? []),
        ...(query.timeDimensions ?? []).map((td) => td.dimension),
      ].some((m) => m && m.split(".").pop() === "dates_school_week_start_date");

      // School weeks (PowerSchool week_start_monday, via dim_dates) replace Cube's
      // ISO week for snapshot measures: the *_week_end anchors are school-week-based,
      // so weekly trends MUST group by dates_school_week_start_date. Treat that
      // grouping as the "week" period; Cube's native granularity drives only day/month.
      const period = groupsBySchoolWeek ? "week" : granularity;

      if (granularity === "week" && !groupsBySchoolWeek) {
        throw new Error(
          "Weekly snapshot trends use school weeks — group by " +
            '<view>.dates_school_week_start_date, not Cube\'s granularity: "week" ' +
            "(ISO Monday weeks do not match PowerSchool school weeks).",
        );
      }

      // Named period-end measures must be grouped by the matching period.
      // Without it, the result is "CA at any period-end during the range."
      for (const { suffix, ok, hint } of [
        {
          suffix: "_month_end",
          ok: granularity === "month",
          hint: 'timeDimensions granularity: "month"',
        },
        {
          suffix: "_week_end",
          ok: groupsBySchoolWeek,
          hint: "a dates_school_week_start_date grouping",
        },
      ]) {
        if (measures.some((m) => m.endsWith(suffix)) && !ok) {
          throw new Error(
            `${suffix} measures must be grouped by ${hint}. Without it, the ` +
              `result counts students across all period-ends in the date range, ` +
              `not a per-period breakdown.`,
          );
        }
      }

      const hasUnanchoredMeasure = measures.some(
        (m) => !SNAPSHOT_SELF_ANCHORED_SUFFIXES.some((s) => m.endsWith(s)),
      );
      if (!hasUnanchoredMeasure) continue;

      if (granularity && !["day", "week", "month"].includes(granularity)) {
        throw new Error(
          `Snapshot measures (e.g. pct_chronically_absent) do not support ` +
            `"${granularity}" granularity. Use the day-level base measure, ` +
            `or the _week_end / _month_end named measures for week/month ` +
            `trends, or omit timeDimensions for a year-end snapshot.`,
        );
      }

      if (period === "day") continue;

      const anchorMap = {
        ...SNAPSHOT_ANCHOR_DIMENSIONS,
        ...(SNAPSHOT_ANCHOR_OVERRIDES[cubePrefix] ?? {}),
      };
      const anchorDimension = anchorMap[period] ?? anchorMap.default;
      const anchorMember = `${cubePrefix}.${anchorDimension}`;

      const alreadyAnchored =
        filters.some(
          (f) =>
            Object.values(anchorMap).some((d) => f.member?.endsWith(d)) &&
            f.operator === "equals" &&
            [true, "true", "1"].includes(f.values?.[0]),
        ) ||
        filters.some(
          (f) =>
            f.member?.endsWith("dates_date_day") &&
            f.operator === "equals" &&
            Array.isArray(f.values) &&
            f.values.length === 1,
        ) ||
        (query.dimensions ?? []).some((d) => d.endsWith("dates_date_day")) ||
        // A point-in-time pin expressed via timeDimensions counts as anchored
        // only when it is a single day — a single-element dateRange or
        // granularity "day". A wider dateRange with null granularity is NOT
        // anchored (injecting the period-end snapshot is correct there;
        // treating it as anchored would re-open the "ever-CA-in-range"
        // overcount). Reuse dateDayTd found above rather than re-scanning.
        // A single-day dateRange is either one element (["2025-01-15"], which
        // Cube treats as start === end) or two equal elements.
        (dateDayTd &&
          ((Array.isArray(dateDayTd.dateRange) &&
            (dateDayTd.dateRange.length === 1 ||
              dateDayTd.dateRange[0] === dateDayTd.dateRange[1])) ||
            dateDayTd.granularity === "day"));

      if (!alreadyAnchored) {
        filters.push({
          member: anchorMember,
          operator: "equals",
          values: [true],
        });
      }
    }

    return { ...query, filters };
  },

  canSwitchSqlUser: (current_user, new_user) =>
    current_user === process.env.CUBEJS_SQL_SUPER_USER &&
    new_user.endsWith("@apps.teamschools.org"),
};
