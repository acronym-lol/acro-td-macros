# Acro TD Macros

Hierarchical macro framework for TouchDesigner — named, addressable units of behavior with on-disk persistence and signal routing.

## What it does

`AcroMacros` (`/AcroMacros`, shortcut `op.AM`, extension `ext.AcroMacros`) lets you define small units of behavior — each with an `onInit` and `onTrigger` callback — organized in a folder hierarchy and triggered programmatically or by signal.

Each macro is a directory containing a `data.json` (metadata, subscriptions, errors, log) and a `callbacks.py` (the actual handler functions). The framework loads them into memory at start-up and surfaces them via the `op.AM.*` API.

## Quick start

```python
# Create a new macro at the root
op.AM.CreateMacro('FadeIn', '/')

# Trigger by path
op.AM.TriggerMacro('FadeIn', args={'duration': 0.5})

# Broadcast a signal — every macro that subscribed to it fires
op.AM.Emit('on_show', args={'panel': 'A'})

# List everything
for m in op.AM.ListMacros():
    print(m['path'], m['subscriptions'])

# Get / set a macro's callback code
code = op.AM.GetCallbackCode('FadeIn')
op.AM.SetCallbackCode('FadeIn', code + '\n# edited')
```

## Macro callback template

```python
def onInit(info, mc, macro):
    # subscribe to signals here so they're wired the moment the macro loads
    # mc.Subscribe(macro, 'on_show')
    return

def onTrigger(info, mc, macro, comps, args):
    # info  — caller metadata (path, type, delay)
    # mc    — op.AM (the AcroMacros instance)
    # macro — this macro's data dict (uuid, name, parameters, subscriptions, ...)
    # comps — op.comps shortcut (your project's components)
    # args  — whatever was passed to TriggerMacro or Emit
    return
```

## Features

- **Hierarchical** — macros nest in folders that mirror the macro path
- **On-disk persistence** — `data.json` + `callbacks.py` per macro; survives `.toe` saves and reloads cleanly
- **Signals** — pub/sub layered on top of trigger. `Subscribe(macro, signal)` in `onInit`; `Emit(signal, args)` from anywhere
- **Logging + errors** — per-macro log buffer and traceback captures, surfaced in the AcroMacroList widget
- **MCP-friendly** — every method returns JSON-serializable shapes, so `td_execute` calls can drive macros directly
- **Widgets** — `AcroMacroList` (tree view + drag/drop/rename), `AcroSignalsList` (signal routing table)
- **REST API** — an optional HTTP layer (`/AcroMacros/webserver1`, configured via the `API` custom page) exposes the same operations to non-Python clients (browser UIs, curl, etc.)

## Where to go next

- **[API Reference](api)** — Full method tables (`ListMacros`, `GetMacroInfo`, `GetCallbackCode`, `SetCallbackCode`, `CreateMacro`, `DeleteMacro`, `TriggerMacro`, `Emit`, `Subscribe`, `MoveMacro`, `RenameMacroUUID`, `CopyMacro`, `CutMacro`, `PasteMacro`), on-disk layout, signal routing internals, widget integration.
- **[REST API](http-api)** — HTTP endpoint reference for the `webserver1` bridge, for clients that can't call `op.AM.*` directly.

## Installation

```bash
git subtree add --prefix=modules/acro-td-macros https://github.com/acronym-lol/acro-td-macros.git main --squash
```

`setup.ps1` / `setup.sh` register `ACRO_TD_MACROS` pointing at the module on disk so the extension can locate its `CallbacksTemplates/` (Jinja2 templates for new-macro callback scaffolding) via `var('ACRO_TD_MACROS')`.
