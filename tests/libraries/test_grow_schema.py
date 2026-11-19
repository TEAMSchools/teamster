import io

import fastavro
import pytest

from teamster.code_locations.kipptaf.level_data.grow.schema import ASSET_SCHEMA


@pytest.mark.parametrize("schema_key", ["generic-tags/meetingtypes", "meetings"])
@pytest.mark.parametrize("content", [[], ["v"]])
def test_checkbox_additional_field_writes(schema_key, content):
    # Grow sends a checkbox field's content as a list, with its options alongside
    record = {
        "_id": "a",
        "additionalFields": [
            {
                "_id": "b",
                "type": "checkbox",
                "content": content,
                "checkboxOptions": [{"value": "v", "label": "l", "description": ""}],
            }
        ],
    }

    fastavro.writer(
        fo=io.BytesIO(),
        schema=fastavro.parse_schema(ASSET_SCHEMA[schema_key]),
        records=[record],
    )
