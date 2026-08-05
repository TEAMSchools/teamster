# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Seasonality probe: does ticket demand repeat in the same week each year?

Groups tickets by category and week-offset-from-first-instructional-day, so
the four regional school calendars align. Flags cells that are heavy in both
school years, then emits a worksheet for the judgment step the probe actually
turns on: are the tickets inside a cell the same ask, or merely the same week?

Kill criterion: if no cell holds 10 or more same-ask tickets in both years,
seasonal pre-building has no target and the idea is dropped.

Usage:
    uv run scripts/zendesk_probe_seasonality.py

Design reference:
    docs/superpowers/specs/2026-08-05-zendesk-data-queue-ticket-analysis-design.md
"""

from __future__ import annotations

import collections
import csv
import json
import statistics
from pathlib import Path

SCRATCH = Path(".claude/scratch/zendesk")
CORPUS = SCRATCH / "corpus.jsonl"
TOP_N = 5
WORKSHEET_SAMPLE = 12


def load_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def cell_counts(corpus: list[dict]) -> dict[tuple[str, int], dict[int, int]]:
    counts: dict[tuple[str, int], dict[int, int]] = collections.defaultdict(
        lambda: collections.defaultdict(int)
    )
    for row in corpus:
        key = (row["category"] or "(none)", row["week_offset"])
        counts[key][row["academic_year"]] += 1
    return {k: dict(v) for k, v in counts.items()}


def consistent_cells(
    counts: dict[tuple[str, int], dict[int, int]], top_n: int
) -> list[tuple[str, int, int, int, int]]:
    by_category: dict[str, list[int]] = collections.defaultdict(list)
    for (category, _), years in counts.items():
        by_category[category].extend(years.values())

    thresholds = {
        category: statistics.quantiles(values, n=4)[2] if len(values) > 1 else 0
        for category, values in by_category.items()
    }

    selected = []
    for (category, offset), years in counts.items():
        c2024 = years.get(2024, 0)
        c2025 = years.get(2025, 0)
        threshold = thresholds[category]
        if c2024 >= threshold and c2025 >= threshold and c2024 and c2025:
            selected.append((category, offset, c2024, c2025, c2024 + c2025))

    selected.sort(key=lambda row: row[4], reverse=True)
    return selected[:top_n]


def main() -> int:
    corpus = load_corpus()
    counts = cell_counts(corpus)

    with (SCRATCH / "seasonality.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "week_offset", "sy2024_25", "sy2025_26", "total"])
        for (category, offset), years in sorted(counts.items()):
            c2024 = years.get(2024, 0)
            c2025 = years.get(2025, 0)
            writer.writerow([category, offset, c2024, c2025, c2024 + c2025])

    cells = consistent_cells(counts, TOP_N)
    by_cell = collections.defaultdict(list)
    for row in corpus:
        by_cell[(row["category"] or "(none)", row["week_offset"])].append(row)

    with (SCRATCH / "seasonality_worksheet.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "category",
                "week_offset",
                "academic_year",
                "ticket_id",
                "url",
                "subject",
                "same_ask_group",
            ]
        )
        for category, offset, _, _, _ in cells:
            tickets = sorted(by_cell[(category, offset)], key=lambda r: r["created_at"])
            for year in (2024, 2025):
                sample = [t for t in tickets if t["academic_year"] == year]
                for t in sample[:WORKSHEET_SAMPLE]:
                    writer.writerow(
                        [
                            category,
                            offset,
                            year,
                            t["ticket_id"],
                            t["url"],
                            t["subject"].replace("\t", " ").replace("\n", " "),
                            "",
                        ]
                    )

    print(f"{len(counts)} cells written to seasonality.csv")
    print(f"top {len(cells)} two-year-consistent cells:")
    for category, offset, c2024, c2025, total in cells:
        print(f"  {category} week {offset}: {c2024} + {c2025} = {total}")
    print("\nNow hand-tag the same_ask_group column in seasonality_worksheet.tsv.")
    print("Kill criterion: no cell with 10+ same-ask tickets in BOTH years.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
