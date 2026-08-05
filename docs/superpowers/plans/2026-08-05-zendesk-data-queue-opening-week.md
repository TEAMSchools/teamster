# Zendesk Data-queue Opening Week Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the three opening-week probes from the design spec, so
their kill criteria can be evaluated before any clustering machinery is built.

**Architecture:** Four standalone PEP 723 scripts in `scripts/`, run with
`uv run`. One extracts the corpus from BigQuery into a local JSONL file; three
read that file and emit probe worksheets. Every pure function is unit-tested in
`tests/test_zendesk_probes.py`. Analysis **code** is committed; analysis
**output** contains student PII and stays in gitignored `.claude/scratch/`.

**Tech Stack:** Python 3.13, PEP 723 inline dependencies,
`google-cloud-bigquery` (ADC auth), pytest, BigQuery.

## Global Constraints

- Scope is Zendesk groups `21474460` (Data) and `31319068` (Teaching and
  Learning), `created_at` between `2024-07-01` and `2026-06-30`, 4,608 tickets.
- Reconciliation targets, verified during design: 4,608 tickets; 16,819 comment
  events; 4,474 tickets with at least one public comment; 4,130 with two or
  more; 1,082 comments carrying at least one attachment.
- First instructional day anchors: SY24-25 = `2024-08-22`, SY25-26 =
  `2025-08-25`.
- Kill criteria, committed before any probe runs: partition probe dies under 20%
  self-inflicted; reply-shape probe dies if fewer than 20 slugs cover half the
  number-shaped volume; seasonality probe dies if no cell holds 10 or more
  same-ask tickets in both years.
- PII: ticket text contains student names and student numbers. All script output
  goes to `.claude/scratch/zendesk/`. Nothing raw reaches GitHub, Asana, or
  Slack. Aggregates and counts are not PII.
- No dbt models, no warehouse writes. Scripts are read-only against BigQuery.
- Always `uv run`, never bare `python`.
- Work happens in the worktree at
  `/workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis`.
  Use `git -C <worktree>` for git and `cd <worktree> &&` for pytest.
- `scripts/` has no `__init__.py` and must not gain one. Scripts are standalone
  executables and do not import each other; they communicate through files.

---

## File Structure

| File                                   | Responsibility                                                                                                                                                                           |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/zendesk_extract_corpus.py`    | Sole BigQuery reader. Owns all date logic (`academic_year_of`, `week_offset`) and persists derived fields so no other script recomputes them. Writes `corpus.jsonl` and `manifest.json`. |
| `scripts/zendesk_probe_seasonality.py` | Reads `corpus.jsonl`, aggregates category by week-offset by year, identifies two-year-consistent cells, emits a hand-tagging worksheet.                                                  |
| `scripts/zendesk_probe_reply_shape.py` | Reads `corpus.jsonl`, classifies each first agent reply into four shapes, emits a slug-assignment worksheet.                                                                             |
| `scripts/zendesk_probe_sample.py`      | Reads `corpus.jsonl`, filters to the partition-probe pool, draws a deterministic stratified sample, emits a labeling worksheet.                                                          |
| `tests/test_zendesk_probes.py`         | Unit tests for every pure function across the four scripts. Loads them via `importlib`.                                                                                                  |
| `scripts/CLAUDE.md`                    | Add four rows to the script catalog.                                                                                                                                                     |

Output files, all gitignored, all under `.claude/scratch/zendesk/`:
`corpus.jsonl`, `manifest.json`, `seasonality.csv`, `seasonality_worksheet.tsv`,
`reply_shape.csv`, `slug_worksheet.tsv`, `partition_sample.tsv`.

---

### Task 1: Corpus extraction

**Files:**

- Create: `scripts/zendesk_extract_corpus.py`
- Test: `tests/test_zendesk_probes.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `FIRST_INSTRUCTIONAL_DAY: dict[int, datetime.date]`
  - `academic_year_of(d: datetime.date) -> int`
  - `week_offset(d: datetime.date, anchor: datetime.date) -> int`
  - `.claude/scratch/zendesk/corpus.jsonl`, one JSON object per line with keys
    `ticket_id` (int), `created_at` (str, ISO), `academic_year` (int),
    `week_offset` (int), `status` (str), `group_id` (int), `category` (str or
    null), `subject` (str), `description` (str), and `comments` (list of objects
    with `seq` (int, 1-based), `created_at` (str), `is_public` (bool),
    `author_id` (str or null), `plain_body` (str), `attachment_count` (int)).
  - `.claude/scratch/zendesk/manifest.json` with keys `n_tickets`, `n_comments`,
    `n_tickets_with_public_comment`, `n_tickets_with_agent_reply`,
    `n_comments_with_attachments`.

