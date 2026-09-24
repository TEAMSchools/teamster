# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "psycopg[binary]>=3.3",
#   "pyyaml>=6.0",
# ]
# ///

"""Validate Cube row-level security by emulating each viewer over the SQL API.

Ground-truth pre-pilot check. Cube's `checkSqlAuth` resolves identity from the
connecting SQL user, so one connection per viewer email runs the SAME query under
a different security context — any difference in the result is attributable to
access policy alone, not to the query.

This is the surface a BI tool (Superset, Tableau) actually uses, which is why it
is the sign-off tool rather than the REST Playground.

Viewer emails are staff PII: pass them as arguments or in a local file (e.g.
under `.claude/scratch/`, which is gitignored). Never commit a viewer list, and
never paste this script's output into a PR, issue, or Slack message — summarize
it instead ("5 viewers checked, all scopes as intended").

Requires the local Cube server with the SQL API enabled (`CUBEJS_PG_SQL_PORT`,
`CUBEJS_SQL_USER`, `CUBEJS_SQL_PASSWORD`) — see `docs/guides/cube.md`.

Start it with auth ON, not the plain "Cube: Dev Server" task:

    cd src/cube && NODE_ENV=production CUBEJS_DEV_MODE=false npm run dev

Scoped viewers report the same rows either way, but a DEV-MODE server downgrades
an out-of-tier member request to a quiet "0 rows" where production hard-fails
("Table or CTE with name '<view>' not found"). Signing off from a dev-mode run
therefore reports a falsely benign result for out-of-tier members. This is a
mode difference, not a Cube version difference — measured identical on 1.6.59
and 1.7.14 (#4605).

With `--expect`, it stops being a human-read matrix and becomes an assertion
runner: each entry in the canaries file names a persona, a query shape and an
expected outcome, and any mismatch exits non-zero. The sandbox's personas are
fabricated and committed, so that file carries no PII and both KTAF CI and
MasterBorn's kit suite run it unmodified.

Usage:
    uv run scripts/cube_rls_matrix.py --viewers a@x.org b@x.org
    uv run scripts/cube_rls_matrix.py --viewers-file .claude/scratch/viewers.txt
    uv run scripts/cube_rls_matrix.py --viewers a@x.org --query "SELECT ..."
    uv run scripts/cube_rls_matrix.py --expect src/cube/sandbox/canaries.yml

Design reference:
    docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml

# The SQL API's denial text. Cube reports an out-of-tier or default-denied
# view as if the relation did not exist, so this exact shape IS the denial.
# Matching a bare "not found" instead would also accept a column-not-found or
# dataset-not-found error, and a canary that passes on the wrong error is
# worse than one that fails.
#
# One ambiguity survives and cannot be resolved here: a misconfigured
# CUBEJS_SCHEMA_PATH compiles an EMPTY schema, which produces this same
# string for every view. That is why the canaries must include a ROWS
# expectation — an empty schema fails those, where a BLOCKED-only suite would
# report a uniformly green deny.
_DENIED = re.compile(r"table or cte with name '.+' not found", re.IGNORECASE)

EXPECTATIONS = ("BLOCKED", "ZERO", "ROWS")

# Region breakdown of student enrollment. count_students is a distinct-student
# count over whatever slice is queried, with no anchor filter, and the fact
# carries a row for every enrolled calendar day including breaks — so it returns
# real numbers year-round and a 0 can only mean a scope denial.
DEFAULT_QUERY = (
    "SELECT regions_region_name, MEASURE(count_students) "
    "FROM student_attendance_enrollment_daily_view GROUP BY 1 ORDER BY 1"
)


# The local dev server ignores the database name; Cube Cloud does not.
LOCAL_DBNAME = "cube"


@dataclass(frozen=True)
class CubeConnection:
    """Local Cube SQL API connection settings, shared across every viewer."""

    host: str
    port: int
    dbname: str
    password: str | None
    query: str


@dataclass(frozen=True)
class Canary:
    """One declared expectation: this persona, this query, this outcome."""

    persona: str
    query_shape: str
    expect: str
    why: str = ""


def expectation_met(expect: str, rows: list[tuple], error: str | None) -> bool:
    """Whether one viewer's result matches its declared expectation.

    BLOCKED asserts a REAL denial. A quiet zero rows is a FAILURE, not a
    pass — that one distinction is what mechanically forces production-mode
    sign-off, because a dev-mode runner downgrades an out-of-tier member
    request to 0 rows where production hard-fails (#4605). Treating that as a
    pass reports a falsely benign matrix, which is the failure this whole
    tool exists to prevent.
    """
    match expect:
        case "BLOCKED":
            return error is not None and bool(_DENIED.search(error))
        case "ZERO":
            return error is None and not rows
        case "ROWS":
            return error is None and bool(rows)
        case _:
            raise ValueError(f"unknown expectation {expect!r}")


def load_canaries(path: Path) -> list[Canary]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    canaries = [Canary(**entry) for entry in doc.get("canaries", [])]
    if not canaries:
        raise ValueError(f"{path} declares no canaries")
    for canary in canaries:
        if canary.expect not in EXPECTATIONS:
            raise ValueError(
                f"unknown expectation {canary.expect!r} for {canary.persona}; "
                f"expected one of {', '.join(EXPECTATIONS)}"
            )
    # A suite of BLOCKED-only canaries goes green against an empty compiled
    # schema, where every view reports "not found" for everyone. At least one
    # ROWS expectation is what makes a uniformly-denying deployment fail.
    if not any(c.expect == "ROWS" for c in canaries):
        raise ValueError(
            f"{path} declares no ROWS canary: a BLOCKED-only suite passes "
            "against a deployment that denies everyone, which looks exactly "
            "like perfect isolation"
        )
    return canaries


# Cube Cloud routes on the database name: it selects the deployment, and a
# name it does not recognise is refused before any query runs. The local dev
# server ignores it, so `cube` works there and nowhere else.
CLOUD_DBNAME_REFUSAL = "db is required and must be in one of the following formats"


def preflight(connection: CubeConnection, viewer: str) -> None:
    """Fail once on a setup error, instead of ten times on the same one.

    Every canary opens its own connection, so a wrong host, password or
    database name produces one identical multi-line FATAL per canary and
    buries the single thing that is actually wrong. Worse, each of those
    reads as `expected BLOCKED, got error` — which is the shape of a real
    denial, and the runner exists to keep those two apart.
    """
    _, error = run_for_viewer(
        viewer,
        CubeConnection(
            host=connection.host,
            port=connection.port,
            dbname=connection.dbname,
            password=connection.password,
            query="SELECT 1",
        ),
    )
    if error is None:
        return
    if CLOUD_DBNAME_REFUSAL in error:
        raise SystemExit(
            f"Cube Cloud refused the database name {connection.dbname!r}.\n\n"
            f"It routes on that name: it has to be the DEPLOYMENT's name, as "
            f"Cube Cloud shows it, not a schema you choose. The default here "
            f"is {LOCAL_DBNAME!r}, which is right for the local dev server and "
            f"wrong for every Cube Cloud deployment.\n\n"
            f"  --dbname <deployment-name>\n"
        )
    if error.startswith("connection failed"):
        raise SystemExit(
            f"cannot reach the SQL API at {connection.host}:{connection.port} "
            f"-- {error}\n\nNo canary ran, so nothing was proven either way.\n"
        )


def run_canaries(canaries: list[Canary], connection: CubeConnection) -> int:
    """Assert every canary, reporting each. Non-zero on any mismatch."""
    preflight(connection, canaries[0].persona)
    failures = 0
    for canary in canaries:
        rows, error = run_for_viewer(
            canary.persona,
            CubeConnection(
                host=connection.host,
                port=connection.port,
                dbname=connection.dbname,
                password=connection.password,
                query=canary.query_shape,
            ),
        )
        met = expectation_met(canary.expect, rows, error)
        observed = f"error: {error}" if error else f"{len(rows)} row(s)"
        if met:
            print(f"PASS  {canary.persona} expected {canary.expect}, got {observed}")
            continue
        failures += 1
        print(f"FAIL  {canary.persona} expected {canary.expect}, got {observed}")
        if canary.why:
            print(f"      why it should hold: {canary.why}")

    print(f"\n{len(canaries)} canary/canaries checked, {failures} failed.")
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--viewers", nargs="+", help="viewer emails to emulate, space-separated"
    )
    source.add_argument(
        "--viewers-file",
        type=Path,
        help="file with one viewer email per line (blank lines and # comments ignored)",
    )
    source.add_argument(
        "--expect",
        type=Path,
        help="canaries YAML to assert instead of printing a matrix; "
        "exits non-zero on any mismatch",
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="SQL to run per viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=15432)
    parser.add_argument(
        "--dbname",
        default=LOCAL_DBNAME,
        help="the database to connect to. Cube Cloud routes on this and "
        "requires the DEPLOYMENT's name; the default suits the local dev "
        "server only",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("CUBEJS_SQL_PASSWORD"),
        help="local Cube SQL API password (defaults to the CUBEJS_SQL_PASSWORD value)",
    )
    return parser.parse_args()


def load_viewers(viewers: list[str] | None, viewers_file: Path | None) -> list[str]:
    if viewers:
        return viewers
    if viewers_file is None:
        # Unreachable via the CLI: parse_args puts --viewers and --viewers-file in
        # a required mutually exclusive group. Raise rather than assert, so the
        # narrowing survives -O and bandit does not flag a stripped check.
        raise ValueError("pass either viewers or viewers_file")
    lines = viewers_file.read_text(encoding="utf-8").splitlines()
    return [
        stripped
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]


def run_for_viewer(
    viewer: str, connection: CubeConnection
) -> tuple[list[tuple], str | None]:
    """Return (rows, error) for one viewer.

    Identity is the connecting user, so opening a connection per viewer is what
    switches the security context — there is no in-session way to swap it.

    prepare_threshold=None disables psycopg's automatic statement preparation.
    Cube's SQL API is a partial Postgres implementation, and preparing repeated
    statements against it is an unnecessary risk when each viewer runs the query
    exactly once.
    """
    try:
        with (
            psycopg.connect(
                host=connection.host,
                port=connection.port,
                user=viewer,
                password=connection.password,
                dbname=connection.dbname,
                prepare_threshold=None,
            ) as conn,
            conn.cursor() as cur,
        ):
            # psycopg types `query` as LiteralString to make injection hard to
            # write by accident. This query is a CLI argument by design — the
            # operator chooses what to run as each viewer — so it can never be a
            # literal, and there is no runtime problem to fix here.
            # trunk-ignore(pyright/reportCallIssue,pyright/reportArgumentType): operator-supplied CLI query, not a literal
            cur.execute(connection.query)
            return cur.fetchall(), None
    except psycopg.Error as err:
        # Report and continue: one unreachable or denied viewer must not abort
        # the rest of the matrix, since the comparison across viewers is the
        # whole point.
        first_line = next(iter(str(err).strip().splitlines()), "unknown error")
        return [], first_line


def main() -> int:
    args = parse_args()
    if not args.password:
        print(
            "No SQL password given: pass --password, or set the CUBEJS_SQL_PASSWORD"
            " value in your shell.",
            file=sys.stderr,
        )
        return 1

    connection = CubeConnection(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        password=args.password,
        query=args.query,
    )

    if args.expect:
        return run_canaries(load_canaries(args.expect), connection)

    viewers = load_viewers(args.viewers, args.viewers_file)
    if not viewers:
        print("No viewer emails to test.", file=sys.stderr)
        return 1

    failures = 0
    empty = 0
    # One fingerprint per viewer that returned rows, so identical result sets are
    # detectable. Rows are stringified before sorting because a NULL dimension
    # value cannot be compared against a string (None < 'Camden' raises).
    fingerprints: list[str] = []
    for viewer in viewers:
        rows, error = run_for_viewer(viewer, connection)
        if error:
            failures += 1
            print(f"{viewer}: FAILED - {error}")
            continue
        if not rows:
            empty += 1
            print(f"{viewer}: 0 rows (default-deny, or no scope on this view)")
            continue
        fingerprints.append(repr(sorted(repr(row) for row in rows)))
        print(f"{viewer}: {len(rows)} group(s)")
        for row in rows:
            print(f"    {row}")

    print(f"\n{len(viewers)} viewer(s) checked, {failures} failed, {empty} at 0 rows.")
    all_zero = empty == len(viewers)
    # A SINGLE viewer at 0 rows is a documented, legitimate PASS: validating
    # default-deny for a `none`-scope viewer is exactly this scenario (see the
    # docstring's usage example and docs/guides/cube.md), and the cross-viewer
    # comparison this gate exists for needs at least two viewers to mean
    # anything. Only 2+ viewers all landing at 0 rows is never legitimate.
    multi_viewer_all_zero = all_zero and len(viewers) > 1
    if multi_viewer_all_zero:
        print(
            "EVERY viewer returned 0 rows, including any network-scoped one. That"
            " usually means the identity read itself failed rather than the"
            " policies denying - check the dev-server log for 'resolveAccess"
            " failed for', and confirm CUBE_GROUP_MAP is not set."
        )
    elif all_zero:
        print(
            "0 rows for the single viewer checked. That is the expected result"
            " when deliberately validating default-deny for a `none`-scope"
            " viewer - not an error. This tool's cross-viewer comparison needs"
            " 2+ viewers to say anything; pass more viewers if you meant to"
            " compare scopes."
        )
    elif len(fingerprints) > 1 and len(set(fingerprints)) == 1:
        print(
            "EVERY viewer returned IDENTICAL rows. That is correct only if they"
            " genuinely share a scope (e.g. two network-scoped viewers)."
            " Otherwise CUBE_SQL_DEV_EMAIL is set, which overrides the connecting"
            " user and pins every connection to one identity - unset it and"
            " restart the dev server."
        )
    # "All zero" across 2+ viewers can never be a legitimate pass (see docstring
    # above), so it must fail the gate on its own even when every individual
    # connection succeeded. A single viewer at 0 rows is left at the ordinary
    # exit status - see multi_viewer_all_zero above. The "all identical" case is
    # also left at the ordinary exit status: it can be a true positive (two
    # viewers who really do share one scope) as well as a false positive
    # (CUBE_SQL_DEV_EMAIL pinning), and telling those apart needs a human to
    # check the viewer list - the diagnostic flags it, but exit status would be
    # misleading either way we exited from here.
    return 1 if failures or multi_viewer_all_zero else 0


if __name__ == "__main__":
    sys.exit(main())
