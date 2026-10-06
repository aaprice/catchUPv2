"""Content schemas for Ember Crypt.

Pydantic models = single source of truth for what valid game content looks like.
Same schemas get reused as:
  - JSON Schema for LLM structured output   (module 02)
  - tool input schemas                       (module 03)
  - MCP tool validation                      (module 05)
  - eval graders                             (module 09)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

DATA_DIR = Path(__file__).parent / "data"

ItemKind = Literal["weapon", "armor", "potion", "key", "trinket"]


class Item(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$", description="snake_case unique id")
    name: str = Field(min_length=2, max_length=40)
    kind: ItemKind
    power: int = Field(ge=0, le=20, description="weapon=+atk, armor=+def, potion=heal amount/5, else 0")
    value: int = Field(ge=0, le=500, description="gold price at shop")
    description: str = Field(min_length=5, max_length=200)


class Enemy(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    name: str = Field(min_length=2, max_length=40)
    hp: int = Field(ge=1, le=60)
    atk: int = Field(ge=1, le=15)
    defense: int = Field(ge=0, le=10)
    xp: int = Field(ge=1, le=100)
    loot: list[str] = Field(default_factory=list, description="item ids dropped on death")
    description: str = Field(min_length=5, max_length=200)

    @property
    def threat(self) -> int:
        """Rough difficulty score. Used for level budget."""
        return self.hp // 4 + self.atk * 2 + self.defense * 2


class Placement(BaseModel):
    id: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class Level(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    theme: str = Field(default="crypt", max_length=60)
    # Legend: '#' wall  '.' floor  '@' start  '>' exit  'D' locked door (needs kind=key item)
    map: list[str] = Field(min_length=5, max_length=40)
    enemies: list[Placement] = Field(default_factory=list)
    items: list[Placement] = Field(default_factory=list)
    threat_budget: int = Field(default=60, ge=1, le=400)

    @field_validator("map")
    @classmethod
    def _rect(cls, rows: list[str]) -> list[str]:
        w = len(rows[0])
        if any(len(r) != w for r in rows):
            raise ValueError("map rows must all be same width")
        bad = {c for r in rows for c in r} - set("#.@>D")
        if bad:
            raise ValueError(f"map has illegal chars {sorted(bad)}; legal: # . @ > D")
        return rows


class ContentDB:
    """Loads items/enemies from JSON. Tiny repository pattern."""

    def __init__(self, data_dir: Path = DATA_DIR, include_generated: bool = False):
        """include_generated=True also loads generated/items_*.json + generated/enemies_*.json (agent-made)."""
        self.data_dir = Path(data_dir)
        self.include_generated = include_generated
        self.items: dict[str, Item] = {}
        self.enemies: dict[str, Enemy] = {}
        self.reload()

    def reload(self) -> None:
        self.items = {d["id"]: Item(**d) for d in _read(self.data_dir / "items.json")}
        self.enemies = {d["id"]: Enemy(**d) for d in _read(self.data_dir / "enemies.json")}
        if self.include_generated:
            for f in sorted((self.data_dir / "generated").glob("items_*.json")):
                self.items.update({d["id"]: Item(**d) for d in _read(f)})
            for f in sorted((self.data_dir / "generated").glob("enemies_*.json")):
                self.enemies.update({d["id"]: Enemy(**d) for d in _read(f)})
        for e in self.enemies.values():
            for loot in e.loot:
                if loot not in self.items:
                    raise ValueError(f"enemy {e.id} drops unknown item {loot}")

    def load_level(self, name: str) -> Level:
        path = self.data_dir / f"{name}.json"
        if not path.exists():
            path = self.data_dir / "generated" / f"{name}.json"
        return Level(**json.loads(path.read_text(encoding="utf-8")))


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def validate_json(model: type[BaseModel], raw: str | dict) -> tuple[BaseModel | None, list[str]]:
    """Parse + validate. Returns (obj, errors). Errors formatted for feeding BACK to an LLM."""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]
    try:
        return model(**data), []
    except ValidationError as e:
        return None, [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
    except TypeError as e:
        return None, [f"expected JSON object: {e}"]
