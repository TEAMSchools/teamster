"""Turn College Board raw-to-scale conversion pastes into act_scale_score_key rows.

Reads columns BY HEADER NAME, not position. This is load-bearing: Foundation's
tabs differ in shape (some carry `Scale Score Upper`, some don't, some append
`Percentage`), so a positional parser reads `Percentage` as the scale score and
silently emits garbage.

Also tolerates: rows in any order, descending sort, headers repeated mid-stream,
data rows appearing above the first header, and duplicate rows (consistent
duplicates are absorbed, conflicting ones abort).

Emits `Scale Score Lower`, which is what every existing sheet row uses.

Usage:
    uv run python build_scale_score_rows.py <out.tsv> <paste1.tsv> [paste2.tsv ...]

Edit TARGETS for the administration you are loading.
"""

import sys
from collections import defaultdict
from pathlib import Path

# Section label in the paste -> Subject value in the sheet.
SUBJECT = {
    "reading and writing section": "Reading and Writing",
    "reading and writing": "Reading and Writing",
    "math": "Mathematics",
    "math section": "Mathematics",
}

# (assessment_id, Administration_Round, Subject, source "Test" label in the paste)
# BOY -> SAT1, MOY -> SAT2. The two rounds MUST differ: the composite branch
# partitions sum(scale_score) by scope_round + administration_round, so a shared
# value sums both rounds' sections into one bogus total.
TARGETS = [
    (226182, "SAT1", "Reading and Writing", "SAT Practice Test 1"),
    (226183, "SAT1", "Mathematics", "SAT Practice Test 1"),
    (226184, "SAT2", "Reading and Writing", "SAT Practice Test 2"),
    (226185, "SAT2", "Mathematics", "SAT Practice Test 2"),
]

ACADEMIC_YEAR = 2026  # academic_year_clean, NOT Illuminate's raw academic_year
TEST_TYPE = "SAT"  # stays SAT even though Illuminate scope reads Benchmark
GRADE = 11  # illuminate grade_level_id - 1

# Column positions assumed for data rows appearing before any header.
DEFAULT_COLS = {"test": 0, "section": 1, "raw": 2, "lower": 3}


def header_cols(parts: list[str]) -> dict[str, int] | None:
    """Map field names to indices from a header row, or None if not a header."""
    lowered = [p.strip().lower() for p in parts]
    if "raw score" not in lowered:
        return None

    cols: dict[str, int] = {}
    for i, name in enumerate(lowered):
        if name == "test":
            cols["test"] = i
        elif name == "section":
            cols["section"] = i
        elif name == "raw score":
            cols["raw"] = i
        elif name in ("scale score lower", "scale score"):
            cols["lower"] = i

    missing = {"test", "section", "raw", "lower"} - cols.keys()
    if missing:
        sys.exit(f"header missing required columns {missing}: {parts}")
    return cols


def parse(paths: list[str]) -> dict[tuple[str, str], dict[int, int]]:
    rows: dict[tuple[str, str], dict[int, int]] = defaultdict(dict)
    conflicts, skipped = [], 0

    for src in paths:
        cols = dict(DEFAULT_COLS)
        for line in Path(src).read_text().splitlines():
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split("\t")]

            found = header_cols(parts)
            if found is not None:
                cols = found
                continue

            if max(cols.values()) >= len(parts):
                skipped += 1
                continue

            raw, lower = parts[cols["raw"]], parts[cols["lower"]]
            if not raw.isdigit() or not lower.isdigit():
                skipped += 1
                continue

            subject = SUBJECT.get(parts[cols["section"]].lower())
            if subject is None:
                skipped += 1
                continue

            key = (parts[cols["test"]], subject)
            raw_i, scale_i = int(raw), int(lower)
            if raw_i in rows[key] and rows[key][raw_i] != scale_i:
                conflicts.append((key, raw_i, rows[key][raw_i], scale_i))
            rows[key][raw_i] = scale_i

    print("=== parsed ===")
    for key, m in sorted(rows.items()):
        print(f"{key[0]} | {key[1]}: {len(m)} raw scores, {min(m)}-{max(m)}")
    print(f"skipped non-data lines: {skipped}")

    if conflicts:
        sys.exit(f"CONFLICTING duplicate rows, refusing to emit: {conflicts}")
    return rows


def collapse(mapping: dict[int, int]) -> list[list[int]]:
    """Collapse consecutive raw scores sharing a scale score into ranges."""
    out: list[list[int]] = []
    for raw in sorted(mapping):
        if out and out[-1][2] == mapping[raw] and out[-1][1] == raw - 1:
            out[-1][1] = raw
        else:
            out.append([raw, raw, mapping[raw]])
    return out


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    rows = parse(sys.argv[2:])

    # Two rounds reusing one conversion table is common and legitimate.
    print("\n=== round comparison ===")
    for subj in sorted({k[1] for k in rows}):
        have = sorted(t for t in {k[0] for k in rows} if (t, subj) in rows)
        if len(have) == 2:
            same = rows[(have[0], subj)] == rows[(have[1], subj)]
            verdict = "IDENTICAL" if same else "DIFFER"
            print(f"{subj}: {have[0]} vs {have[1]} -> {verdict}")

    lines, notes, failed = [], [], False
    for aid, rnd, subject, test in TARGETS:
        key = (test, subject)
        if key not in rows:
            notes.append(f"{aid} {rnd} {subject}: NO DATA in paste — skipped")
            failed = True
            continue

        collapsed = collapse(rows[key])
        scales = [s for _, _, s in collapsed]
        raws = sorted(rows[key])

        problems = []
        if raws[0] != 0:
            problems.append(f"starts at raw {raws[0]}, not 0")
        if [r for r in range(raws[0], raws[-1] + 1) if r not in rows[key]]:
            problems.append("GAPS in raw coverage")
        if scales != sorted(scales):
            problems.append("scale not monotonic non-decreasing")
        if min(scales) < 200 or max(scales) > 800:
            problems.append(f"scale outside 200-800 ({min(scales)}-{max(scales)})")

        failed = failed or bool(problems)
        notes.append(
            f"{aid} {rnd} {subject}: {len(collapsed)} rows, raw 0-{raws[-1]}, "
            f"scale {min(scales)}-{max(scales)}  "
            + ("!! " + "; ".join(problems) if problems else "OK")
        )

        for lo, hi, scale in collapsed:
            lines.append(
                f"{aid}\t{ACADEMIC_YEAR}\t{TEST_TYPE}\t{rnd}\t{subject}\t"
                f"{GRADE}\t{lo}\t{hi}\t{scale}"
            )

    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")

    print("\n=== emitted ===")
    print("\n".join(notes))
    print(f"\ntotal rows: {len(lines)} -> {out}")
    if failed:
        sys.exit("\nNOT READY: resolve the problems above before pasting.")


if __name__ == "__main__":
    main()
