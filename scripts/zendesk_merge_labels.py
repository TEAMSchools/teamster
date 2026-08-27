# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Merge labeled partition worksheets, validate them, and report the rate.

Enforces the rubric mechanically so the headline number cannot drift from
what the guide says. In particular a `self_inflicted` row missing either
`artifact_name` or `one_line_fix` is DEMOTED to `genuine` before counting,
and the demotion rate is reported -- that rule is the only thing keeping an
elastic label honest, so it is applied here rather than trusted to a human.

Usage:
    uv run scripts/zendesk_merge_labels.py .claude/scratch/zendesk/partition_answered_slice_*.tsv
    uv run scripts/zendesk_merge_labels.py --population 4120 <files>

Design reference:
    docs/superpowers/plans/2026-08-05-zendesk-partition-labeling-guide.md
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import sys
from pathlib import Path

LABELS = {"self_inflicted", "genuine", "vendor_or_user_error"}
CLASSES = {"ticket", "request"}


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Honest at small proportions where Wald is not."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def read_worksheet(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def merge(paths: list[Path]) -> tuple[list[dict], list[str]]:
    """Combine worksheets, flagging any ticket labeled in more than one file."""
    seen: dict[str, dict] = {}
    problems: list[str] = []
    for path in paths:
        for row in read_worksheet(path):
            tid = row["ticket_id"]
            if tid in seen:
                prior = seen[tid]
                if (prior.get("label"), prior.get("class")) != (
                    row.get("label"),
                    row.get("class"),
                ):
                    problems.append(
                        f"ticket {tid} labeled differently in two files: "
                        f"{prior.get('label')}/{prior.get('class')} vs "
                        f"{row.get('label')}/{row.get('class')}"
                    )
                continue
            row["_source"] = path.name
            seen[tid] = row
    return list(seen.values()), problems


def validate(rows: list[dict]) -> tuple[list[str], int]:
    """Return blocking problems, and demote unsupported self_inflicted rows."""
    problems: list[str] = []
    demoted = 0
    for row in rows:
        tid = row["ticket_id"]
        label = (row.get("label") or "").strip()
        klass = (row.get("class") or "").strip()

        if not label:
            problems.append(f"ticket {tid}: no label")
            continue
        if label not in LABELS:
            problems.append(f"ticket {tid}: label '{label}' is not one of {LABELS}")
            continue
        if not klass:
            problems.append(f"ticket {tid}: no class")
        elif klass not in CLASSES:
            problems.append(f"ticket {tid}: class '{klass}' is not one of {CLASSES}")

        if label == "self_inflicted":
            if (
                not (row.get("artifact_name") or "").strip()
                or not (row.get("one_line_fix") or "").strip()
            ):
                row["label"] = "genuine"
                row["_demoted"] = "1"
                demoted += 1
    return problems, demoted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--population",
        type=int,
        default=None,
        help="Frame size, for context. Omit for a census.",
    )
    parser.add_argument("--out", type=Path, default=None, help="Write merged TSV here.")
    args = parser.parse_args()

    rows, merge_problems = merge(args.files)
    validation_problems, demoted = validate(rows)
    problems = merge_problems + validation_problems

    labels = collections.Counter(r["label"] for r in rows if r.get("label"))
    classes = collections.Counter(r.get("class") for r in rows if r.get("class"))
    n = sum(labels.values())
    k = labels["self_inflicted"]

    print(f"merged {len(rows)} rows from {len(args.files)} file(s)")
    if args.population:
        print(f"frame population: {args.population}  sampled: {len(rows)}")
    else:
        print("no population given - treating as a census")
    print()
    print("label:")
    for label, count in labels.most_common():
        print(f"  {label:22s} {count:4d}  {count / n:6.1%}" if n else f"  {label}")
    print("class:")
    for klass, count in classes.most_common():
        print(f"  {klass:22s} {count:4d}")
    if demoted:
        print(
            f"\ndemoted {demoted} self_inflicted row(s) to genuine "
            f"for missing artifact_name or one_line_fix"
        )

    if n:
        lo, hi = wilson_interval(k, n)
        print(f"\nself-inflicted rate: {k}/{n} = {k / n:.1%}")
        print(f"95% interval: {lo:.1%} to {hi:.1%}")
        threshold = 0.20
        if lo >= threshold:
            verdict = "ABOVE threshold - the interval clears 20%"
        elif hi < threshold:
            verdict = "BELOW threshold - the interval is entirely under 20%"
        else:
            verdict = "INCONCLUSIVE - the interval straddles 20%"
        print(f"verdict vs 20%: {verdict}")

    if problems:
        print(f"\n{len(problems)} problem(s):", file=sys.stderr)
        for p in problems[:40]:
            print(f"  {p}", file=sys.stderr)
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more", file=sys.stderr)

    if args.out:
        fieldnames = [k for k in rows[0] if not k.startswith("_")] + [
            "_source",
            "_demoted",
        ]
        with args.out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nmerged worksheet written to {args.out}")

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