- [ ] **Step 1: Write the failing tests for the date functions**

Create `tests/test_zendesk_probes.py`:

```python
"""Unit tests for the Zendesk opening-week probe scripts.

Scripts under `scripts/` are standalone PEP 723 executables with no
`__init__.py`, so they are loaded by path. Registration in `sys.modules`
before `exec_module` is required for dataclass resolution.
"""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


extract = load_script("zendesk_extract_corpus")


def test_academic_year_starts_in_july():
    assert extract.academic_year_of(datetime.date(2024, 7, 1)) == 2024
    assert extract.academic_year_of(datetime.date(2024, 12, 31)) == 2024
    assert extract.academic_year_of(datetime.date(2025, 6, 30)) == 2024
    assert extract.academic_year_of(datetime.date(2025, 7, 1)) == 2025


def test_week_offset_is_zero_for_the_anchor_week():
    anchor = datetime.date(2025, 8, 25)
    assert extract.week_offset(anchor, anchor) == 0
    assert extract.week_offset(anchor + datetime.timedelta(days=6), anchor) == 0
    assert extract.week_offset(anchor + datetime.timedelta(days=7), anchor) == 1


def test_week_offset_is_negative_before_the_anchor():
    anchor = datetime.date(2025, 8, 25)
    assert extract.week_offset(anchor - datetime.timedelta(days=1), anchor) == -1
    assert extract.week_offset(anchor - datetime.timedelta(days=7), anchor) == -1
    assert extract.week_offset(anchor - datetime.timedelta(days=8), anchor) == -2


def test_anchors_cover_both_school_years_in_scope():
    assert extract.FIRST_INSTRUCTIONAL_DAY[2024] == datetime.date(2024, 8, 22)
    assert extract.FIRST_INSTRUCTIONAL_DAY[2025] == datetime.date(2025, 8, 25)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -v
```

Expected: collection error — `scripts/zendesk_extract_corpus.py` does not exist.

- [ ] **Step 3: Write the extraction script**

Create `scripts/zendesk_extract_corpus.py`:

```python
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

TICKETS_QUERY = f"""
select
    t.id as ticket_id,
    t.created_at,
    t.status,
    t.group_id,
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

        thread = sorted(by_ticket[t["ticket_id"]], key=lambda c: c["comment_created_at"])
        corpus.append(
            {
                "ticket_id": t["ticket_id"],
                "created_at": created.isoformat(),
                "academic_year": year,
                "week_offset": week_offset(created_date, anchor),
                "status": t["status"],
                "group_id": t["group_id"],
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Run the extraction and confirm reconciliation**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run scripts/zendesk_extract_corpus.py --verify
```

Expected: exit 0, no `MISMATCH` lines, and a manifest reading exactly
`n_tickets: 4608`, `n_comments: 16819`, `n_tickets_with_public_comment: 4474`,
`n_tickets_with_agent_reply: 4130`, `n_comments_with_attachments: 1082`.

A mismatch means either the scope filter drifted or the source data changed
since the design measurements. Investigate before proceeding — every downstream
probe inherits this corpus.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && git add scripts/zendesk_extract_corpus.py tests/test_zendesk_probes.py && git commit -m "feat: extract Zendesk Data-queue corpus for opening-week probes

