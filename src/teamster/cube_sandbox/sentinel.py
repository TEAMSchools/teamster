"""Assert that what the DEPLOYED sandbox serves is fabricated.

The isolation test proves the sandbox service account cannot read production,
but it tests whichever key it is handed. It cannot see what the deployment
itself is configured with: a production project id or key pasted into the
sandbox deployment would serve real records under a secret an outside party
holds, and every other check here would stay green.

This reads through the deployment's own endpoint instead. Every fabricated
person is on a `.invalid` domain and every fabricated school is `SBX###`, so
one value outside those shapes means the deployment is not reading the
sandbox. A run that sees no values at all fails too: a deployment that denies
everyone has no violations either.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any

from teamster.cube_sandbox.meta_check import API_SECRET, DEFAULT_VIEWER, REST_URL

EMAIL_MEMBERS = (
    "staff_directory.work_email",
    "staff_directory.google_email",
    "staff_directory.staff_manager_work_email",
    "staff_pii.personal_email",
)
SCHOOL_MEMBERS = (
    "staff_directory.locations_abbreviation",
    "staff_pii.locations_abbreviation",
    "student_assessment_scores_view.abbreviation",
    "student_attendance_enrollment_daily_view.locations_abbreviation",
    "student_attendance_enrollment_periods_view.locations_abbreviation",
    "student_section_enrollments_view.locations_abbreviation",
)
MEMBERS = EMAIL_MEMBERS + SCHOOL_MEMBERS

_SCHOOL = re.compile(r"^SBX\d{3}$")
_POLL_SECONDS = 120


def violations(seen: dict[str, list[Any]]) -> list[str]:
    """Every value outside the fabricated shapes, and every empty member."""
    found = []
    for member, values in seen.items():
        present = [v for v in values if v is not None]
        if not present:
            found.append(f"{member} returned no values, so nothing was checked")
            continue
        for value in present:
            if member in EMAIL_MEMBERS and not str(value).endswith(".invalid"):
                found.append(f"{member}: {value!r} is not on a .invalid domain")
            elif member in SCHOOL_MEMBERS and not _SCHOOL.match(str(value)):
                found.append(f"{member}: {value!r} is not a sandbox school")
    return found


def fetch_values(url: str, secret: str, member: str, viewer: str) -> list[Any]:
    """Every distinct value of one member, as the deployment serves it.

    Mints the same token `meta_check.fetch_meta` does: HS256 over the
    deployment's API secret, the whole payload as the security context, sent
    raw. `/v1/load` can answer 200 with `Continue wait`, which is a request
    to poll again, not a result.
    """
    import jwt
    import requests

    body = json.dumps({"query": {"dimensions": [member], "limit": 50000}})
    deadline = time.monotonic() + _POLL_SECONDS
    while True:
        token = jwt.encode(
            {"email": viewer, "iat": int(time.time())}, secret, algorithm="HS256"
        )
        response = requests.post(
            url.rstrip("/") + "/v1/load",
            headers={"Authorization": token, "Content-Type": "application/json"},
            data=body,
            timeout=90,
        )
        payload = response.json()
        if response.ok and payload.get("error") == "Continue wait":
            if time.monotonic() > deadline:
                raise SystemExit(f"{member}: still computing after {_POLL_SECONDS}s")
            time.sleep(1)
            continue
        if not response.ok or "data" not in payload:
            raise SystemExit(f"{member}: HTTP {response.status_code} {payload}")
        return [row.get(member) for row in payload["data"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # The widest persona, so the check reads every row the sandbox holds.
    parser.add_argument("--viewer", default=DEFAULT_VIEWER)
    args = parser.parse_args(argv)

    missing = [name for name in (REST_URL, API_SECRET) if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "cannot reach the sandbox REST API: set "
            + " and ".join(missing)
            + ". This check reads the DEPLOYED sandbox and has no offline mode."
        )

    url, secret = os.environ[REST_URL], os.environ[API_SECRET]
    seen = {m: fetch_values(url, secret, m, args.viewer) for m in MEMBERS}
    found = violations(seen)
    for line in found:
        print(f"FAIL  {line}")
    checked = sum(len(v) for v in seen.values())
    if found:
        print(f"\n{len(found)} problem(s) across {checked} value(s).")
        return 1
    print(f"PASS  {checked} value(s) across {len(MEMBERS)} members, all fabricated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
