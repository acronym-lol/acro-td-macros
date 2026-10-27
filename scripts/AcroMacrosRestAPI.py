"""
AcroMacrosRestAPI.py

REST API bridge for AcroMacros. Handles the webserver_api DAT's HTTP
callback (CORS, JSON body parsing) and delegates actual routing to
macro_api_router.route_request().

Lives as a second extension on the same component as AcroMacros itself (see
/AcroMacros's Extensions page - slot 0 is AcroMacros, slot 1 is this). That
placement is the whole point: because this extension's ownerComp is always
the component AcroMacros is attached to, macro_api_router never has to
assume/hardcode an absolute path like op('/AcroMacros') - it just uses
whatever ownerComp is handed to it.
"""
from json import loads, dumps
from typing import Any, Dict

from macro_api_router import route_request


class AcroMacrosRestAPI:
    """ REST API bridge - routes webserver_api's HTTP callback to macro_api_router. """

    def __init__(self, ownerComp: Any) -> None:
        """
        Initialize the AcroMacrosRestAPI extension.

        :param ownerComp: The component this extension is attached to - the
            same component AcroMacros (extension slot 0) lives on.
        """
        self.ownerComp = ownerComp

    def OnHTTPRequest(self, dat: 'webserverDAT', request: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle one HTTP request from webserver_api. Called by
        macro_webserver.py's onHTTPRequest, which just forwards here.

        Sets CORS headers on every response (this API has no auth, and
        browser-based clients call it from a different origin), answers
        OPTIONS preflight directly, validates the JSON body, then delegates
        to macro_api_router.route_request() for the actual routing.

        :param dat: The connected Web Server DAT (webserver_api).
        :param request: Dictionary of request fields (method, uri, pars, data, ...).
        :param response: Dictionary defining the response to be filled in.
        :return: The response dictionary.
        """
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type'
        # Let the browser cache the preflight result for a day, so a chatty
        # client doesn't re-send an OPTIONS request before every single call.
        response['Access-Control-Max-Age'] = '86400'

        # Normalize casing defensively - real clients send uppercase per the
        # HTTP spec, but comparisons below (and in macro_api_router) are
        # exact-match ('GET', 'POST', ...).
        method = (request.get('method') or 'GET').upper()
        if method == 'OPTIONS':
            # preflight - no body needed
            response['statusCode'] = 204
            response['statusReason'] = 'No Content'
            response['data'] = ''
            return response

        uri = request.get('uri', '')
        pars = request.get('pars') or {}
        raw_data = request.get('data') or ''

        response['content-type'] = 'application/json'

        body = {}
        if raw_data:
            try:
                body = loads(raw_data)
            except Exception:
                response['statusCode'] = 400
                response['statusReason'] = 'Bad Request'
                response['data'] = dumps({'error': {'code': 'invalid_json', 'message': 'Request body is not valid JSON'}})
                return response
            # Valid JSON doesn't guarantee an object - "42", "null", '"x"'
            # and "[1,2]" all parse fine but have no .get(), which every
            # route handler in macro_api_router relies on. Reject those
            # cleanly here instead of letting them surface as a 500 deep
            # inside a handler.
            if not isinstance(body, dict):
                response['statusCode'] = 400
                response['statusReason'] = 'Bad Request'
                response['data'] = dumps({'error': {'code': 'invalid_body', 'message': 'Request body must be a JSON object'}})
                return response

        status, reason, payload = route_request(self.ownerComp, method, uri, pars, body)
        response['statusCode'] = status
        response['statusReason'] = reason
        response['data'] = dumps(payload) if payload is not None else ''
        return response
