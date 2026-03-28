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

STALE_ASSETS_QUERY = """
query GetStaleAssets {
  assetNodes {
    assetKey { path }
    groupName
    description
    computeKind
    isPartitioned
    jobNames
    owners {
      ... on UserAssetOwner { email }
      ... on TeamAssetOwner { team }
    }
    changedReasons
    staleStatus
    staleCauses {
      key { path }
      partitionKey
      category
      reason
      dependency { path }
      dependencyPartitionKey
    }
  }
}
"""

ASSET_MATERIALIZATIONS_QUERY = """
query GetAssetMaterializations($assetKey: AssetKeyInput!, $limit: Int, $partitions: [String!]) {
  assetNodes(assetKeys: [$assetKey]) {
    assetKey { path }
    assetMaterializations(limit: $limit, partitions: $partitions) {
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
query GetAssetCheckExecutions($assetKey: AssetKeyInput!, $checkName: String!, $limit: Int!, $cursor: String) {
  assetCheckExecutions(assetKey: $assetKey, checkName: $checkName, limit: $limit, cursor: $cursor) {
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
    ... on PythonError {
      message
      stack
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
      ticks(limit: $limit, statuses: $statuses) {
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
query ListBackfills($status: BulkActionStatus, $cursor: String, $limit: Int) {
  partitionBackfillsOrError(status: $status, cursor: $cursor, limit: $limit) {
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
        ... on PythonError { message }
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
