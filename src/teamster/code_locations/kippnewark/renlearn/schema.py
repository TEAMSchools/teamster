import json

import py_avro_schema

from teamster.libraries.renlearn.schema import AcceleratedReader, Star

ACCELERATED_READER_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=AcceleratedReader)
)

STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=Star))
