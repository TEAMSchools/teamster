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

To avoid wiping pre-existing externalIds entries (Google's PATCH semantics
REPLACE the entire array, not merge), each candidate is GET-then-PATCHed
live against the Directory API — never trusting BigQuery's (possibly stale)
view of external_ids. Doubles API calls; safe across re-runs.

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
IAM_SIGN_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


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
        target_scopes=IAM_SIGN_SCOPES,
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


def is_already_set(external_ids: list[dict], student_number_str: str) -> bool:
    """True if external_ids already contains our (type, customType, value) entry."""
    return any(
        e.get("type") == "custom"
        and e.get("customType") == "student_number"
        and e.get("value") == student_number_str
        for e in external_ids
    )


def build_merged_external_ids(
    existing: list[dict], student_number_str: str
) -> list[dict]:
    """Preserve all existing entries except a stale (custom, student_number) one; append ours."""
    kept = [
        e
        for e in existing
        if not (e.get("type") == "custom" and e.get("customType") == "student_number")
    ]
    return [
        *kept,
        {
            "value": student_number_str,
            "type": "custom",
            "customType": "student_number",
        },
    ]


def fetch_external_ids_batch(
    service: discovery.Resource,
    emails: Iterable[str],
) -> tuple[dict[str, list[dict]], list[tuple[str, str]]]:
    """GET externalIds for each email via batch; return ({email: ext_ids}, [(email, err), ...])."""
    results: dict[str, list[dict]] = {}
    errors: list[tuple[str, str]] = []

    def callback(
        request_id: str,
        response: dict | None,
        exception: Exception | None,
    ) -> None:
        if exception is not None:
            errors.append((request_id, str(exception)))
        elif response is not None:
            results[request_id] = list(response.get("externalIds") or [])

    # trunk-ignore(pyright/reportAttributeAccessIssue)
    batch = service.new_batch_http_request(callback=callback)
    for email in emails:
        batch.add(
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            service.users().get(userKey=email, fields="externalIds"),
            request_id=email,
        )

    batch.execute()
    return results, errors


def patch_batch(
    service: discovery.Resource,
    payloads: Iterable[tuple[str, list[dict]]],
) -> tuple[int, list[tuple[str, str]]]:
    """PATCH each (email, merged_external_ids); return (patched_count, [(email, err), ...])."""
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
    for email, merged_external_ids in payloads:
        batch.add(
            # trunk-ignore(pyright/reportAttributeAccessIssue)
            service.users().patch(
                userKey=email, body={"externalIds": merged_external_ids}
            ),
            request_id=email,
        )

    batch.execute()
    return patched, errors


_RATE_LIMIT_MARKERS = ("rateLimitExceeded", "userRateLimitExceeded", "429")


def _is_rate_limit_error(err: str) -> bool:
    return any(marker in err for marker in _RATE_LIMIT_MARKERS)


def _call_with_rate_limit_retry(
    fn,
    items: list[str],
    max_retries: int = 4,
) -> tuple[dict[str, list[dict]], list[tuple[str, str]]]:
    """Run fn(items) and retry rate-limited items with exponential backoff."""
    results: dict[str, list[dict]] = {}
    pending = list(items)
    persistent_errors: list[tuple[str, str]] = []

    for attempt in range(max_retries + 1):
        round_results, round_errors = fn(pending)
        results.update(round_results)
        rate_limited = [k for (k, err) in round_errors if _is_rate_limit_error(err)]
        non_rate_limited = [
            (k, err) for (k, err) in round_errors if not _is_rate_limit_error(err)
        ]
        persistent_errors.extend(non_rate_limited)
        if not rate_limited or attempt == max_retries:
            persistent_errors.extend(
                (k, err) for (k, err) in round_errors if _is_rate_limit_error(err)
            )
            break
        wait = 30 * (2**attempt)
        print(
            f"  ! {len(rate_limited)} GETs rate-limited, sleeping {wait}s",
            file=sys.stderr,
        )
        time.sleep(wait)
        pending = rate_limited

    return results, persistent_errors


