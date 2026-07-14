"""
macro_api_router.py

Route dispatch for the Macro_API REST server. Pure functions: given the
AcroMacros component (the caller's ownerComp - see AcroRestAPI.py), HTTP
method, URI, query params and parsed JSON body, return (statusCode,
statusReason, payload_dict_or_None) for AcroRestAPI.OnHTTPRequest to write
into the response.

This module never hardcodes where AcroMacros lives (no op('/AcroMacros')) -
the caller (AcroRestAPI, an extension living on that same component) always
passes its own ownerComp in, so routing works regardless of the component's
actual path or name.

Route table (base: /api/v1):
    GET    /health
    GET    /signals
    POST   /signals/{signal}/emit
    GET    /macros                    (?parent={path} to filter)
    POST   /macros
    GET    /macros/{path}
    PATCH  /macros/{path}
    DELETE /macros/{path}
    GET    /macros/{path}/children
    GET    /macros/{path}/callback
    PUT    /macros/{path}/callback
    POST   /macros/{path}/trigger
    POST   /macros/{path}/move
    POST   /macros/{path}/duplicate
    GET    /macros/{path}/log
    DELETE /macros/{path}/log
    DELETE /macros/{path}/errors

Note: a macro path is itself slash-delimited and user-named, so a macro whose
own name collides with a suffix keyword (e.g. a macro literally named
"callback" nested under another macro) is ambiguous with that sub-resource.
Acceptable tradeoff for the readability of clean nested URIs; documented here
rather than hidden.
"""

import traceback
from contextlib import contextmanager

API_PREFIX = '/api/v1'
KNOWN_SUFFIXES = {'children', 'callback', 'trigger', 'move', 'duplicate', 'log', 'errors'}


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@contextmanager
def _no_safety_prompt(mc):
    """Suspend Macrocosm's Safety confirmation dialogs for one call.

    DeleteMacro/MoveMacro/copyMacro call ui.messageBox() when Safety is on,
    which blocks waiting for a click - fatal for a headless HTTP request.

    This mutates shared state (mc.stored['Safety']) for the duration of the
    call, which is only safe because TD's webserverDAT handles one request
    to completion before the next one starts - there's no real concurrency
    here. If that ever changes, this would need a real lock instead.
    """
    prev = mc.stored['Safety']
    mc.stored['Safety'] = False
    try:
        yield
    finally:
        mc.stored['Safety'] = prev


def _get_macrocosm(owner_comp):
    """Resolve the AcroMacros extension (slot 0) on owner_comp.

    owner_comp is the component AcroRestAPI is attached to - the same one
    AcroMacros itself is attached to - so this never needs to guess a path.
    """
    if not owner_comp.extensions:
        raise ApiError(503, 'macrocosm_unavailable', 'No AcroMacros extension found on the owning component')
    return owner_comp.extensions[0]


def _require_macro(mc, path):
    """Fetch a macro's info by path, or raise 404 if it doesn't exist."""
    info = mc.GetMacroInfo(path)
    if info is None:
        raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')
    return info


def _require_structure(mc, path):
    """Fetch a macro's tree-structure node by path, or raise 404 if it doesn't exist."""
    structure = mc.GetStructureByPath(path)
    if structure is None:
        raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')
    return structure


def _children_of(mc, parent_path):
    """Return the live children list for a parent path ('' means root)."""
    structure = _require_structure(mc, parent_path) if parent_path else {'children': mc.stored['MacroStructure']}
    return structure.get('children', [])


