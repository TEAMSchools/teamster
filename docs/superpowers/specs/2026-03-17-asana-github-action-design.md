# Design: Replace Zapier Asana/GitHub Integration with GitHub Action

**Date:** 2026-03-17 **Status:** Approved

## Overview

Replace the existing Zapier integration that creates Asana tasks from new GitHub
issues and pull requests with a native GitHub Actions workflow. The new workflow
calls the Asana REST API directly via `actions/github-script` and requires no
third-party action dependencies.

## Scope

- Create Asana tasks when issues or pull requests are opened (or a draft PR
  becomes ready for review)
- Skip `dependabot[bot]` (the only bot actor that opens PRs/issues in this repo)
  and draft PRs
- No updates on close, reassignment, or any other lifecycle event — creation
  only

## Workflow Structure

**File:** `.github/workflows/asana-sync.yaml`

**Triggers:**

```yaml
on:
  issues:
    types: [opened]
  pull_request:
    types: [opened, ready_for_review]
```

**Job-level condition** (skip dependabot and draft PRs):

```yaml
jobs:
  create-asana-task:
    if: |
      github.actor != 'dependabot[bot]' &&
      !(github.event_name == 'pull_request' && github.event.pull_request.draft == true)
```

Note: when a PR transitions from draft to ready (`ready_for_review`),
`github.event.pull_request.draft` is `false` at the time the event fires, so
`ready_for_review` events always pass the draft check.

**Runs on:** `ubuntu-latest`

**Job-level permissions** (explicit reduction from defaults; GITHUB_TOKEN is
available to `github-script` but only used to read event context, not to call
the GitHub API):

```yaml
permissions:
  contents: none
  issues: read
  pull-requests: read
```

No checkout step is needed — the job only makes outbound API calls to Asana.

## Task Field Mapping

| Asana field   | Source                                                                                                          |
| ------------- | --------------------------------------------------------------------------------------------------------------- |
| `name`        | Issue or PR title                                                                                               |
| `notes`       | GitHub URL (no body text — body can be lengthy and the URL is sufficient)                                       |
| `assignee`    | Opener's GitHub login looked up in `USER_MAP`; key **omitted entirely** from payload if no match                |
| `memberships` | Project `1205971774138578` (hardcoded constant) + Backlog section ID (from `ASANA_BACKLOG_SECTION_ID` variable) |

The assignee is the opener. Further assignment happens manually in Asana.

## User Mapping

A `USER_MAP` JSON object is defined as an `env` variable in the workflow file,
mapping GitHub usernames to Asana user IDs:

```yaml
env:
  USER_MAP: '{"github-username": "asana-user-id", ...}'
```

Asana user IDs are not sensitive, so storing the map in the workflow file as
plaintext is intentional — it keeps the mapping visible and reviewable in source
control. The map is populated during setup by collecting the Asana user ID for
each team member.

If a GitHub login has no entry in the map, the `assignee` key is omitted from
the Asana API payload entirely (not set to `null`), and the task is created
without an assignee.

## Asana API Interaction

A single `actions/github-script` step makes one `POST` request:

```
POST https://app.asana.com/api/1.0/tasks
Authorization: Bearer <ASANA_PAT>
```

Payload (assignee key omitted when no user match):

```json
{
  "data": {
    "name": "<title>",
    "notes": "<github url>",
    "assignee": "<asana user id>",
    "memberships": [
      { "project": "1205971774138578", "section": "<ASANA_BACKLOG_SECTION_ID>" }
    ]
  }
}
```

The Asana project ID (`1205971774138578`) is hardcoded in the workflow as a
constant. The Backlog section ID is stored as a GitHub Actions variable
(`ASANA_BACKLOG_SECTION_ID`) since it requires a one-time lookup.

If `ASANA_BACKLOG_SECTION_ID` is unset, the Asana API will return an error,
which will fail the step — no pre-flight guard is needed. A non-2xx response
from Asana always fails the step, surfacing the error in the Actions tab. No
retry logic — manual workflow re-run is sufficient for one-off failures.

## Secrets & Variables

| Name                       | Type                  | How to obtain                                                                        |
| -------------------------- | --------------------- | ------------------------------------------------------------------------------------ |
| `ASANA_PAT`                | Secret                | Asana → My Profile → Apps → Personal Access Tokens                                   |
| `ASANA_BACKLOG_SECTION_ID` | Variable (not secret) | `GET https://app.asana.com/api/1.0/projects/1205971774138578/sections` using the PAT |

## Setup Checklist

1. Create Asana PAT and add as GitHub Actions secret `ASANA_PAT`
2. Retrieve the Backlog section ID and add as GitHub Actions variable
   `ASANA_BACKLOG_SECTION_ID`
3. Collect GitHub username → Asana user ID pairs for all team members and
   populate `USER_MAP` in the workflow file
4. Remove or disable the Zapier integration once the action is confirmed working

## Out of Scope

- Closing or updating Asana tasks when issues/PRs are closed or merged
- Syncing labels, milestones, or other GitHub metadata to Asana custom fields
- Bidirectional sync (Asana → GitHub)
- Excluding bot actors beyond `dependabot[bot]`
