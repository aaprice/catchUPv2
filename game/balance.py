"""Balance report: every enemy vs player gear tiers. Deterministic.

    uv run python -m game.balance           # table
    uv run python -m game.balance --json    # machine-readable (skills/hooks/agents consume this)
"""
from __future__ import annotations

import argparse
import json

from .content import ContentDB
from .world import simulate_fight

BASE_ATK, BASE_DEF, BASE_HP = 4, 1, 30


def report(db: ContentDB) -> list[dict]:
    weapons = [None] + [i for i in db.items.values() if i.kind == "weapon"]
    armors = [None] + [i for i in db.items.values() if i.kind == "armor"]
    rows = []
    for e in db.enemies.values():
        for w in weapons:
            for a in armors:
                r = simulate_fight(BASE_ATK + (w.power if w else 0), BASE_DEF + (a.power if a else 0), BASE_HP, e)
                r.update(weapon=w.id if w else "-", armor=a.id if a else "-", threat=e.threat)
                rows.append(r)
    return rows


def flags(rows: list[dict]) -> list[str]:
    """Heuristic red flags. An agent (or Stop hook) can block on these."""
    out = []
    by_enemy: dict[str, list[dict]] = {}
    for r in rows:
        by_enemy.setdefault(r["enemy"], []).append(r)
    for enemy, rs in by_enemy.items():
        if not any(r["player_survives"] for r in rs):
            out.append(f"{enemy}: unbeatable with ANY gear combo")
        if all(r["hp_lost"] == 0 for r in rs):
            out.append(f"{enemy}: never deals damage; pointless")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = report(ContentDB())
    if args.json:
        print(json.dumps({"rows": rows, "flags": flags(rows)}, indent=1))
        return
    print(f"{'enemy':<16}{'weapon':<14}{'armor':<12}{'turns':>6}{'hp_lost':>8}  ok")
    for r in rows:
        print(f"{r['enemy']:<16}{r['weapon']:<14}{r['armor']:<12}{r['turns_to_kill']:>6}{r['hp_lost']:>8}  "
              f"{'Y' if r['player_survives'] else 'DEAD'}")
    for f in flags(rows):
        print("FLAG:", f)


if __name__ == "__main__":
    main()
