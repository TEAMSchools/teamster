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

Requires the local Cube dev server with the SQL API enabled
(`CUBEJS_PG_SQL_PORT`, `CUBEJS_SQL_USER`, `CUBEJS_SQL_PASSWORD`) — see
`docs/guides/cube.md`. Start it with the "Cube: Dev Server" VS Code task.

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


def load_viewers(args: argparse.Namespace) -> list[str]:
    if args.viewers:
        return args.viewers
    lines = args.viewers_file.read_text(encoding="utf-8").splitlines()
    return [
        stripped
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    ]


def run_for_viewer(
    viewer: str, args: argparse.Namespace
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
                host=args.host,
                port=args.port,
                user=viewer,
                password=args.password,
                dbname=args.dbname,
                prepare_threshold=None,
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(args.query)
            return cur.fetchall(), None
    except psycopg.Error as err:
        # Report and continue: one unreachable or denied viewer must not abort
        # the rest of the matrix, since the comparison across viewers is the
        # whole point.
        return [], str(err).strip().splitlines()[0]


def main() -> int:
    args = parse_args()
    if not args.password:
        print(
            "No SQL password given: pass --password, or set the CUBEJS_SQL_PASSWORD"
            " value in your shell.",
            file=sys.stderr,
        )
        return 1

    viewers = load_viewers(args)
    if not viewers:
        print("No viewer emails to test.", file=sys.stderr)
        return 1

    failures = 0
    empty = 0
    for viewer in viewers:
        rows, error = run_for_viewer(viewer, args)
        if error:
            failures += 1
            print(f"{viewer}: FAILED - {error}")
            continue
        if not rows:
            empty += 1
            print(f"{viewer}: 0 rows (default-deny, or no scope on this view)")
            continue
        print(f"{viewer}: {len(rows)} group(s)")
        for row in rows:
            print(f"    {row}")

    print(f"\n{len(viewers)} viewer(s) checked, {failures} failed, {empty} at 0 rows.")
    if empty == len(viewers):
        print(
            "EVERY viewer returned 0 rows, including any network-scoped one. That"
            " usually means the identity read itself failed rather than the"
            " policies denying - check the dev-server log for 'resolveAccess"
            " failed for', and confirm CUBE_GROUP_MAP is not set."
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
