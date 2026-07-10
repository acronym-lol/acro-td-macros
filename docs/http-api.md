# AcroMacros REST API

A REST API over HTTP that wraps the [AcroMacros](api) Python methods for external tools — browser
UIs, curl, other languages — anything that can't call `op.AM.*` directly.

## Overview

| Property | Value |
|----------|-------|
| **Extension** | `MacroApi` webserver callbacks |
| **Scripts** | `modules/acro-td-macros/scripts/macro_webserver.py` (webserverDAT callbacks), `macro_api_router.py` (route dispatch) |
| **TD Location** | `/AcroMacros/webserver1` (a `webserverDAT` living inside `/AcroMacros` itself) |
| **Configuration** | The **`Api`** custom page on `/AcroMacros` — every `webserver1` parameter (port, active, TLS, content-type, etc.) is bound there, so configure the server from the parent component, not the child DAT |
| **Base URL** | `http://localhost:{port}/api/v1` — port is whatever `Webserverport` is set to on the `Api` page (`9980` by default in this project) |
| **Auth** | None. Local-dev only — do not expose beyond localhost without adding one. |
| **CORS** | Wide open (`Access-Control-Allow-Origin: *`), so any local page/app can call it cross-origin. |

## Data model

Everything is a **macro** — a node in a tree, identified by a slash-delimited `path` (e.g. `Arcade/Mortal Kombat/Reset`).
A macro can have children, a free-text `comment`, a Python callback (`onInit` / `onTrigger`), and a list of
`subscriptions` (signal names it listens for). There's no separate "folder" type — anything can have children.

**Signals** are pub/sub on top of macros: `POST /signals/{signal}/emit` fires every macro subscribed to that
name. A macro subscribes from inside its own `onInit`, via `mc.Subscribe(macro, 'signal_name')`.

> **Naming convention:** namespace per-machine/per-feature signals (`MortalKombat.EnteredEasyMode`) rather than
> bare names (`EnteredEasyMode`). Signals are global — a bare name used by two different callers would cross-trigger
> both. Reserve un-namespaced names for signals that are intentionally shared/global.

## Endpoints

All bodies/responses are JSON. Errors are `{"error": {"code": "...", "message": "..."}}` with a matching HTTP status.

| Method | Path | Body | Description |
|---|---|---|---|
| `GET` | `/health` | — | API liveness, port, whether AcroMacros is reachable |
| `GET` | `/macros` | — | List all macros, flat. `?parent={path}` filters to a subtree (any depth) |
| `POST` | `/macros` | `{name, path}` | Create a macro under `path` (`""` for root) |
| `GET` | `/macros/{path}` | — | Full detail (comment, parameters, subscriptions, errors, children) |
| `PATCH` | `/macros/{path}` | `{name?, comment?}` | Rename and/or update comment. Rename applies before the comment update, so both can be sent in one call |
| `DELETE` | `/macros/{path}` | — | Delete a macro and its data (204) |
| `GET` | `/macros/{path}/children` | — | Direct children only, with `comment`/`subscriptions`/`has_errors` per child |
| `GET` | `/macros/{path}/callback` | — | Get the macro's Python callback source |
| `PUT` | `/macros/{path}/callback` | `{code}` | Replace the callback source (re-runs `onInit`) |
| `POST` | `/macros/{path}/trigger` | `{args?, delayMilliSeconds?, delayFrames?}` | Fire `onTrigger` (202 — runs next TD frame, not synchronously) |
| `POST` | `/macros/{path}/move` | `{to_path, move_type?}` | Move/reorder. `move_type`: `above` \| `below` \| `under` (default) |
| `POST` | `/macros/{path}/duplicate` | `{dest_path}` | Clone a macro (and subtree), auto-renamed on conflict |
| `GET` | `/macros/{path}/log` | — | Recent trigger/emit log entries (newest first) |
| `DELETE` | `/macros/{path}/log` | — | Clear the macro's log (204) |
| `DELETE` | `/macros/{path}/errors` | — | Clear the macro's error list (204) |
| `GET` | `/signals` | — | Full signal routing table: `{signal_name: [macro_path, ...]}` |
| `POST` | `/signals/{signal}/emit` | `{args?}` | Emit a signal — triggers every subscribed macro (202) |

### Caveat: nested resource ambiguity

A macro path is user-named and slash-delimited, so a macro whose own name collides with a suffix keyword
(`children`, `callback`, `trigger`, `move`, `duplicate`, `log`, `errors`) is ambiguous with that sub-resource
**only when nested at least one level deep**. A top-level macro named e.g. `callback` is fine.

### Safety prompts

`DeleteMacro`/`MoveMacro`/`copyMacro` normally pop a `ui.messageBox()` confirmation when AcroMacros' `Safety`
storage flag is on — which would hang an HTTP request forever. The router suspends `Safety` for the duration of
those specific calls, then restores it, so it never blocks regardless of the project's Safety setting.

## Example

```bash
curl -X POST http://localhost:9980/api/v1/macros \
  -H "Content-Type: application/json" \
  -d '{"name":"Hello World","path":""}'

curl -X PATCH http://localhost:9980/api/v1/macros/Hello%20World \
  -H "Content-Type: application/json" \
  -d '{"comment":"created via REST"}'

curl -X POST http://localhost:9980/api/v1/macros/Hello%20World/trigger \
  -H "Content-Type: application/json" \
  -d '{"args":{"greeting":"hi"}}'
```
