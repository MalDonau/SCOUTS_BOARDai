import os, json, base64, time, urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# serve files from this script's folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))
_seq = [0]

# Optional password gate (HTTP Basic Auth). Set APP_PASSWORD to enable it.
APP_USER = os.environ.get('APP_USER', 'scouts')
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')

class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, max-age=0')
        super().end_headers()

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

    def do_GET(self):
        if not self._authed():
            return self._deny()
        return super().do_GET()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def _send_json(self, code, obj):
        data = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self._cors()
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self._authed():
            return self._deny()
        path = self.path.split('?')[0]
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
        if path == '/gemini':
            try:
                req = json.loads(raw or b'{}')
                model = req.get('model', 'gemini-2.5-flash-image')
                key = req.get('key', '')
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model, key)
                r = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
                try:
                    with urllib.request.urlopen(r, timeout=180) as resp:
                        data = resp.read(); code = resp.getcode()
                except urllib.error.HTTPError as e:
                    data = e.read(); code = e.code
            except Exception as e:
                data = json.dumps({'error': {'message': str(e)}}).encode(); code = 500
            self._send_json(code, data)
        elif path == '/claude':
            try:
                req = json.loads(raw or b'{}')
                key = req.get('key', '')
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                url = "https://api.anthropic.com/v1/messages"
                r = urllib.request.Request(url, data=payload, headers={
                    'Content-Type': 'application/json',
                    'x-api-key': key,
                    'anthropic-version': '2023-06-01',
                }, method='POST')
                try:
                    with urllib.request.urlopen(r, timeout=180) as resp:
                        data = resp.read(); code = resp.getcode()
                except urllib.error.HTTPError as e:
                    data = e.read(); code = e.code
            except Exception as e:
                data = json.dumps({'error': {'message': str(e)}}).encode(); code = 500
            self._send_json(code, data)
        elif path == '/openai':
            try:
                req = json.loads(raw or b'{}')
                key = req.get('key', '')
                payload = json.dumps(req.get('body', {})).encode('utf-8')
                url = "https://api.openai.com/v1/images/generations"
                r = urllib.request.Request(url, data=payload, headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + key,
                }, method='POST')
                try:
                    with urllib.request.urlopen(r, timeout=180) as resp:
                        data = resp.read(); code = resp.getcode()
                except urllib.error.HTTPError as e:
                    data = e.read(); code = e.code
            except Exception as e:
                data = json.dumps({'error': {'message': str(e)}}).encode(); code = 500
            self._send_json(code, data)
        elif path == '/openai_edit':
            try:
                req = json.loads(raw or b'{}')
                key = req.get('key', '')
                model = str(req.get('model', 'gpt-image-2'))
                prompt = str(req.get('prompt', ''))
                size = str(req.get('size', '1024x1024'))
                images = req.get('images', []) or []
                boundary = '----scoutsboundary%d' % int(time.time() * 1000)
                bnd = ('--' + boundary).encode()
                body = b''
                for name, value in (('model', model), ('prompt', prompt), ('size', size)):
                    body += bnd + b'\r\n'
                    body += ('Content-Disposition: form-data; name="%s"\r\n\r\n' % name).encode()
                    body += value.encode('utf-8') + b'\r\n'
                for i, img in enumerate(images):
                    img = str(img)
                    b64 = img.split(',', 1)[1] if img.startswith('data:') and ',' in img else img
                    raw_img = base64.b64decode(b64)
                    body += bnd + b'\r\n'
                    body += ('Content-Disposition: form-data; name="image[]"; filename="img%d.png"\r\n' % i).encode()
                    body += b'Content-Type: image/png\r\n\r\n'
                    body += raw_img + b'\r\n'
                body += bnd + b'--\r\n'
                r = urllib.request.Request('https://api.openai.com/v1/images/edits', data=body, headers={
                    'Authorization': 'Bearer ' + key,
                    'Content-Type': 'multipart/form-data; boundary=' + boundary,
                }, method='POST')
                try:
                    with urllib.request.urlopen(r, timeout=300) as resp:
                        data = resp.read(); code = resp.getcode()
                except urllib.error.HTTPError as e:
                    data = e.read(); code = e.code
            except Exception as e:
                data = json.dumps({'error': {'message': str(e)}}).encode(); code = 500
            self._send_json(code, data)
        elif path == '/save':
            try:
                req = json.loads(raw or b'{}')
                scout = ''.join(c for c in str(req.get('scout', 'misc')) if c.isalnum() or c in '-_')[:40] or 'misc'
                kind = ''.join(c for c in str(req.get('kind', 'img')) if c.isalnum())[:20] or 'img'
                head, b64 = req.get('dataURL', '').split(',', 1)
                ext = 'png'
                if 'jpeg' in head or 'jpg' in head: ext = 'jpg'
                elif 'webp' in head: ext = 'webp'
                elif 'svg' in head: ext = 'svg'
                _seq[0] += 1
                d = os.path.join('assets', 'gen', scout)
                os.makedirs(d, exist_ok=True)
                name = '%s-%d-%d.%s' % (kind, int(time.time()), _seq[0], ext)
                with open(os.path.join(d, name), 'wb') as f:
                    f.write(base64.b64decode(b64))
                self._send_json(200, {'ok': True, 'path': 'assets/gen/%s/%s' % (scout, name)})
            except Exception as e:
                self._send_json(500, {'ok': False, 'error': str(e)})
        else:
            self.send_response(404); self.end_headers()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    host = os.environ.get('HOST', '0.0.0.0')
    print('Scouts proxy running on http://%s:%d' % (host, port))
    ThreadingHTTPServer((host, port), H).serve_forever()
