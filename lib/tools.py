"""@tool decorator: Python function -> JSON-Schema tool spec the model can read.

The model never runs code. It emits a *request* {"name": ..., "arguments": {...}}.
YOUR harness decides whether/how to run it. Tool = API contract written for an LLM reader:
name + description + parameter schema. Description quality matters as much as code quality.
"""
from __future__ import annotations

import inspect
import re
import typing
from dataclasses import dataclass
from typing import Any, Callable, Literal, get_args, get_origin

_PY2JSON = {str: "string", int: "integer", float: "number", bool: "boolean"}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]
    read_only: bool = True        # harness policy uses this (read-only tools auto-allowed)

    def spec(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.parameters}

    def __call__(self, **kw):
        return self.fn(**kw)


def _schema_for(tp: Any) -> dict:
    origin = get_origin(tp)
    if origin is Literal:
        vals = list(get_args(tp))
        return {"type": _PY2JSON.get(type(vals[0]), "string"), "enum": vals}
    if origin in (list, typing.List):
        (inner,) = get_args(tp) or (str,)
        return {"type": "array", "items": _schema_for(inner)}
    if origin in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        non_none = [a for a in get_args(tp) if a is not type(None)]
        return _schema_for(non_none[0])
    if tp is dict or origin is dict:
        return {"type": "object"}
    return {"type": _PY2JSON.get(tp, "string")}


def _param_docs(doc: str) -> dict[str, str]:
    """Parse Google-style 'Args:' block -> {param: description}."""
    out, in_args = {}, False
    for line in doc.splitlines():
        s = line.strip()
        if s.lower().startswith("args:"):
            in_args = True
            continue
        if not in_args:
            continue
        if not s or s.endswith(":") and " " not in s:   # blank line or next section ("Returns:")
            break
        m = re.match(r"(\w+)\s*(\(.*?\))?:\s*(.+)", s)
        if m:
            out[m.group(1)] = m.group(3)
    return out


def tool(fn: Callable | None = None, *, name: str | None = None, read_only: bool = True):
    """Decorate a function to make it a Tool. Type hints -> schema, docstring -> descriptions."""

    def wrap(f: Callable) -> Tool:
        hints = typing.get_type_hints(f)
        sig = inspect.signature(f)
        doc = inspect.getdoc(f) or ""
        summary = doc.split("\n\nArgs:")[0].split("\nArgs:")[0].strip()
        pdocs = _param_docs(doc)
        props, required = {}, []
        for pname, p in sig.parameters.items():
            sch = _schema_for(hints.get(pname, str))
            if pname in pdocs:
                sch["description"] = pdocs[pname]
            props[pname] = sch
            if p.default is inspect.Parameter.empty:
                required.append(pname)
        params = {"type": "object", "properties": props, "required": required}
        return Tool(name=name or f.__name__, description=summary, parameters=params, fn=f, read_only=read_only)

    return wrap(fn) if fn else wrap
