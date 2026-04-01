# Design: VS Code Task — dbt: Open YAML

**Issue:** TEAMSchools/teamster#3559 **Date:** 2026-04-01 **Author:** grangel

---

## Problem

When editing a dbt SQL model, opening the corresponding YAML properties file
requires manually navigating the file tree to `properties/<model>.yml`. This is
a repetitive, friction-inducing step that interrupts the development flow.

## Goal

A single keystroke opens the YAML properties file for whatever SQL model is
currently active in the editor. If no YAML exists yet, it creates a minimal stub
so the developer has a starting point. No terminal output, no panel reveal —
just the file.

---

## Context

dbt model files and their property files follow a consistent layout:

```text
<model_dir>/
  my_model.sql
  properties/
    my_model.yml   ← or .yaml
```

VS Code tasks support
[predefined variables](https://code.visualstudio.com/docs/editor/variables-reference)
such as `${fileDirname}` and `${fileBasenameNoExtension}`, which makes path
construction straightforward.

VS Code does **not** support workspace-level keybindings. Each developer must
add the binding once to their own User Keybindings profile.

---

## Design

### Task definition (`.vscode/tasks.json`)

Add one entry to the `tasks` array:

```json
{
  "label": "dbt: Open YAML",
  "type": "shell",
  "command": "YML=\"${fileDirname}/properties/${fileBasenameNoExtension}.yml\"; YAML=\"${fileDirname}/properties/${fileBasenameNoExtension}.yaml\"; if [ -f \"$YML\" ]; then code \"$YML\"; elif [ -f \"$YAML\" ]; then code \"$YAML\"; else mkdir -p \"${fileDirname}/properties\" && printf 'models:\\n  - name: ${fileBasenameNoExtension}\\n    config:\\n      contract:\\n        enforced: false\\n' > \"$YML\" && code \"$YML\"; fi",
  "presentation": {
    "reveal": "never",
    "panel": "shared",
    "focus": false,
    "close": true
  },
  "problemMatcher": []
}
```

**Behavior:**

- Checks for `.yml` first (house convention); falls back to `.yaml`
- If neither exists, creates `properties/<model>.yml` with a minimal stub and
  opens it
- `reveal: never` + `close: true` — terminal panel never opens or flashes
- `focus: false` — editor focus stays on the SQL file after invocation

### Stub format

When no YAML exists, the generated stub is:

```yaml
models:
  - name: <model_name>
    config:
      contract:
        enforced: false
```

`contract: enforced: false` is intentional — the developer builds out the model
first, then flips the contract on once columns are stable. Full column
generation with data types is handled by TEAMSchools/teamster#3551 once the
model exists.

### User keybinding (each developer, one-time setup)

Open User Keybindings (`Ctrl+K Ctrl+S`, then click `{}` in the top right) and
add:

```json
{
  "key": "ctrl+shift+y",
  "command": "workbench.action.tasks.runTask",
  "args": "dbt: Open YAML"
}
```

`Ctrl+Shift+Y` is unbound by default in VS Code on Linux and Windows; verify
there is no conflict on macOS (`Cmd+Shift+Y` is used by Debug Console).

---

## Scope

| In scope                                   | Out of scope                                      |
| ------------------------------------------ | ------------------------------------------------- |
| Open matching YAML for the active SQL file | Supporting non-`properties/` subdirectory layouts |
| `.yml` / `.yaml` fallback                  | Workspace-level keybinding (VS Code limitation)   |
| Create minimal stub if no YAML exists      | Full column generation with data types (#3551)    |
| Silent invocation (no terminal reveal)     |                                                   |

---

## Acceptance Criteria

- [ ] `.vscode/tasks.json` contains a `"dbt: Open YAML"` task
- [ ] Task prefers `.yml`, falls back to `.yaml`
- [ ] When no YAML exists, task creates a stub with `contract: enforced: false`
      and opens it
- [ ] Terminal panel does not appear on invocation
- [ ] Task is manually verified against a real model file in the Codespace

---

## Implementation

Single file change: add the task object to `.vscode/tasks.json`.

The stub creation logic is embedded in the shell command — no external scripts,
no new dependencies, no environment variables required.
