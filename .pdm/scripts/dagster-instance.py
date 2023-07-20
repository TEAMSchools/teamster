import os
import pathlib

from dagster import DagsterInstance

dagster_home_path = pathlib.Path("/workspaces/teamster/.dagster/home")

dagster_home_path.mkdir(parents=True, exist_ok=True)

os.environ["DAGSTER_HOME"] = str(dagster_home_path)

instance = DagsterInstance.get()

for pk in ["2023-05-18|Current_SchedPeriod", "2023-05-03|Previous_SchedPeriod"]:
    instance.delete_dynamic_partition(
        partitions_def_name="kipptaf__adp__TimeDetails_date", partition_key=pk
    )
