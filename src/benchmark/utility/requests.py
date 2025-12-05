import http.client
import urllib.parse
import json as js

class Response:
    def __init__(self, status, data):
        self.status_code = status
        self.text = data
        self.ok = 200 <= status < 300

    def json(self):
        return js.loads(self.text)

def get(url, timeout=5):
    parsed = urllib.parse.urlparse(url)
    conn_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_class(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), timeout=timeout)
    path = parsed.path or "/"
    print(path, flush=True)
    if parsed.query:
        path += "?" + parsed.query
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        data = resp.read().decode()
        return Response(resp.status, data)
    finally:
        conn.close()

def post(url, json=None, timeout=5):
    parsed = urllib.parse.urlparse(url)
    conn_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    conn = conn_class(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), timeout=timeout)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    body = None
    headers = {}
    if json is not None:
        body = js.dumps(json)
        headers["Content-Type"] = "application/json"
    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read().decode()
        return Response(resp.status, data)
    finally:
        conn.close()