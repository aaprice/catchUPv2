"""Play Ember Crypt in terminal.

    uv run python -m game.play                 # level_01
    uv run python -m game.play --level my_gen  # game/data/generated/my_gen.json

Keys: w/a/s/d move (bump enemy = attack), u <item_id> use, q quit.
Legend: @ you  # wall  D locked door  > exit  ! item  Letter = enemy (first letter of id)
"""
from __future__ import annotations

import argparse

from .content import ContentDB
from .level import validate_level
from .world import Game

KEYMAP = {"w": "n", "a": "w", "s": "s", "d": "e", ".": "wait"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", default="level_01")
    args = ap.parse_args()
    db = ContentDB(include_generated=True)
    level = db.load_level(args.level)
    report = validate_level(level, db)
    if not report.ok:
        print(report.as_feedback())
        return
    g = Game(level, db)
    print(f"== {level.name} ({level.theme}) ==")
    while not g.over:
        print(g.render())
        s = g.status()
        print(f"HP {s['hp']}/{s['max_hp']} ATK {s['atk']} DEF {s['def']} XP {s['xp']} INV {s['inventory']}")
        cmd = input("> ").strip().lower()
        if cmd == "q":
            break
        if cmd.startswith("u "):
            action = "use:" + cmd[2:].strip()
        else:
            action = KEYMAP.get(cmd, cmd)
        for line in g.step(action):
            print("  " + line)
    print(g.render())
    print("VICTORY" if g.won else "THE CRYPT CLAIMS YOU" if g.player.hp <= 0 else "bye")


if __name__ == "__main__":
    main()
