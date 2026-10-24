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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

    def test_width_param_scales_scene(self):
        status, body = self.get("/api/scene?plan=flat1.png&width=24")
        self.assertEqual(status, 200)
        scene12 = json.loads(self.get("/api/scene?plan=flat1.png")[1])
        scene24 = json.loads(body)
        self.assertAlmostEqual(scene12["cell_m"] * 2, scene24["cell_m"])
        self.assertAlmostEqual(scene12["rooms"][0]["area_m2"] * 4,
                               scene24["rooms"][0]["area_m2"], places=1)

    def test_width_validated(self):
        for bad in ("0", "-5", "999", "abc"):
            status, _ = self.get("/api/scene?plan=flat1.png&width=" + bad)
            self.assertEqual(status, 400, bad)

    def test_upload_plan(self):
        with open(os.path.join(ROOT, "fixtures", "flat1.png"), "rb") as f:
            data = f.read()
        url = "http://127.0.0.1:%d/api/plan?width=18" % self.port
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            scene = json.loads(r.read())
        self.assertEqual(scene["width"], 96)
        self.assertEqual(len(scene["rooms"]), 3)
        self.assertAlmostEqual(scene["cell_m"], 18.0 * 2 / 192)

    def test_upload_rejects_garbage(self):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/plan" % self.port,
            data=b"not a png", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code; e.read(); e.close()
        self.assertEqual(status, 422)

    def test_upload_rejects_bad_width(self):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/plan?width=0" % self.port,
            data=b"x", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code; e.read(); e.close()
        self.assertEqual(status, 400)

    def test_cells_param_scales_grid(self):
        status, body = self.get("/api/scene?plan=flat1.png&cells=48")
        self.assertEqual(status, 200)
        scene = json.loads(body)
        self.assertEqual(scene["width"], 48)
        self.assertEqual(len(scene["rooms"]), 3)

    def test_cells_validated(self):
        for bad in ("8", "999", "abc"):
            status, _ = self.get("/api/scene?plan=flat1.png&cells=" + bad)
            self.assertEqual(status, 400, bad)

    def test_no_subpath_serving(self):
        status, _ = self.get("/walkthru/plan.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
