"""import json
import pathlib

import fastavro
import py_avro_schema

from teamster.code_locations.kipptaf.schoolmint.grow.schema import assignments_record

fp = pathlib.Path("env/schoolmint/grow/assignments/data.avro")

generated_schema = py_avro_schema.generate(py_type=assignments_record)

reader_schema = fastavro.parse_schema(json.loads(generated_schema))

avro_reader = fastavro.reader(fo=fp.open(mode="rb"))

record = next(avro_reader)

print(record)
"""