Refs #4739"
```

---

### Task 2: Seasonality probe

**Files:**

- Create: `scripts/zendesk_probe_seasonality.py`
- Modify: `tests/test_zendesk_probes.py`

**Interfaces:**

- Consumes: `.claude/scratch/zendesk/corpus.jsonl` from Task 1, specifically the
  `category`, `academic_year`, and `week_offset` keys.
- Produces:
  - `cell_counts(corpus: list[dict]) -> dict[tuple[str, int], dict[int, int]]`
    keyed by `(category, week_offset)`, valued by `{academic_year: count}`.
  - `consistent_cells(counts, top_n: int) -> list[tuple[str, int, int, int, int]]`
    returning `(category, week_offset, count_2024, count_2025, total)` for cells
    whose count in **both** years reaches that category's 75th percentile,
    sorted by total descending.
  - `.claude/scratch/zendesk/seasonality.csv` and
    `.claude/scratch/zendesk/seasonality_worksheet.tsv`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_zendesk_probes.py`:

```python
seasonality = load_script("zendesk_probe_seasonality")


def _row(category: str, year: int, offset: int) -> dict:
    return {"category": category, "academic_year": year, "week_offset": offset}


def test_cell_counts_buckets_by_category_year_and_offset():
    corpus = [
        _row("data__deanslist", 2024, 3),
        _row("data__deanslist", 2024, 3),
        _row("data__deanslist", 2025, 3),
        _row("data__deanslist", 2025, 9),
    ]
    counts = seasonality.cell_counts(corpus)
    assert counts[("data__deanslist", 3)] == {2024: 2, 2025: 1}
    assert counts[("data__deanslist", 9)] == {2025: 1}


def test_cell_counts_labels_missing_category():
    counts = seasonality.cell_counts([_row(None, 2024, 0)])
    assert counts[("(none)", 0)] == {2024: 1}


def test_consistent_cells_requires_both_years_above_threshold():
    corpus = []
    # week 3 is heavy in both years; week 9 is heavy only in 2025.
    corpus += [_row("c", 2024, 3) for _ in range(10)]
    corpus += [_row("c", 2025, 3) for _ in range(10)]
    corpus += [_row("c", 2025, 9) for _ in range(10)]
    corpus += [_row("c", 2024, w) for w in range(10, 30)]
    corpus += [_row("c", 2025, w) for w in range(10, 30)]

    cells = seasonality.consistent_cells(seasonality.cell_counts(corpus), top_n=5)
    selected = {(c[0], c[1]) for c in cells}
    assert ("c", 3) in selected
    assert ("c", 9) not in selected


def test_consistent_cells_respects_top_n():
    corpus = []
    for offset in range(8):
        corpus += [_row("c", 2024, offset) for _ in range(5)]
        corpus += [_row("c", 2025, offset) for _ in range(5)]
    cells = seasonality.consistent_cells(seasonality.cell_counts(corpus), top_n=3)
    assert len(cells) == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -k seasonality -v
```

Expected: collection error — `scripts/zendesk_probe_seasonality.py` does not
exist.

- [ ] **Step 3: Write the seasonality probe**

Create `scripts/zendesk_probe_seasonality.py`:

```python
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
            ["category", "week_offset", "academic_year", "ticket_id", "subject",
             "same_ask_group"]
        )
        for category, offset, _, _, _ in cells:
            tickets = sorted(
                by_cell[(category, offset)], key=lambda r: r["created_at"]
            )
            for year in (2024, 2025):
                sample = [t for t in tickets if t["academic_year"] == year]
                for t in sample[:WORKSHEET_SAMPLE]:
                    writer.writerow(
                        [category, offset, year, t["ticket_id"],
                         t["subject"].replace("\t", " ").replace("\n", " "), ""]
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Run the probe**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run scripts/zendesk_probe_seasonality.py
```

Expected: a cell count printed, five candidate cells listed, and
`seasonality_worksheet.tsv` written with up to 120 rows. Read the worksheet and
fill `same_ask_group` with a short label per ticket, leaving it blank when the
ticket is unrelated to its neighbours. This is the human judgment step — a model
can suggest labels, but the count that meets the kill criterion must be one a
person stands behind.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && git add scripts/zendesk_probe_seasonality.py tests/test_zendesk_probes.py && git commit -m "feat: add Zendesk seasonality probe

