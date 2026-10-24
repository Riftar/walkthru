"""Loopback dev server: static client + /api/scene?plan=<name>.

python3 -m walkthru.server [port]  — binds 127.0.0.1 only.
Plan names are resolved strictly inside fixtures/ (basename check);
there is no path handling beyond that, on purpose.
"""
import json
import os
import posixpath
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import plan as plan_mod
from . import scene as scene_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WWW = os.path.join(ROOT, "www")
FIXTURES = os.path.join(ROOT, "fixtures")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
         ".css": "text/css", ".png": "image/png", ".json": "application/json"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet; tests parse stdout-free

    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/scene":
            qs = parse_qs(url.query)
            name = (qs.get("plan") or [""])[0]
            base = posixpath.basename(name)
            if name != base or not name.endswith(".png"):
                return self._send(400, b"bad plan name")
            path = os.path.join(FIXTURES, base)
            if not os.path.isfile(path):
                return self._send(404, b"no such plan")
            try:
                p = plan_mod.load_plan(path)
                body = scene_mod.scene_json(p).encode()
            except Exception as e:  # parser boundary: never leak a traceback
                return self._send(422, ("parse failed: %s" % e).encode())
            return self._send(200, body, "application/json")

        rel = "index.html" if url.path == "/" else url.path.lstrip("/")
        base = posixpath.basename(rel)
        if rel != base and rel != "index.html":  # no subpaths served
            return self._send(404, b"not found")
        path = os.path.join(WWW, rel)
        if not os.path.isfile(path):
            return self._send(404, b"not found")
        with open(path, "rb") as f:
            body = f.read()
        ext = os.path.splitext(rel)[1]
        return self._send(200, body, TYPES.get(ext, "application/octet-stream"))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("walkthru on http://127.0.0.1:%d/?plan=flat1.png" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
