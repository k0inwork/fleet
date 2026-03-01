import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Simple in-memory store
db = {}

class MockFirebaseHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_GET(self):
        path = self.path.split('.json')[0].strip('/')
        keys = [k for k in path.split('/') if k]

        current = db
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return self._send_json(None)
        self._send_json(current)

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            data = json.loads(self.rfile.read(content_length))
        else:
            data = None

        path = self.path.split('.json')[0].strip('/')
        keys = [k for k in path.split('/') if k]

        current = db
        for k in keys[:-1]:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        current[keys[-1]] = data
        self._send_json(data)

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(content_length)) if content_length > 0 else None

        path = self.path.split('.json')[0].strip('/')
        keys = [k for k in path.split('/') if k]

        current = db
        for k in keys:
            if k not in current or not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]

        new_id = str(len(current))
        current[new_id] = data
        self._send_json({"name": new_id})

    def log_message(self, format, *args):
        return

def run_server(port=8888):
    server = HTTPServer(('localhost', port), MockFirebaseHandler)
    print(f"Mock Firebase running on http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
