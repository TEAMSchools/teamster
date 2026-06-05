# Error group triage

Apply when step 12 has any `inWindow` entries. `staleOpen` entries skip straight
to "cleanup candidates" treatment without needing this procedure.

## In-window groups

First, check `category` + `correlatedPodEvent` — both are auto-resolved by the
collector:

- **`category: "sigterm_during_import"`** with a `correlatedPodEvent` → the
  group is a SIGTERM-mid-import artifact of code-server preemption (the
  by-design priority-tier behavior in `.k8s/CLAUDE.md`). Do NOT include in
  Emerging Issues. Emit a single Actions row:
  `Mute | Error group <id> (SIGTERM during import, <count> hits)`. The
  traceback's deepest project-code frame names whichever module was importing
  when SIGTERM arrived (pathlib, pydantic, fldoe.schema, etc.) — that file is
  NOT the emitter; it was just in-flight when the signal arrived.
- **`category: "preemption_artifact"`** → correlated to a preemption/eviction
  event but exception class is not a known SIGTERM type. Investigate
  `exceptionLine` before recommending action.
- **`category: "unclassified"`** (no correlated pod event) → genuine emerging
  issue. Proceed with dedupe below.

### Dedupe remaining (uncorrelated) groups against the timeline

Each group's `affectedServices[].version` is a pod name. Query GCP logs for
ERROR-severity entries on that pod within the group's lastSeenTime window and
extract the `k8s-pod/dagster/run-id` label. If that runId is a failed run
already listed in the timeline (step 1), mark the group "same event as run X"
and fold it INTO the existing timeline entry instead of reporting it as a
separate finding. Only groups with NO matching run are standalone emerging
issues.

For remaining (non-deduped) groups: if the stack trace matches a retry-recovered
run, it is likely a false-positive from a retry-wrapped helper (see
`src/teamster/CLAUDE.md`). Recommend changing the helper's log level in that
case.

### Use `exceptionLine`, not `exception`, for triage

The `exception` field is the 300-char truncated header that Error Reporting
groups by — often just the entry-point line (`Traceback... sys.exit(main())`).
The collector resolves the bottom-of-traceback class into `exceptionLine` via a
pod-log query; that is the real exception class.

## Stale open groups

OPEN groups last-seen before the window. Treat as cleanup candidates. Note the
last-seen date and whether the stack matches a retry-wrapped helper. These do
not belong in the timeline.

## Attribution: who logged at ERROR, not just whose stack appears

When attributing an error group to a file, identify what is logging at ERROR
severity — GCP Error Reporting fires on ERROR logs, not on stack frames. A
traceback that passes through a file does NOT mean that file is the emitter.
`SIGTERM` during run preemption unwinds the stack through wherever execution was
when the signal arrived, so the top frames of the traceback will name whatever
helper was in-flight. Before proposing a fix to a file, confirm the file itself
emits ERROR-level logs for this path (read the source — not just that it appears
in the stack). Retry-wrapped helpers in `src/teamster/CLAUDE.md` log at WARNING
and do NOT file groups; stack frames through them are incidental.
