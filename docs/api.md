---
last_reviewed: 2026-08-27
---

# Macros — Macro Framework

## Overview

Macros is a hierarchical macro management framework. A macro is a small, persistent unit of behavior with two callback functions (`onInit` and `onTrigger`) and an attached metadata bundle. Macros are stored on disk as folders containing a JSON metadata file and a Python callback file, and are loaded into memory at start-up.

The component lives at `/AcroMacros` and is exposed as `op.AM`. It inherits from `CallbacksExt` and `AcroVersionExt`, so it carries the standard Component / Version pages and is discoverable via the `tox_managed` and `version_tracking` tags.

Use Macros when you want named, addressable behaviors that survive saves, can be triggered programmatically or by signal, and are organized in a hierarchy you can edit at runtime.

---

## On-Disk Layout

Each macro is a directory under the `Macrosfolder` parameter (default `{project.folder}/macros/main/`), nested to mirror the macro path. Inside each directory:

```
macros/main/
  fade-in/
    data.json              ← metadata (uuid, name, comment, subscriptions, order)
    callbacks.py           ← onInit / onTrigger functions
  group/
    data.json
    callbacks.py
    fade-in/               ← nested macros are subfolders
      data.json
      callbacks.py
```

The `data.json` schema:

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | `string` | Stable identifier — survives renames and moves. |
| `name` | `string` | Display name. Folder name on disk is kept in sync with this. |
| `path` | `string` | Slash-delimited path of parent macros (empty string for root). |
| `order` | `int` | Position among siblings. |
| `comment` | `string` | Free-form comment. |
| `parameters` | `dict` | User-defined parameter bag (read in callbacks via `macro['parameters']`). |
| `subscriptions` | `list[str]` | Signal names this macro listens for. |
| `errors` | `list[str]` | Recent error log (capped at 100 entries). In memory only — never written to `data.json`. |
| `log` | `list[str]` | Recent trigger log (capped at 100 entries). In memory only — never written to `data.json`. |

`callbacks.py` is loaded as a module at runtime. It is expected to expose two functions:

```python
def onInit(info, am, macro):
    # am.Subscribe(macro, 'signal_name')   # subscribe to signals
    return

def onTrigger(info, am, macro, comps, args):
    # comps is op.comps (component shortcuts)
    # args is whatever was passed to TriggerMacro / Emit
    return
```

`info` is a dict containing the caller name/type and any delay parameters — useful for tracing where a trigger originated.

---

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `Macrosfolder` | `folder` | Path to the macro tree root. Defaults to `{project.folder}/macros/main`. |
| `Reloaddataonstart` | `toggle` | If on, the manager calls `ReloadData(force=True)` during init — useful in dev workflows where macros are edited externally. |

The component also carries the standard pages from `AcroToxExt` (Component) and `AcroVersionExt` (Version), plus the `Callbacks` page from `CallbacksExt`.

---

## Public API

### Properties (via stored)

| Name | Type | Description |
|------|------|-------------|
| `MacroData` | `dict[uuid, dict]` | All macro metadata bundles, keyed by UUID. |
| `MacroStructure` | `list[dict]` | Hierarchical tree of macros (uuid, name, expanded, selected, error, children). |
| `SelectedMacro` | `str` | UUID of the currently selected macro. |
| `Safety` | `bool` | When on, destructive operations (delete, rename, trigger) prompt for confirmation. |
| `Signals` | `dict[str, list[str]]` | Signal routing table, derived from each macro's `subscriptions`. |
| `Log` | `list[str]` | Top-level log of triggers and errors (capped). |

### Listing & Reading

| Method | Returns | Purpose |
|--------|---------|---------|
| `ListMacros()` | `list[dict]` | List every macro with a flat metadata view. |
| `GetMacroInfo(path)` | `dict \| None` | Full info for a macro. |
| `GetCallbackCode(path)` | `str \| None` | Read the macro's `callbacks.py` source. |
| `GetStructureByPath(path)` | `dict \| None` | Get a node from `MacroStructure` by path. |
| `GetUUIDByPath(path)` | `str \| None` | Look up the UUID for a path. |
| `GetPathByUUID(uuid)` | `str \| None` | Look up the path for a UUID. |
| `GetSignals()` | `dict` | Return the signal routing table. |

### Mutation

