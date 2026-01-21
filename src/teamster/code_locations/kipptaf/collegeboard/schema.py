import json

import py_avro_schema

from teamster.libraries.collegeboard.schema import AP, PSAT, SAT

options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

AP_SCHEMA = json.loads(py_avro_schema.generate(py_type=AP, options=options))

PSAT_SCHEMA = json.loads(py_avro_schema.generate(py_type=PSAT, options=options))

SAT_SCHEMA = json.loads(py_avro_schema.generate(py_type=SAT, options=options))