def _child_path(parent_path, child):
    """Build the full macro path for a child dict living under parent_path."""
    return (parent_path + '/' + child['name']).strip('/') if parent_path else child['name']


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def route_request(owner_comp, method, uri, pars, body):
    try:
        segments = _parse_segments(uri)

        # /health is a liveness probe and must answer even if AcroMacros
        # itself is unreachable - that's the whole point of a health check,
        # and its response schema ("macrocosm_available") only makes sense
        # if this route doesn't itself require AcroMacros to resolve. So
        # handle it before calling _get_macrocosm(), not after.
        if segments == ['health']:
            return _handle_health(owner_comp, method)

        mc = _get_macrocosm(owner_comp)
        if segments and segments[0] == 'signals':
            return _handle_signals(mc, method, segments[1:], body)
        if segments and segments[0] == 'macros':
            return _handle_macros(mc, method, segments[1:], pars, body)

        raise ApiError(404, 'not_found', f'Unknown route: {method} {uri}')
    except ApiError as e:
        return e.status, e.message, {'error': {'code': e.code, 'message': e.message}}
    except Exception:
        print(traceback.format_exc())
        return 500, 'Internal Server Error', {
            'error': {'code': 'internal_error', 'message': 'Unexpected server error - see TouchDesigner textport'}
        }


def _parse_segments(uri):
    if not uri.startswith(API_PREFIX):
        raise ApiError(404, 'not_found', f'Unknown route prefix: {uri}')
    sub = uri[len(API_PREFIX):]
    return [s for s in sub.split('/') if s]


# -----------------------------------------------------------------------------
# /health
# -----------------------------------------------------------------------------

def _handle_health(owner_comp, method):
    if method != 'GET':
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on /health')
    # Relative lookup off owner_comp, not an absolute op('/AcroMacros/...')
    # path - works no matter where this component actually lives.
    ws = owner_comp.op('webserver_api')
    macrocosm_available = bool(owner_comp.extensions) and owner_comp.extensions[0] is not None
    return 200, 'OK', {
        'status': 'ok',
        'api_active': bool(ws.par.active.eval()) if ws else False,
        'api_port': ws.par.port.eval() if ws else None,
        'macrocosm_available': macrocosm_available,
    }


# -----------------------------------------------------------------------------
# /signals
# -----------------------------------------------------------------------------

def _handle_signals(mc, method, segments, body):
    if not segments:
        if method == 'GET':
            return 200, 'OK', {'signals': mc.GetSignals()}
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on /signals')

    if len(segments) == 2 and segments[1] == 'emit':
        if method != 'POST':
            raise ApiError(405, 'method_not_allowed', f'{method} not allowed on /signals/{{signal}}/emit')
        signal = segments[0]
        mc.Emit(signal, body.get('args'))
        return 202, 'Accepted', {'signal': signal, 'emitted': True}

    raise ApiError(404, 'not_found', 'Unknown /signals route')


# -----------------------------------------------------------------------------
# /macros
# -----------------------------------------------------------------------------

def _handle_macros(mc, method, segments, pars, body):
    if not segments:
        if method == 'GET':
            items = mc.ListMacros()
            parent = pars.get('parent')
            if parent:
                items = [m for m in items if m['path'] == parent or m['path'].startswith(parent + '/')]
            return 200, 'OK', {'macros': items}
        if method == 'POST':
            return _handle_create(mc, body)
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on /macros')

    if len(segments) > 1 and segments[-1] in KNOWN_SUFFIXES:
        suffix = segments[-1]
        path = '/'.join(segments[:-1])
    else:
        suffix = None
        path = '/'.join(segments)

    if suffix is None:
        return _handle_macro_item(mc, method, path, body)
    if suffix == 'children':
        return _handle_children(mc, method, path)
    if suffix == 'callback':
        return _handle_callback(mc, method, path, body)
    if suffix == 'trigger':
        return _handle_trigger(mc, method, path, body)
    if suffix == 'move':
        return _handle_move(mc, method, path, body)
    if suffix == 'duplicate':
        return _handle_duplicate(mc, method, path, body)
    if suffix == 'log':
        return _handle_log(mc, method, path)
    if suffix == 'errors':
        return _handle_errors(mc, method, path)

    # Unreachable today - suffix is always a member of KNOWN_SUFFIXES, and
    # every member has a branch above. This is a guardrail against future
    # drift: add a new suffix to KNOWN_SUFFIXES without adding its branch
    # here, and without this, the function would fall off the end and
    # return None - which macro_webserver.py's `status, reason, payload =
    # route_request(...)` would fail to unpack, raising an uncaught
    # TypeError instead of a clean error response.
    raise ApiError(500, 'internal_error', f'No handler wired up for suffix: {suffix}')


