# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "google-cloud-bigquery>=3.25",
#   "google-auth>=2.0",
# ]
# ///

"""Assert the sandbox service account is isolated from production BigQuery.

Two legs, and both must run or neither counts:

- **Positive** — the sandbox service account reads the sandbox project
  successfully.
- **Negative** — the same account, in the same run, is refused on
  `teamster-332318`.

The positive leg runs FIRST and the negative is skipped when it fails. A
service account whose key is broken, revoked or misconfigured is refused by
production exactly like an isolated one, so a negative-only test goes green on
the day the sandbox breaks. That is the failure this ordering exists to
prevent, and it is why a skipped negative leg reports UNPROVEN rather than
PASS.

A 403 and a 404 are not the same answer. `Forbidden` means the boundary held;
`NotFound` means the table was not there to be refused, which proves nothing
about permissions and would read as a pass if the two were merged.

Authenticate with the service account's own key, which is the path Cube Cloud
uses through `CUBEJS_DB_BQ_CREDENTIALS`, so the test exercises the real
connection rather than a stand-in. Running it under ambient production
credentials is refused outright: those can read production, so the negative
leg would fail for the wrong reason and the run would report a boundary that
was never tested.

This asserts the grant. It does NOT assert that `deny-sandbox-bigquery` still
exists — an absent grant and an active deny policy produce the same 403, so
that needs a different identity and lives in
`scripts/cube_sandbox_deny_policy.py`.

Exit codes: 0 pass, 1 fail, 2 unproven.

Usage:
    uv run scripts/cube_sandbox_isolation.py --key-stdin

Design reference:
    docs/superpowers/specs/2026-09-11-cube-sandbox-build-design.md, Piece 1
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SANDBOX_PROJECT = "teamster-cube-sandbox"
SANDBOX_DATASET = "kipptaf_marts"
SERVICE_ACCOUNT = "cube-cloud-sandbox@teamster-cube-sandbox.iam.gserviceaccount.com"
PRODUCTION_PROJECT = "teamster-332318"
PRODUCTION_TABLE = f"{PRODUCTION_PROJECT}.kipptaf_marts.dim_students"
SANDBOX_TABLE = f"{SANDBOX_PROJECT}.{SANDBOX_DATASET}.INFORMATION_SCHEMA.TABLES"

PASS = 0
FAIL = 1
UNPROVEN = 2

PERMISSION = "permission"
MISSING = "missing"
OTHER = "other"


@dataclass(frozen=True)
class Leg:
    """One leg's outcome. `denial` is set only when the read was refused."""

    ran: bool
    succeeded: bool
    denial: str | None = None
    detail: str = ""


def classify(status: int | None, message: str) -> str:
    """Tell a real permission denial from a table that was never there.

    Merging them is the whole trap: a typo in the production table name makes
    the negative leg 404, and calling that a denial reports a boundary that
    was never exercised.
    """
    if status == 403:
        return PERMISSION
    if status == 404:
        return MISSING
    lowered = message.lower()
    if "permission" in lowered or "access denied" in lowered or "forbidden" in lowered:
        return PERMISSION
    if "not found" in lowered:
        return MISSING
    return OTHER


def decide(positive: Leg, negative: Leg) -> tuple[int, str]:
    """The run's verdict, from both legs. Returns (exit code, reason)."""
    if not positive.ran:
        return UNPROVEN, "the positive leg did not run"
    if not positive.succeeded:
        return (
            UNPROVEN,
            (
                "the sandbox read FAILED, so the production refusal proves "
                "nothing: broken credentials fail production identically. "
                f"{positive.detail}"
            ),
        )
    if not negative.ran:
        return UNPROVEN, "the negative leg did not run"
    if negative.succeeded:
        return (
            FAIL,
            f"the sandbox account READ {PRODUCTION_TABLE}. Isolation is broken.",
        )
    if negative.denial == PERMISSION:
        return PASS, "sandbox read succeeded and production was refused"
    if negative.denial == MISSING:
        return (
            UNPROVEN,
            (
                f"production returned NOT FOUND for {PRODUCTION_TABLE}, not a "
                "permission denial. The table may have been renamed; nothing "
                "about the boundary was tested."
            ),
        )
    return UNPROVEN, f"production failed for an unrecognised reason: {negative.detail}"


