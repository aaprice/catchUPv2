"""Tracing: every LLM call + tool call -> JSONL in runs/. Plus colored console view.

Senior-dev mapping: this is your structured logging / distributed tracing. With agents,
traces ARE the debugger. "Read the traces" is rule #1 of agent engineering.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
C = {"dim": "\033[2m", "cyan": "\033[36m", "yellow": "\033[33m", "green": "\033[32m",
     "red": "\033[31m", "mag": "\033[35m", "bold": "\033[1m", "end": "\033[0m"}
if os.name == "nt":
    os.system("")  # enables ANSI colors in Windows console


def _clip(s: str, n: int = 400) -> str:
    s = str(s)
    return s if len(s) <= n else s[:n] + f" ...[+{len(s) - n} chars]"


class Tracer:
    def __init__(self, name: str, verbose: bool = True, to_file: bool = True):
        self.name, self.verbose = name, verbose
        self.path = None
        if to_file:
            RUNS.mkdir(exist_ok=True)
            self.path = RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.jsonl"

    def event(self, kind: str, **data) -> None:
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), "agent": self.name, "kind": kind, **data}, default=str) + "\n")
        if self.verbose:
            self._print(kind, data)

    def _print(self, kind: str, d: dict) -> None:
        tag = f"{C['dim']}[{self.name}]{C['end']}"
        if kind == "llm_reply":
            u = d.get("usage", {})
            meta = f"{C['dim']}({u.get('in', 0)} in / {u.get('out', 0)} out tok, {d.get('latency_ms', 0)}ms){C['end']}"
            if d.get("text"):
                print(f"{tag} {C['cyan']}assistant:{C['end']} {_clip(d['text'], 600)} {meta}")
            else:
                print(f"{tag} {meta}")
        elif kind == "tool_call":
            print(f"{tag} {C['yellow']}-> {d['name']}({json.dumps(d['arguments'])}){C['end']}")
        elif kind == "tool_result":
            col = C["red"] if d.get("error") else C["green"]
            print(f"{tag} {col}<- {_clip(d['result'], 300)}{C['end']}")
        elif kind in ("hook", "policy", "compact", "loop"):
            print(f"{tag} {C['mag']}{kind}: {_clip(d.get('msg', d), 300)}{C['end']}")
        elif kind == "final":
            print(f"{tag} {C['bold']}DONE ({d.get('reason')}) turns={d.get('turns')} usage={d.get('usage')}{C['end']}")
        elif kind == "info":
            print(f"{tag} {d.get('msg')}")
        sys.stdout.flush()
