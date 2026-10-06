"""[v2] Profiles + prompt-mode tool calling (no model needed: inner HTTP call is stubbed)."""
import json

from lib import LLM, Agent, Reply, Tracer, tool
from lib.profiles import PROFILES, resolve


def test_profiles_resolve(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "stale:model")          # must NOT leak into a named profile
    cfg = resolve("gemma4-26b")
    assert cfg["model"] == "gemma4:26b" and cfg["provider"] == "ollama"
    monkeypatch.setenv("DGX_URL", "http://gpu-box:9000/v1")
    assert resolve("dgx-vllm")["base"] == "http://gpu-box:9000/v1"
    monkeypatch.setenv("LLM_TOOL_MODE", "prompt")
    assert resolve("qwen3-8b")["tool_mode"] == "prompt"
    assert all("provider" in p and "model" in p for p in PROFILES.values())


def test_prompt_mode_tool_loop(monkeypatch):
    monkeypatch.delenv("LLM_TOOL_MODE", raising=False)
    llm = LLM(profile="gemma4-e4b")
    assert llm.tool_mode == "prompt"
    seen = []

    def fake_inner(wire, tools, schema, temperature, max_tokens):
        seen.append({"wire": wire, "tools": tools, "schema": schema})
        if len(seen) == 1:
            return Reply(text=json.dumps({"action": "call", "calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]}))
        return Reply(text=json.dumps({"action": "final", "text": "five"}))

    monkeypatch.setattr(llm, "_chat_ollama", fake_inner)

    @tool
    def add(a: int, b: int) -> int:
        """Add two ints."""
        return a + b

    res = Agent(llm, "You add.", [add], tracer=Tracer("t", verbose=False, to_file=False)).run("2+3?")
    assert res.text == "five" and res.tool_log[0]["result"] == "5"
    first, second = seen
    assert first["tools"] is None                                   # no native tools sent
    assert first["schema"]["properties"]["calls"]["items"]["properties"]["name"]["enum"] == ["add"]
    assert "<tools>" in first["wire"][0]["content"]
    assert any(m["content"].startswith("[tool_result add] 5") for m in second["wire"])   # tool msg re-encoded