_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def credentials_from_info(info: dict):
    """Build credentials from an already-parsed key.

    Split out from the file and stdin readers so both paths share one place
    where the key becomes credentials, and so a test can exercise it without
    a key on disk.
    """
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def credentials_from_stdin(stream=None):
    """Read the key from stdin. Preferred: it never touches the filesystem.

    A downloaded key is a long-lived credential, and every copy on disk is a
    place it can leak from or be committed by accident. This path leaves none.
    """
    stream = sys.stdin if stream is None else stream
    if stream.isatty():
        print("Paste the sandbox service account JSON, then press Ctrl-D:\n")
    raw = stream.read().strip()
    if not raw:
        raise SystemExit("nothing arrived on stdin — re-run and paste the key")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as err:
        raise SystemExit(f"that is not valid JSON: {err}") from err
    return credentials_from_info(info)


def _credentials(key_file: Path):
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(
        str(key_file), scopes=_SCOPES
    )


def assert_sandbox_identity(credentials) -> None:
    """Refuse to run as anything but the sandbox service account.

    Ambient production credentials CAN read production, so the negative leg
    would fail for the wrong reason and the run would report a boundary it
    never touched.
    """
    email = getattr(credentials, "service_account_email", None)
    if email != SERVICE_ACCOUNT:
        raise SystemExit(
            f"refusing to run as {email!r}: this test is only meaningful as "
            f"{SERVICE_ACCOUNT}. Pass that account's own key."
        )


def _read(client, sql: str) -> Leg:
    from google.api_core import exceptions

    try:
        list(client.query(sql).result())
        return Leg(ran=True, succeeded=True)
    except exceptions.GoogleAPICallError as err:
        message = str(err)
        return Leg(
            ran=True,
            succeeded=False,
            denial=classify(getattr(err, "code", None), message),
            detail=message.strip().splitlines()[0] if message.strip() else "",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--key-stdin",
        action="store_true",
        help="read the sandbox service account key from stdin (preferred: "
        "the key never touches the filesystem)",
    )
    source.add_argument(
        "--key-file",
        type=Path,
        help="read the key from a file instead. Prefer --key-stdin unless a "
        "scheduled runner mounts the key for you",
    )
    args = parser.parse_args()

    from google.cloud import bigquery

    credentials = (
        credentials_from_stdin() if args.key_stdin else _credentials(args.key_file)
    )
    assert_sandbox_identity(credentials)
    client = bigquery.Client(project=SANDBOX_PROJECT, credentials=credentials)

    # Positive first, always.
    # trunk-ignore(bandit/B608): SANDBOX_TABLE is a module constant built from
    # two other module constants. No caller can influence it.
    positive = _read(client, f"SELECT table_name FROM `{SANDBOX_TABLE}` LIMIT 1")
    if not positive.succeeded:
        code, reason = decide(positive, Leg(ran=False, succeeded=False))
        print(f"UNPROVEN - {reason}")
        return code

    print(f"positive leg: read {SANDBOX_PROJECT} successfully")
    # trunk-ignore(bandit/B608): PRODUCTION_TABLE is a module constant. This
    # query is meant to be refused — it is the negative leg.
    negative = _read(client, f"SELECT 1 FROM `{PRODUCTION_TABLE}` LIMIT 1")
    code, reason = decide(positive, negative)
    print(f"{['PASS', 'FAILED', 'UNPROVEN'][code]} - {reason}")
    return code


if __name__ == "__main__":
    sys.exit(main())
