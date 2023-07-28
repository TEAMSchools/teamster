import os
import pathlib

from dagster import DagsterInstance

dagster_home_path = pathlib.Path("/workspaces/teamster/.dagster/home")

dagster_home_path.mkdir(parents=True, exist_ok=True)

os.environ["DAGSTER_HOME"] = str(dagster_home_path)

instance = DagsterInstance.get()

print()
