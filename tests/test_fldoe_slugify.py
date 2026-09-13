"""The FAST standards columns gained a leading ordinal in 2026-27 (see #5283).

`slugify` applies `replacements` as plain string substitutions in list order, so
the ordinals have to be replaced from highest to lowest. Ascending order rewrites
the `1. ` inside `11. Category` first and yields `1category_1`. That failure is
silent -- the column simply lands somewhere nothing reads -- so it is pinned here.
"""

import pytest
from slugify import slugify

from teamster.code_locations.kippmiami.fldoe.assets import FAST_STANDARDS_REPLACEMENTS
from teamster.code_locations.kippmiami.fldoe.schema import FAST_SCHEMA

STANDARDS_LABELS = [
    ("Category", "category"),
    ("Benchmark", "benchmark"),
    ("Points Earned", "points_earned"),
    ("Points Possible", "points_possible"),
]


def _slug(text: str) -> str:
    return slugify(text=text, separator="_", replacements=FAST_STANDARDS_REPLACEMENTS)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("1. Category", "category_1"),
        ("4. Points Earned", "points_earned_4"),
        ("1. Points Possible", "points_possible_1"),
        ("11. Category", "category_11"),
        ("14. Benchmark", "benchmark_14"),
        ("40. Points Earned", "points_earned_40"),
    ],
)
def test_ordinal_headers_slugify_to_schema_names(header: str, expected: str) -> None:
    assert _slug(header) == expected


def test_every_ordinal_maps_onto_an_existing_schema_field() -> None:
    schema_fields = {field["name"] for field in FAST_SCHEMA["fields"]}

    for ordinal in range(1, 45):
        for label, slug in STANDARDS_LABELS:
            name = _slug(f"{ordinal}. {label}")

            assert name == f"{slug}_{ordinal}"
            assert name in schema_fields
