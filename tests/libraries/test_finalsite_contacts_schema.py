import io
import json

import fastavro
import py_avro_schema

from teamster.libraries.finalsite.api.schema import Contact

PAS_OPTIONS = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


def test_custom_attribute_number_value_writes():
    # Finalsite number fields (e.g. inquiry_student_age_num) return a float;
    # the IO manager writes with this same fastavro call
    schema = json.loads(py_avro_schema.generate(py_type=Contact, options=PAS_OPTIONS))

    record = {
        "custom_attributes": [
            {"field_name": "inquiry_student_age_num", "value": 9.0},
            {"field_name": "school_1_ss", "value": "Other"},
        ]
    }

    fastavro.writer(
        fo=io.BytesIO(), schema=fastavro.parse_schema(schema), records=[record]
    )