Refs #4739"
```

---

### Task 3: Reply-shape probe

**Files:**

- Create: `scripts/zendesk_probe_reply_shape.py`
- Modify: `tests/test_zendesk_probes.py`

**Interfaces:**

- Consumes: `.claude/scratch/zendesk/corpus.jsonl` from Task 1, specifically
  each ticket's `comments` list.
- Produces:
  - `first_agent_reply(ticket: dict) -> dict | None` returning the public
    comment at `seq` position 2 or later that is not the opening comment, or
    `None`.
  - `classify_reply_shape(plain_body: str, attachment_count: int) -> str`
    returning one of `"existing_link"`, `"attached_file"`, `"pasted_value"`,
    `"not_a_data_ask"`.
  - `.claude/scratch/zendesk/reply_shape.csv` and
    `.claude/scratch/zendesk/slug_worksheet.tsv`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_zendesk_probes.py`:

```python
reply_shape = load_script("zendesk_probe_reply_shape")


def test_link_wins_over_number():
    text = "Here are your 47 students: https://tableau.kipptaf.org/#/views/Foo"
    assert reply_shape.classify_reply_shape(text, 0) == "existing_link"


def test_attachment_wins_over_number_when_no_link():
    assert reply_shape.classify_reply_shape("Attached, 47 rows.", 1) == "attached_file"


def test_bare_number_is_a_pasted_value():
    assert reply_shape.classify_reply_shape("It's 47 as of today.", 0) == "pasted_value"
    assert reply_shape.classify_reply_shape("Total: 1,204 students", 0) == "pasted_value"


def test_dates_and_ticket_refs_are_not_pasted_values():
    assert reply_shape.classify_reply_shape(
        "Fixed on 2025-09-04, see ticket #12345.", 0
    ) == "not_a_data_ask"


def test_prose_with_no_number_is_not_a_data_ask():
    assert reply_shape.classify_reply_shape(
        "You'll need to ask the school ops manager for that.", 0
    ) == "not_a_data_ask"


def test_empty_reply_is_not_a_data_ask():
    assert reply_shape.classify_reply_shape("", 0) == "not_a_data_ask"


def test_first_agent_reply_skips_the_requester_opening_comment():
    ticket = {
        "comments": [
            {"seq": 1, "is_public": True, "plain_body": "Can you pull this?"},
            {"seq": 2, "is_public": False, "plain_body": "internal note"},
            {"seq": 3, "is_public": True, "plain_body": "Here you go."},
        ]
    }
    assert reply_shape.first_agent_reply(ticket)["seq"] == 3


def test_first_agent_reply_is_none_when_only_the_opening_comment_exists():
    ticket = {"comments": [{"seq": 1, "is_public": True, "plain_body": "Help"}]}
    assert reply_shape.first_agent_reply(ticket) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -k reply -v
```

Expected: collection error — `scripts/zendesk_probe_reply_shape.py` does not
exist.

- [ ] **Step 3: Write the reply-shape probe**

Create `scripts/zendesk_probe_reply_shape.py`:

```python
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
    """The first public comment after the requester's opening comment."""
    public = [c for c in ticket["comments"] if c["is_public"]]
    return public[1] if len(public) >= 2 else None


def classify_reply_shape(plain_body: str, attachment_count: int) -> str:
    text = plain_body or ""
    if URL_RE.search(text):
        return "existing_link"
    if attachment_count > 0:
        return "attached_file"

    stripped = TIME_RE.sub(" ", TICKET_REF_RE.sub(" ", DATE_RE.sub(" ", text)))
    if NUMBER_RE.search(stripped):
        return "pasted_value"
    return "not_a_data_ask"


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
        shape = classify_reply_shape(reply["plain_body"], reply["attachment_count"])
        shapes[shape] += 1
        rows.append((ticket, reply, shape))

    with (SCRATCH / "reply_shape.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["shape", "n_tickets"])
        for shape, n in shapes.most_common():
            writer.writerow([shape, n])

    worksheet = [
        (t, r, s)
        for t, r, s in rows
        if (t["category"] or "") in WORKSHEET_CATEGORIES
    ]
    worksheet.sort(key=lambda item: item[0]["created_at"], reverse=True)

    with (SCRATCH / "slug_worksheet.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            ["ticket_id", "category", "shape", "subject", "reply_excerpt", "slug"]
        )
        for ticket, reply, shape in worksheet[:WORKSHEET_LIMIT]:
            excerpt = reply["plain_body"][:300].replace("\t", " ").replace("\n", " ")
            writer.writerow(
                [
                    ticket["ticket_id"],
                    ticket["category"],
                    shape,
                    ticket["subject"].replace("\t", " ").replace("\n", " "),
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -v
```

