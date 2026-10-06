"""M08.4 — One LLM playtester agent playing a level through tools. Base for the "playtester swarm" exercise.

    uv run python modules/08_multi_agent/playtester.py --level level_01 --persona cautious
    uv run python modules/08_multi_agent/playtester.py --level rat_nest --persona speedrunner

Compare against deterministic bot: uv run python -m game.autoplay --level level_01
(LLMs are bad at grid navigation -> lesson: use LLM for judgment, code for search/pathfinding.)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from game import ContentDB, Game  # noqa: E402
from lib import Agent, get_llm  # noqa: E402
from lib.game_tools import playtest_tools  # noqa: E402

PERSONAS = {
    "cautious": "You hate taking damage. Collect gear and potions before fighting; drink potions early.",
    "speedrunner": "You want the exit in as few turns as possible. Fight only what blocks you.",
    "looter": "You want every item on the map before leaving.",
}

ap = argparse.ArgumentParser()
ap.add_argument("--level", default="level_01")
ap.add_argument("--persona", choices=PERSONAS, default="cautious")
ap.add_argument("--max-turns", type=int, default=40)
a = ap.parse_args()

db = ContentDB(include_generated=True)
game = Game(db.load_level(a.level), db)
agent = Agent(get_llm(), f"""You are playtesting roguelike Ember Crypt. {PERSONAS[a.persona]}
Map: '@' you, '#' wall, 'D' locked door (walk into it with a key), '>' exit, '!' item (walk onto it), letters = enemies
(walk into enemy to attack). Coordinates: x right, y down; n=up s=down e=right w=left.
Call look first, then act with short action lists (<=4), re-look often. Goal: reach '>'.
When the game ends or you are stuck, stop and write a playtest report: outcome, where it was hard, 2 design suggestions.""",
              playtest_tools(game), name=f"play-{a.persona}", max_turns=a.max_turns, policy=lambda t, c: "allow",
              temperature=0.3)
res = agent.run("Begin playtest.")
print("\nREPORT:\n", res.text)
print("\nFINAL STATE:", game.status())
