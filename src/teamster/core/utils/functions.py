def get_avro_type(value):
    if isinstance(value, bool):
        return ["boolean"]
    elif isinstance(value, int):
        return ["int", "long"]
    elif isinstance(value, float):
        return ["float", "double"]
    elif isinstance(value, bytes):
        return ["bytes"]
    elif isinstance(value, list):
        return infer_avro_schema_fields(value)
    elif isinstance(value, dict):
        return infer_avro_schema_fields([value])
    elif isinstance(value, str):
        return ["string"]


def infer_avro_schema_fields(list_of_dicts):
    all_keys = set().union(*(d.keys() for d in list_of_dicts))

    types = {}
    while all_keys:
        d = next(iter(list_of_dicts))

        for k in all_keys.copy():
            v = d.get(k)
            print(k, v)

            avro_type = get_avro_type(v)
            if avro_type:
                types[k] = avro_type
                all_keys.remove(k)

    fields = []
    for k, v in types.items():
        v.insert(0, "null")
        fields.append({"name": k, "type": v})

    return fields