Expected: 16 passed.

- [ ] **Step 5: Run the probe and validate the classifier by hand**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run scripts/zendesk_probe_reply_shape.py
```

Expected: a shape distribution summing to 4,608, with `no_agent_reply` reading
exactly 478 — the 344 tickets with exactly one public comment (4,474 − 4,130)
plus the 134 with none at all (4,608 − 4,474) — and a 200-row
`slug_worksheet.tsv`.

Before trusting the distribution, read 20 rows of `slug_worksheet.tsv` and
confirm the `shape` column matches your reading. The `pasted_value` bucket is
the error-prone one; if it is visibly wrong, tighten `NUMBER_RE` and re-run
rather than proceeding on a bad base rate.

Then assign slugs. This is the tier-2 step — a `sonnet` subagent can draft slugs
in batches of 25, but consistency across the 200 rows is the whole point, so
review the distinct-slug list before counting it.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && git add scripts/zendesk_probe_reply_shape.py tests/test_zendesk_probes.py && git commit -m "feat: add Zendesk reply-shape probe

Refs #4739"
```

---

### Task 4: Partition probe sample builder

**Files:**

- Create: `scripts/zendesk_probe_sample.py`
- Modify: `tests/test_zendesk_probes.py`

**Interfaces:**

- Consumes: `.claude/scratch/zendesk/corpus.jsonl` from Task 1.
- Produces:
  - `matches_grant_lexicon(text: str) -> bool`
  - `stratified_sample(rows: list[dict], stratum_of, n: int, seed: int) -> list[dict]`
    returning a deterministic sample allocated proportionally across strata.
  - `.claude/scratch/zendesk/partition_sample.tsv`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_zendesk_probes.py`:

```python
sample_mod = load_script("zendesk_probe_sample")


def test_grant_lexicon_matches_access_language():
    assert sample_mod.matches_grant_lexicon("I've granted you access to the view.")
    assert sample_mod.matches_grant_lexicon("Added you to the Tableau group.")
    assert sample_mod.matches_grant_lexicon("Your permissions are updated.")


def test_grant_lexicon_ignores_unrelated_prose():
    assert not sample_mod.matches_grant_lexicon("The report runs on Tuesdays.")
    assert not sample_mod.matches_grant_lexicon("")


def test_stratified_sample_is_deterministic_for_a_seed():
    rows = [{"id": i, "s": i % 4} for i in range(200)]
    a = sample_mod.stratified_sample(rows, lambda r: r["s"], n=40, seed=7)
    b = sample_mod.stratified_sample(rows, lambda r: r["s"], n=40, seed=7)
    assert [r["id"] for r in a] == [r["id"] for r in b]


def test_stratified_sample_covers_every_stratum():
    rows = [{"id": i, "s": i % 4} for i in range(200)]
    picked = sample_mod.stratified_sample(rows, lambda r: r["s"], n=40, seed=7)
    assert {r["s"] for r in picked} == {0, 1, 2, 3}
    assert len(picked) == 40


def test_stratified_sample_returns_everything_when_n_exceeds_population():
    rows = [{"id": i, "s": i % 2} for i in range(6)]
    picked = sample_mod.stratified_sample(rows, lambda r: r["s"], n=99, seed=1)
    assert len(picked) == 6


def test_stratified_sample_allocates_proportionally():
    rows = [{"id": i, "s": "big"} for i in range(90)]
    rows += [{"id": 100 + i, "s": "small"} for i in range(10)]
    picked = sample_mod.stratified_sample(rows, lambda r: r["s"], n=20, seed=3)
    counts = collections.Counter(r["s"] for r in picked)
    assert counts["big"] > counts["small"]
    assert counts["small"] >= 1
```

Add `import collections` to the test file's imports.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -k sample -v
```

