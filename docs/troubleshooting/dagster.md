# Troubleshooting :: Dagster

## Check `#dagster-alerts`. If there is a run failure notification

1.  Click on the link to the failed run.
2.  Determine whether the failure is a framework error or a programming error. Typically, it's a
    famework error.

    - framework error: re-execute the run "From Failure"
    - programming error: examine the run logs and determine the cause. Fix via pull request
      - Python: focus on the traceback in the `STEP_FAILURE` log
      - dbt: go to "Raw compute logs" and find the dbt error to fix
        ![image](https://github.com/TEAMSchools/teamster/assets/5003326/63b560bc-75e4-4346-86c5-fe3791ea202b)
