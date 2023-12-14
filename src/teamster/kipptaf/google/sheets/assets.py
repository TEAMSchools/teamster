import re

import pendulum
from dagster import DataVersion, observable_source_asset

from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.dbt.manifest import dbt_manifest


def build_google_sheets_asset(source_name, name, uri, range_name):
    re_match = re.match(
        pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
    )

    @observable_source_asset(
        key=[CODE_LOCATION, source_name, name],
        metadata={"sheet_id": re_match.group(1), "range_name": range_name},
        group_name="google_sheets",
    )
    def _asset():
        return DataVersion(str(pendulum.now().timestamp()))

    return _asset


google_sheets_assets = [
    build_google_sheets_asset(
        source_name=source["source_name"],
        name=source["name"].split("__")[-1],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in dbt_manifest["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]

_all = [
    google_sheets_assets,
]
