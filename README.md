# walkthru

Walk a floor plan in first person, straight from an image. Zero
dependencies: the parser is Python stdlib, the client is one HTML file
with vanilla JS and canvas. Same plan, same walk, forever — nothing is
invented, every wall you see came from a dark pixel.

For anyone who needs to walk a space that does not exist yet (an
unbuilt house, a venue layout) or that they cannot visit, from nothing
more than a plan image.

## Play

```sh
python3 fixtures/gen_plans.py        # regenerate the demo plans
python3 -m walkthru.server 8000
# open http://127.0.0.1:8000/?plan=flat1.png
```

WASD to move (A/D strafe), arrow left/right to turn. The minimap
colors each detected room; the HUD shows the room you are standing in
and its measured area.

## How it works

- `walkthru/pngio.py` — minimal 8-bit PNG reader/writer (zlib +
  struct, defiltering included). Honest subset: gray/RGB/RGBA,
  non-interlaced; anything else is a clear error.
- `walkthru/plan.py` — the parser. Downsamples to an occupancy grid
  (block-minimum luma, so thin walls survive), detects doors as short
  floor runs piercing a wall, flood-fills rooms, extracts axis-aligned
  wall rectangles, and picks a spawn. Scale is a declared parameter
  (`plan_width_m`), because an image cannot prove its own size.
- `walkthru/scene.py` — Plan → compact deterministic JSON.
- `walkthru/server.py` — stdlib `http.server`, loopback by default;
  serves `www/` and `/api/scene?plan=<name>` (names resolve strictly
  inside `fixtures/`).
- `www/index.html` — the whole client: a DDA raycaster on canvas
  (Wolfenstein-style — a floor plan needs no mesh), doors rendered in
  wood, fog with distance, minimap, room HUD.
- `fixtures/gen_plans.py` — deterministic demo plans (three layouts);
  fixtures are generated, never hand-edited.
- `tests/` — offline `unittest` suite; loopback-only. Asserts room and
  door counts against the known layouts, wall-rectangle coverage is
  exact and non-overlapping, scale math, byte-identical determinism,
  and server path handling.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Status

Checkpoint 1 (MVP): floor-plan image → parsed rooms, doors, walls →
walkable first-person view with measured room areas. The walkthrough
engine is a 2.5D raycaster by design — grids are what floor plans
give you, and grids are what a raycaster eats.

MIT license.
