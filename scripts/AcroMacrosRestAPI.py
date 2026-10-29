"""
AcroMacrosRestAPI.py

REST API bridge for AcroMacros. Handles the webserver_api DAT's HTTP
callback (access checks, CORS, JSON body parsing) and delegates actual
routing to macro_api_router.route_request().

Lives as a second extension on the same component as AcroMacros itself (see
/AcroMacros's Extensions page - slot 0 is AcroMacros, slot 1 is this). That
placement is the whole point: because this extension's ownerComp is always
the component AcroMacros is attached to, macro_api_router never has to
assume/hardcode an absolute path like op('/AcroMacros') - it just uses
whatever ownerComp is handed to it.

Access rules (configured on the API page's Security group):
- Every request must send 'Authorization: Bearer <key>', where the key is in
  the environment variable named by Apikeyenv. With no key set up, the API
  rejects everything.
- Requests from other machines are refused unless Allowremote is on. This is
  a filter, not the security boundary: the webserverDAT lets a request header
  named 'clientAddress' overwrite the real client address, so only the key
  can be relied on.
- Browser pages may call the API only from origins listed in Alloworigins.
"""
from fnmatch import fnmatchcase
import hmac
import ipaddress
import os
from json import loads, dumps
from typing import Any, Dict

from macro_api_router import route_request


def _header(request: Dict[str, Any], name: str) -> str:
    """Case-insensitive lookup of an HTTP header in the webserverDAT request dict."""
    name = name.lower()
    for key, value in request.items():
        if isinstance(key, str) and key.lower() == name:
            return str(value)
    return ''


def _hostPart(address: str) -> str:
    """Strip the port from 'host:port' or '[v6]:port'."""
    address = (address or '').strip()
    if address.startswith('['):
        return address[1:].split(']', 1)[0]
    if address.count(':') == 1:
        return address.split(':', 1)[0]
    return address


def _isLoopbackClient(address: str) -> bool:
    """True if the client address (as reported by the webserverDAT) is this machine."""
    try:
        ip = ipaddress.ip_address(_hostPart(address))
    except ValueError:
        return False
    if getattr(ip, 'ipv4_mapped', None):
        ip = ip.ipv4_mapped
    return ip.is_loopback


