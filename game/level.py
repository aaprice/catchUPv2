"""Deterministic level validator.

THIS FILE = the "verifier" in every generate->verify loop (module 07).
Rule of thumb: anything you CAN check with code, check with code. Save LLM judges for taste.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .content import ContentDB, Level

Pos = tuple[int, int]


@dataclass
class Report:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def as_feedback(self) -> str:
        """Compact text for an LLM to read and fix. Errors first, specific, actionable."""
        lines = [f"VALID: {self.ok}"]
        lines += [f"ERROR: {e}" for e in self.errors]
        lines += [f"WARN: {w}" for w in self.warnings]
        lines.append(f"STATS: {self.stats}")
        return "\n".join(lines)


def find(level: Level, ch: str) -> list[Pos]:
    return [(x, y) for y, row in enumerate(level.map) for x, c in enumerate(row) if c == ch]


def bfs(level: Level, start: Pos, doors_open: bool) -> dict[Pos, int]:
    """Distance map from start. Walls block. Doors block unless doors_open."""
    h, w = len(level.map), len(level.map[0])
    dist = {start: 0}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in dist:
                continue
            c = level.map[ny][nx]
            if c == "#" or (c == "D" and not doors_open):
                continue
            dist[(nx, ny)] = dist[(x, y)] + 1
            q.append((nx, ny))
    return dist


def validate_level(level: Level, db: ContentDB) -> Report:
    errs: list[str] = []
    warns: list[str] = []
    rows = level.map
    h, w = len(rows), len(rows[0])

    # 1. structure
    if any(c != "#" for c in rows[0] + rows[-1]) or any(r[0] != "#" or r[-1] != "#" for r in rows):
        errs.append("border must be all '#' walls")
    starts, exits = find(level, "@"), find(level, ">")
    if len(starts) != 1:
        errs.append(f"need exactly 1 '@' start, found {len(starts)}")
    if len(exits) != 1:
        errs.append(f"need exactly 1 '>' exit, found {len(exits)}")

    # 2. placements
    occupied: dict[Pos, str] = {}
    for kind, plist, table in (("enemy", level.enemies, db.enemies), ("item", level.items, db.items)):
        for p in plist:
            if p.id not in table:
                errs.append(f"{kind} id '{p.id}' not in content db (known: {sorted(table)[:12]})")
            if not (0 <= p.x < w and 0 <= p.y < h):
                errs.append(f"{kind} {p.id} at ({p.x},{p.y}) out of bounds {w}x{h}")
                continue
            if rows[p.y][p.x] != ".":
                errs.append(f"{kind} {p.id} at ({p.x},{p.y}) must be on '.', found '{rows[p.y][p.x]}'")
            if (p.x, p.y) in occupied:
                errs.append(f"{kind} {p.id} overlaps {occupied[(p.x, p.y)]} at ({p.x},{p.y})")
            occupied[(p.x, p.y)] = p.id

    # 3. threat budget
    threat = sum(db.enemies[e.id].threat for e in level.enemies if e.id in db.enemies)
    if threat > level.threat_budget:
        errs.append(f"threat {threat} exceeds budget {level.threat_budget}; remove or weaken enemies")

    # 4. solvability (only if structure sane)
    path_len = None
    if len(starts) == 1 and len(exits) == 1:
        start, exit_ = starts[0], exits[0]
        closed = bfs(level, start, doors_open=False)
        if exit_ in closed:
            path_len = closed[exit_]
            if find(level, "D"):
                warns.append("doors exist but exit reachable without them; doors are decorative")
        else:
            keys = [i for i in level.items if db.items.get(i.id) and db.items[i.id].kind == "key"]
            reachable_keys = [k for k in keys if (k.x, k.y) in closed]
            if not find(level, "D"):
                errs.append("exit unreachable from start (walls block every path)")
            elif not reachable_keys:
                errs.append("exit behind door 'D' but no key item reachable before the door")
            else:
                opened = bfs(level, start, doors_open=True)
                if exit_ in opened:
                    path_len = opened[exit_]
                else:
                    errs.append("exit unreachable even with doors open")

    floor = sum(r.count(".") for r in rows)
    if floor and len(level.enemies) / floor > 0.15:
        warns.append("enemy density >15% of floor; feels crowded")
    if path_len is not None and path_len < max(w, h) // 2:
        warns.append(f"shortest path {path_len} is short for {w}x{h}; level may feel trivial")

    return Report(
        ok=not errs,
        errors=errs,
        warnings=warns,
        stats={"size": f"{w}x{h}", "floor": floor, "path_len": path_len, "threat": threat,
               "enemies": len(level.enemies), "items": len(level.items)},
    )
