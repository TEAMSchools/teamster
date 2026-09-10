import json

import py_avro_schema

from teamster.libraries.cambium.schema import NJGPA

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

NJGPA_SCHEMA = json.loads(py_avro_schema.generate(py_type=NJGPA, options=pas_options))
