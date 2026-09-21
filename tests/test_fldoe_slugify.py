"""The FAST standards columns gained a leading ordinal in 2026-27 (see #5283).

`slugify` applies `replacements` as plain string substitutions, so a shorter key
that prefixes a longer one wins and corrupts it: `1. ` rewrites the head of
`11. Category` and yields `1category_1`. `dict_reader_to_records` sorts longest
key first to stop that, and this pins the result against the real schema -- the
failure is silent otherwise, since the column just lands somewhere nothing reads.

Driven through `dict_reader_to_records` rather than `slugify` on purpose: the sort
that makes the mapping correct lives there, so calling `slugify` direct would pass
while production broke.
"""

import csv
import io

from teamster.code_locations.kippmiami.fldoe.assets import (
    FAST_ORDINAL_STRIP,
    FAST_STANDARDS_REPLACEMENTS,
)
from teamster.code_locations.kippmiami.fldoe.schema import FAST_SCHEMA
from teamster.core.utils.functions import dict_reader_to_records

# Spelled out here rather than imported from `assets.py` on purpose. The test
# states the expected label set independently, so renaming a label in production
# fails this test instead of silently redefining what the test asserts.
STANDARDS_LABELS = [
    ("Category", "category"),
    ("Benchmark", "benchmark"),
    ("Points Earned", "points_earned"),
    ("Points Possible", "points_possible"),
]

# 3 of the 21 `N. <Prose> Performance` headers: the longest, one carrying an
# ampersand, and one whose ordinal a sibling grade reuses for a different standard.
PERFORMANCE_HEADERS = [
    (
        "4. Geometric Reasoning, Measurement, and Data Analysis and Probability"
        " Performance",
        "geometric_reasoning_measurement_and_data_analysis_and_probability_performance",
    ),
    (
        "3. Reading Across Genres & Vocabulary Performance",
        "reading_across_genres_vocabulary_performance",
    ),
    (
        "3. Geometric Reasoning Performance",
        "geometric_reasoning_performance",
    ),
]


def _slugify_headers(headers: list[str]) -> list[str]:
    # csv.writer, not ",".join -- several headers contain a comma of their own.
    buffer = io.StringIO()
    csv.writer(buffer).writerow(headers)

    dict_reader = csv.DictReader(io.StringIO(buffer.getvalue()))

    dict_reader_to_records(
        dict_reader=dict_reader,
        slugify_replacements=[*FAST_STANDARDS_REPLACEMENTS, *FAST_ORDINAL_STRIP],
    )

    return list(dict_reader.fieldnames or [])


def test_every_standards_ordinal_maps_onto_an_existing_schema_field() -> None:
    """Ordinal 11 is the regression case: `1. ` is a substring of `11. `."""
    schema_fields = {field["name"] for field in FAST_SCHEMA["fields"]}

    headers = [
        f"{ordinal}. {label}"
        for ordinal in range(1, 45)
        for label, _ in STANDARDS_LABELS
    ]
    expected = [
        f"{slug}_{ordinal}" for ordinal in range(1, 45) for _, slug in STANDARDS_LABELS
    ]

    assert _slugify_headers(headers) == expected
    assert set(expected) <= schema_fields


def test_performance_headers_lose_only_the_leading_ordinal() -> None:
    """The ordinal strip must not eat the standards ordinals alongside it."""
    schema_fields = {field["name"] for field in FAST_SCHEMA["fields"]}

    headers = [header for header, _ in PERFORMANCE_HEADERS]
    expected = [name for _, name in PERFORMANCE_HEADERS]

    assert _slugify_headers(headers) == expected
    assert set(expected) <= schema_fields
