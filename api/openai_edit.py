from http.server import BaseHTTPRequestHandler
import json, base64, time, urllib.request, urllib.error


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b'{}'
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