def _handle_create(mc, body):
    name = body.get('name')
    parent_path = body.get('path') or ''
    if not name:
        raise ApiError(400, 'invalid_body', "'name' is required")
    if parent_path and mc.GetStructureByPath(parent_path) is None:
        raise ApiError(404, 'parent_not_found', f'Parent path not found: {parent_path}')

    mc.CreateMacro(name, parent_path)

    # CreateMacro doesn't return what it created, and may have auto-renamed
    # it on a name collision (e.g. "Foo" -> "Foo_1") - but it always appends
    # to the end of the parent's children, so the last child is ours.
    children = _children_of(mc, parent_path)
    if not children:
        raise ApiError(500, 'internal_error', 'Macro created but could not be located afterward')
    new_path = _child_path(parent_path, children[-1])
    return 201, 'Created', {'macro': mc.GetMacroInfo(new_path)}


def _handle_macro_item(mc, method, path, body):
    if method == 'GET':
        return 200, 'OK', {'macro': _require_macro(mc, path)}

    if method == 'PATCH':
        uuid = mc.GetUUIDByPath(path)
        if not uuid:
            raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')

        # Rename first, then re-resolve the path, then apply the comment.
        # Renaming changes the macro's path (it's the last path segment), so
        # if both `name` and `comment` are sent in the same request, the
        # comment update must target the *new* path, not the original one.
        new_name = body.get('name')
        if new_name and new_name != mc.GetPathByUUID(uuid).split('/')[-1]:
            mc.RenameMacroUUID(uuid, new_name)

        new_path = mc.GetPathByUUID(uuid)
        if 'comment' in body:
            result = mc.SetMacroComment(new_path, body['comment'])
            if not result.get('ok'):
                raise ApiError(500, 'internal_error', result.get('error', 'Failed to set comment'))

        return 200, 'OK', {'macro': mc.GetMacroInfo(new_path)}

    if method == 'DELETE':
        _require_macro(mc, path)
        with _no_safety_prompt(mc):
            mc.DeleteMacro(path)
        return 204, 'No Content', None

    raise ApiError(405, 'method_not_allowed', f'{method} not allowed on macro item')


def _handle_children(mc, method, path):
    if method != 'GET':
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on children')
    structure = _require_structure(mc, path)
    result = []
    for child in structure.get('children', []):
        child_path = (path + '/' + child['name']).strip('/') if path else child['name']
        raw = mc.stored['MacroData'][child['uuid']].getRaw()
        result.append({
            'uuid': child['uuid'],
            'name': child['name'],
            'path': child_path,
            'comment': raw.get('comment', ''),
            'subscriptions': raw.get('subscriptions', []),
            'has_errors': bool(raw.get('errors', [])),
            'has_children': bool(child.get('children')),
        })
    return 200, 'OK', {'path': path, 'children': result}


def _handle_callback(mc, method, path, body):
    if method == 'GET':
        code = mc.GetCallbackCode(path)
        if code is None:
            raise ApiError(404, 'macro_not_found', f'No macro/callback at path: {path}')
        return 200, 'OK', {'path': path, 'code': code}

    if method == 'PUT':
        if 'code' not in body:
            raise ApiError(400, 'invalid_body', "'code' is required")
        result = mc.SetCallbackCode(path, body['code'])
        if not result.get('ok'):
            raise ApiError(404, 'macro_not_found', result.get('error', f'Macro not found: {path}'))
        return 200, 'OK', {'macro': mc.GetMacroInfo(path)}

    raise ApiError(405, 'method_not_allowed', f'{method} not allowed on callback')


