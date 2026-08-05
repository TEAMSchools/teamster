# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Partition probe: build the hand-labeling sample.

Draws a deterministic stratified sample from the partition-probe pool (the
uncategorized tickets plus every ticket whose first agent reply reads like a
permission grant), stratified across academic year and group so no year or
queue dominates the base rate.

This script builds the worksheet. It does NOT assign labels. The base rate it
feeds is measured against a pre-committed 20% kill criterion, so a model
producing that number would mean measuring the model rather than the queue.
The label column is filled by a person.

Usage:
    uv run scripts/zendesk_probe_sample.py

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

GRANT_RE = re.compile(
    r"\b(grant(?:ed|ing)?|access|permission(?:s)?|added you|add(?:ed)? "
    r"(?:you|them|him|her) to|provision(?:ed)?|enabled? your)\b",
    re.IGNORECASE,
)


def matches_grant_lexicon(text: str) -> bool:
    return bool(GRANT_RE.search(text or ""))


def stratified_sample(rows: list[dict], stratum_of, n: int, seed: int) -> list[dict]:
    """Deterministic proportional sample across strata.

    Every non-empty stratum contributes at least one row. Returns the whole
    population when n meets or exceeds it.
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

    # Trim or top up so the allocations sum to exactly n.
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
        take = min(allocations[key], len(bucket))
        picked.extend(rng.sample(bucket, take))
    return picked


def load_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def first_public_reply_body(ticket: dict) -> str:
    """Body of the first public comment not written by the requester.

    Matches `zendesk_probe_reply_shape.first_agent_reply`. Selecting by
    sequence position alone would score a requester's own follow-up as the
    reply, which would put their words through the grant lexicon.
    """
    public = [c for c in ticket["comments"] if c["is_public"]]
    requester_id = ticket.get("requester_id")
    if requester_id is None:
        return public[1]["plain_body"] if len(public) >= 2 else ""

    for comment in public:
        if comment.get("author_id") != requester_id:
            return comment["plain_body"]
    return ""


def clean(text: str, limit: int) -> str:
    return text[:limit].replace("\t", " ").replace("\n", " ")


def select_pool(corpus: list[dict], pool: str) -> list[dict]:
    """Tickets eligible for partition labeling.

    `uncategorized` is the subset the 20% kill criterion is actually measured
    on, so it is the stratum worth deepening. `mixed` adds grant-lexicon
    matches for a broader but less decision-relevant read.
    """
    uncategorized = [t for t in corpus if t["category"] is None]
    if pool == "uncategorized":
        return uncategorized
    grant_matched = [
        t
        for t in corpus
        if t["category"] is not None
        and matches_grant_lexicon(first_public_reply_body(t))
    ]
    return uncategorized + grant_matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pool",
        choices=("mixed", "uncategorized"),
        default="mixed",
        help="Ticket pool to sample from. Default mixed.",
    )
    parser.add_argument(
        "--size", type=int, default=SAMPLE_SIZE, help="Rows to draw. Default 150."
    )
    args = parser.parse_args()

    corpus = load_corpus()
    pool = select_pool(corpus, args.pool)

    picked = stratified_sample(
        pool,
        lambda t: (t["academic_year"], t["group_id"]),
        n=args.size,
        seed=SEED,
    )
    picked.sort(key=lambda t: t["created_at"])

    suffix = "" if args.pool == "mixed" else f"_{args.pool}"
    with (SCRATCH / f"partition_sample{suffix}.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "ticket_id",
                "academic_year",
                "group_id",
                "category",
                "subject",
                "request_excerpt",
                "reply_excerpt",
                "label",
                "artifact_name",
                "one_line_fix",
            ]
        )
        for t in picked:
            writer.writerow(
                [
                    t["ticket_id"],
                    t["academic_year"],
                    t["group_id"],
                    t["category"] or "(none)",
                    clean(t["subject"], 120),
                    clean(t["description"], 400),
                    clean(first_public_reply_body(t), 400),
                    "",
                    "",
                    "",
                ]
            )

    print(f"pool [{args.pool}]: {len(pool)} tickets ({len(corpus)} in corpus)")
    print(f"sample: {len(picked)} rows in partition_sample{suffix}.tsv")
    print("\nLabel each row: self_inflicted | genuine | vendor_or_user_error")
    print("Choosing self_inflicted REQUIRES artifact_name and one_line_fix.")
    print("Kill criterion: under 20% self_inflicted in the uncategorized subset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
