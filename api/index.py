from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, base64, time, os, mimetypes, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Optional password gate (HTTP Basic Auth). Set APP_PASSWORD env var on Vercel to enable.
APP_USER = os.environ.get('APP_USER', 'scouts').lstrip('﻿').strip()
APP_PASSWORD = os.environ.get('APP_PASSWORD', '').lstrip('﻿').strip()


def forward(url, data, headers):
    r = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.read(), resp.getcode()
    except urllib.error.HTTPError as e:
        return e.read(), e.code


class handler(BaseHTTPRequestHandler):
    def _authed(self):
        if not APP_PASSWORD:
            return True
        h = self.headers.get('Authorization', '')
        if h.startswith('Basic '):
            try:
                u, p = base64.b64decode(h[6:]).decode('utf-8').split(':', 1)
                return u == APP_USER and p == APP_PASSWORD
            except Exception:
                return False
        return False

    def _deny(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Scouts Board"')
        self.send_header('Content-Length', '0')
        self.end_headers()

    # ---- serve the static frontend (index.html + assets) ----
    def do_GET(self):
        if not self._authed():
            return self._deny()
        path = urlparse(self.path).path
        if path in ('', '/'):
            path = '/index.html'
        fp = os.path.normpath(os.path.join(ROOT, path.lstrip('/')))
        if not fp.startswith(ROOT) or not os.path.isfile(fp):
            fp = os.path.join(ROOT, 'index.html')  # SPA fallback
        try:
            with open(fp, 'rb') as f:
                data = f.read()
            ctype = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()

    # ---- proxy to the AI APIs (POST) ----
    def do_POST(self):
        if not self._authed():
            return self._deny()
        ep = parse_qs(urlparse(self.path).query).get('endpoint', [''])[0]
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        try:
            req = json.loads(raw or b'{}')
            key = req.get('key', '')
            if ep == 'gemini':
                model = req.get('model', 'gemini-2.5-flash-image')
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
                data, code = forward(url, payload, {'Content-Type': 'application/json'})
            elif ep == 'claude':
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                data, code = forward("https://api.anthropic.com/v1/messages", payload, {
                    'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01'})
            elif ep == 'openai':
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                data, code = forward("https://api.openai.com/v1/images/generations", payload, {
                    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
            elif ep == 'openai_edit':
                model = str(req.get('model', 'gpt-image-2'))
                prompt = str(req.get('prompt', ''))
                size = str(req.get('size', '1024x1024'))
                images = req.get('images', []) or []
                boundary = '----scoutsboundary%d' % int(time.time() * 1000)
                bnd = ('--' + boundary).encode()
                body = b''
                for name, value in (('model', model), ('prompt', prompt), ('size', size)):
                    body += bnd + b'\r\n' + ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode() + value.encode('utf-8') + b'\r\n'
                for i, img in enumerate(images):
                    img = str(img)
                    b64 = img.split(',', 1)[1] if img.startswith('data:') and ',' in img else img
                    ri = base64.b64decode(b64)
                    body += bnd + b'\r\n' + ('Content-Disposition: form-data; name="image[]"; filename="img%d.png"\r\n' % i).encode() + b'Content-Type: image/png\r\n\r\n' + ri + b'\r\n'
                body += bnd + b'--\r\n'
                data, code = forward("https://api.openai.com/v1/images/edits", body, {
                    'Authorization': 'Bearer ' + key, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
            else:
                data, code = json.dumps({'error': {'message': 'unknown endpoint'}}).encode(), 404
        except Exception as e:
            data, code = json.dumps({'error': {'message': str(e)}}).encode(), 500
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
