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

# Valid Scale_Score range per Test_Type, used as a sanity guard. SAT sections run
# 200-800; PSAT 8/9 sections run 120-720; PSAT 10 and PSAT/NMSQT sections run
# 160-760 (a DIFFERENT scale from PSAT 8/9 -- do not share one bound across the
# two PSATs); ACT sections run 1-36. A single hardcoded range silently rejects
# every PSAT row.
SCALE_RANGE = {
    "SAT": (200, 800),
    "PSAT 8/9": (120, 720),
    "PSAT10": (160, 760),
    "ACT": (1, 36),
}

# Corrections to a published conversion table, as
# (assessment_id, Subject) -> {raw_score: corrected_scale_score}.
#
# College Board does publish tables that dip. The monotonic check below is a real
# guard against column misalignment during parsing, so it stays fatal -- a source
# anomaly gets a correction here, where it is visible and reviewable, rather than
# an exemption that lets the guard go quiet. Corrections are reported on stdout.
#
# 226308: PSAT 8/9 practice test #1 Reading and Writing dips at the top -- raw 65
# converts to 710 but raw 66 to 700, so a perfect section would score ten points
# below missing one. Verified against the rendered PDF, not just extracted text.
# Corrected to 720, which is both that row's own UPPER value and the section
# maximum. This deviates from the published table, and no downstream check can
# detect that -- it is recorded in SKILL.md and the CARAT reference doc.
SCALE_CORRECTIONS = {
    (226308, "Reading and Writing"): {66: 720},
}

# One entry per assessment:
#   (assessment_id, Test_Type, Administration_Round, Subject, Grade_Level,
#    source "Test" label as it appears in the paste)
#
# Test_Type and Grade_Level are per-assessment, not global -- a single run can
# mix PSAT 8/9 (grade 9) and PSAT 10 (grade 10).
#
# Rounds within one Test_Type and academic year MUST differ. The composite branch
# partitions sum(scale_score) by scope_round + administration_round, so a shared
# value sums two administrations into one bogus total.
TARGETS = [
    (226308, "PSAT 8/9", "PSAT891", "Reading and Writing", 9, "PSAT 8/9 Practice"),
    (226309, "PSAT 8/9", "PSAT891", "Mathematics", 9, "PSAT 8/9 Practice"),
    (226310, "PSAT10", "PSAT101", "Reading and Writing", 10, "PSAT 10 Practice"),
    (226311, "PSAT10", "PSAT101", "Mathematics", 10, "PSAT 10 Practice"),
]

ACADEMIC_YEAR = 2026  # academic_year_clean, NOT Illuminate's raw academic_year

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
    for aid, test_type, rnd, subject, grade, test in TARGETS:
        key = (test, subject)
        if key not in rows:
            notes.append(f"{aid} {rnd} {subject}: NO DATA in paste — skipped")
            failed = True
            continue

        mapping = dict(rows[key])
        for raw, corrected in SCALE_CORRECTIONS.get((aid, subject), {}).items():
            if raw not in mapping:
                sys.exit(
                    f"{aid} {subject}: SCALE_CORRECTIONS names raw {raw}, which "
                    "is not in the parsed table -- stale correction or wrong paste"
                )
            if mapping[raw] == corrected:
                sys.exit(
                    f"{aid} {subject}: SCALE_CORRECTIONS sets raw {raw} to "
                    f"{corrected}, which the source already says -- stale entry"
                )
            notes.append(
                f"{aid} {subject}: CORRECTED raw {raw} from {mapping[raw]} to "
                f"{corrected} (published-source anomaly, see SCALE_CORRECTIONS)"
            )
            mapping[raw] = corrected

        collapsed = collapse(mapping)
        scales = [s for _, _, s in collapsed]
        raws = sorted(mapping)

        if test_type not in SCALE_RANGE:
            sys.exit(f"{aid}: no SCALE_RANGE entry for Test_Type {test_type!r}")
        lo_bound, hi_bound = SCALE_RANGE[test_type]

        problems = []
        if raws[0] != 0:
            problems.append(f"starts at raw {raws[0]}, not 0")
        if [r for r in range(raws[0], raws[-1] + 1) if r not in mapping]:
            problems.append("GAPS in raw coverage")
        # Stays fatal. A dip that is genuinely in the source belongs in
        # SCALE_CORRECTIONS, which resolves it before this check runs.
        if scales != sorted(scales):
            problems.append("scale not monotonic non-decreasing")
        if min(scales) < lo_bound or max(scales) > hi_bound:
            problems.append(
                f"scale outside {lo_bound}-{hi_bound} ({min(scales)}-{max(scales)})"
            )

        failed = failed or bool(problems)
        notes.append(
            f"{aid} {test_type} {rnd} {subject} g{grade}: {len(collapsed)} rows, "
            f"raw 0-{raws[-1]}, scale {min(scales)}-{max(scales)}  "
            + ("!! " + "; ".join(problems) if problems else "OK")
        )

        for lo, hi, scale in collapsed:
            lines.append(
                f"{aid}\t{ACADEMIC_YEAR}\t{test_type}\t{rnd}\t{subject}\t"
                f"{grade}\t{lo}\t{hi}\t{scale}"
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
