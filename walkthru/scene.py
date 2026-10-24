"""Scene assembly: Plan -> compact deterministic JSON for the browser client."""
import json


def build_scene(plan, wall_height=2.8):
    """Build a scene dict from a Plan. Deterministic: same plan in, same bytes out."""
    if plan.spawn is None:
        raise ValueError("plan has no walkable room")
    room_ids = [[0] * plan.width for _ in range(plan.height)]
    for room in plan.rooms:
        for (x, y) in room.cells:
            room_ids[y][x] = room.id
    return {
        "width": plan.width,
        "height": plan.height,
        "cell_m": round(plan.cell_m, 4),
        "wall_height_m": wall_height,
        "spawn": list(plan.spawn),
        "grid": ["".join(str(v) for v in row) for row in plan.grid],
        "room_ids": ["".join(str(min(v, 9)) for v in row) for row in room_ids],
        "rooms": [room.as_dict() for room in plan.rooms],
        "doors": [list(d) for d in plan.doors],
        "walls": [list(r) for r in plan.walls],
    }


def scene_json(plan, wall_height=2.8):
    return json.dumps(build_scene(plan, wall_height), sort_keys=True,
                      separators=(",", ":"))
