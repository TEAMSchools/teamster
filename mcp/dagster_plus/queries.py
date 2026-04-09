"""GraphQL query strings for the Dagster+ API."""

LIST_RUNS_QUERY = """
query ListRuns($filter: RunsFilter, $cursor: String, $limit: Int) {
  runsOrError(filter: $filter, cursor: $cursor, limit: $limit) {
    ... on Runs {
      results {
        id
        jobName
        status
        creationTime
        startTime
        endTime
        updateTime
        parentRunId
        rootRunId
        assetSelection { path }
        tags { key value }
        repositoryOrigin {
          repositoryName
          repositoryLocationName
        }
      }
    }
    ... on InvalidPipelineRunsFilterError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

RUN_BY_ID_QUERY = """
query GetRun($runId: ID!) {
  runOrError(runId: $runId) {
    ... on Run {
      id
      jobName
      status
      creationTime
      startTime
      endTime
      updateTime
      parentRunId
      rootRunId
      stepKeysToExecute
      assetSelection { path }
      tags { key value }
      stats {
        ... on RunStatsSnapshot {
          stepsSucceeded
          stepsFailed
          materializations
          expectations
        }
      }
      stepStats {
        stepKey
        status
        startTime
        endTime
        attempts { startTime endTime }
      }
      repositoryOrigin {
        repositoryName
        repositoryLocationName
      }
    }
    ... on RunNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

RUN_LOGS_QUERY = """
query GetRunLogs($runId: ID!, $afterCursor: String, $limit: Int) {
  logsForRun(runId: $runId, afterCursor: $afterCursor, limit: $limit) {
    ... on EventConnection {
      events {
        __typename
        ... on MessageEvent {
          message
          level
          stepKey
          timestamp
        }
        ... on ExecutionStepFailureEvent {
          stepKey
          error {
            message
            stack
            errorChain {
              error { message stack }
            }
          }
        }
        ... on RunFailureEvent {
          error {
            message
            stack
            errorChain {
              error { message stack }
            }
          }
        }
        ... on ExecutionStepStartEvent { stepKey }
        ... on ExecutionStepSuccessEvent { stepKey }
        ... on ExecutionStepSkippedEvent { stepKey }
        ... on ExecutionStepRestartEvent { stepKey }
        ... on ExecutionStepUpForRetryEvent {
          stepKey
          error { message stack }
        }
        ... on LogsCapturedEvent {
          logKey
          stepKeys
          externalUrl
        }
        ... on AssetMaterializationPlannedEvent {
          assetKey { path }
        }
        ... on MaterializationEvent {
          assetKey { path }
          label
          description
        }
        ... on EngineEvent {
          error { message stack }
        }
        ... on ResourceInitFailureEvent {
          stepKey
          error { message stack }
        }
      }
      cursor
      hasMore
    }
    ... on RunNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

COMPUTE_LOGS_QUERY = """
query GetComputeLogs($logKey: [String!]!, $cursor: String, $limit: Int) {
  capturedLogs(logKey: $logKey, cursor: $cursor, limit: $limit) {
    stdout
    stderr
    cursor
  }
}
"""

CAPTURED_LOGS_METADATA_QUERY = """
query GetCapturedLogsMetadata($logKey: [String!]!) {
  capturedLogsMetadata(logKey: $logKey) {
    stdoutDownloadUrl
    stdoutLocation
    stderrDownloadUrl
    stderrLocation
  }
}
"""

DAEMON_HEALTH_QUERY = """
query DaemonHealth {
  instance {
    daemonHealth {
      allDaemonStatuses {
        daemonType
        healthy
        id
        required
        lastHeartbeatTime
        lastHeartbeatErrors {
          message
          stack
          errorChain {
            error { message stack }
          }
        }
      }
    }
  }
}
"""

ASSET_MATERIALIZATIONS_QUERY = """
query GetAssetMaterializations($assetKey: AssetKeyInput!, $limit: Int, $partitions: [String!], $beforeTimestampMillis: String) {
  assetNodes(assetKeys: [$assetKey]) {
    assetKey { path }
    assetMaterializations(limit: $limit, partitions: $partitions, beforeTimestampMillis: $beforeTimestampMillis) {
      timestamp
      runId
      partition
      stepKey
      tags { key value }
      metadataEntries {
        label
        description
        ... on TextMetadataEntry { text }
        ... on UrlMetadataEntry { url }
        ... on FloatMetadataEntry { floatValue }
        ... on IntMetadataEntry { intValue }
        ... on BoolMetadataEntry { boolValue }
        ... on PathMetadataEntry { path }
        ... on JsonMetadataEntry { jsonString }
        ... on MarkdownMetadataEntry { mdStr }
      }
    }
  }
}
"""

ASSET_PARTITION_STATUSES_QUERY = """
query GetAssetPartitionStatuses($assetKey: AssetKeyInput!) {
  assetNodes(assetKeys: [$assetKey]) {
    assetKey { path }
    isPartitioned
    partitionStats {
      numMaterialized
      numMaterializing
      numPartitions
      numFailed
    }
    assetPartitionStatuses {
      ... on TimePartitionStatuses {
        ranges {
          status
          startKey
          endKey
          startTime
          endTime
        }
      }
      ... on DefaultPartitionStatuses {
        materializedPartitions
        failedPartitions
        unmaterializedPartitions
        materializingPartitions
      }
    }
  }
}
"""

ASSET_CHECK_EXECUTIONS_QUERY = """
query GetAssetCheckExecutions($assetKey: AssetKeyInput!, $checkName: String!, $limit: Int!, $cursor: String, $partition: String) {
  assetCheckExecutions(assetKey: $assetKey, checkName: $checkName, limit: $limit, cursor: $cursor, partition: $partition) {
    id
    runId
    status
    timestamp
    stepKey
    partition
    evaluation {
      success
      severity
      description
      targetMaterialization {
        timestamp
        runId
        storageId
      }
      metadataEntries {
        label
        description
        ... on TextMetadataEntry { text }
        ... on UrlMetadataEntry { url }
        ... on FloatMetadataEntry { floatValue }
        ... on IntMetadataEntry { intValue }
        ... on BoolMetadataEntry { boolValue }
        ... on JsonMetadataEntry { jsonString }
      }
    }
  }
}
"""

ASSET_CONDITION_EVALUATIONS_QUERY = """
query GetAssetConditionEvaluations($assetKey: AssetKeyInput!, $limit: Int!, $cursor: String) {
  assetConditionEvaluationRecordsOrError(assetKey: $assetKey, limit: $limit, cursor: $cursor) {
    ... on AssetConditionEvaluationRecords {
      records {
        evaluationId
        timestamp
        startTimestamp
        endTimestamp
        numRequested
        runIds
        rootUniqueId
        isLegacy
        assetKey { path }
        evaluationNodes {
          uniqueId
          userLabel
          expandedLabel
          startTimestamp
          endTimestamp
          numTrue
          numCandidates
          isPartitioned
          childUniqueIds
          operatorType
          sinceMetadata {
            triggerEvaluationId
            triggerTimestamp
            resetEvaluationId
            resetTimestamp
          }
        }
      }
    }
    ... on AutoMaterializeAssetEvaluationNeedsMigrationError {
      message
    }
  }
}
"""

TICK_HISTORY_QUERY = """
query GetTickHistory(
  $name: String!
  $repositoryName: String!
  $repositoryLocationName: String!
  $limit: Int
  $statuses: [InstigationTickStatus!]
  $afterTimestamp: Float
  $beforeTimestamp: Float
) {
  instigationStateOrError(instigationSelector: {
    name: $name
    repositoryName: $repositoryName
    repositoryLocationName: $repositoryLocationName
  }) {
    ... on InstigationState {
      name
      instigationType
      status
      nextTick { timestamp }
      ticks(limit: $limit, statuses: $statuses, afterTimestamp: $afterTimestamp, beforeTimestamp: $beforeTimestamp) {
        id
        tickId
        status
        timestamp
        endTimestamp
        runIds
        skipReason
        requestedAssetKeys { path }
        requestedAssetMaterializationCount
        error {
          message
          stack
          errorChain { error { message stack } }
        }
      }
    }
    ... on InstigationStateNotFoundError {
      name
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

CODE_LOCATIONS_QUERY = """
query ListCodeLocations {
  workspaceOrError {
    ... on Workspace {
      locationEntries {
        id
        name
        loadStatus
        updatedTimestamp
        displayMetadata { key value }
        locationOrLoadError {
          ... on RepositoryLocation {
            id
            name
            repositories {
              name
            }
          }
          ... on PythonError {
            message
            stack
          }
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

BACKFILLS_QUERY = """
query ListBackfills($status: BulkActionStatus, $cursor: String, $limit: Int, $filters: BulkActionsFilter) {
  partitionBackfillsOrError(status: $status, cursor: $cursor, limit: $limit, filters: $filters) {
    ... on PartitionBackfills {
      results {
        id
        status
        timestamp
        endTimestamp
        numPartitions
        isAssetBackfill
        assetSelection { path }
        partitionStatusCounts { runStatus count }
        error { message stack }
        user
        tags { key value }
        title
        hasCancelPermission
        hasResumePermission
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

BACKFILL_QUERY = """
query GetBackfill($backfillId: String!) {
  partitionBackfillOrError(backfillId: $backfillId) {
    ... on PartitionBackfill {
      id
      status
      timestamp
      endTimestamp
      numPartitions
      partitionNames
      isAssetBackfill
      assetSelection { path }
      partitionStatusCounts { runStatus count }
      error { message stack }
      user
      tags { key value }
      title
      description
      hasCancelPermission
      hasResumePermission
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

ASSET_HEALTH_QUERY = """
query AssetHealthQuery($assetKeys: [AssetKeyInput!]!) {
  assetsOrError(assetKeys: $assetKeys) {
    ... on AssetConnection {
      nodes {
        id
        key { path }
        latestMaterializationTimestamp
        latestFailedToMaterializeTimestamp
        freshnessStatusChangedTimestamp
        assetHealth {
          assetHealth
          materializationStatus
          materializationStatusMetadata {
            ... on AssetHealthMaterializationDegradedPartitionedMeta {
              numMissingPartitions
              numFailedPartitions
              totalNumPartitions
              latestFailedRunId
            }
            ... on AssetHealthMaterializationHealthyPartitionedMeta {
              numMissingPartitions
              totalNumPartitions
              latestRunId
            }
            ... on AssetHealthMaterializationDegradedNotPartitionedMeta {
              failedRunId
            }
          }
          assetChecksStatus
          assetChecksStatusMetadata {
            ... on AssetHealthCheckDegradedMeta {
              numFailedChecks
              numWarningChecks
              totalNumChecks
            }
            ... on AssetHealthCheckWarningMeta {
              numWarningChecks
              totalNumChecks
            }
            ... on AssetHealthCheckUnknownMeta {
              numNotExecutedChecks
              totalNumChecks
            }
          }
          freshnessStatus
          freshnessStatusMetadata {
            ... on AssetHealthFreshnessMeta {
              lastMaterializedTimestamp
            }
          }
        }
      }
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

ASSET_STALENESS_QUERY = """
query AssetStalenessQuery($assetKeys: [AssetKeyInput!]!) {
  assetNodes(assetKeys: $assetKeys) {
    id
    assetKey { path }
    staleStatus
    staleCauses {
      key { path }
      reason
      category
      dependency { path }
    }
  }
}
"""

ASSET_CATALOG_QUERY = """
query AssetCatalogQuery($cursor: String, $limit: Int!, $prefix: [String!]) {
  assetsOrError(cursor: $cursor, limit: $limit, prefix: $prefix) {
    ... on AssetConnection {
      nodes {
        id
        key { path }
        definition {
          id
          groupName
          computeKind
          isPartitioned
          isMaterializable
          isObservable
          hasAssetChecks
          description
          jobNames
          owners {
            ... on UserAssetOwner { email }
            ... on TeamAssetOwner { team }
          }
          tags { key value }
          automationCondition { label }
          repository {
            name
            location { name }
          }
        }
      }
      cursor
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

LAUNCH_RUN_MUTATION = """
mutation LaunchRun($executionParams: ExecutionParams!) {
  launchRun(executionParams: $executionParams) {
    __typename
    ... on LaunchRunSuccess {
      run {
        id
        jobName
        status
        creationTime
        assetSelection { path }
        tags { key value }
        repositoryOrigin {
          repositoryName
          repositoryLocationName
        }
      }
    }
    ... on PythonError { message stack }
    ... on InvalidSubsetError { message }
    ... on PipelineNotFoundError { message }
    ... on RunConfigValidationInvalid {
      errors { message reason }
    }
    ... on RunConflict { message }
    ... on UnauthorizedError { message }
    ... on ConflictingExecutionParamsError { message }
    ... on PresetNotFoundError { message }
    ... on NoModeProvidedError { message }
    ... on InvalidStepError { invalidStepKey }
    ... on InvalidOutputError { stepKey invalidOutputName }
  }
}
"""

LAUNCH_MULTIPLE_RUNS_MUTATION = """
mutation LaunchMultipleRuns($executionParamsList: [ExecutionParams!]!) {
  launchMultipleRuns(executionParamsList: $executionParamsList) {
    __typename
    ... on LaunchMultipleRunsResult {
      launchMultipleRunsResult {
        __typename
        ... on LaunchRunSuccess {
          run { id jobName status creationTime assetSelection { path } }
        }
        ... on PythonError { message stack }
        ... on InvalidSubsetError { message }
        ... on PipelineNotFoundError { message }
        ... on RunConfigValidationInvalid {
          errors { message reason }
        }
        ... on RunConflict { message }
        ... on UnauthorizedError { message }
        ... on ConflictingExecutionParamsError { message }
        ... on InvalidStepError { invalidStepKey }
        ... on InvalidOutputError { stepKey invalidOutputName }
      }
    }
    ... on PythonError { message stack }
  }
}
"""

LAUNCH_RUN_REEXECUTION_MUTATION = """
mutation LaunchRunReexecution($reexecutionParams: ReexecutionParams!) {
  launchRunReexecution(reexecutionParams: $reexecutionParams) {
    __typename
    ... on LaunchRunSuccess {
      run {
        id
        jobName
        status
        creationTime
        parentRunId
        rootRunId
        assetSelection { path }
        tags { key value }
      }
    }
    ... on PythonError { message stack }
    ... on InvalidSubsetError { message }
    ... on PipelineNotFoundError { message }
    ... on RunConfigValidationInvalid {
      errors { message reason }
    }
    ... on RunConflict { message }
    ... on UnauthorizedError { message }
    ... on ConflictingExecutionParamsError { message }
    ... on InvalidStepError { invalidStepKey }
    ... on InvalidOutputError { stepKey invalidOutputName }
  }
}
"""

CLOUD_AGENTS_QUERY = """
query CloudAgents {
  agents {
    id
    agentLabel
    status
    lastHeartbeatTime
    metadata {
      key
      value
    }
    errors {
      timestamp
      error {
        message
        stack
        errorChain {
          isExplicitLink
          error {
            message
            stack
          }
        }
      }
    }
    codeServerStates {
      locationName
      status
      error {
        message
        stack
        errorChain {
          isExplicitLink
          error {
            message
            stack
          }
        }
      }
    }
    runWorkerStates {
      message
      status
      runId
    }
  }
}
"""

SCHEDULES_QUERY = """
query ListSchedules(
  $repositoryName: String!
  $repositoryLocationName: String!
  $scheduleStatus: InstigationStatus
) {
  schedulesOrError(repositorySelector: {
    repositoryName: $repositoryName
    repositoryLocationName: $repositoryLocationName
  }, scheduleStatus: $scheduleStatus) {
    ... on Schedules {
      results {
        id
        name
        cronSchedule
        pipelineName
        executionTimezone
        description
        defaultStatus
        scheduleState {
          status
          hasStartPermission
          hasStopPermission
        }
        tags { key value }
      }
    }
    ... on RepositoryNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

SENSORS_QUERY = """
query ListSensors(
  $repositoryName: String!
  $repositoryLocationName: String!
  $sensorStatus: InstigationStatus
) {
  sensorsOrError(repositorySelector: {
    repositoryName: $repositoryName
    repositoryLocationName: $repositoryLocationName
  }, sensorStatus: $sensorStatus) {
    ... on Sensors {
      results {
        id
        name
        sensorType
        description
        defaultStatus
        minIntervalSeconds
        nextTick { timestamp }
        sensorState {
          status
          hasStartPermission
          hasStopPermission
        }
        targets {
          pipelineName
        }
        tags { key value }
      }
    }
    ... on RepositoryNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

RUN_GROUP_QUERY = """
query GetRunGroup($runId: ID!) {
  runGroupOrError(runId: $runId) {
    ... on RunGroup {
      rootRunId
      runs {
        id
        jobName
        status
        creationTime
        startTime
        endTime
        parentRunId
        rootRunId
        assetSelection { path }
        tags { key value }
      }
    }
    ... on RunGroupNotFoundError {
      message
    }
    ... on PythonError {
      message
      stack
    }
  }
}
"""

LOCATION_LOAD_HISTORY_QUERY = """
query GetLocationLoadHistory($locationName: String!, $limit: Int!, $cursor: String) {
  locationLoadHistory(locationName: $locationName, limit: $limit, cursor: $cursor) {
    locationName
    codeLocationDataUploadTimestamp
    codeLocationUpdateTriggerTimestamp
    loadStatus
    displayMetadata { key value }
    error {
      message
      stack
    }
  }
}
"""
