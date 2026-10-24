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

    def _scene_response(self, path, width, cells=None):
        try:
            params = {}
            if width:
                params["plan_width_m"] = width
            if cells:
                params["grid_width"] = cells
            p = plan_mod.load_plan(path, **params)
            body = scene_mod.scene_json(p).encode()
        except Exception as e:  # parser boundary: never leak a traceback
            return self._send(422, ("parse failed: %s" % e).encode())
        return self._send(200, body, "application/json")

    @staticmethod
    def _width(query):
        qs = parse_qs(query)
        raw = (qs.get("width") or [""])[0]
        if not raw:
            return None
        try:
            w = float(raw)
        except ValueError:
            return -1
        return w if 1.0 <= w <= 200.0 else -1

    @staticmethod
    def _cells(query):
        """Grid resolution (model scale, in cells across the image)."""
        qs = parse_qs(query)
        raw = (qs.get("cells") or [""])[0]
        if not raw:
            return None
        try:
            n = int(raw)
        except ValueError:
            return -1
        return n if 16 <= n <= 256 else -1

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/scene":
            name = (parse_qs(url.query).get("plan") or [""])[0]
            width = self._width(url.query)
            if width == -1:
                return self._send(400, b"width must be meters in [1,200]")
            cells = self._cells(url.query)
            if cells == -1:
                return self._send(400, b"cells must be an int in [16,256]")
            base = posixpath.basename(name)
            if name != base or not name.endswith(".png"):
                return self._send(400, b"bad plan name")
            path = os.path.join(FIXTURES, base)
            if not os.path.isfile(path):
                return self._send(404, b"no such plan")
            return self._scene_response(path, width, cells)

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


    def do_POST(self):
        # Upload a plan PNG (raw body) -> parsed scene. Loopback tool:
        # body capped, written to a temp file, deleted after parsing.
        if urlparse(self.path).path != "/api/plan":
            return self._send(404, b"not found")
        width = self._width(urlparse(self.path).query)
        if width == -1:
            return self._send(400, b"width must be meters in [1,200]")
        cells = self._cells(urlparse(self.path).query)
        if cells == -1:
            return self._send(400, b"cells must be an int in [16,256]")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._send(400, b"bad content-length")
        if not 1 <= length <= 20 * 1024 * 1024:
            return self._send(413, b"body must be 1 byte..20MB")
        data = self.rfile.read(length)
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return self._scene_response(path, width, cells)
        finally:
            os.unlink(path)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("walkthru on http://127.0.0.1:%d/?plan=flat1.png" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
