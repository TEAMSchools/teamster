import io
import json

import fastavro
import py_avro_schema
from dagster_shared import check

from teamster.libraries.finalsite.api.schema import Contact

PAS_OPTIONS = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


def test_custom_attribute_number_value_writes():
    # Finalsite number fields (e.g. inquiry_student_age_num) return a float;
    # the IO manager writes with this same fastavro call
    schema = json.loads(py_avro_schema.generate(py_type=Contact, options=PAS_OPTIONS))

    record = {
        "custom_attributes": [
            {"field_name": "inquiry_student_age_num", "value": 9.0},
            # a whole number may arrive as a JSON int; bool must stay boolean
            {"field_name": "inquiry_student_age_num", "value": 9},
            {"field_name": "is_parent2", "value": True},
            {"field_name": "school_1_ss", "value": "Other"},
        ]
    }

    fo = io.BytesIO()
    fastavro.writer(fo=fo, schema=fastavro.parse_schema(schema), records=[record])
    fo.seek(0)

    written = check.inst(next(fastavro.reader(fo)), dict)
    values = [a["value"] for a in written["custom_attributes"]]

    assert values == [9.0, 9.0, True, "Other"]
    assert values[2] is True


def test_us_citizen_union_writes():
    # us_citizen's type is unconfirmed; a bool must not be written as a string
    schema = json.loads(py_avro_schema.generate(py_type=Contact, options=PAS_OPTIONS))

    records = [{"us_citizen": None}, {"us_citizen": True}, {"us_citizen": "Yes"}]

    fo = io.BytesIO()
    fastavro.writer(fo=fo, schema=fastavro.parse_schema(schema), records=records)
    fo.seek(0)

    values = [check.inst(r, dict)["us_citizen"] for r in fastavro.reader(fo)]

    assert values == [None, True, "Yes"]
    assert values[1] is True
