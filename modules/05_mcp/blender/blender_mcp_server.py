"""M05.3 — MCP server that drives Blender through the Ember Bridge add-on.

Claude Code picks this up from .mcp.json as server "blender". Blender must be open with bridge started.
Manual test:  npx @modelcontextprotocol/inspector uv run python modules/05_mcp/blender/blender_mcp_server.py
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

mcp = MCPServer("blender", instructions="Builds Ember Crypt level blockouts in a running Blender. "
                                        "Call blender_ping first. Grid coords match game coords.")


def send(cmd: str, **args) -> str:
    """One request/response over TCP JSON lines."""
    try:
        with socket.create_connection(("127.0.0.1", 9876), timeout=120) as s:
            s.sendall((json.dumps({"cmd": cmd, "args": args}) + "\n").encode())
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
    except OSError as e:
        return f"ERROR: Blender bridge not reachable ({e}). Open Blender, N-panel > Ember > Start Server."
    resp = json.loads(buf.decode())
    return json.dumps(resp["result"]) if resp.get("ok") else f"ERROR: {resp.get('error')}"


@mcp.tool()
def blender_ping() -> str:
    """Check Blender bridge is up; returns Blender version."""
    return send("ping")


@mcp.tool()
def blender_scene_info() -> str:
    """Count + sample of objects in the 'Ember' collection."""
    return send("scene_info")


@mcp.tool()
def blender_build_level(level_name: str = "level_01", tile: float = 2.0, wall_height: float = 3.0) -> str:
    """Validate a game level then build a grey-box blockout in Blender (walls, doors, start/exit, enemy cones,
    item spheres) with an overhead ortho camera. Replaces previous Ember objects."""
    db = ContentDB(include_generated=True)
    try:
        lv = db.load_level(level_name)
    except FileNotFoundError:
        return f"ERROR: no level '{level_name}'"
    rep = validate_level(lv, db)
    if not rep.ok:
        return "REFUSED: level invalid\n" + rep.as_feedback()
    return send("build_level", map=lv.map, enemies=[e.model_dump() for e in lv.enemies],
                items=[i.model_dump() for i in lv.items], tile=tile, wall_height=wall_height)


@mcp.tool()
def blender_add_prop(kind: str, x: int, y: int) -> str:
    """Add decorative prop at grid cell. kind: pillar | coffin | brazier. Put props on floor cells only."""
    return send("add_prop", kind=kind, x=x, y=y)


@mcp.tool()
def blender_render_preview(filename: str = "blockout.png") -> str:
    """Render overhead preview PNG into runs/. Returns path. (Claude Code can Read the PNG to SEE the result.)"""
    out = ROOT / "runs" / Path(filename).name
    out.parent.mkdir(exist_ok=True)
    return send("render_preview", path=str(out))


@mcp.tool()
def blender_clear() -> str:
    """Delete all objects in the Ember collection."""
    return send("clear")


if __name__ == "__main__":
    mcp.run()
