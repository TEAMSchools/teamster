from dagster import build_resources

from teamster.core.resources import DEANSLIST_RESOURCE
from teamster.libraries.deanslist.resources import DeansListResource


def test_behavior_paginated():
    with build_resources(resources={"deanslist": DEANSLIST_RESOURCE}) as resources:
        deanslist: DeansListResource = resources.deanslist

    deanslist.list(
        api_version="v1",
        endpoint="behavior",
        school_id=124,
        params={
            "UpdatedSince": "2024-07-01",
            "StartDate": "2024-07-01",
            "EndDate": "2025-06-30",
        },
    )
