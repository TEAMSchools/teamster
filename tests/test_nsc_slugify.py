"""The StudentTracker "2-Year / 4-Year" header must land on a schema field.

`slugify` applies `replacements` before it swaps `-` for the `_` separator, so a
key written in the slugified form never matches. The column then drops out of
the Avro file with no error, and only the `avro_schema_valid` check notices.
"""

import csv
import io

from teamster.code_locations.kipptaf.nsc.assets import STUDENT_TRACKER_REPLACEMENTS
from teamster.code_locations.kipptaf.nsc.schema import STUDENT_TRACKER_SCHEMA
from teamster.core.utils.functions import dict_reader_to_records

HEADER_SPELLINGS = ["2-Year / 4-Year", "2-Year/4-Year", "2 Year / 4 Year"]


def test_two_year_four_year_header_maps_onto_the_schema_field() -> None:
    schema_fields = {field["name"] for field in STUDENT_TRACKER_SCHEMA["fields"]}

    for header in HEADER_SPELLINGS:
        dict_reader = csv.DictReader(io.StringIO(f"{header},College Name\nx,y\n"))

        records = dict_reader_to_records(
            dict_reader=dict_reader, slugify_replacements=STUDENT_TRACKER_REPLACEMENTS
        )

        assert set(records[0]) <= schema_fields, header
        assert records[0]["two_year_four_year"] == "x", header
