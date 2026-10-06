"""Harness tests with MockLLM: deterministic, free, fast.
Lesson: test the HARNESS with scripted models; test the MODEL+PROMPT with evals (module 09)."""
from game import ContentDB
from lib import Agent, Hooks, MockLLM, Reply, ToolCall, Tracer, tool
from lib.game_tools import Shop


def quiet(name="t"):
    return Tracer(name, verbose=False, to_file=False)


def test_tool_schema_from_hints():
    @tool
    def roll(sides: int, label: str = "d") -> str:
        """Roll a die.

        Args:
            sides: number of faces
            label: display label
        """
        return str(sides)

    spec = roll.spec()
    assert spec["name"] == "roll" and spec["description"] == "Roll a die."
    assert spec["parameters"]["properties"]["sides"] == {"type": "integer", "description": "number of faces"}
    assert spec["parameters"]["required"] == ["sides"]


def test_loop_runs_tool_then_answers():
    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    llm = MockLLM([Reply(text="", tool_calls=[ToolCall("c1", "add", {"a": 2, "b": 3})]), "It's 5."])
    res = Agent(llm, "sys", [add], tracer=quiet()).run("2+3?")
    assert res.text == "It's 5." and res.reason == "done" and res.turns == 2
    tool_msg = llm.calls[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and tool_msg["content"] == "5"


def test_unknown_tool_and_bad_args_are_fed_back():
    @tool
    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    llm = MockLLM([
        Reply(text="", tool_calls=[ToolCall("1", "mul", {}), ToolCall("2", "add", {"a": 1})]),
        "ok",
    ])
    res = Agent(llm, "sys", [add], tracer=quiet()).run("x")
    assert "no tool named" in res.tool_log[0]["result"]
    assert "bad arguments" in res.tool_log[1]["result"]


def test_policy_denies_mutation():
    shop = Shop(ContentDB(), gold=100)
    llm = MockLLM([Reply(text="", tool_calls=[ToolCall("1", "sell_item", {"item_id": "red_tonic", "price": 10})]), "fine"])
    res = Agent(llm, "sys", shop.tools(), tracer=quiet(), ask_fn=lambda q: False).run("buy tonic")
    assert "DENIED" in res.tool_log[0]["result"] and shop.player_gold == 100


def test_shop_enforces_rules_in_tool():
    shop = Shop(ContentDB(), gold=20)
    sell = {t.name: t for t in shop.tools()}["sell_item"]
    assert "below allowed minimum" in sell(item_id="ember_blade", price=1)
    assert "Sale impossible" in sell(item_id="ember_blade", price=60)
    assert sell(item_id="red_tonic", price=8).startswith("SOLD")
    assert shop.player_gold == 12


def test_stop_hook_vetoes_until_condition():
    state = {"checks": 0}

    def gate(text):
        state["checks"] += 1
        return None if "VERIFIED" in text else "you must say VERIFIED"

    llm = MockLLM(["done!", "VERIFIED done"])
    res = Agent(llm, "sys", [], hooks=Hooks(on_stop=[gate]), tracer=quiet()).run("go")
    assert res.text == "VERIFIED done" and state["checks"] == 2


def test_pre_tool_hook_blocks():
    @tool
    def danger(path: str) -> str:
        """Delete path."""
        raise AssertionError("must not run")

    block = Hooks(pre_tool=[lambda c: "no deleting saves" if "save" in c.arguments.get("path", "") else None])
    llm = MockLLM([Reply(text="", tool_calls=[ToolCall("1", "danger", {"path": "save.dat"})]), "ok"])
    res = Agent(llm, "sys", [danger], hooks=block, policy=None, tracer=quiet()).run("x")
    assert "BLOCKED by hook" in res.tool_log[0]["result"]


def test_max_turns():
    llm = MockLLM([Reply(text="", tool_calls=[ToolCall(str(i), "nope", {})]) for i in range(10)])
    res = Agent(llm, "sys", [], max_turns=3, tracer=quiet()).run("x")
    assert res.reason == "max_turns" and res.turns == 3