def _handle_trigger(mc, method, path, body):
    if method != 'POST':
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on trigger')
    _require_macro(mc, path)
    mc.TriggerMacro(
        path,
        body.get('args'),
        body.get('delayMilliSeconds', 0),
        body.get('delayFrames', 0),
    )
    return 202, 'Accepted', {'path': path, 'triggered': True}


def _handle_move(mc, method, path, body):
    if method != 'POST':
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on move')
    uuid = mc.GetUUIDByPath(path)
    if not uuid:
        raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')

    to_path = body.get('to_path') or ''
    move_type = body.get('move_type', 'under')
    if move_type not in ('above', 'below', 'under'):
        raise ApiError(400, 'invalid_body', "'move_type' must be 'above', 'below', or 'under'")

    # Reject moving a macro into itself or one of its own descendants.
    # Neither this router nor MoveMacro itself guards against that, and the
    # result would be a cyclic tree - every recursive walk in this codebase
    # (GetPathByUUID, GetStructureByPath, ListMacros, ...) would then loop
    # forever over that cycle, hanging the whole single-threaded TD process.
    if to_path == path or to_path.startswith(path + '/'):
        raise ApiError(400, 'invalid_move', 'Cannot move a macro into itself or one of its own descendants')

    if to_path and mc.GetStructureByPath(to_path) is None:
        raise ApiError(404, 'macro_not_found', f'Destination path not found: {to_path}')

    from_list = mc.GetPathListFromPath(path)
    to_list = mc.GetPathListFromPath(to_path) if to_path else []

    with _no_safety_prompt(mc):
        mc.MoveMacro(from_list, to_list, move_type)

    new_path = mc.GetPathByUUID(uuid)
    return 200, 'OK', {'macro': mc.GetMacroInfo(new_path)}


def _handle_duplicate(mc, method, path, body):
    if method != 'POST':
        raise ApiError(405, 'method_not_allowed', f'{method} not allowed on duplicate')
    _require_macro(mc, path)

    dest_path = body.get('dest_path') or ''

    # No separate "does dest_path exist" check needed here - _children_of()
    # below calls _require_structure() internally, which raises 404 for a
    # missing dest_path anyway. A prior version of this function checked it
    # twice (once explicitly, once inside _children_of) - redundant, removed.
    #
    # PasteMacro silently no-ops (just prints to the textport) instead of
    # raising when dest_path is inside the source path - so the only way to
    # detect that failure is to check whether a child actually got added.
    before_count = len(_children_of(mc, dest_path))

    with _no_safety_prompt(mc):
        mc.CopyMacro(path)
        mc.PasteMacro(dest_path)

    # PasteMacro doesn't return the macro it created, so we confirm success
    # (and find the new macro) by comparing child counts before and after.
    children = _children_of(mc, dest_path)
    if len(children) <= before_count:
        raise ApiError(409, 'duplicate_failed',
                        'Could not duplicate macro into the given destination '
                        '(e.g. destination is inside the source path)')
    new_path = _child_path(dest_path, children[-1])
    return 201, 'Created', {'macro': mc.GetMacroInfo(new_path)}


def _handle_log(mc, method, path):
    uuid = mc.GetUUIDByPath(path)
    if not uuid:
        raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')

    if method == 'GET':
        raw = mc.stored['MacroData'][uuid].getRaw()
        return 200, 'OK', {'path': path, 'log': raw.get('log', [])}

    if method == 'DELETE':
        mc.ClearMacroLog(uuid)
        return 204, 'No Content', None

    raise ApiError(405, 'method_not_allowed', f'{method} not allowed on log')


def _handle_errors(mc, method, path):
    uuid = mc.GetUUIDByPath(path)
    if not uuid:
        raise ApiError(404, 'macro_not_found', f'No macro at path: {path}')

    if method == 'DELETE':
        mc.ClearMacroErrors(uuid)
        return 204, 'No Content', None

    raise ApiError(405, 'method_not_allowed',
                    f'{method} not allowed on errors (GET /macros/{{path}} already includes errors)')
