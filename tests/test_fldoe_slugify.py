"""The FAST standards columns gained a leading ordinal in 2026-27 (see #5283).

`slugify` applies `replacements` as plain string substitutions in list order, so
the ordinals have to be replaced from highest to lowest. Ascending order rewrites
the `1. ` inside `11. Category` first and yields `1category_1`. That failure is
silent -- the column simply lands somewhere nothing reads -- so it is pinned here.
"""

from slugify import slugify

from teamster.code_locations.kippmiami.fldoe.assets import FAST_STANDARDS_REPLACEMENTS
from teamster.code_locations.kippmiami.fldoe.schema import FAST_SCHEMA

# Spelled out here rather than imported from `assets.py` on purpose. The test
# states the expected label set independently, so renaming a label in production
# fails this test instead of silently redefining what the test asserts.
STANDARDS_LABELS = [
    ("Category", "category"),
    ("Benchmark", "benchmark"),
    ("Points Earned", "points_earned"),
    ("Points Possible", "points_possible"),
]


def _slug(text: str) -> str:
    return slugify(text=text, separator="_", replacements=FAST_STANDARDS_REPLACEMENTS)


def test_every_ordinal_maps_onto_an_existing_schema_field() -> None:
    """Ordinal 11 is the regression case: `1. ` is a substring of `11. `."""
    schema_fields = {field["name"] for field in FAST_SCHEMA["fields"]}

    for ordinal in range(1, 45):
        for label, slug in STANDARDS_LABELS:
            name = _slug(f"{ordinal}. {label}")

            assert name == f"{slug}_{ordinal}"
            assert name in schema_fields
