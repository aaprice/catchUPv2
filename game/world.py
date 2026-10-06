"""Ember Crypt simulation. Pure Python, deterministic, no I/O.

Why pure + deterministic? Agents need a world they can poke via tools and
tests can replay exactly. Same reason you keep game logic out of render code.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .content import ContentDB, Enemy, Level

DIRS = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


@dataclass
class Actor:
    x: int
    y: int
    hp: int
    max_hp: int
    atk: int
    defense: int


@dataclass
class Player(Actor):
    gold: int = 30
    xp: int = 0
    inventory: list[str] = field(default_factory=list)
    weapon: str | None = None
    armor: str | None = None


@dataclass
class Monster(Actor):
    kind: str = ""
    uid: int = 0


def damage(atk: int, defense: int) -> int:
    return max(1, atk - defense)


def simulate_fight(player_atk: int, player_def: int, player_hp: int, enemy: Enemy) -> dict:
    """Closed-form duel, player swings first. Used for balance checks + MCP tool."""
    to_kill = -(-enemy.hp // damage(player_atk, enemy.defense))        # ceil div
    hits_taken = to_kill - 1                                            # enemy dies before last swing back
    hp_lost = hits_taken * damage(enemy.atk, player_def)
    return {"enemy": enemy.id, "turns_to_kill": to_kill, "hp_lost": hp_lost,
            "player_survives": hp_lost < player_hp, "hp_left": player_hp - hp_lost}


class Game:
    def __init__(self, level: Level, db: ContentDB):
        self.db, self.level = db, level
        self.grid = [list(r) for r in level.map]
        (sx, sy), = [(x, y) for y, r in enumerate(self.grid) for x, c in enumerate(r) if c == "@"]
        self.grid[sy][sx] = "."
        self.player = Player(x=sx, y=sy, hp=30, max_hp=30, atk=4, defense=1)
        self.monsters: list[Monster] = []
        for i, p in enumerate(level.enemies):
            e = db.enemies[p.id]
            self.monsters.append(Monster(p.x, p.y, e.hp, e.hp, e.atk, e.defense, kind=e.id, uid=i))
        self.floor_items: dict[tuple[int, int], str] = {(p.x, p.y): p.id for p in level.items}
        self.log: list[str] = []
        self.turn = 0
        self.won = False

    # ---------- queries (safe, read-only -> good agent tools) ----------
    @property
    def over(self) -> bool:
        return self.won or self.player.hp <= 0

    def monster_at(self, x: int, y: int) -> Monster | None:
        return next((m for m in self.monsters if m.x == x and m.y == y and m.hp > 0), None)

    def render(self) -> str:
        g = [row[:] for row in self.grid]
        for (x, y), _ in self.floor_items.items():
            g[y][x] = "!"
        for m in self.monsters:
            if m.hp > 0:
                g[m.y][m.x] = m.kind[0].upper()
        g[self.player.y][self.player.x] = "@"
        return "\n".join("".join(r) for r in g)

    def status(self) -> dict:
        p = self.player
        return {"turn": self.turn, "hp": p.hp, "max_hp": p.max_hp, "atk": self.total_atk(),
                "def": self.total_def(), "gold": p.gold, "xp": p.xp, "pos": [p.x, p.y],
                "inventory": p.inventory, "weapon": p.weapon, "armor": p.armor,
                "won": self.won, "dead": p.hp <= 0}

    def total_atk(self) -> int:
        w = self.db.items.get(self.player.weapon or "")
        return self.player.atk + (w.power if w else 0)

    def total_def(self) -> int:
        a = self.db.items.get(self.player.armor or "")
        return self.player.defense + (a.power if a else 0)

    # ---------- commands (mutate state) ----------
    def step(self, action: str) -> list[str]:
        """action: n|s|e|w|wait|use:<item_id>. Returns log lines for this turn."""
        if self.over:
            return ["game over"]
        start = len(self.log)
        self.turn += 1
        if action in DIRS:
            self._move(*DIRS[action])
        elif action.startswith("use:"):
            self.use(action[4:])
        elif action != "wait":
            self.log.append(f"unknown action '{action}'")
            self.turn -= 1
            return self.log[start:]
        self._monsters_act()
        return self.log[start:]

    def use(self, item_id: str) -> None:
        p = self.player
        if item_id not in p.inventory:
            self.log.append(f"no {item_id} in inventory")
            return
        it = self.db.items[item_id]
        if it.kind == "potion":
            heal = it.power * 5
            p.hp = min(p.max_hp, p.hp + heal)
            p.inventory.remove(item_id)
            self.log.append(f"drank {it.name} (+{heal} hp)")
        elif it.kind == "weapon":
            p.weapon = item_id
            self.log.append(f"wield {it.name}")
        elif it.kind == "armor":
            p.armor = item_id
            self.log.append(f"wear {it.name}")
        else:
            self.log.append(f"{it.name} can't be used directly")

    def _move(self, dx: int, dy: int) -> None:
        p = self.player
        nx, ny = p.x + dx, p.y + dy
        tile = self.grid[ny][nx]
        m = self.monster_at(nx, ny)
        if m:
            self._attack_monster(m)
            return
        if tile == "#":
            self.log.append("bump wall")
            return
        if tile == "D":
            key = next((i for i in p.inventory if self.db.items[i].kind == "key"), None)
            if not key:
                self.log.append("door locked; need key")
                return
            p.inventory.remove(key)
            self.grid[ny][nx] = "."
            self.log.append("unlocked door")
        p.x, p.y = nx, ny
        if (nx, ny) in self.floor_items:
            item = self.floor_items.pop((nx, ny))
            p.inventory.append(item)
            self.log.append(f"picked up {self.db.items[item].name}")
        if tile == ">":
            self.won = True
            self.log.append("reached exit. victory!")

    def _attack_monster(self, m: Monster) -> None:
        dmg = damage(self.total_atk(), m.defense)
        m.hp -= dmg
        self.log.append(f"hit {m.kind} for {dmg}")
        if m.hp <= 0:
            e = self.db.enemies[m.kind]
            self.player.xp += e.xp
            self.log.append(f"{m.kind} dies (+{e.xp}xp)")
            for loot in e.loot:
                self.player.inventory.append(loot)
                self.log.append(f"looted {loot}")

    def _monsters_act(self) -> None:
        p = self.player
        for m in self.monsters:
            if m.hp <= 0 or self.over:
                continue
            dist = abs(m.x - p.x) + abs(m.y - p.y)
            if dist == 1:
                dmg = damage(m.atk, self.total_def())
                p.hp -= dmg
                self.log.append(f"{m.kind} hits you for {dmg}")
                if p.hp <= 0:
                    self.log.append("you died")
            elif dist <= 5:  # greedy chase
                for dx, dy in sorted(DIRS.values(), key=lambda d: abs(m.x + d[0] - p.x) + abs(m.y + d[1] - p.y)):
                    nx, ny = m.x + dx, m.y + dy
                    if self.grid[ny][nx] in ".>" and not self.monster_at(nx, ny) and (nx, ny) != (p.x, p.y):
                        m.x, m.y = nx, ny
                        break
