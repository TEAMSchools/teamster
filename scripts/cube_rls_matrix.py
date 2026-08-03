# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "psycopg[binary]>=3.3",
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

Usage:
    uv run scripts/cube_rls_matrix.py --viewers a@x.org b@x.org
    uv run scripts/cube_rls_matrix.py --viewers-file .claude/scratch/viewers.txt
    uv run scripts/cube_rls_matrix.py --viewers a@x.org --query "SELECT ..."

Design reference:
    docs/superpowers/specs/2026-07-23-cube-internal-user-emulation-design.md
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

# Region breakdown of student attendance. Chosen because student_attendance's
# count_students is stint-keyed and additive, so it returns real numbers
# year-round — student_enrollments.count_students anchors to is_current_record
# and reads 0 off-season, which looks identical to a scope denial.
DEFAULT_QUERY = (
    "SELECT regions_region_name, MEASURE(count_students) "
    "FROM student_attendance_view GROUP BY 1 ORDER BY 1"
)


@dataclass(frozen=True)
class CubeConnection:
    """Local Cube SQL API connection settings, shared across every viewer."""

    host: str
    port: int
    dbname: str
    password: str | None
    query: str


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
    parser.add_argument("--query", default=DEFAULT_QUERY, help="SQL to run per viewer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=15432)
    parser.add_argument("--dbname", default="cube")
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

    viewers = load_viewers(args.viewers, args.viewers_file)
    if not viewers:
        print("No viewer emails to test.", file=sys.stderr)
        return 1

    connection = CubeConnection(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        password=args.password,
        query=args.query,
    )

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
    if all_zero:
        print(
            "EVERY viewer returned 0 rows, including any network-scoped one. That"
            " usually means the identity read itself failed rather than the"
            " policies denying - check the dev-server log for 'resolveAccess"
            " failed for', and confirm CUBE_GROUP_MAP is not set."
        )
    elif len(fingerprints) > 1 and len(set(fingerprints)) == 1:
        print(
            "EVERY viewer returned IDENTICAL rows. That is correct only if they"
            " genuinely share a scope (e.g. two network-scoped viewers)."
            " Otherwise CUBE_SQL_DEV_EMAIL is set, which overrides the connecting"
            " user and pins every connection to one identity - unset it and"
            " restart the dev server."
        )
    # "All zero" can never be a legitimate pass (see docstring above), so it must
    # fail the gate on its own even when every individual connection succeeded.
    # The "all identical" case is left at the ordinary exit status: it can be a
    # true positive (two viewers who really do share one scope) as well as a
    # false positive (CUBE_SQL_DEV_EMAIL pinning), and telling those apart needs
    # a human to check the viewer list - the diagnostic flags it, but exit status
    # would be misleading either way we exited from here.
    return 1 if failures or all_zero else 0


if __name__ == "__main__":
    sys.exit(main())
