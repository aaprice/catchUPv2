"""[v2] M05 — MCP server driving the Unity Editor via the Ember Bridge (EmberBridge.cs, TCP 9877).

Unity must be open with Ember > Start Bridge (or Auto-start). Register:
  OpenCode:    opencode.json  "unity": {..., "enabled": true}
  Claude Code: .mcp.json already lists "unity"
Debug:        npx @modelcontextprotocol/inspector uv run python modules/05_mcp/unity/unity_mcp_server.py

Same architecture as the Blender bridge: thin whitelisted command server INSIDE the engine,
MCP + validation logic OUTSIDE in Python (where your schemas + validator live).
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from game import ContentDB, validate_level  # noqa: E402

PORT = 9877
mcp = MCPServer("unity", instructions="Builds Ember Crypt level grey-boxes in a running Unity Editor. "
                                      "Call unity_ping first. Grid coords match game coords (x right, y down).")


def send(cmd: str, **args) -> str:
    """One request/response. Args double-encoded as a JSON string (JsonUtility can't parse free-form dicts)."""
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=120) as s:
            s.sendall((json.dumps({"cmd": cmd, "args": json.dumps(args)}) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
    except OSError as e:
        return f"ERROR: Unity bridge not reachable ({e}). Open Unity, menu Ember > Start Bridge."
    if not buf:
        return "ERROR: empty response from Unity (bridge busy or editor throttled; retry)"
    resp = json.loads(buf.decode())
    return resp["result"] if resp.get("ok") else f"ERROR: {resp.get('error')}"


@mcp.tool()
def unity_ping() -> str:
    """Check Unity bridge is up; returns Unity version + active scene."""
    return send("ping")


@mcp.tool()
def unity_scene_info() -> str:
    """Counts of Ember objects (walls, doors, enemies, items, props) in the scene."""
    return send("scene_info")


@mcp.tool()
def unity_build_level(level_name: str = "level_01", tile: float = 2.0, wall_height: float = 3.0) -> str:
    """Validate a game level, then build it in the open Unity scene: grey-box walls/doors/markers, enemy capsules,
    item spheres, a playable PlayerAvatar (EmberGridPlayer) and top-down camera. Replaces previous EmberLevel."""
    db = ContentDB(include_generated=True)
    try:
        lv = db.load_level(level_name)
    except FileNotFoundError:
        return f"ERROR: no level '{level_name}'"
    rep = validate_level(lv, db)
    if not rep.ok:
        return "REFUSED: level invalid\n" + rep.as_feedback()
    return send("build_level", level=json.loads(lv.model_dump_json()), tile=tile, wall_height=wall_height)


@mcp.tool()
def unity_add_prop(kind: str, x: int, y: int) -> str:
    """Add prop at grid cell (floor '.' only). kind: pillar | coffin | brazier (brazier adds a point light)."""
    return send("add_prop", kind=kind, x=x, y=y)


@mcp.tool()
def unity_screenshot(filename: str = "unity_blockout.png") -> str:
    """Render Main Camera to PNG in runs/. Returns path. A multimodal model can Read it to SEE the layout."""
    out = ROOT / "runs" / Path(filename).name
    out.parent.mkdir(exist_ok=True)
    return send("screenshot", path=str(out), width=1280, height=720)


@mcp.tool()
def unity_clear() -> str:
    """Delete the EmberLevel root object."""
    return send("clear")


if __name__ == "__main__":
    mcp.run()
