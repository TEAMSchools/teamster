from dagster import StaticPartitionsDefinition


def get_finalsite_school_year_partition_keys(start_year: int, end_year: int):
    partition_keys = [
        f"{school_year}_{str(school_year + 1)[-2:]}"
        for school_year in range(start_year, end_year + 1)
    ]

    return StaticPartitionsDefinition(partition_keys=partition_keys)