| Method | Returns | Purpose |
|--------|---------|---------|
| `CreateMacro(name, path)` | `None` | Create a macro under `path` (`""` for root). Auto-renames on collision. Generates a new UUID and `callbacks.py` from the template. |
| `DeleteMacro(path)` | `None` | Delete a macro and its folder. Re-numbers sibling `order`. Prompts when `Safety` is on. |
| `DeleteSelected()` | `None` | Delete the currently selected macro. |
| `RenameMacroUUID(uuid, name)` | `None` | Rename in-memory and on disk. Verifies the folder rename completed before re-saving. |
| `RenameMacroPath(path, name)` | `None` | Convenience wrapper around `RenameMacroUUID`. |
| `MoveMacro(from_path_list, to_path_list, mode)` | `None` | Move a macro within the tree. `mode` is `'under'`, `'before'`, or `'after'`. |
| `CopyMacro(macro)` / `CutMacro(macro)` / `PasteMacro(dest_path)` | `None` | Standard clipboard operations. Uses `ui.clipboard` so paste survives selection changes. |
| `SelectMacro(uuid)` | `None` | Mark a macro as selected. |
| `SetMacroComment(path, comment)` | `dict` | Update the comment field. |
| `SetCallbackCode(path, code)` | `dict` | Write callback source and persist to disk. |

### Execution

| Method | Returns | Purpose |
|--------|---------|---------|
| `TriggerMacro(macro_path, args=None, delayMilliSeconds=0, delayFrames=0)` | `None` | Execute a macro's `onTrigger`. Captures caller info and logs the trigger. |
| `TriggerSelected(args=None, delay…)` | `None` | Trigger the currently selected macro. Prompts when `Safety` is on. |
| `Emit(signal, args=None)` | `None` | Trigger every macro whose `subscriptions` contains `signal`. |
| `Subscribe(macro, signal)` | `None` | Subscribe a macro to a signal (called from inside `onInit`). |
| `ToggleSafety()` | `None` | Toggle the `Safety` storage flag. |

### Lifecycle / Maintenance

| Method | Returns | Purpose |
|--------|---------|---------|
| `InitData(deleteFolders=True)` | `None` | Wipe in-memory state and (optionally) delete every macro folder on disk. Prompts before deleting. |
| `ReloadData(force=False)` | `None` | Re-read every `data.json` and `callbacks.py` from disk into memory. Generates new UUIDs for any duplicates encountered. |
| `SaveMacroData(macro_uuid)` | `None` | Persist a macro's metadata back to its `data.json`. |
| `UpdateMacroCallbacks(macro_uuid)` | `None` | Re-import a macro's callback module and re-run `onInit`. Captures import errors. |
| `UpdateSignals()` | `None` | Rebuild the `Signals` routing table from current `subscriptions`. |

### Logging

| Method | Purpose |
|--------|---------|
| `AddLog(log, level='INFO')` | Append a top-level log entry. |
| `ClearLog()` | Clear the top-level log. |
| `AddMacroLog(uuid, log)` | Append a per-macro log entry. |
| `ClearMacroLog(uuid)` | Clear a macro's log. |
| `AddMacroError(uuid, error)` | Append an error entry to a macro and flag its structure node `error: True`. |
| `ClearMacroErrors(uuid)` | Clear a macro's error list and reset its structure flag. |

---

## Trigger Flow

Calling `TriggerMacro(path, args)` executes the following sequence:

1. `_get_caller_info()` walks the stack to record where the trigger came from. This is what makes the `Caller` field in macro logs accurate.
2. `AddMacroLog` writes a log entry tagged `trigger` (or `emit` if the call came from `Emit`).
3. The trigger is dispatched via TD's `run()` to honor `delayFrames` / `delayMilliSeconds`.
4. The callback module's `onTrigger(info, am, macro, comps, args)` is invoked.
5. Errors are caught — the macro is flagged in the structure (`error: True`) and the traceback is appended to the macro's `errors` list.
6. The Macros-level `onTriggerMacro` callback fires.

`Emit(signal, args)` performs the same flow for every macro subscribed to `signal`, then fires the Macros-level `onEmit` callback.

---

## Custom Callbacks

The Macros component dispatches a few global lifecycle callbacks via `CallbacksExt`. Implement them on the manager's external `Callbackdat`:

| Callback | Info Keys | Purpose |
|----------|-----------|---------|
| `onInit` | `ownerComp` | Fired during extension init. |
| `onTriggerMacro` | `info`, `macro`, `args` | Fired after each individual macro trigger. |
| `onEmit` | `signal`, `args` | Fired once per `Emit` call, after every subscribed macro has been triggered. |

These are global hooks — for per-macro logic, use the macro's own `onInit` / `onTrigger`.

---

## UUIDs vs Paths

Macros uses two parallel addressing schemes:

- **UUIDs** are stable and survive renames or moves. They are the right key for storage, callbacks, and external references.
- **Paths** are human-readable but ephemeral — renaming or moving a macro changes its path. They are the right key for user-facing APIs and quick scripting.

Conversion helpers (`GetUUIDByPath`, `GetPathByUUID`) are cheap; reach for them whenever you need to cross between the two.

---

## Tag Discovery

Like every `AcroVersionExt` component, Macros carries `tox_managed` and `version_tracking` tags and is discoverable via `root.findChildren(tags=['version_tracking'])`.
