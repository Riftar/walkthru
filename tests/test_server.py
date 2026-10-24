"""Loopback server tests: static client, scene API, path handling."""
import json
import os
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from walkthru import server as srv  # noqa: E402


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            e.close()
            return e.code, body

    def test_index_served(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<canvas", body)

    def test_scene_api(self):
        status, body = self.get("/api/scene?plan=flat1.png")
        self.assertEqual(status, 200)
        scene = json.loads(body)
        self.assertEqual(scene["width"], 96)
        self.assertIn("spawn", scene)

    def test_rejects_traversal(self):
        for bad in ("../walkthru/plan.py", "..%2Fwalkthru%2Fplan.py",
                    "sub/dir/x.png", ""):
            status, _ = self.get("/api/scene?plan=" + bad)
            self.assertIn(status, (400, 404), bad)

    def test_missing_plan_404(self):
        status, _ = self.get("/api/scene?plan=nope.png")
        self.assertEqual(status, 404)

    def test_no_subpath_serving(self):
        status, _ = self.get("/walkthru/plan.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
