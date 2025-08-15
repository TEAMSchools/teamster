import json

import py_avro_schema

from teamster.libraries.powerschool.sis.sftp.schema import Schools

options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

SCHOOLS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Schools, options=options))

SCHEMAS = {
    "schools": SCHOOLS_SCHEMA,
}
