from http.server import BaseHTTPRequestHandler
import json, urllib.request, urllib.error


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            req = json.loads(raw or b'{}')
            model = req.get('model', 'gemini-2.5-flash-image')
            key = req.get('key', '')
            payload = json.dumps(req.get('body', {})).encode('utf-8')
            url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
            r = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
            try:
                with urllib.request.urlopen(r, timeout=120) as resp:
                    data = resp.read(); code = resp.getcode()
            except urllib.error.HTTPError as e:
                data = e.read(); code = e.code
        except Exception as e:
            data = json.dumps({'error': {'message': str(e)}}).encode(); code = 500
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
