"""THE HARNESS. ~150 lines that turn a stateless text predictor into an agent.

    model  = engine        (predicts next tokens; no memory, no hands)
    harness = rest of car  (loop, tools, memory, brakes, dashboard)

Every agent product (Claude Code, Gemini CLI, Cursor, Codex) = this loop + better parts:

    while not done and turns < max:
        reply = llm(messages, tools)            # think
        if no tool calls: done                  # model says "I'm finished"
        for call in reply.tool_calls:
            policy check / pre-hook             # brakes  (permissions)
            result = run tool                   # hands   (side effects)
            post-hook                           # sensors (lint, validate)
            messages += result                  # memory  (context grows)
        maybe compact(messages)                 # context engineering
    stop-hook may say "not done yet" -> loop again  # loop engineering

Read this file top to bottom once. Modules 03-09 all reuse it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Literal

from .llm import Reply, ToolCall, tool_result_message
from .tools import Tool
from .trace import Tracer

Decision = Literal["allow", "deny", "ask"]


@dataclass
class Hooks:
    """Mirror of Claude Code hook events (module 06). Same ideas, your code.

    pre_tool(call)          -> None to proceed | str = block reason (sent back to model)
    post_tool(call, result) -> None | str replacement/extra feedback appended to result
    on_stop(text)           -> None to finish | str = "not done" message; loop continues
    """
    pre_tool: list[Callable[[ToolCall], str | None]] = field(default_factory=list)
    post_tool: list[Callable[[ToolCall, str], str | None]] = field(default_factory=list)
    on_stop: list[Callable[[str], str | None]] = field(default_factory=list)


def default_policy(tool: Tool, call: ToolCall) -> Decision:
    """Read-only tools auto-allowed; mutating tools ask human. Same default Claude Code ships."""
    return "allow" if tool.read_only else "ask"


@dataclass
class Result:
    text: str
    messages: list[dict]
    turns: int
    reason: str                       # "done" | "max_turns" | "stopped_by_hook_limit"
    tool_log: list[dict]
    usage: dict


class Agent:
    def __init__(self, llm, system: str, tools: list[Tool] | None = None, *, name: str = "agent",
                 max_turns: int = 12, hooks: Hooks | None = None,
                 policy: Callable[[Tool, ToolCall], Decision] | None = default_policy,
                 compactor: Callable[[list[dict]], list[dict]] | None = None,
                 tracer: Tracer | None = None, temperature: float = 0.4, max_stop_retries: int = 3,
                 ask_fn: Callable[[str], bool] | None = None):
        self.llm, self.system, self.name = llm, system, name
        self.tools = {t.name: t for t in (tools or [])}
        self.max_turns, self.temperature = max_turns, temperature
        self.hooks = hooks or Hooks()
        self.policy, self.compactor = policy, compactor
        self.tracer = tracer or Tracer(name)
        self.max_stop_retries = max_stop_retries
        self.ask_fn = ask_fn or (lambda q: input(f"\n  ALLOW? {q} [y/N] ").strip().lower() == "y")

    # ------------------------------------------------------------------ main loop
    def run(self, user_msg: str, history: list[dict] | None = None) -> Result:
        messages = [{"role": "system", "content": self.system}, *(history or []),
                    {"role": "user", "content": user_msg}]
        specs = [t.spec() for t in self.tools.values()] or None
        tool_log: list[dict] = []
        stop_retries = 0
        reply = Reply(text="")

        for turn in range(1, self.max_turns + 1):
            if self.compactor:
                before = len(messages)
                messages = self.compactor(messages)
                if len(messages) != before:
                    self.tracer.event("compact", msg=f"{before} -> {len(messages)} messages")

            reply = self.llm.chat(messages, tools=specs, temperature=self.temperature)
            self.tracer.event("llm_reply", text=reply.text, usage=reply.usage, latency_ms=reply.latency_ms,
                              tool_calls=[c.__dict__ for c in reply.tool_calls])
            messages.append(reply.as_message())

            if not reply.tool_calls:
                # model thinks it's done. Stop hooks get a veto (back-pressure).
                veto = next((v for h in self.hooks.on_stop if (v := h(reply.text))), None)
                if veto and stop_retries < self.max_stop_retries:
                    stop_retries += 1
                    self.tracer.event("hook", msg=f"stop vetoed: {veto}")
                    messages.append({"role": "user", "content": f"[harness] Not done: {veto}"})
                    continue
                reason = "done" if not veto else "stopped_by_hook_limit"
                return self._finish(reply.text, messages, turn, reason, tool_log)

            for call in reply.tool_calls:
                result = self._execute(call)
                tool_log.append({"turn": turn, "name": call.name, "arguments": call.arguments, "result": result})
                messages.append(tool_result_message(call, result))

        return self._finish(reply.text, messages, self.max_turns, "max_turns", tool_log)

    # ------------------------------------------------------------------ one tool call
    def _execute(self, call: ToolCall) -> str:
        self.tracer.event("tool_call", name=call.name, arguments=call.arguments)
        tool = self.tools.get(call.name)
        if tool is None:   # hallucinated tool name: tell model, don't crash
            return self._res(call, f"ERROR: no tool named '{call.name}'. Available: {list(self.tools)}", True)

        if self.policy:
            decision = self.policy(tool, call)
            if decision == "ask":
                decision = "allow" if self.ask_fn(f"{call.name}({json.dumps(call.arguments)})") else "deny"
            if decision == "deny":
                self.tracer.event("policy", msg=f"denied {call.name}")
                return self._res(call, "DENIED by user/policy. Do not retry; choose another approach or explain.", True)

        for h in self.hooks.pre_tool:
            if (block := h(call)):
                self.tracer.event("hook", msg=f"pre_tool blocked {call.name}: {block}")
                return self._res(call, f"BLOCKED by hook: {block}", True)

        try:
            out = tool.fn(**call.arguments)
            result = out if isinstance(out, str) else json.dumps(out, default=str)
            err = False
        except TypeError as e:          # bad/missing args -> teach the model the contract
            result, err = f"ERROR: bad arguments: {e}. Schema: {json.dumps(tool.parameters)}", True
        except Exception as e:          # tool failed -> model can recover/try differently
            result, err = f"ERROR: {type(e).__name__}: {e}", True

        for h in self.hooks.post_tool:
            if (extra := h(call, result)):
                self.tracer.event("hook", msg=f"post_tool feedback on {call.name}")
                result = f"{result}\n[hook] {extra}"
        return self._res(call, result, err)

    def _res(self, call: ToolCall, result: str, error: bool) -> str:
        self.tracer.event("tool_result", name=call.name, result=result, error=error)
        return result

    def _finish(self, text, messages, turns, reason, tool_log) -> Result:
        usage = dict(getattr(self.llm, "total_usage", {}))
        self.tracer.event("final", reason=reason, turns=turns, usage=usage, text=text)
        return Result(text=text, messages=messages, turns=turns, reason=reason, tool_log=tool_log, usage=usage)
