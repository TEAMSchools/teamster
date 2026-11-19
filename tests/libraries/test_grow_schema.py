import io

import fastavro

from teamster.code_locations.kipptaf.level_data.grow.schema import ASSET_SCHEMA


def test_meetingtype_checkbox_additional_field_writes():
    # Grow sends a checkbox field's content as a list, with its options alongside
    record = {
        "_id": "a",
        "additionalFields": [
            {
                "_id": "b",
                "type": "checkbox",
                "content": [],
                "checkboxOptions": [{"value": "v", "label": "l", "description": ""}],
            }
        ],
    }

    fastavro.writer(
        fo=io.BytesIO(),
        schema=fastavro.parse_schema(ASSET_SCHEMA["generic-tags/meetingtypes"]),
        records=[record],
    )