class AcroMacrosRestAPI:
    """ REST API bridge - routes webserver_api's HTTP callback to macro_api_router. """

    def __init__(self, ownerComp: Any) -> None:
        """
        Initialize the AcroMacrosRestAPI extension.

        :param ownerComp: The component this extension is attached to - the
            same component AcroMacros (extension slot 0) lives on.
        """
        self.ownerComp = ownerComp
        self._ensureSecurityPars()

    def _ensureSecurityPars(self) -> None:
        """
        Add the Security group to the API page, and move the TLS certificate
        password out of a saved parameter. Idempotent.
        """
        comp = self.ownerComp
        page = next((p for p in comp.customPages if p.name == 'API'), None)
        if page is None:
            return

        # The certificate password used to live in Webserverpassword, which saved
        # it into the .tox. It now comes from the environment variable named by
        # Webserverpasswordenv. Repoint webserver_api's password before
        # destroying the parameter it was bound to.
        api = comp.op('webserver_api')
        if api is not None:
            password = api.par.password
            if password.mode != ParMode.EXPRESSION or password.expr != 'parent.AM.CertificatePassword':
                password.expr = 'parent.AM.CertificatePassword'
                password.mode = ParMode.EXPRESSION
            # The constant value and old bind would otherwise keep a saved copy
            if password.val or password.bindExpr:
                password.val = ''
                password.bindExpr = ''
        if hasattr(comp.par, 'Webserverpassword'):
            old = comp.par.Webserverpassword
            if old.eval():
                debug(f"{comp.path}: removed the saved Webserverpassword parameter. Put the certificate "
                      f"password in an environment variable and enter that variable's name in "
                      f"Webserverpasswordenv.")
            old.destroy()
        if not hasattr(comp.par, 'Webserverpasswordenv'):
            par = page.appendStr('Webserverpasswordenv', label='Certificate Password Env Variable')[0]
            par.help = 'Name of the environment variable that holds the certificate password'

        # (name, label, style, help) - placed after the Web Server group
        securityPars = [
            ('Webserversecurityheader', 'Security', 'Header', ''),
            ('Allowremote', 'Allow Remote Clients', 'Toggle',
             'Accept requests from other machines. They still need the API key.'),
            ('Apikeyenv', 'API Key Env Variable', 'Str',
             'Name of the environment variable that holds the API key. Required: every request '
             'must send "Authorization: Bearer <key>".'),
            ('Alloworigins', 'Allowed Browser Origins', 'Str',
             'Space-separated origins that browser pages may call the API from, e.g. '
             'https://ui.example.com http://192.168.1.*:8080'),
        ]
        for name, label, style, helpText in securityPars:
            if not hasattr(comp.par, name):
                getattr(page, 'append' + style)(name, label=label)
            if helpText:
                getattr(comp.par, name).help = helpText

        # Security group after the Web Server group, the password variable
        # where the password used to be in the TLS group.
        current = [p.name for p in sorted(page.pars, key=lambda p: p.order)]
        security = [name for name, *_ in securityPars]
        wanted = [n for n in current if n not in security and n != 'Webserverpasswordenv']
        wanted.insert(wanted.index('Webservercertificate') + 1 if 'Webservercertificate' in wanted
                      else len(wanted), 'Webserverpasswordenv')
        at = wanted.index('Webservercallbacks') + 1 if 'Webservercallbacks' in wanted else len(wanted)
        wanted[at:at] = security
        if wanted != current:
            page.sort(*wanted)

    def _parValue(self, name: str, default: Any) -> Any:
        par = getattr(self.ownerComp.par, name, None)
        return par.eval() if par is not None else default

    def _envValue(self, parName: str) -> str:
        """The value of the environment variable named by parameter parName, or ''."""
        name = str(self._parValue(parName, '')).strip()
        return os.environ.get(name, '') if name else ''

    @property
    def ApiKey(self) -> str:
        """The API key, from the environment variable named by Apikeyenv ('' if none)."""
        return self._envValue('Apikeyenv')

    @property
    def CertificatePassword(self) -> str:
        """The TLS certificate password, from the environment variable named by Webserverpasswordenv."""
        return self._envValue('Webserverpasswordenv')

    def _originAllowed(self, origin: str) -> bool:
        patterns = str(self._parValue('Alloworigins', '')).split()
        origin = origin.strip().lower()
        return any(fnmatchcase(origin, p.strip().lower().rstrip('/')) for p in patterns)

    def _error(self, response: Dict[str, Any], status: int, reason: str, code: str, message: str) -> Dict[str, Any]:
        response['statusCode'] = status
        response['statusReason'] = reason
        response['content-type'] = 'application/json'
        response['data'] = dumps({'error': {'code': code, 'message': message}})
        return response

    def OnHTTPRequest(self, dat: 'webserverDAT', request: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle one HTTP request from webserver_api. Called by
        webserver_api_callbacks.py's onHTTPRequest, which just forwards here.

        Checks the request's origin, client address and API key (see the
        module docstring), sets CORS headers for allowed browser origins,
        answers OPTIONS preflight directly, validates the JSON body, then
        delegates to macro_api_router.route_request() for the actual routing.

        :param dat: The connected Web Server DAT (webserver_api).
        :param request: Dictionary of request fields (method, uri, pars, data, ...).
        :param response: Dictionary defining the response to be filled in.
        :return: The response dictionary.
        """
        # Normalize casing defensively - real clients send uppercase per the
        # HTTP spec, but comparisons below (and in macro_api_router) are
        # exact-match ('GET', 'POST', ...).
        method = (request.get('method') or 'GET').upper()

        # Browsers send Origin on cross-origin requests. Only listed origins get
        # through: leaving out the CORS headers alone wouldn't stop a simple
        # (text/plain) POST from running - the browser just hides the reply.
        origin = _header(request, 'Origin')
        if origin:
            if not self._originAllowed(origin):
                return self._error(response, 403, 'Forbidden', 'origin_not_allowed',
                                   f'Origin {origin} is not in Alloworigins')
            response['Access-Control-Allow-Origin'] = origin
            response['Vary'] = 'Origin'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            # Let the browser cache the preflight result for a day, so a chatty
            # client doesn't re-send an OPTIONS request before every single call.
            response['Access-Control-Max-Age'] = '86400'
            # Chrome asks this when a public site calls a local-network address.
            if _header(request, 'Access-Control-Request-Private-Network'):
                response['Access-Control-Allow-Private-Network'] = 'true'

        if method == 'OPTIONS':
            # preflight - no body needed, and browsers never send credentials on it
            response['statusCode'] = 204
            response['statusReason'] = 'No Content'
            response['data'] = ''
            return response

        # A best-effort filter only - a 'clientAddress' request header overwrites
        # the real address. The API key below is what actually protects the API.
        if not _isLoopbackClient(request.get('clientAddress', '')) and not self._parValue('Allowremote', False):
            return self._error(response, 403, 'Forbidden', 'remote_not_allowed',
                               'Requests from other machines are off (Allowremote)')

        # Fail closed: no key set up means no access. The variable's name stays
        # in the textport, not the reply.
        keyName = str(self._parValue('Apikeyenv', '')).strip()
        key = os.environ.get(keyName, '') if keyName else ''
        if not key:
            if keyName:
                debug(f"{self.ownerComp.path}: Apikeyenv names {keyName}, which isn't set. "
                      f"Rejecting requests until it is (TouchDesigner reads it at launch).")
            return self._error(response, 503, 'Service Unavailable', 'api_key_not_configured',
                               'The REST API needs an API key: set Apikeyenv on the API page to the name of '
                               'an environment variable that holds it')
        scheme, _, token = _header(request, 'Authorization').partition(' ')
        if scheme.lower() != 'bearer' or not hmac.compare_digest(token.strip().encode(), key.encode()):
            response['WWW-Authenticate'] = 'Bearer'
            return self._error(response, 401, 'Unauthorized', 'unauthorized',
                               'Missing or wrong API key (Authorization: Bearer <key>)')

        uri = request.get('uri', '')
        pars = request.get('pars') or {}
        raw_data = request.get('data') or ''

        response['content-type'] = 'application/json'

        body = {}
        if raw_data:
            # Requiring JSON means a browser must preflight before sending a body.
            contentType = _header(request, 'Content-Type').split(';')[0].strip().lower()
            if contentType != 'application/json':
                return self._error(response, 415, 'Unsupported Media Type', 'unsupported_media_type',
                                   'Request body must be sent as Content-Type: application/json')
            try:
                body = loads(raw_data)
            except Exception:
                return self._error(response, 400, 'Bad Request', 'invalid_json', 'Request body is not valid JSON')
            # Valid JSON doesn't guarantee an object - "42", "null", '"x"'
            # and "[1,2]" all parse fine but have no .get(), which every
            # route handler in macro_api_router relies on. Reject those
            # cleanly here instead of letting them surface as a 500 deep
            # inside a handler.
            if not isinstance(body, dict):
                return self._error(response, 400, 'Bad Request', 'invalid_body', 'Request body must be a JSON object')

        status, reason, payload = route_request(self.ownerComp, method, uri, pars, body)
        response['statusCode'] = status
        response['statusReason'] = reason
        response['data'] = dumps(payload) if payload is not None else ''
        return response
