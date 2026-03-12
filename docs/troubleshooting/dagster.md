# Troubleshooting Dagster

!!! warning "DON'T PANIC! :fontawesome-solid-thumbs-up:"

## Pipeline failures

### Check #dagster-alerts

Check [#dagster-alerts](https://kippnj.slack.com/archives/C04A0KC1YSW) on Slack
for failed job run notifications. Most failures are transient framework errors
and can be retried. Failures that recur or follow a code change require
investigation and a fix via pull request.

### Diagnose the failure

1. Click the link to the failed run.
2. Determine whether it is a **framework error** or a **programming error**.

**Framework error** (most common) — infrastructure or transient issue unrelated
to the code:

- Re-execute the run **From Failure** using the button in the Dagster Cloud UI.

**Programming error** — a bug in the asset code or dbt model:

- **Python assets**: find the `STEP_FAILURE` event in the run logs and read the
  traceback.
- **dbt assets**: go to **Raw compute logs** and search for the dbt error
  message.

### Failed or missing partitions

Check the
[Asset Health](https://kipptaf.dagster.cloud/prod/overview/asset-health) page
for assets with failed materializations.

- **Unpartitioned asset**: click the asset, then click **Materialize**.
- **Partitioned asset**: go to the **Partitions** tab, filter for **Failed**
  partitions, and materialize only those.

### "Unsynced" views

View assets may show as **Unsynced** in the Dagster UI after an upstream table
materializes. This is expected — see
[Automation Conditions](../reference/automation-conditions.md#the-unsynced-indicator)
for the explanation.
