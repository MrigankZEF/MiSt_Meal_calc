#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import os
ROOT = os.path.dirname(__file__)
SNAP = os.path.join(ROOT, '..', 'mist-mealcalc-snapshot.html')
# also check workspace root snapshot location
WORKSPACE_SNAP = os.path.abspath(os.path.join(ROOT, '..', '..', 'mist-mealcalc-snapshot.html'))
if os.path.exists(WORKSPACE_SNAP):
    SNAP = WORKSPACE_SNAP


class Handler(BaseHTTPRequestHandler):
    def _set(self, code=200, ct='application/json'):
        self.send_response(code)
        self.send_header('Content-type', ct)
        self.end_headers()
    def do_GET(self):
        p = urlparse(self.path)
        if p.path == '/':
            # serve snapshot if exists
            try:
                with open(SNAP, 'rb') as f:
                    content = f.read()
                self._set(200, 'text/html')
                self.wfile.write(content)
            except Exception:
                self._set(404,'text/plain')
                self.wfile.write(b'No snapshot')
            return
        if p.path == '/ingredient':
            q = parse_qs(p.query).get('name',[''])[0]
            canned = [
                {'name':'potato','score':95},
                {'name':'sweet potatoes','score':78},
                {'name':'mashed potato','score':60}
            ]
            self._set(200)
            self.wfile.write(json.dumps({'matches':canned}).encode())
            return
        self._set(404,'text/plain')
        self.wfile.write(b'Not found')

    def do_POST(self):
        p = urlparse(self.path)
        length = int(self.headers.get('content-length',0))
        body = self.rfile.read(length) if length>0 else b''
        try:
            payload = json.loads(body.decode() or '{}')
        except Exception:
            payload = {}
        if p.path == '/meal':
            items = payload.get('items',[]) if isinstance(payload, dict) else []
            total = 0.0
            details = []
            for it in items:
                name = it.get('name','')
                amt = float(it.get('amount') or 0)
                kg = amt/1000.0
                contrib = round(0.2 * kg, 4)
                total += contrib
                details.append({'requested': name, 'matched': name, 'score': 90, 'contrib': contrib})
            self._set(200)
            self.wfile.write(json.dumps({'total_co2_kgCO2eq': round(total,4), 'details': details}).encode())
            return
        if p.path == '/export':
            # return CSV minimal
            items = payload.get('items',[])
            rows = ['requested,matched,score,contrib']
            for it in items:
                name = it.get('name','')
                rows.append(f'{name},{name},90,0.0')
            self._set(200,'text/csv')
            self.wfile.write('\n'.join(rows).encode())
            return
        if p.path == '/missing':
            items = payload.get('items',[])
            missing = []
            for it in items:
                name = it.get('name','')
                # fake: nothing missing
            self._set(200)
            self.wfile.write(json.dumps({'missing': []}).encode())
            return
        self._set(404,'text/plain')
        self.wfile.write(b'Not found')

if __name__=='__main__':
    server_address = ('127.0.0.1', 9000)
    httpd = HTTPServer(server_address, Handler)
    print('Mock server running at http://127.0.0.1:9000')
    httpd.serve_forever()
