# DON'T PANIC

Nothing is irreparably broken. Follow these steps, and you'll be back on your way towards fulfilling
data analysis.

## Dagster

Dagster is our data orchestrator. Every ETL step takes place here.

[Dagster Cloud](https://kipptaf.dagster.cloud/) is a hosted front-end for our Dagster servers where
you can observe and run integration jobs.

Dagster hosts multiple "code locations", one for each of our business units, including a separate
one for our CMO:

- kipptaf
- kippnewark
- kippcamden
- kippmiami

Each code location hosts and runs the code and configurations for each respective business unit.
Behind-the-scenes, these are containers run on Google Cloud Kubernetes. Each code location has it's
own respective jobs, schedules, sensors, and assets.

## dbt & Github

Before you merge:

1. Ensure dbt build runs successfully on your branch
2. Format your SQL changes in dbt
3. Ensure the Dagster build action runs successfully

## Google Cloud Platform

## Fivetran & Airbyte

## Chores

### Check `#dagster-alerts`. If there is a run failure notification

1.  Click on the link to the failed run.
2.  Determine whether the failure is a framework error or a programming error. Typically, it's a
    famework error. a. framework error: re-execute the run "From Failure" b. programming error:
    examine the run logs and determine the cause. Fix via pull request - Python: focus on the
    traceback in the `STEP_FAILURE` log - dbt: go to "Raw compute logs" and find the dbt error to
    fix

          ![image](https://github.com/TEAMSchools/teamster/assets/5003326/63b560bc-75e4-4346-86c5-fe3791ea202b)
