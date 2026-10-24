"""Floor-plan parsing: a PNG image -> occupancy grid, doors, rooms, walls.

Deterministic: same image, same parameters, same output. Dark pixels are
walls; light pixels are floor. Doors are narrow floor gaps that pierce a
wall (a short floor run with wall at both ends, horizontally or
vertically). Rooms are connected floor areas once doors are excluded;
tiny fragments become void. Every number here traces to an observation in
the image or to a declared parameter — nothing is invented.
"""
from . import pngio

WALL, FLOOR, DOOR, VOID = 1, 0, 2, 3

DEFAULTS = {
    "grid_width": 96,      # downsample target width, in cells
    "threshold": 128,      # luma <= this -> wall
    "door_max": 3,         # floor run <= this many cells piercing a wall -> door
    "min_room_cells": 12,  # smaller floor fragments -> void
    "plan_width_m": 12.0,  # declared scale: meters across the image width
}


class Room:
    def __init__(self, rid, cells, width, height):
        self.id = rid
        self.cells = cells  # list of (x, y)
        self.area_cells = len(cells)
        self.area_m2 = None  # filled by caller once cell_m known
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.centroid = (sum(xs) / len(xs), sum(ys) / len(ys))

    def as_dict(self):
        return {
            "id": self.id,
            "name": "Room %d" % self.id,
            "area_cells": self.area_cells,
            "area_m2": round(self.area_m2, 2),
            "bbox_cells": list(self.bbox),
        }


class Plan:
    def __init__(self, width, height, cell_m, grid, rooms, doors, walls, spawn):
        self.width = width
        self.height = height
        self.cell_m = cell_m
        self.grid = grid          # rows (top->bottom) of WALL/FLOOR/DOOR/VOID
        self.rooms = rooms        # sorted by area desc
        self.doors = doors        # list of (x, y) cells
        self.walls = walls        # axis-aligned rects (x0, y0, x1, y1) in cells
        self.spawn = spawn        # (x, y) cell in the largest room

    def walkable(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height and \
            self.grid[y][x] in (FLOOR, DOOR)


def _luma(px):
    r, g, b = px
    return (299 * r + 587 * g + 114 * b) // 1000


def load_plan(path, **params):
    """Parse a floor-plan image into a Plan. Keyword params override DEFAULTS."""
    cfg = dict(DEFAULTS)
    cfg.update(params)
    w, h, rows = pngio.read_png(path)

    # Downsample: block-minimum luma so thin walls survive.
    gx = cfg["grid_width"]
    if gx > w:
        gx = w
    block = -(-w // gx)  # ceil division
    gy = -(-h // block)
    grid = [[WALL] * gx for _ in range(gy)]
    for cy in range(gy):
        for cx in range(gx):
            x0, y0 = cx * block, cy * block
            dark = False
            for iy in range(y0, min(y0 + block, h)):
                for ix in range(x0, min(x0 + block, w)):
                    if _luma(rows[iy][ix]) <= cfg["threshold"]:
                        dark = True
                        break
                if dark:
                    break
            grid[cy][cx] = WALL if dark else FLOOR
    # A plan image cannot prove its own scale; that is a declared
    # parameter (meters across the full image width), not an observation.
    plan_width_m = cfg["plan_width_m"]
    cell_m = plan_width_m * block / w

    # Doors: short floor runs with wall at both ends.
    doors = set()
    dm = cfg["door_max"]
    for y in range(gy):
        x = 0
        while x < gx:
            if grid[y][x] == FLOOR:
                run = x
                while run < gx and grid[y][run] == FLOOR:
                    run += 1
                length = run - x
                if length <= dm and x > 0 and run < gx and \
                        grid[y][x - 1] == WALL and grid[y][run] == WALL:
                    for dx in range(x, run):
                        doors.add((dx, y))
                x = run
            else:
                x += 1
    for x in range(gx):
        y = 0
        while y < gy:
            if grid[y][x] == FLOOR:
                run = y
                while run < gy and grid[run][x] == FLOOR:
                    run += 1
                length = run - y
                if length <= dm and y > 0 and run < gy and \
                        grid[y - 1][x] == WALL and grid[run][x] == WALL:
                    for dy in range(y, run):
                        doors.add((x, dy))
                y = run
            else:
                y += 1
    for (x, y) in doors:
        grid[y][x] = DOOR

    # Rooms: flood-fill floor excluding doors; tiny fragments -> void.
    seen = [[False] * gx for _ in range(gy)]
    rooms = []
    for y in range(gy):
        for x in range(gx):
            if grid[y][x] != FLOOR or seen[y][x]:
                continue
            stack, cells = [(x, y)], []
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < gx and 0 <= ny < gy and not seen[ny][nx] \
                            and grid[ny][nx] == FLOOR:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            if len(cells) < cfg["min_room_cells"]:
                for (cx, cy) in cells:
                    grid[cy][cx] = VOID
            else:
                rooms.append(cells)
    rooms.sort(key=len, reverse=True)
    room_objs = []
    for i, cells in enumerate(rooms, 1):
        r = Room(i, cells, gx, gy)
        r.area_m2 = len(cells) * cell_m * cell_m
        room_objs.append(r)

    # Spawn: floor cell of the largest room nearest its centroid.
    if room_objs:
        big = room_objs[0]
        spawn = min(big.cells, key=lambda c: (c[0] - big.centroid[0]) ** 2
                    + (c[1] - big.centroid[1]) ** 2)
    else:
        spawn = None

    walls = _wall_rects(grid)
    return Plan(gx, gy, cell_m, grid, room_objs, sorted(doors), walls, spawn)


def _wall_rects(grid):
    """Greedy axis-aligned rectangles covering every WALL/VOID cell.

    Scan rows for horizontal runs; merge runs with identical [x0, x1]
    spans across consecutive rows. Deterministic and cheap.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    open_rects = {}  # (x0, x1) -> y0
    rects = []
    for y in range(h + 1):
        row = grid[y] if y < h else None
        runs = []
        if row is not None:
            x = 0
            while x < w:
                if row[x] in (WALL, VOID):
                    x0 = x
                    while x < w and row[x] in (WALL, VOID):
                        x += 1
                    runs.append((x0, x - 1))
                else:
                    x += 1
        runset = set(runs)
        # close rects that ended
        for span in list(open_rects):
            if span not in runset:
                rects.append((span[0], open_rects[span], span[1], y - 1))
                del open_rects[span]
        # open new rects
        for span in runs:
            if span not in open_rects:
                open_rects[span] = y
    return rects
