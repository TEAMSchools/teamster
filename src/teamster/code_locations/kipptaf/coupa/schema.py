import json

import py_avro_schema

from teamster.libraries.coupa.schema import Address, BusinessGroup, User

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

ADDRESS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Address, options=pas_options)
)

BUSINESS_GROUP_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=BusinessGroup, options=pas_options)
)

USER_SCHEMA = json.loads(py_avro_schema.generate(py_type=User, options=pas_options))
