"""Offline unittest suite for walkthru. Loopback-only; run from repo root:
    python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from walkthru import pngio, plan as plan_mod, scene as scene_mod  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "fixtures")


def fixture_path(name):
    path = os.path.join(FIX, name)
    if not os.path.isfile(path):
        raise RuntimeError("fixtures missing — run: python3 fixtures/gen_plans.py")
    return path


class TestPngio(unittest.TestCase):
    def test_roundtrip(self):
        path = os.path.join(ROOT, "tests", "_roundtrip.png")
        rows = [[(x % 256, y % 256, (x + y) % 256) for x in range(17)]
                for y in range(11)]
        pngio.write_png(path, 17, 11, rows)
        w, h, out = pngio.read_png(path)
        os.unlink(path)
        self.assertEqual((w, h), (17, 11))
        self.assertEqual(out, rows)

    def test_rejects_non_png(self):
        path = os.path.join(ROOT, "tests", "_junk.png")
        with open(path, "wb") as f:
            f.write(b"not a png at all")
        with self.assertRaises(ValueError):
            pngio.read_png(path)
        os.unlink(path)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.plans = {name: plan_mod.load_plan(fixture_path(name))
                      for name in ("flat1.png", "venue.png", "offices.png")}

    def test_expected_room_counts(self):
        self.assertEqual(len(self.plans["flat1.png"].rooms), 3)
        self.assertEqual(len(self.plans["venue.png"].rooms), 5)
        self.assertEqual(len(self.plans["offices.png"].rooms), 5)

    def test_doors_detected(self):
        for name, minimum in (("flat1.png", 2), ("venue.png", 4),
                              ("offices.png", 4)):
            self.assertGreaterEqual(len(self.plans[name].doors), minimum,
                                    "%s: doors" % name)

    def test_grid_dimensions_and_values(self):
        p = self.plans["flat1.png"]
        self.assertEqual(p.width, 96)
        self.assertEqual(p.height, 72)
        for row in p.grid:
            for v in row:
                self.assertIn(v, (plan_mod.WALL, plan_mod.FLOOR,
                                  plan_mod.DOOR, plan_mod.VOID))

    def test_spawn_is_walkable_floor_of_largest_room(self):
        for name, p in self.plans.items():
            self.assertIsNotNone(p.spawn, name)
            x, y = p.spawn
            self.assertTrue(p.walkable(x, y), name)
            biggest = p.rooms[0]
            self.assertIn(p.spawn, biggest.cells, name)

    def test_wall_rects_cover_every_wall_cell_exactly_once(self):
        for name, p in self.plans.items():
            total = sum(1 for row in p.grid for v in row
                        if v in (plan_mod.WALL, plan_mod.VOID))
            covered = 0
            for (x0, y0, x1, y1) in p.walls:
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        self.assertIn(p.grid[y][x],
                                      (plan_mod.WALL, plan_mod.VOID),
                                      "%s: rect over floor at %d,%d" % (name, x, y))
                        covered += 1
            self.assertEqual(covered, total, name)

    def test_scale_is_declared_not_invented(self):
        p = self.plans["flat1.png"]  # 192px wide, block=2 -> cell_m = 12*2/192
        self.assertAlmostEqual(p.cell_m, 0.125)

    def test_deterministic(self):
        for name in ("flat1.png", "venue.png", "offices.png"):
            a = scene_mod.scene_json(plan_mod.load_plan(fixture_path(name)))
            b = scene_mod.scene_json(plan_mod.load_plan(fixture_path(name)))
            self.assertEqual(a, b, name)


class TestScene(unittest.TestCase):
    def setUp(self):
        self.plan = plan_mod.load_plan(fixture_path("flat1.png"))

    def test_scene_shape(self):
        s = scene_mod.build_scene(self.plan)
        self.assertEqual(len(s["grid"]), self.plan.height)
        self.assertEqual(len(s["grid"][0]), self.plan.width)
        self.assertEqual(len(s["room_ids"]), self.plan.height)
        self.assertEqual(s["spawn"], list(self.plan.spawn))
        self.assertGreater(s["wall_height_m"], 0)
        json.loads(scene_mod.scene_json(self.plan))  # serializable, sorted

    def test_room_ids_match_room_membership(self):
        s = scene_mod.build_scene(self.plan)
        for room in self.plan.rooms:
            for (x, y) in room.cells:
                self.assertEqual(int(s["room_ids"][y][x]), room.id)

    def test_spawn_json_is_floor(self):
        s = scene_mod.build_scene(self.plan)
        x, y = s["spawn"]
        self.assertEqual(int(s["grid"][y][x]), plan_mod.FLOOR)


if __name__ == "__main__":
    unittest.main()
