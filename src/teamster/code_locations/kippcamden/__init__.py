from datetime import datetime
from zoneinfo import ZoneInfo

from dagster_dbt import DbtProject

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = ZoneInfo("America/New_York")

CURRENT_FISCAL_YEAR = FiscalYear(datetime=datetime.now(LOCAL_TIMEZONE), start_month=7)
DBT_PROJECT = DbtProject(project_dir=f"src/dbt/{CODE_LOCATION}")
