# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "google-cloud-bigquery>=3.25",
# ]
# ///

"""Extract the Zendesk Data-queue corpus from BigQuery to local JSONL.

Sole BigQuery reader for the opening-week probes. Owns all date logic and
persists `academic_year` and `week_offset` per ticket so downstream probe
scripts never recompute them.

Reads the raw Airbyte tables directly. `fct_support_tickets` is NOT usable
here: it inner-joins submitters to the staff roster (dropping roughly a
third of tickets) and carries no `group_id`.

Output contains student PII and is written to the gitignored scratch dir.

Usage:
    uv run scripts/zendesk_extract_corpus.py
    uv run scripts/zendesk_extract_corpus.py --verify

Design reference:
    docs/superpowers/specs/2026-08-05-zendesk-data-queue-ticket-analysis-design.md
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import sys
from pathlib import Path

from google.cloud import bigquery

PROJECT = "teamster-332318"
GROUP_IDS = (21474460, 31319068)
START_DATE = "2024-07-01"
END_DATE = "2026-06-30"

OUTPUT_DIR = Path(".claude/scratch/zendesk")

# Derived from dim_school_calendars: the first date on or after July 1 where the
# count of in-session locations reaches at least 90% of that year's peak. The
# naive min(is_in_session) anchors on summer programming (2 of 21 locations) and
# is wrong by roughly two months.
FIRST_INSTRUCTIONAL_DAY = {
    2024: datetime.date(2024, 8, 22),
    2025: datetime.date(2025, 8, 25),
}

# Verified during design against the same scope filter.
EXPECTED = {
    "n_tickets": 4608,
    "n_comments": 16819,
    "n_tickets_with_public_comment": 4474,
    "n_tickets_with_agent_reply": 4130,
    "n_comments_with_attachments": 1082,
}

# trunk-ignore(bandit/B608): interpolates module constants only, no user input
TICKETS_QUERY = f"""
select
    t.id as ticket_id,
    t.created_at,
    t.status,
    t.group_id,
    cast(t.requester_id as string) as requester_id,
    t.subject,
    t.description,
    cf.category,
from `{PROJECT}.kipptaf_zendesk.tickets` as t
left join
    `{PROJECT}.kipptaf_zendesk.int_zendesk__tickets__custom_fields_pivot` as cf
    on t.id = cf.ticket_id
where date(t.created_at) between '{START_DATE}' and '{END_DATE}'
    and t.group_id in {GROUP_IDS}
"""

# trunk-ignore(bandit/B608): interpolates module constants only, no user input
COMMENTS_QUERY = f"""
with scoped as (
    select id
    from `{PROJECT}.kipptaf_zendesk.tickets`
    where date(created_at) between '{START_DATE}' and '{END_DATE}'
        and group_id in {GROUP_IDS}
)
select
    ta.ticket_id,
    ta.created_at as comment_created_at,
    json_value(e, '$.public') = 'true' as is_public,
    json_value(e, '$.author_id') as author_id,
    json_value(e, '$.plain_body') as plain_body,
    coalesce(array_length(json_extract_array(e, '$.attachments')), 0)
        as attachment_count,
    -- plain_body drops anchor hrefs, so link detection must read html_body or
    -- every "here is the dashboard" reply misclassifies as prose.
    coalesce(
        regexp_contains(json_value(e, '$.html_body'), r'https?://'), false
    ) as has_url,
from `{PROJECT}.kipptaf_zendesk.ticket_audits` as ta
inner join scoped as s on ta.ticket_id = s.id
cross join unnest(json_extract_array(ta.events)) as e
where json_value(e, '$.type') = 'Comment'
"""


def academic_year_of(d: datetime.date) -> int:
    """Return the academic year a date falls in. Years start July 1."""
    return d.year if d.month >= 7 else d.year - 1


def week_offset(d: datetime.date, anchor: datetime.date) -> int:
    """Whole weeks from the anchor. Floor division, so pre-anchor is negative."""
    return (d - anchor).days // 7


def fetch(client: bigquery.Client, query: str) -> list[dict]:
    return [dict(row) for row in client.query(query).result()]


def build_corpus(tickets: list[dict], comments: list[dict]) -> list[dict]:
    by_ticket: dict[int, list[dict]] = collections.defaultdict(list)
    for c in comments:
        by_ticket[c["ticket_id"]].append(c)

    corpus = []
    for t in tickets:
        created = t["created_at"]
        created_date = created.date()
        year = academic_year_of(created_date)
        anchor = FIRST_INSTRUCTIONAL_DAY[year]

        thread = sorted(
            by_ticket[t["ticket_id"]], key=lambda c: c["comment_created_at"]
        )
        corpus.append(
            {
                "ticket_id": t["ticket_id"],
                "created_at": created.isoformat(),
                "academic_year": year,
                "week_offset": week_offset(created_date, anchor),
                "status": t["status"],
                "group_id": t["group_id"],
                "requester_id": t["requester_id"],
                "category": t["category"],
                "subject": t["subject"] or "",
                "description": t["description"] or "",
                "comments": [
                    {
                        "seq": i,
                        "created_at": c["comment_created_at"].isoformat(),
                        "is_public": c["is_public"],
                        "author_id": c["author_id"],
                        "plain_body": c["plain_body"] or "",
                        "attachment_count": c["attachment_count"],
                        "has_url": c["has_url"],
                    }
                    for i, c in enumerate(thread, start=1)
                ],
            }
        )
    return corpus


def build_manifest(corpus: list[dict]) -> dict[str, int]:
    def public(t: dict) -> list[dict]:
        return [c for c in t["comments"] if c["is_public"]]

    return {
        "n_tickets": len(corpus),
        "n_comments": sum(len(t["comments"]) for t in corpus),
        "n_tickets_with_public_comment": sum(1 for t in corpus if public(t)),
        "n_tickets_with_agent_reply": sum(1 for t in corpus if len(public(t)) >= 2),
        "n_comments_with_attachments": sum(
            1 for t in corpus for c in t["comments"] if c["attachment_count"] > 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Exit nonzero if the manifest does not match the expected counts.",
    )
    args = parser.parse_args()

    client = bigquery.Client(project=PROJECT)
    corpus = build_corpus(fetch(client, TICKETS_QUERY), fetch(client, COMMENTS_QUERY))
    manifest = build_manifest(corpus)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row) + "\n")
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))

    mismatches = {k: (v, manifest[k]) for k, v in EXPECTED.items() if manifest[k] != v}
    for key, (want, got) in mismatches.items():
        print(f"MISMATCH {key}: expected {want}, got {got}", file=sys.stderr)
    print(json.dumps(manifest, indent=2))

    if mismatches and args.verify:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
