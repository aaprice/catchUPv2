"""Agent-facing tool sets over Ember Crypt. Reused by modules 03, 05, 08, 09.

Design rules for agent tools (learned the hard way across the industry):
  1. Few, high-level tools > many tiny ones (less to choose wrong).
  2. Return compact, model-readable text/JSON; include IDs the model needs next.
  3. Errors = instructions ("not enough gold: have 12, need 60"), never stack traces.
  4. Mutations validated IN THE TOOL. Never trust the model to follow rules in prose.
  5. Mark read_only honestly -> harness permission policy relies on it.
"""
from __future__ import annotations

import json
from pathlib import Path

from game import ContentDB, Game, simulate_fight

from .tools import Tool, tool

SHOP_FILE = Path(__file__).resolve().parent.parent / "game" / "data" / "shop.json"


class Shop:
    def __init__(self, db: ContentDB, gold: int = 50):
        cfg = json.loads(SHOP_FILE.read_text(encoding="utf-8"))
        self.db = db
        self.merchant, self.persona = cfg["merchant"], cfg["persona"]
        self.stock: dict[str, int] = dict(cfg["stock"])
        self.max_discount = cfg["max_discount_pct"]
        self.player_gold = gold
        self.player_inv: list[str] = []
        self.sales: list[dict] = []

    def tools(self) -> list[Tool]:
        shop = self

        @tool
        def list_stock() -> str:
            """List items for sale with id, name, kind, power, list price and quantity."""
            rows = []
            for iid, qty in shop.stock.items():
                if qty > 0:
                    it = shop.db.items[iid]
                    rows.append({"id": iid, "name": it.name, "kind": it.kind, "power": it.power,
                                 "price": it.value, "qty": qty})
            return json.dumps(rows)

        @tool
        def item_info(item_id: str) -> str:
            """Full details of one item (stats + description).

            Args:
                item_id: snake_case item id from list_stock
            """
            it = shop.db.items.get(item_id)
            return it.model_dump_json() if it else f"ERROR: unknown item '{item_id}'. Call list_stock for valid ids."

        @tool
        def customer_wallet() -> str:
            """Customer's current gold and what they already bought."""
            return json.dumps({"gold": shop.player_gold, "inventory": shop.player_inv})

        @tool(read_only=False)
        def sell_item(item_id: str, price: int) -> str:
            """Complete a sale. Deducts gold, moves item to customer. Only way a sale actually happens.

            Args:
                item_id: item to sell
                price: final agreed price in gold (list price minus any discount, max discount enforced)
            """
            it = shop.db.items.get(item_id)
            if not it or shop.stock.get(item_id, 0) <= 0:
                return f"ERROR: '{item_id}' not in stock."
            floor = it.value * (100 - shop.max_discount) // 100
            if price < floor:
                return f"ERROR: price {price} below allowed minimum {floor} (max {shop.max_discount}% off {it.value})."
            if price > shop.player_gold:
                return f"ERROR: customer has {shop.player_gold} gold, price is {price}. Sale impossible."
            shop.player_gold -= price
            shop.stock[item_id] -= 1
            shop.player_inv.append(item_id)
            shop.sales.append({"item": item_id, "price": price})
            return f"SOLD {it.name} for {price}. Customer gold now {shop.player_gold}."

        @tool
        def fight_odds(enemy_id: str, weapon_id: str = "", armor_id: str = "") -> str:
            """Predict a duel vs an enemy with given gear. Helps advise customers.

            Args:
                enemy_id: e.g. ash_skeleton, gravewarden
                weapon_id: optional weapon item id
                armor_id: optional armor item id
            """
            e = shop.db.enemies.get(enemy_id)
            if not e:
                return f"ERROR: unknown enemy. Known: {list(shop.db.enemies)}"
            w, a = shop.db.items.get(weapon_id), shop.db.items.get(armor_id)
            return json.dumps(simulate_fight(4 + (w.power if w else 0), 1 + (a.power if a else 0), 30, e))

        return [list_stock, item_info, customer_wallet, sell_item, fight_odds]


def playtest_tools(game: Game) -> list[Tool]:
    """Tools that let an agent PLAY a level. Agent-as-QA (module 08)."""

    @tool
    def look() -> str:
        """See the map (@ you, # wall, D door, > exit, ! item, Letter enemy) and your status."""
        return game.render() + "\n" + json.dumps(game.status())

    @tool(read_only=False)
    def act(actions: list[str]) -> str:
        """Perform up to 8 actions in order. Each: n|s|e|w (move/attack), wait, or use:<item_id>.

        Args:
            actions: list of actions, e.g. ["e","e","s","use:red_tonic"]
        """
        out = []
        for a in actions[:8]:
            out += [f"{a}: {line}" for line in game.step(a)] or [f"{a}: ok"]
            if game.over:
                break
        return "\n".join(out) + "\n" + game.render() + "\n" + json.dumps(game.status())

    return [look, act]
