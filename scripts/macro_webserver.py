"""
webserverDAT callbacks

dat - the connected Web Server DAT
request - A dictionary of the request fields. The dictionary will always
	contain the below entries, plus any additional entries dependent on the
	contents of the request
		'method' - The HTTP method of the request (ie. 'GET', 'PUT').
		'uri' - The client's requested URI path. If there are parameters
			in the URI then they will be located under the 'pars' key in
			the request dictionary.
		'pars' - The query parameters.
		'clientAddress' - The client's address.
		'serverAddress' - The server's address.
		'data' - The data of the HTTP request.
response - A dictionary defining the response, to be filled in during the
	request method. Additional fields not specified below can be added
	(eg. response['content-type'] = 'application/json').
		'statusCode' - A valid HTTP status code integer (ie. 200, 401, 404).
			Default is 404.
		'statusReason' - The reason for the above status code being returned
			(ie. 'Not Found.').
		'data' - The data to send back to the client. If displaying a
			web-page, any HTML would be put here.
"""
from json import loads, dumps
from typing import Dict, Any

from macro_api_router import route_request

# return the response dictionary
def onHTTPRequest(dat: webserverDAT, request: Dict[str, Any],
				  response: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Called when an HTTP request is received. Parses the request, delegates
	routing to macro_api_router.route_request(), and writes the result back
	into the response dict. Also handles CORS headers and OPTIONS preflight,
	since browser-based clients (e.g. a show-control UI) call this API from a
	different origin and this API has no auth to gate that with.

	Args:
		dat: The connected Web Server DAT
		request: Dictionary of request fields
		response: Dictionary defining the response to be filled in

	Returns:
		Dict[str, Any]: The response dictionary
	"""
	response['Access-Control-Allow-Origin'] = '*'
	response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
	response['Access-Control-Allow-Headers'] = 'Content-Type'

	method = request.get('method', 'GET')
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

	status, reason, payload = route_request(method, uri, pars, body)
	response['statusCode'] = status
	response['statusReason'] = reason
	response['data'] = dumps(payload) if payload is not None else ''
	return response

def onWebSocketOpen(dat: webserverDAT, client: str, uri: str):
	"""
	Called when a WebSocket connection is opened.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
		uri: The requested URI
	"""
	return

def onWebSocketClose(dat: webserverDAT, client: str):
	"""
	Called when a WebSocket connection is closed.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
	"""
	return

def onWebSocketReceiveText(dat: webserverDAT, client: str, data: str):
	"""
	Called when text data is received via WebSocket.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
		data: The text data received
	"""
	dat.webSocketSendText(client, data)
	return

def onWebSocketReceiveBinary(dat: webserverDAT, client: str, data: bytes):
	"""
	Called when binary data is received via WebSocket.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
		data: The binary data received
	"""
	dat.webSocketSendBinary(client, data)
	return

def onWebSocketReceivePing(dat: webserverDAT, client: str, data: bytes):
	"""
	Called when a ping is received via WebSocket.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
		data: The ping data received
	"""
	dat.webSocketSendPong(client, data=data);
	return

def onWebSocketReceivePong(dat: webserverDAT, client: str, data: bytes):
	"""
	Called when a pong is received via WebSocket.

	Args:
		dat: The connected Web Server DAT
		client: The client identifier
		data: The pong data received
	"""
	return

def onServerStart(dat: webserverDAT):
	"""
	Called when the web server starts.

	Args:
		dat: The connected Web Server DAT
	"""
	return

def onServerStop(dat: webserverDAT):
	"""
	Called when the web server stops.

	Args:
		dat: The connected Web Server DAT
	"""
	return
