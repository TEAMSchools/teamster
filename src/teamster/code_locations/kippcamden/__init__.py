import pendulum
from dagster_dbt import DbtProject
from pendulum import timezone

from teamster.core.utils.classes import FiscalYear

CODE_LOCATION = "kippcamden"
LOCAL_TIMEZONE = timezone("America/New_York")

CURRENT_FISCAL_YEAR = FiscalYear(datetime=pendulum.today(LOCAL_TIMEZONE), start_month=7)
DBT_PROJECT = DbtProject(project_dir=f"src/dbt/{CODE_LOCATION}")
