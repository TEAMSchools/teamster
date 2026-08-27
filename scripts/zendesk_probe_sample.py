# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Partition probe: build the hand-labeling worksheets.

Two sampling frames, chosen after measuring that "uncategorized" is a proxy
for never-worked rather than worked-but-unlabeled (of 581 uncategorized
tickets, 42% are deleted and only 27.5% ever got an agent reply, against
98.4% of categorized tickets):

- `uncategorized_answered` (frame C, 160 tickets) -- a CENSUS, not a sample.
  Answers whether the uncategorized bucket is hidden demand or queue
  detritus. No sampling error because every row is labeled.
- `answered` (frame D, 4,120 tickets) -- every non-deleted ticket that a
  human actually answered. This is the frame the self-inflicted base rate is
  measured on, because "should never have existed" only means something for
  a ticket that consumed effort.

The legacy `uncategorized` and `mixed` frames are retained for reproducing
earlier draws; neither should be used for a new base rate.

This script builds worksheets. It does NOT assign labels. The base rate is
measured against a threshold committed before labeling, so a model producing
that number would mean measuring the model rather than the queue.

Usage:
    uv run scripts/zendesk_probe_sample.py --pool uncategorized_answered
    uv run scripts/zendesk_probe_sample.py --pool answered --size 350 --slices 2

Design reference:
    docs/superpowers/specs/2026-08-05-zendesk-data-queue-ticket-analysis-design.md
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
from pathlib import Path

SCRATCH = Path(".claude/scratch/zendesk")
CORPUS = SCRATCH / "corpus.jsonl"
SAMPLE_SIZE = 150
SEED = 4739

WHITESPACE_RE = re.compile(r"\s+")

GRANT_RE = re.compile(
    r"\b(grant(?:ed|ing)?|access|permission(?:s)?|added you|add(?:ed)? "
    r"(?:you|them|him|her) to|provision(?:ed)?|enabled? your)\b",
    re.IGNORECASE,
)

HEADER = [
    "ticket_id",
    "url",
    "academic_year",
    "group_id",
    "status",
    "category",
    "subject",
    "request_excerpt",
    "reply_excerpt",
    "label",
    "class",
    "artifact_name",
    "one_line_fix",
]


def matches_grant_lexicon(text: str) -> bool:
    return bool(GRANT_RE.search(text or ""))


def clean(text: str, limit: int) -> str:
    """Flatten to one TSV-safe cell.

    Ticket bodies carry embedded carriage returns as well as tabs and
    newlines; any of the three splits a cell or a row in Excel and Sheets.
    """
    return WHITESPACE_RE.sub(" ", text[:limit]).strip()


def agent_reply(ticket: dict) -> dict | None:
    """First public comment not written by the requester.

    Sequence position is not sufficient: a requester who posts twice before
    anyone answers would otherwise have their own follow-up scored as the
    reply. Falls back to position only when `requester_id` is unknown.
    """
    public = [c for c in ticket["comments"] if c["is_public"]]
    requester_id = ticket.get("requester_id")
    if requester_id is None:
        return public[1] if len(public) >= 2 else None
    for comment in public:
        if comment.get("author_id") != requester_id:
            return comment
    return None


def first_public_reply_body(ticket: dict) -> str:
    reply = agent_reply(ticket)
    return reply["plain_body"] if reply else ""


def stratified_sample(rows: list[dict], stratum_of, n: int, seed: int) -> list[dict]:
    """Deterministic proportional sample across strata.

    Every non-empty stratum contributes at least one row. Returns the whole
    population when n meets or exceeds it, which is how a census is drawn.
    """
    if n >= len(rows):
        return list(rows)

    buckets: dict[object, list[dict]] = collections.defaultdict(list)
    for row in rows:
        buckets[stratum_of(row)].append(row)

    # trunk-ignore(bandit/B311): reproducible sampling, not a security context
    rng = random.Random(seed)
    ordered = sorted(buckets.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))

    total = len(rows)
    allocations: dict[object, int] = {}
    for key, bucket in ordered:
        allocations[key] = max(1, round(n * len(bucket) / total))

    while sum(allocations.values()) > n:
        key = max(allocations, key=lambda k: allocations[k])
        if allocations[key] == 1:
            break
        allocations[key] -= 1
    while sum(allocations.values()) < n:
        key = min(
            (k for k, _ in ordered if allocations[k] < len(buckets[k])),
            key=lambda k: allocations[k] / len(buckets[k]),
            default=None,
        )
        if key is None:
            break
        allocations[key] += 1

    picked: list[dict] = []
    for key, bucket in ordered:
        picked.extend(rng.sample(bucket, min(allocations[key], len(bucket))))
    return picked