def _patch_with_rate_limit_retry(
    service: discovery.Resource,
    payloads: list[tuple[str, list[dict]]],
    max_retries: int = 4,
) -> tuple[int, list[tuple[str, str]]]:
    """Run patch_batch and retry rate-limited PATCHes with exponential backoff."""
    total_patched = 0
    pending = list(payloads)
    persistent_errors: list[tuple[str, str]] = []

    for attempt in range(max_retries + 1):
        round_patched, round_errors = patch_batch(service, pending)
        total_patched += round_patched
        rate_limited_emails = {
            k for (k, err) in round_errors if _is_rate_limit_error(err)
        }
        non_rate_limited = [
            (k, err) for (k, err) in round_errors if not _is_rate_limit_error(err)
        ]
        persistent_errors.extend(non_rate_limited)
        if not rate_limited_emails or attempt == max_retries:
            persistent_errors.extend(
                (k, err) for (k, err) in round_errors if _is_rate_limit_error(err)
            )
            break
        wait = 30 * (2**attempt)
        print(
            f"  ! {len(rate_limited_emails)} PATCHes rate-limited, sleeping {wait}s",
            file=sys.stderr,
        )
        time.sleep(wait)
        pending = [(eid, p) for (eid, p) in pending if eid in rate_limited_emails]

    return total_patched, persistent_errors


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
        default=40,
        help=(
            "Candidates per batch (default 40). Each round does N GETs + up to "
            "N PATCHes; with the default sleep this averages under the "
            "Workspace Admin SDK quota of 2400 QPM per user."
        ),
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.0,
        help=(
            "Sleep between batches (default 2.0s). With batch-size=40 this caps "
            "at ~2400 QPM (40 GET + 40 PATCH per 2s)."
        ),
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
    total_already_set = 0
    total_get_errors: list[tuple[str, str]] = []
    total_patch_errors: list[tuple[str, str]] = []

    batches = list(chunks(rows, args.batch_size))
    for i, batch in enumerate(batches):
        emails = [row["primary_email"] for row in batch]
        current_ext_ids, get_errors = _call_with_rate_limit_retry(
            lambda items: fetch_external_ids_batch(service, items),
            emails,
        )
        total_get_errors.extend(get_errors)

        payloads: list[tuple[str, list[dict]]] = []
        decisions: dict[str, str] = {}
        for row in batch:
            email = row["primary_email"]
            student_number_str = str(row["student_number"])
            if email not in current_ext_ids:
                decisions[email] = "get-error"
                continue
            existing = current_ext_ids[email]
            if is_already_set(existing, student_number_str):
                decisions[email] = "already-set"
                total_already_set += 1
                continue
            merged = build_merged_external_ids(existing, student_number_str)
            payloads.append((email, merged))
            decisions[email] = "patch-queued"

        patched, patch_errors = (
            _patch_with_rate_limit_retry(service, payloads) if payloads else (0, [])
        )
        total_patched += patched
        total_patch_errors.extend(patch_errors)
        patch_err_by_email = dict(patch_errors)

        for row in batch:
            email = row["primary_email"]
            decision = decisions[email]
            if decision == "already-set":
                status = "already-set"
            elif decision == "get-error":
                status = "get-error"
            elif email in patch_err_by_email:
                status = "patch-error"
            else:
                status = "patched"
            print(f"{email} | {row['student_number']} | {status}")
            if email in patch_err_by_email:
                print(f"  -> {patch_err_by_email[email]}", file=sys.stderr)

        if i < len(batches) - 1:
            time.sleep(args.sleep_seconds)

    total_errors = len(total_get_errors) + len(total_patch_errors)
    print(
        f"\nTotal: patched={total_patched} already_set={total_already_set} "
        f"get_errors={len(total_get_errors)} patch_errors={len(total_patch_errors)} "
        f"candidates={len(rows)}",
        file=sys.stderr,
    )
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
