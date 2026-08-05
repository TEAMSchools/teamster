"""Unit tests for the Zendesk opening-week probe scripts.

Scripts under `scripts/` are standalone PEP 723 executables with no
`__init__.py`, so they are loaded by path. Registration in `sys.modules`
before `exec_module` is required for dataclass resolution.

Design reference:
    docs/superpowers/plans/2026-08-05-zendesk-data-queue-opening-week.md
"""

from __future__ import annotations

import collections
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
seasonality = load_script("zendesk_probe_seasonality")
reply_shape = load_script("zendesk_probe_reply_shape")
sample_mod = load_script("zendesk_probe_sample")


# --- zendesk_extract_corpus -------------------------------------------------


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


# --- zendesk_probe_seasonality ----------------------------------------------


def _row(category: str | None, year: int, offset: int) -> dict:
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


# --- zendesk_probe_reply_shape ----------------------------------------------


def test_link_wins_over_number():
    text = "Here are your 47 students: https://tableau.kipptaf.org/#/views/Foo"
    assert reply_shape.classify_reply_shape(text, 0) == "existing_link"


def test_attachment_wins_over_number_when_no_link():
    assert reply_shape.classify_reply_shape("Attached, 47 rows.", 1) == "attached_file"


def test_bare_number_is_a_pasted_value():
    assert reply_shape.classify_reply_shape("It's 47 as of today.", 0) == "pasted_value"
    assert (
        reply_shape.classify_reply_shape("Total: 1,204 students", 0) == "pasted_value"
    )


def test_dates_and_ticket_refs_are_not_pasted_values():
    assert (
        reply_shape.classify_reply_shape("Fixed on 2025-09-04, see ticket #12345.", 0)
        == "not_a_data_ask"
    )


def test_prose_with_no_number_is_not_a_data_ask():
    assert (
        reply_shape.classify_reply_shape(
            "You'll need to ask the school ops manager for that.", 0
        )
        == "not_a_data_ask"
    )


def test_empty_reply_is_not_a_data_ask():
    assert reply_shape.classify_reply_shape("", 0) == "not_a_data_ask"


def test_html_url_flag_forces_existing_link():
    # plain_body drops anchor hrefs, so the flag from html_body must win.
    assert (
        reply_shape.classify_reply_shape("Here's the dashboard.", 0, True)
        == "existing_link"
    )


def test_first_agent_reply_skips_the_requester_opening_comment():
    ticket = {
        "requester_id": "111",
        "comments": [
            {"seq": 1, "is_public": True, "author_id": "111", "plain_body": "Pull?"},
            {"seq": 2, "is_public": False, "author_id": "999", "plain_body": "note"},
            {"seq": 3, "is_public": True, "author_id": "999", "plain_body": "Here."},
        ],
    }
    assert reply_shape.first_agent_reply(ticket)["seq"] == 3


def test_first_agent_reply_skips_a_repeated_requester_message():
    # The requester follows up before anyone answers; comment 2 is still theirs.
    ticket = {
        "requester_id": "111",
        "comments": [
            {"seq": 1, "is_public": True, "author_id": "111", "plain_body": "Pull?"},
            {"seq": 2, "is_public": True, "author_id": "111", "plain_body": "Oops, 0"},
            {"seq": 3, "is_public": True, "author_id": "999", "plain_body": "Here."},
        ],
    }
    assert reply_shape.first_agent_reply(ticket)["seq"] == 3


def test_first_agent_reply_is_none_when_the_requester_is_the_only_voice():
    ticket = {
        "requester_id": "111",
        "comments": [
            {"seq": 1, "is_public": True, "author_id": "111", "plain_body": "Help"},
            {"seq": 2, "is_public": True, "author_id": "111", "plain_body": "Still?"},
        ],
    }
    assert reply_shape.first_agent_reply(ticket) is None


def test_first_agent_reply_falls_back_to_position_without_a_requester_id():
    ticket = {
        "comments": [
            {"seq": 1, "is_public": True, "plain_body": "Pull?"},
            {"seq": 2, "is_public": True, "plain_body": "Here."},
        ]
    }
    assert reply_shape.first_agent_reply(ticket)["seq"] == 2


def test_sample_reply_body_also_skips_the_requester():
    ticket = {
        "requester_id": "111",
        "comments": [
            {"is_public": True, "author_id": "111", "plain_body": "need access"},
            {"is_public": True, "author_id": "999", "plain_body": "granted access"},
        ],
    }
    assert sample_mod.first_public_reply_body(ticket) == "granted access"


# --- zendesk_probe_sample ---------------------------------------------------


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