def load_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def select_pool(corpus: list[dict], pool: str) -> list[dict]:
    """Tickets eligible for partition labeling. See module docstring."""
    if pool == "uncategorized":
        return [t for t in corpus if t["category"] is None]
    if pool == "uncategorized_answered":
        return [t for t in corpus if t["category"] is None and agent_reply(t)]
    if pool == "answered":
        return [t for t in corpus if t["status"] != "deleted" and agent_reply(t)]

    uncategorized = [t for t in corpus if t["category"] is None]
    grant_matched = [
        t
        for t in corpus
        if t["category"] is not None
        and matches_grant_lexicon(first_public_reply_body(t))
    ]
    return uncategorized + grant_matched


def stratum_for(pool: str):
    """Strata guard the two known confounders for the chosen frame.

    Frame D spans every category, so category mix must be preserved. The
    uncategorized frames have no category, so group stands in for it.
    """
    if pool == "answered":
        return lambda t: (t["academic_year"], t["category"] or "(none)")
    return lambda t: (t["academic_year"], t["group_id"])


def row_for(ticket: dict) -> list:
    return [
        ticket["ticket_id"],
        ticket["url"],
        ticket["academic_year"],
        ticket["group_id"],
        ticket["status"],
        ticket["category"] or "(none)",
        clean(ticket["subject"], 120),
        clean(ticket["description"], 400),
        clean(first_public_reply_body(ticket), 400),
        "",
        "",
        "",
        "",
    ]


def write_worksheet(path: Path, tickets: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        for ticket in tickets:
            writer.writerow(row_for(ticket))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pool",
        choices=("mixed", "uncategorized", "uncategorized_answered", "answered"),
        default="answered",
        help="Sampling frame. Default answered (frame D).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=SAMPLE_SIZE,
        help="Rows to draw. Exceeding the pool yields a census.",
    )
    parser.add_argument(
        "--slices",
        type=int,
        default=1,
        help="Split into N disjoint interleaved worksheets for parallel labeling.",
    )
    args = parser.parse_args()

    corpus = load_corpus()
    pool = select_pool(corpus, args.pool)
    picked = stratified_sample(pool, stratum_for(args.pool), args.size, SEED)
    picked.sort(key=lambda t: t["created_at"])

    census = args.size >= len(pool)
    stem = f"partition_{args.pool}" + ("_census" if census else "")

    if args.slices <= 1:
        write_worksheet(SCRATCH / f"{stem}.tsv", picked)
        outputs = [(f"{stem}.tsv", len(picked))]
    else:
        # Interleave, never chunk: the list is date-sorted and labeling
        # practice changed between the two school years, so contiguous
        # blocks would hand one labeler a systematically different corpus.
        outputs = []
        for i in range(args.slices):
            part = picked[i :: args.slices]
            name = f"{stem}_slice_{chr(ord('a') + i)}.tsv"
            write_worksheet(SCRATCH / name, part)
            outputs.append((name, len(part)))

    print(f"pool [{args.pool}]: {len(pool)} tickets ({len(corpus)} in corpus)")
    print("CENSUS - every row labeled, no sampling error" if census else "sample")
    for name, n in outputs:
        print(f"  {n:4d} rows  {name}")
    print("\nlabel: self_inflicted | genuine | vendor_or_user_error")
    print("class: ticket | request  (REQUIRED on every row)")
    print("self_inflicted also REQUIRES artifact_name and one_line_fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
