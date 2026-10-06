"""Game core tests. These are also the BACK-PRESSURE for agent loops (module 07):
an agent editing game code must keep these green."""
import json

import pytest

from game import ContentDB, Game, Level, validate_json, validate_level
from game.content import Item
from game.balance import flags, report


@pytest.fixture(scope="module")
def db():
    return ContentDB()


def test_content_loads(db):
    assert "rusty_sword" in db.items
    assert "gravewarden" in db.enemies


def test_level_01_valid(db):
    r = validate_level(db.load_level("level_01"), db)
    assert r.ok, r.as_feedback()


def _lvl(rows, **kw):
    return Level(name="test", map=rows, **kw)


def test_unreachable_exit_detected(db):
    lv = _lvl(["#######", "#@.#.>#", "#..#..#", "#..#..#", "#######"])
    r = validate_level(lv, db)
    assert not r.ok and any("unreachable" in e for e in r.errors)


def test_door_needs_reachable_key(db):
    rows = ["#######", "#@.D.>#", "#..#..#", "#..#..#", "#######"]
    assert not validate_level(_lvl(rows), db).ok
    ok = validate_level(_lvl(rows, items=[{"id": "iron_key", "x": 1, "y": 2}]), db)
    assert ok.ok, ok.as_feedback()


def test_bad_placement_and_unknown_id(db):
    rows = ["#######", "#@...>#", "#.....#", "#.....#", "#######"]
    r = validate_level(_lvl(rows, enemies=[{"id": "dragon", "x": 0, "y": 0}]), db)
    assert any("not in content db" in e for e in r.errors)
    assert any("must be on '.'" in e for e in r.errors)


def test_threat_budget(db):
    rows = ["#######", "#@...>#", "#.....#", "#.....#", "#######"]
    lv = _lvl(rows, enemies=[{"id": "gravewarden", "x": 2, "y": 2}], threat_budget=5)
    assert any("exceeds budget" in e for e in validate_level(lv, db).errors)


def test_validate_json_feedback():
    obj, errs = validate_json(Item, '{"id": "Bad Id", "name": "x"}')
    assert obj is None and errs
    obj, errs = validate_json(Item, "not json")
    assert errs[0].startswith("invalid JSON")


def test_game_walk_pickup_and_door(db):
    rows = ["#######", "#@.D.>#", "#..#..#", "#..#..#", "#######"]
    lv = _lvl(rows, items=[{"id": "iron_key", "x": 2, "y": 1}])
    g = Game(lv, db)
    g.step("e")
    assert "iron_key" in g.player.inventory
    g.step("e")  # unlock + step into door tile
    g.step("e")
    g.step("e")
    assert g.won


def test_combat_kills_rat_and_awards_xp(db):
    rows = ["#######", "#@r..>#", "#.....#", "#.....#", "#######"]
    lv = _lvl([r.replace("r", ".") for r in rows], enemies=[{"id": "crypt_rat", "x": 2, "y": 1}])
    g = Game(lv, db)
    for _ in range(5):
        g.step("e")
    assert g.player.xp == db.enemies["crypt_rat"].xp


def test_balance_no_flags(db):
    assert flags(report(db)) == []


def test_level_json_roundtrip(db):
    lv = db.load_level("level_01")
    again = Level(**json.loads(lv.model_dump_json()))
    assert again == lv


def test_bot_beats_level_01(db):
    from game.autoplay import play
    r = play(db.load_level("level_01"), db)
    assert r["won"], r
