# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "google-api-python-client",
#     "google-auth",
#     "google-cloud-bigquery",
# ]
# ///
r"""One-shot backfill: set externalIds[type='custom', customType='student_number'] on existing student Google accounts.

Identifies matched student accounts under any /Students/* org unit (including
/Students/Disabled) whose Workspace externalIds does not already contain a
'custom' entry whose value equals the PowerSchool student_number, then PATCHes
each one. Dry-run by default; pass --apply to execute.

Usage:
    uv run scripts/backfill_google_directory_student_external_ids.py \\
        --delegated-account <admin@kippteamandfamily.org> [--apply]

Auth: ADC -> impersonate user-cloud-dagster-cloud-agent@... (the
DWD-allowlisted SA) -> IAM Signer with subject=delegated_account. Caller's
ADC principal must have roles/iam.serviceAccountTokenCreator on
user-cloud-dagster-cloud-agent@... — in a Codespace this is codespaces@...,
in a Dagster pod this is the WI binding (self-impersonation, no-op).

Output (stdout): one line per user, plus aggregate counts. Output contains
student emails and student_numbers; capture only to .claude/scratch/ or
local terminal. Never paste to PRs, issues, or external surfaces.
"""

import argparse
import sys
import time
from collections.abc import Iterable, Iterator

from google.auth import default, impersonated_credentials
from google.auth.iam import Signer
from google.auth.transport import requests
from google.cloud import bigquery
from google.oauth2 import service_account
from googleapiclient import discovery

BQ_PROJECT = "teamster-332318"
DWD_SERVICE_ACCOUNT = (
    "user-cloud-dagster-cloud-agent@teamster-332318.iam.gserviceaccount.com"
)

QUERY = """
-- stg_google_directory__users.external_ids is ARRAY<STRUCT<value, type>>;
-- the upstream avro/Pydantic schema drops customType. The (type='custom',
-- value=student_number) pair is practically unique — no other consumer
-- writes PowerSchool student_numbers into a custom externalId.
select
    u.primary_email,
    se.student_number,
    u.org_unit_path
from `teamster-332318.kipptaf_google_directory.stg_google_directory__users` as u
inner join `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as se
    on u.primary_email = se.student_email
    and se.rn_all = 1
where u.org_unit_path like '/Students/%'
    and se.region != 'Paterson'
    and se.student_number is not null
    and not exists (
        select 1 from unnest(u.external_ids) as e
        where e.type = 'custom'
            and e.value = cast(se.student_number as string)
    )
"""

SCOPES = ["https://www.googleapis.com/auth/admin.directory.user"]


def chunks[T](items: list[T], size: int) -> Iterator[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def build_directory_client(delegated_account: str) -> discovery.Resource:
    """Build a Directory API client via ADC -> impersonated SA -> IAM Signer DWD.

    The DWD-authorized service account (`DWD_SERVICE_ACCOUNT`) is the only SA
    whose OAuth Client ID is allowlisted in Workspace Admin for the
    admin.directory.user scope. We impersonate it from whatever ADC the caller
    has (Codespace's `codespaces@...` SA, or the same SA in a Workload Identity
    pod — self-impersonation is a no-op there), then use IAM Signer to self-sign
    a JWT with `subject=delegated_account` for DWD.

    Caller's ADC principal needs `roles/iam.serviceAccountTokenCreator` on
    DWD_SERVICE_ACCOUNT. DWD_SERVICE_ACCOUNT needs the same role on itself
    (already true since prod uses the same self-sign path).
    """
    request = requests.Request()
    source_credentials, _ = default()

    target_credentials = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=DWD_SERVICE_ACCOUNT,
        target_scopes=SCOPES,
    )
    target_credentials.refresh(request)

    credentials = service_account.Credentials(
        signer=Signer(
            request=request,
            credentials=target_credentials,
            service_account_email=DWD_SERVICE_ACCOUNT,
        ),
        service_account_email=DWD_SERVICE_ACCOUNT,
        # trunk-ignore(bandit/B106): public Google OAuth token endpoint
        token_uri="https://accounts.google.com/o/oauth2/token",
        scopes=SCOPES,
        subject=delegated_account,
    )

    return discovery.build("admin", "directory_v1", credentials=credentials)


def fetch_rows() -> list[dict]:
    bq = bigquery.Client(project=BQ_PROJECT)
    return [dict(row) for row in bq.query(QUERY).result()]


def patch_batch(
    service: discovery.Resource,
    rows: Iterable[dict],
) -> tuple[int, list[tuple[str, str]]]:
    """PATCH a batch of users; return (patched_count, [(email, error_message), ...])."""
    patched = 0
    errors: list[tuple[str, str]] = []

    def callback(
        request_id: str,
        _response: dict | None,
        exception: Exception | None,
    ) -> None:
        nonlocal patched
        if exception is not None:
            errors.append((request_id, str(exception)))
        else:
            patched += 1

    # trunk-ignore(pyright/reportAttributeAccessIssue)
    batch = service.new_batch_http_request(callback=callback)
    for row in rows:
        body = {
            "externalIds": [
                {
                    "value": str(row["student_number"]),
                    "type": "custom",
                    "customType": "student_number",
                }
            ]
        }
        batch.add(
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            service.users().patch(userKey=row["primary_email"], body=body),
            request_id=row["primary_email"],
        )

    batch.execute()
    return patched, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute PATCHes. Without this flag, runs dry (prints only).",
    )
    parser.add_argument(
        "--delegated-account",
        required=True,
        help="Google Workspace admin email to impersonate (same value Dagster uses).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="PATCHes per batch HTTP request (default 50).",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=1.0,
        help="Sleep between batches to stay under quota (default 1.0s).",
    )
    args = parser.parse_args()

    print(f"Fetching candidate rows from {BQ_PROJECT}...", file=sys.stderr)
    rows = fetch_rows()
    print(f"Found {len(rows)} candidates.", file=sys.stderr)

    if not rows:
        print("Nothing to do.", file=sys.stderr)
        return 0

    if not args.apply:
        print("DRY RUN — no PATCHes will be sent.", file=sys.stderr)
        for row in rows:
            print(f"{row['primary_email']} | {row['student_number']} | would-patch")
        print(f"\nTotal: {len(rows)} would-patch", file=sys.stderr)
        return 0

    service = build_directory_client(args.delegated_account)

    total_patched = 0
    total_errors: list[tuple[str, str]] = []

    batches = list(chunks(rows, args.batch_size))
    for i, batch in enumerate(batches):
        patched, errs = patch_batch(service, batch)
        total_patched += patched
        total_errors.extend(errs)
        for row in batch:
            email = row["primary_email"]
            err = next((e for (k, e) in errs if k == email), None)
            status = "error" if err else "patched"
            print(f"{email} | {row['student_number']} | {status}")
            if err:
                print(f"  -> {err}", file=sys.stderr)
        if i < len(batches) - 1:
            time.sleep(args.sleep_seconds)

    print(
        f"\nTotal: patched={total_patched} errors={len(total_errors)} "
        f"candidates={len(rows)}",
        file=sys.stderr,
    )
    return 0 if not total_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
