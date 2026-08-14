"""Regenerate every row of the Expected Assessments tab from a calendar spec.

The tab drives the forced scaffold in int_tableau__college_assessment_roster_scores
-- one expected row per student per assessment, covering a current student's whole
high school history. Hand-editing it does not work, for two reasons:

  1. expected_admin_season_order is a single reverse-chronological sequence across
     all four grades. Inserting one administration renumbers every row after it,
     and nothing errors -- Tableau just orders the seasons wrongly.
  2. A season whose months are not listed matches no scores at all. The join binds
     month, so an omitted month silently orphans every score in it.

So the tab is regenerated whole, from a spec, and pasted over.

Usage:
    uv run python .claude/skills/carat-dashboard/scripts/build_expected_assessment_rows.py \
        spec.json out.tsv

The spec is JSON:

    {
      "regions": ["Camden", "Newark"],
      "admins": [
        {
          "grade": 9,
          "test_type": "Practice",
          "scope": "PSAT 8/9",
          "season": "Fall",
          "months": ["August", "September"],
          "growth": false
        },
        ...
      ]
    }

Every admin needs its full month list, historical months included -- see the
skill's procedure for deriving those from the score data. Omitting a month a
current student actually tested in orphans that score.

The spec also carries `not_reported`, for months where a test genuinely happens at
that grade but is deliberately not part of a reported season -- an 11th grader
sitting the SAT in September, say. Those rows carry the season `Not Official` and
no order value, and the staging model filters them out. They are inert to every
model, so they exist only as the record of that decision, and regenerating the tab
without them silently deletes it:

    "not_reported": [
      {"grade": 11, "test_type": "Official", "scope": "SAT",
       "months": ["August", "September", "October", "November"]}
    ]
"""

import json
import sys

# Position in the school year, which is what the season order sorts on. Two
# administrations can share a season name and still need separating -- grade 9 has
# a Practice Fall in August and an Official Fall in October -- so the sort key is
# the earliest month, not the season.
SCHOOL_YEAR_MONTHS = {
    "August": 1,
    "September": 2,
    "October": 3,
    "November": 4,
    "December": 5,
    "January": 6,
    "February": 7,
    "March": 8,
    "April": 9,
    "May": 10,
    "June": 11,
    "July": 12,
}

# Score types per scope, in the order they take season-order slots. Total first,
# then Growth where the administration has one, then the two sections -- matching
# the sequence already on the tab.
SCORE_TYPES = {
    "SAT": {
        "total": "sat_total_score",
        "growth": "sat_total_score_growth",
        "ebrw": "sat_ebrw",
        "math": "sat_math",
    },
    "PSAT 8/9": {
        "total": "psat89_total",
        "growth": "psat89_total_growth",
        "ebrw": "psat89_ebrw",
        "math": "psat89_math_section",
    },
    "PSAT10": {
        "total": "psat10_total",
        "growth": "psat10_total_growth",
        "ebrw": "psat10_ebrw",
        "math": "psat10_math_section",
    },
    "PSAT NMSQT": {
        "total": "psatnmsqt_total",
        "growth": "psatnmsqt_total_growth",
        "ebrw": "psatnmsqt_ebrw",
        "math": "psatnmsqt_math_section",
    },
}

HEADER = [
    "expected_region",
    "expected_grade_level",
    "expected_test_type",
    "expected_scope",
    "expected_score_type",
    "expected_month_round",
    "expected_admin_season",
    "expected_admin_season_order",
]


def validate(spec):
    """Fail loudly on the mistakes that would otherwise ship silently."""
    problems = []

    for i, n in enumerate(spec.get("not_reported", [])):
        where = f"not_reported {i} ({n.get('grade')} {n.get('scope')})"
        if n.get("scope") not in SCORE_TYPES:
            problems.append(f"{where}: unknown scope {n.get('scope')!r}")
        for m in n.get("months", []):
            if m not in SCHOOL_YEAR_MONTHS:
                problems.append(f"{where}: {m!r} is not a month name")
        # A month cannot be both reported and not reported for one test and grade.
        for a in spec.get("admins", []):
            same_test = (
                a.get("grade") == n.get("grade")
                and a.get("test_type") == n.get("test_type")
                and a.get("scope") == n.get("scope")
            )
            if same_test:
                overlap = set(n.get("months", [])) & set(a.get("months", []))
                if overlap:
                    problems.append(
                        f"{where}: months {sorted(overlap)} are also reported"
                        f" under season {a.get('season')!r}"
                    )

    if not spec.get("regions"):
        problems.append("no regions listed")
    if not spec.get("admins"):
        problems.append("no admins listed")

    seen = {}
    for i, a in enumerate(spec.get("admins", [])):
        where = f"admin {i} ({a.get('grade')} {a.get('test_type')} {a.get('scope')})"

        if a.get("scope") not in SCORE_TYPES:
            problems.append(f"{where}: unknown scope {a.get('scope')!r}")
        if not a.get("months"):
            problems.append(f"{where}: no months -- it would match no scores")
        for m in a.get("months", []):
            if m not in SCHOOL_YEAR_MONTHS:
                problems.append(f"{where}: {m!r} is not a month name")

        # Two administrations of the same test at the same grade must not share a
        # season, or their scores collapse into one row.
        key = (a.get("grade"), a.get("test_type"), a.get("scope"), a.get("season"))
        if key in seen:
            problems.append(f"{where}: duplicates the season of admin {seen[key]}")
        seen[key] = i

        # A month may belong to only one season within a test and grade, or a score
        # in it would match two expected rows and fan out.
        for other_i, other in enumerate(spec.get("admins", [])[:i]):
            same_test = (
                other.get("grade") == a.get("grade")
                and other.get("test_type") == a.get("test_type")
                and other.get("scope") == a.get("scope")
            )
            if same_test:
                overlap = set(a.get("months", [])) & set(other.get("months", []))
                if overlap:
                    problems.append(
                        f"{where}: months {sorted(overlap)} also on admin {other_i}"
                    )

    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        raise SystemExit(f"spec rejected -- {len(problems)} problem(s)")


