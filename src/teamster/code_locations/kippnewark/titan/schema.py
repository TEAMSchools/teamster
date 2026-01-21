import json

import py_avro_schema

from teamster.libraries.titan.schema import PersonData

PERSON_DATA_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=PersonData,
        options=(
            py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
        ),
    )
)
