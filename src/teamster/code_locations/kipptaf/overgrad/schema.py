import json

import py_avro_schema

from teamster.libraries.overgrad.schema import University

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

UNIVERSITY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=University, options=pas_options)
)