def order_admins(admins):
    """Reverse-chronological: latest grade first, latest administration first.

    Returns the admins with an `order_base` -- the season-order value its Total row
    takes. Section and growth rows count up from there, so each administration
    consumes as many slots as it has score types.
    """
    # scope and test type break a tie so the output does not depend on the order
    # the admins happen to be listed in -- grade 10 has a Practice PSAT10 and an
    # Official PSAT NMSQT that both sit in October.
    ordered = sorted(
        admins,
        key=lambda a: (
            -a["grade"],
            -min(SCHOOL_YEAR_MONTHS[m] for m in a["months"]),
            a["scope"],
            a["test_type"],
        ),
    )

    cursor = 1
    for a in ordered:
        a["order_base"] = cursor
        cursor += 4 if a.get("growth") else 3

    return ordered


def rows_for(admin, region):
    """Emit one row per score type per month, plus a single growth row.

    A growth row carries the SEASON NAME in expected_month_round rather than a
    month, because growth is a change between administrations and so is not
    month-bound. Anything reading expected_month has to tolerate that.
    """
    types = SCORE_TYPES[admin["scope"]]
    slot = admin["order_base"]

    sequence = [("total", True)]
    if admin.get("growth"):
        sequence.append(("growth", False))
    sequence += [("ebrw", True), ("math", True)]

    for kind, per_month in sequence:
        month_values = admin["months"] if per_month else [admin["season"]]
        for month in month_values:
            yield [
                region,
                str(admin["grade"]),
                admin["test_type"],
                admin["scope"],
                types[kind],
                month,
                admin["season"],
                str(slot),
            ]
        slot += 1


def not_reported_rows(entry, region):
    """Season `Not Official`, no order -- filtered out downstream, kept as a record."""
    types = SCORE_TYPES[entry["scope"]]
    for kind in ("total", "ebrw", "math"):
        for month in entry["months"]:
            yield [
                region,
                str(entry["grade"]),
                entry["test_type"],
                entry["scope"],
                types[kind],
                month,
                "Not Official",
                "",
            ]


def main():
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} spec.json out.tsv")

    with open(sys.argv[1], encoding="utf-8") as f:
        spec = json.load(f)

    validate(spec)
    admins = order_admins(spec["admins"])

    out = []
    for region in spec["regions"]:
        for admin in admins:
            out.extend(rows_for(admin, region))
        for entry in spec.get("not_reported", []):
            out.extend(not_reported_rows(entry, region))

    with open(sys.argv[2], "w", encoding="utf-8") as f:
        for row in out:
            f.write("\t".join(row) + "\n")

    n_not_reported = sum(
        len(e["months"]) * 3 for e in spec.get("not_reported", [])
    ) * len(spec["regions"])
    print(
        f"{len(out)} rows -> {sys.argv[2]} (no header; paste over A2)"
        f" -- {len(out) - n_not_reported} reported, {n_not_reported} Not Official"
    )
    print(f"columns: {', '.join(HEADER)}\n")
    print("season order, most recent administration first:")
    for a in admins:
        span = (
            f"{a['months'][0]}-{a['months'][-1]}"
            if len(a["months"]) > 1
            else a["months"][0]
        )
        print(
            f"  {a['order_base']:>3}  G{a['grade']} {a['test_type']:<8}"
            f" {a['scope']:<11} {a['season']:<6} {span}"
            f"{'  +growth' if a.get('growth') else ''}"
        )


if __name__ == "__main__":
    main()
