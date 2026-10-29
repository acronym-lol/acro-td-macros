# AcroMacros REST API

A REST API over HTTP that wraps the [AcroMacros](api) Python methods for external tools — browser
UIs, curl, other languages — anything that can't call `op.AM.*` directly.

## Overview

| Property | Value |
|----------|-------|
| **Extension** | `AcroMacrosRestAPI` — extension slot 1 on `/AcroMacros` (slot 0 is `AcroMacros` itself) |
| **Scripts** | `AcroMacrosRestAPI.py` (access checks, CORS, JSON parsing, calls the router), `webserver_api_callbacks.py` (webserverDAT callback shim), `macro_api_router.py` (route dispatch) |
| **TD Location** | `/AcroMacros/webserver_api` (a `webserverDAT` living inside `/AcroMacros` itself) |
| **Configuration** | The **`API`** custom page on `/AcroMacros` — every `webserver_api` parameter (port, active, TLS, content-type, etc.) is bound there, so configure the server from the parent component, not the child DAT |
| **Base URL** | `http://localhost:{port}/api/v1` — port is whatever `Webserverport` is set to on the `API` page (`9980` by default in this project) |
| **Off by default** | `Webserveractive` is off. Turn it on from the `API` page. |
| **Auth** | Required. Every request sends `Authorization: Bearer <key>`; the key lives in an environment variable. See [Security](#security). |
| **CORS** | Only origins listed in `Alloworigins` (empty by default). |

> **Multiple projects open at once:** the default port (`9980`) is the same across every Acro Core project.
> If you have more than one Acro Core-based `.toe` open at the same time, only the first one binds the port —
> the others will fail to start their server. Change `Webserverport` on the `API` page of `/AcroMacros` to a
> unique value per project so they can run simultaneously.

### Request flow

```
webserver_api (webserverDAT)
  -> webserver_api_callbacks.py: onHTTPRequest(dat, request, response)
     -> ext.AcroMacrosRestAPI.OnHTTPRequest(...)   [AcroMacrosRestAPI.py]
        -> macro_api_router.route_request(ownerComp, method, uri, pars, body)
           -> a _handle_* function, calling into the AcroMacros extension (slot 0)
```

`AcroMacrosRestAPI` is a second extension on the same component `AcroMacros` itself lives on (see
`/AcroMacros`'s Extensions page). Because of that, it reaches the macro engine via
`self.ownerComp.extensions[0]` rather than a hardcoded path — `macro_api_router.py` never assumes
`AcroMacros` lives at `/AcroMacros`; it just uses whatever `ownerComp` `AcroMacrosRestAPI` hands it.
`webserver_api_callbacks.py` itself has no real logic anymore — it exists only because TD requires a
callback DAT with these exact function names.

## Security

The API can create, edit and trigger macros, and a macro's callback is Python. So anyone who can call the API can
run code in TouchDesigner. It is locked down by default:

- **The server is off** until you turn on `Webserveractive`.
- **An API key is required.** With no key set up, every request gets a `503` telling you to set one.
- **Only this machine** can connect, unless you turn on `Allowremote`.
- **Browser pages are refused** unless their origin is listed in `Alloworigins`.

### Setting up the API key

The key never goes in a parameter, because TouchDesigner saves parameter values into the `.toe`/`.tox`. Put it in
an environment variable and enter the variable's **name** in `Apikeyenv`:

```bash
# Windows - setx stores it for new processes, so restart TouchDesigner afterwards
setx MY_MACROS_API_KEY "a-long-random-string"

# macOS - for apps started from the Finder/Dock; restart TouchDesigner afterwards
launchctl setenv MY_MACROS_API_KEY "a-long-random-string"
```

Then set `Apikeyenv` to `MY_MACROS_API_KEY` (any name works). Clients send the key on every request:

```bash
curl -H "Authorization: Bearer $MY_MACROS_API_KEY" http://localhost:9980/api/v1/health
```

If `Apikeyenv` names a variable that isn't set in TouchDesigner's environment, requests get a `503`, and the
textport says which variable is missing. TouchDesigner reads environment variables only when it starts.

### Remote clients

Turn on `Allowremote` to accept requests from other machines, such as a tablet or a show-control computer. They need
the same key.

> [!WARNING]
> `Allowremote` is a convenience filter, not the protection. The Web Server DAT lets a request header named
> `clientAddress` overwrite the client address it reports, so a crafted request can pass as local. The API key is
> what actually keeps other machines out, which is why it's required even for local use.

Over a network you don't control, also turn on **Secure (TLS)** so the key isn't sent in plain text.

### Browser UIs

A browser page on another origin can call the API only if that origin is listed in `Alloworigins`, separated by
spaces. `*` is a wildcard:

```
https://ui.example.com http://192.168.1.*:8080
```

- Listed origins get CORS headers allowing `Content-Type` and `Authorization`. Preflight (`OPTIONS`) requests are
  answered without a key, because browsers never send credentials on them.
- Any other origin gets a `403` before the request runs. Leaving out CORS headers alone wouldn't be enough: a
  browser still sends a simple `text/plain` POST and only hides the reply.
- Request bodies must be `Content-Type: application/json`, which also forces a browser to preflight.
- Write each pattern out in full. `http://localhost*` would also match `http://localhost.evil.example`.

The UI has to supply the key itself, for example by asking for it once. Don't put it in a page you publish.

### TLS certificate password

The certificate password is read from the environment variable named in `Webserverpasswordenv`, for the same reason.
Earlier versions had a `Webserverpassword` parameter; it's removed when the component loads, with a textport
warning if it held a value.

### Error responses

| Status | `code` | When |
|---|---|---|
| `401` | `unauthorized` | Missing or wrong `Authorization: Bearer <key>` |
| `403` | `origin_not_allowed` | The `Origin` header isn't in `Alloworigins` |
| `403` | `remote_not_allowed` | Another machine connected and `Allowremote` is off |
| `415` | `unsupported_media_type` | A request body that isn't `application/json` |
| `503` | `api_key_not_configured` | `Apikeyenv` is empty, or names a variable that isn't set |

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

These assume the key is in `MY_MACROS_API_KEY` (see [Setting up the API key](#setting-up-the-api-key)).

```bash
curl -X POST http://localhost:9980/api/v1/macros \
  -H "Authorization: Bearer $MY_MACROS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Hello World","path":""}'

curl -X PATCH http://localhost:9980/api/v1/macros/Hello%20World \
  -H "Authorization: Bearer $MY_MACROS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"comment":"created via REST"}'

curl -X POST http://localhost:9980/api/v1/macros/Hello%20World/trigger \
  -H "Authorization: Bearer $MY_MACROS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"args":{"greeting":"hi"}}'
```

## Data model

Everything is a **macro** — a node in a tree, identified by a slash-delimited `path` (e.g. `Arcade/Mortal Kombat/Reset`).
A macro can have children, a free-text `comment`, a Python callback (`onInit` / `onTrigger`), and a list of
`subscriptions` (signal names it listens for). There's no separate "folder" type — anything can have children.

**Signals** are pub/sub on top of macros: `POST /signals/{signal}/emit` fires every macro subscribed to that
name. A macro subscribes from inside its own `onInit`, via `mc.Subscribe(macro, 'signal_name')`.

> **Naming convention:** namespace per-machine/per-feature signals (`MortalKombat.EnteredEasyMode`) rather than
> bare names (`EnteredEasyMode`). Signals are global — a bare name used by two different callers would cross-trigger
> both. Reserve un-namespaced names for signals that are intentionally shared/global.

## Configuring the server — the `API` page

`/AcroMacros` has a custom parameter page named **`API`** with every configurable parameter of the
`webserver_api` DAT. Value-type parameters are live-bound (`bindExpr`) to `webserver_api`'s own parameters — set
them here and the actual server reconfigures immediately, no reinitialization needed. There are two exceptions:

- **Restart** is a momentary action, not a bindable value. It's wired via a `pulse_Webserverrestart()` handler
  in `AcroMacros.py` that calls `webserver_api.par.restart.pulse()` directly.
- **The certificate password** is read from an environment variable through an expression, so it's never saved
  (see [TLS certificate password](#tls-certificate-password)).

The page mirrors `webserver_api`'s own three native parameter groups, plus a **Security** group that
`AcroMacrosRestAPI` adds when it loads:

**Web Server**

| Parameter | Label | Type | Notes |
|---|---|---|---|
| `Webserveractive` | Active | Toggle | Starts/stops the server. Bound to `webserver_api.active`. |
| `Webserverrestart` | Restart | Pulse | Restarts the server (handler, not a bind — see above). |
| `Webserverport` | Port | Int | TCP port the API listens on. This is what `{port}` refers to throughout this doc. |
| `Webservercallbacks` | Callbacks DAT | DAT ref | Which DAT handles the webserver callbacks — normally leave pointed at `webserver_api_callbacks`. |

**Security** (created by `AcroMacrosRestAPI`; not bound to `webserver_api`)

| Parameter | Label | Type | Notes |
|---|---|---|---|
| `Allowremote` | Allow Remote Clients | Toggle | Off by default. Accept requests from other machines; they still need the key. |
| `Apikeyenv` | API Key Env Variable | Str | **Required.** Name of the environment variable that holds the API key. |
| `Alloworigins` | Allowed Browser Origins | Str | Space-separated origins (with `*` wildcards) that browser pages may call from. Empty by default. |

**Secure (TLS)**

| Parameter | Label | Type | Notes |
|---|---|---|---|
| `Webserversecure` | Secure (TLS) | Toggle | Enables HTTPS. |
| `Webserverprivatekey` | Private Key File Path | File | Required if TLS is on. |
| `Webservercertificate` | Certificate File Path | File | Required if TLS is on. |
| `Webserverpasswordenv` | Certificate Password Env Variable | Str | Name of the environment variable that holds the certificate password, if any. `webserver_api`'s `password` reads it through the expression `parent.AM.CertificatePassword` rather than a bind. |
| `Webserververifyclient` | Verify Client | Toggle | Require/validate a client certificate. |
| `Webserverminprotocol` | Minimum TLS Protocol | Menu | `tls10` \| `tls11` \| `tls12` \| `tls13`. |

**Content**

| Parameter | Label | Type | Notes |
|---|---|---|---|
| `Webserverlanguage` | Content Language | Menu | Response content-type hint: `input` (from request), `parameter`, `text`, `python`, `glsl`, `json`, `yaml`, `xml`, `tscript`. The router always sets `content-type: application/json` itself on non-OPTIONS responses, so this mostly matters for the raw `/` fallback and error edge cases. |
| `Webserverextension` | Edit/View Extension | Menu | File extension TD associates with served content when editing/viewing — `csv`/`dat`/`frag`/`glsl`/`html`/`json`/`md`/`py`/`rtf`/`sdp`/`tsv`/`txt`/`vert`/`xml`/`yaml`/`yml`, or derive it from `languageext`/`customext`. |
| `Webservercustomext` | Custom Extension | Str | Used when `Webserverextension` is set to `customext`. |
| `Webserverwordwrap` | Word Wrap | Menu | `input` \| `on` \| `off` — TD editor word-wrap behavior for served text content. |

None of the Content-group parameters affect the JSON API responses themselves (the router hardcodes
`application/json`) — they matter if you're using `webserver_api` to also serve non-API content (static files,
HTML) from the same DAT.
