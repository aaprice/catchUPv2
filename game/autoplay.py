"""Deterministic bot playtester. "Can a dumb greedy player beat this level?"

    uv run python -m game.autoplay                       # level_01
    uv run python -m game.autoplay --level rat_nest --show

Strategy: loot every reachable item (equip best gear), grab key, head to exit, attack anything in the way,
drink potion when hp < 40%. Not smart -> if bot wins, humans will. Cheap verifier for loops (M07) + evals (M09).
"""
from __future__ import annotations

import argparse
import json
from collections import deque

from .content import ContentDB, Level
from .world import DIRS, Game


def _path_step(g: Game, goal: tuple[int, int]) -> str | None:
    """First direction of shortest path to goal. Monsters passable (we fight through)."""
    p = g.player
    has_key = any(g.db.items[i].kind == "key" for i in p.inventory)
    start = (p.x, p.y)
    prev: dict = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        for d, (dx, dy) in DIRS.items():
            nx, ny = cur[0] + dx, cur[1] + dy
            if (nx, ny) in prev or not (0 <= ny < len(g.grid) and 0 <= nx < len(g.grid[0])):
                continue
            t = g.grid[ny][nx]
            if t == "#" or (t == "D" and not has_key):
                continue
            prev[(nx, ny)] = (cur, d)
            q.append((nx, ny))
    if goal not in prev:
        return None
    node = goal
    while prev[node] and prev[node][0] != start:
        node = prev[node][0]
    return prev[node][1] if prev[node] else None


def _equip_best(g: Game) -> None:
    for kind, slot in (("weapon", "weapon"), ("armor", "armor")):
        owned = [i for i in g.player.inventory if g.db.items[i].kind == kind]
        if owned:
            best = max(owned, key=lambda i: g.db.items[i].power)
            if getattr(g.player, slot) != best:
                g.step(f"use:{best}")


def play(level: Level, db: ContentDB, max_turns: int = 400, show: bool = False) -> dict:
    g = Game(level, db)
    exit_pos = next((x, y) for y, r in enumerate(g.grid) for x, c in enumerate(r) if c == ">")
    while not g.over and g.turn < max_turns:
        _equip_best(g)
        p = g.player
        if p.hp < p.max_hp * 0.4:
            potions = sorted((i for i in p.inventory if db.items[i].kind == "potion"), key=lambda i: db.items[i].power)
            if potions:
                g.step(f"use:{potions[-1]}")
                continue
        targets = sorted(g.floor_items, key=lambda pos: abs(pos[0] - p.x) + abs(pos[1] - p.y))
        step = None
        for t in targets:                      # nearest reachable item first
            step = _path_step(g, t)
            if step:
                break
        if not step:
            step = _path_step(g, exit_pos)
        if not step:
            break                              # stuck
        g.step(step)
        if show:
            print(g.render(), g.status(), sep="\n")
    killed = [m.kind for m in g.monsters if m.hp <= 0]
    return {"won": g.won, "dead": g.player.hp <= 0, "turns": g.turn, "hp_left": max(g.player.hp, 0),
            "kills": killed, "stuck": not g.over and g.turn < max_turns,
            "last_log": g.log[-4:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level_01")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    db = ContentDB(include_generated=True)
    print(json.dumps(play(db.load_level(a.level), db, show=a.show), indent=1))


if __name__ == "__main__":
    main()