Expected: collection error — `scripts/zendesk_probe_sample.py` does not exist.

- [ ] **Step 3: Write the sample builder**

Create `scripts/zendesk_probe_sample.py`:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""Partition probe: build the hand-labeling sample.

Draws a deterministic stratified sample from the partition-probe pool (the
uncategorized tickets plus every ticket whose first agent reply reads like a
permission grant), stratified across academic year and region proxy so no
year or city dominates the base rate.

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
    public = [c for c in ticket["comments"] if c["is_public"]]
    return public[1]["plain_body"] if len(public) >= 2 else ""


def main() -> int:
    corpus = load_corpus()

    pool = [
        t
        for t in corpus
        if t["category"] is None or matches_grant_lexicon(first_public_reply_body(t))
    ]

    picked = stratified_sample(
        pool,
        lambda t: (t["academic_year"], t["group_id"]),
        n=SAMPLE_SIZE,
        seed=SEED,
    )
    picked.sort(key=lambda t: t["created_at"])

    with (SCRATCH / "partition_sample.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "ticket_id", "academic_year", "group_id", "category", "subject",
                "request_excerpt", "reply_excerpt",
                "label", "artifact_name", "one_line_fix",
            ]
        )
        for t in picked:
            def clean(s: str, limit: int) -> str:
                return s[:limit].replace("\t", " ").replace("\n", " ")

            writer.writerow(
                [
                    t["ticket_id"], t["academic_year"], t["group_id"],
                    t["category"] or "(none)",
                    clean(t["subject"], 120),
                    clean(t["description"], 400),
                    clean(first_public_reply_body(t), 400),
                    "", "", "",
                ]
            )

    print(f"pool: {len(pool)} tickets ({len(corpus)} in corpus)")
    print(f"sample: {len(picked)} rows in partition_sample.tsv")
    print("\nLabel each row: self_inflicted | genuine | vendor_or_user_error")
    print("Choosing self_inflicted REQUIRES artifact_name and one_line_fix.")
    print("Kill criterion: under 20% self_inflicted in the uncategorized subset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run pytest tests/test_zendesk_probes.py -v
```

Expected: 22 passed.

- [ ] **Step 5: Run the sample builder**

Run:

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && uv run scripts/zendesk_probe_sample.py
```

Expected: a pool larger than 581 (the uncategorized tickets plus grant-lexicon
matches) and exactly 150 worksheet rows spanning both academic years and both
group ids.

Then label by hand. Budget roughly a day. Fill `label` for every row; when the
label is `self_inflicted`, `artifact_name` and `one_line_fix` are mandatory — a
row without both is not a defect claim, it is a hunch, and it gets relabelled
`genuine`.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && git add scripts/zendesk_probe_sample.py tests/test_zendesk_probes.py && git commit -m "feat: add Zendesk partition probe sample builder

Refs #4739"
```

---

### Task 5: Gate evaluation

**Files:**

- Modify: `scripts/CLAUDE.md`
- Create: `.claude/scratch/zendesk/gate-findings.md` (not committed — contains
  PII)

**Interfaces:**

- Consumes: the three completed worksheets from Tasks 2, 3, and 4.
- Produces: a scrubbed findings comment on issue #4739 and a go/no-go decision
  per probe.

- [ ] **Step 1: Compute the three rates**

From `partition_sample.tsv`, restricted to rows where `category` is `(none)`:
self-inflicted count divided by total. From the completed `slug_worksheet.tsv`:
sort slugs by frequency, take the cumulative count until it passes half the
`pasted_value` plus `attached_file` volume, and record how many slugs that took.
From `seasonality_worksheet.tsv`: the largest `same_ask_group` present in both
academic years within a single cell.

- [ ] **Step 2: Write both findings files**

Write two files, and keep the split deliberate:

- `.claude/scratch/zendesk/gate-findings.md` — the three rates, the verdict per
  kill criterion, and real ticket examples supporting each verdict. Holds PII.
  Never leaves the machine.
- `.claude/scratch/zendesk/gate-summary.md` — the scrubbed version posted in the
  next step. Rates, counts, verdicts, and artifact names only. No ticket text,
  no student or staff identifiers, and no ticket ids paired with a description
  of their content.

- [ ] **Step 3: Post the scrubbed summary to the issue**

Post `gate-summary.md`, not `gate-findings.md`. Re-read it immediately before
posting and confirm it carries no ticket text.

```bash
gh api -X POST repos/TEAMSchools/teamster/issues/4739/comments -F body=@.claude/scratch/zendesk/gate-summary.md
```

- [ ] **Step 4: Update the script catalog**

Add four rows to the `scripts/CLAUDE.md` catalog table:

| Script                         | Purpose                                                                                                                                                         |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `zendesk_extract_corpus.py`    | Extract the Zendesk Data-queue corpus (groups 21474460 + 31319068, two school years) to `.claude/scratch/zendesk/corpus.jsonl`; `--verify` asserts known counts |
| `zendesk_probe_seasonality.py` | Seasonality probe: category by week-offset-from-first-instructional-day, two-year-consistent cells, hand-tag worksheet                                          |
| `zendesk_probe_reply_shape.py` | Reply-shape probe: classify first agent replies, emit slug-assignment worksheet                                                                                 |
| `zendesk_probe_sample.py`      | Partition probe: deterministic stratified sample for hand-labeling self-inflicted versus genuine                                                                |

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/anthonygwalters/docs/claude-zendesk-data-queue-analysis && git add scripts/CLAUDE.md && git commit -m "docs: catalog the Zendesk opening-week probe scripts

Refs #4739"
```

---

## Execution tiering

What each step should run on. The largest saving is not model choice — it is the
work that needs no model at all.

| Tier                 | Work                                                                                                                                                                                                                 | Rationale                                                                                                                        |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 0, no model** | All of Tasks 1–4: the SQL, the date arithmetic, the shape regex, the sampler, the seasonality histogram. Later: recurrence counts, grants-per-view, the Dagster timing join, commit-within-14-days.                  | These are joins, counts, and pure functions. Running a model over them is waste, and they are unit-tested instead.               |
| **Tier 1, `haiku`**  | Batch pre-labeling to speed the human up: draft `same_ask_group` suggestions, draft slugs, pre-fill `artifact_name` guesses. Later: resolving-verb tagging over ~4,130 replies, scoring the 62 Help Center articles. | Fixed label sets, short text, high volume. Batch 20–50 items per call and force structured output. Omit the effort parameter.    |
| **Tier 2, `sonnet`** | Final slug assignment where cross-row consistency matters; sub-typing within large categories.                                                                                                                       | Open vocabulary, and consistency across the set is the deliverable.                                                              |
| **Tier 3, human**    | The `label` column in `partition_sample.tsv`.                                                                                                                                                                        | The base rate is measured against a pre-committed kill criterion. A model producing it means measuring the model, not the queue. |

**The asymmetry rule.** Cheap models widen the candidate pool (high recall);
humans and expensive models narrow it (high precision). Never the reverse — a
cheap model over-labeling `self_inflicted` is precisely the elasticity failure
the spec's risk section warns about.

**Scale.** The corpus is 16,819 comments at roughly 150 tokens each — about 2.5M
tokens to read everything once. Restricting full-corpus passes to first replies
only cuts that to ~4,130 items and roughly 0.5M.

Note: the `Agent` tool accepts `model` but not `effort`; effort is only settable
on Workflow `agent()`.

---

## After the gate

This plan deliberately stops at the gate. Depending on which criteria survive:

- **Partition probe passes** — a second plan covers Phase 0 at scale: artifact
  resolution against dbt, Cube, Tableau, and Dagster inventories; the two
  text-free joins; defect backlog assembly and hour pricing.
- **Reply-shape probe passes** — the normalization module (the spec's
  load-bearing step, with its 30-sample validation gate) and MinHash clustering.
- **Seasonality probe fails** — fall back to its stronger child: multiply
  forecast volume by median resolve time to build a load calendar for scheduling
  the team's own project work, deploy freezes, and coverage. All of the
  forecast's value, none of the speculative build.

If all three fail, that is a real finding and the report says so. The spec's
framing survives it: the queue would then be genuine, heterogeneous demand, and
the honest recommendation is to staff it rather than automate it.
