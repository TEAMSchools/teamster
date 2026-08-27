# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Reply-shape probe: what fraction of answers are a pasted number?

Classifies the first agent public reply into four shapes and emits a worksheet
for question-shape slug assignment. The classifier is deliberately simple; the
kill criterion turns on slug recurrence, not bucket precision, and a sample of
the buckets is validated by hand.

Kill criterion: if fewer than 20 slugs cover half the number-shaped volume, the
demand is a long tail and a re-runnable-object policy would be a tax.

Usage:
    uv run scripts/zendesk_probe_reply_shape.py

Design reference:
    docs/superpowers/specs/2026-08-05-zendesk-data-queue-ticket-analysis-design.md
"""

from __future__ import annotations

import collections
import csv
import json
import re
from pathlib import Path

SCRATCH = Path(".claude/scratch/zendesk")
CORPUS = SCRATCH / "corpus.jsonl"
WORKSHEET_CATEGORIES = {"data_data_analysis_and_reports", "data_blended_learning"}
WORKSHEET_LIMIT = 200

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
TICKET_REF_RE = re.compile(r"#\d+")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![\w./-])\$?\d[\d,]*(?:\.\d+)?%?(?![\w./-])")


def first_agent_reply(ticket: dict) -> dict | None:
    """The first public comment written by someone other than the requester.

    Sequence position is not sufficient: a requester who posts twice before
    anyone answers would otherwise have their own follow-up scored as the
    agent's reply. Falls back to sequence position only when `requester_id`
    is unknown.
    """
    public = [c for c in ticket["comments"] if c["is_public"]]
    requester_id = ticket.get("requester_id")
    if requester_id is None:
        return public[1] if len(public) >= 2 else None

    for comment in public:
        if comment.get("author_id") != requester_id:
            return comment
    return None


def classify_reply_shape(
    plain_body: str, attachment_count: int, has_url: bool = False
) -> str:
    """Bucket a reply by what it delivers.

    `has_url` comes from the comment's html_body. plain_body drops anchor
    hrefs, so a "here is the dashboard" reply looks like bare prose without it.
    """
    text = plain_body or ""
    if has_url or URL_RE.search(text):
        return "existing_link"
    if attachment_count > 0:
        return "attached_file"

    stripped = TIME_RE.sub(" ", TICKET_REF_RE.sub(" ", DATE_RE.sub(" ", text)))
    if NUMBER_RE.search(stripped):
        return "pasted_value"
    return "not_a_data_ask"


WHITESPACE_RE = re.compile(r"\s+")


def clean(text: str, limit: int | None = None) -> str:
    """Flatten to one TSV-safe cell (tabs, newlines, carriage returns)."""
    return WHITESPACE_RE.sub(" ", text[:limit] if limit else text).strip()


def load_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main() -> int:
    corpus = load_corpus()
    shapes = collections.Counter()
    rows = []

    for ticket in corpus:
        reply = first_agent_reply(ticket)
        if reply is None:
            shapes["no_agent_reply"] += 1
            continue
        shape = classify_reply_shape(
            reply["plain_body"],
            reply["attachment_count"],
            # has_content_url, not has_url: the raw flag counts email signature
            # and footer boilerplate, which is most of the URLs in the corpus.
            reply.get("has_content_url", False),
        )
        shapes[shape] += 1
        rows.append((ticket, reply, shape))

    with (SCRATCH / "reply_shape.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["shape", "n_tickets"])
        for shape, n in shapes.most_common():
            writer.writerow([shape, n])

    worksheet = [
        (t, r, s) for t, r, s in rows if (t["category"] or "") in WORKSHEET_CATEGORIES
    ]
    worksheet.sort(key=lambda item: item[0]["created_at"], reverse=True)

    with (SCRATCH / "slug_worksheet.tsv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(
            [
                "ticket_id",
                "url",
                "category",
                "shape",
                "subject",
                "reply_excerpt",
                "slug",
            ]
        )
        for ticket, reply, shape in worksheet[:WORKSHEET_LIMIT]:
            excerpt = clean(reply["plain_body"], 300)
            writer.writerow(
                [
                    ticket["ticket_id"],
                    ticket["url"],
                    ticket["category"],
                    shape,
                    clean(ticket["subject"]),
                    excerpt,
                    "",
                ]
            )

    total = sum(shapes.values())
    for shape, n in shapes.most_common():
        print(f"{shape:20s} {n:6d}  {n / total:6.1%}")
    print(f"\n{len(worksheet[:WORKSHEET_LIMIT])} rows in slug_worksheet.tsv")
    print("Assign a question-shape slug per row, then count distinct slugs.")
    print("Kill criterion: fewer than ~20 slugs covering half the")
    print("pasted_value + attached_file volume.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
