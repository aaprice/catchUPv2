"""Ember Bridge — Blender add-on exposing a tiny JSON command server on 127.0.0.1:9876.

Install: Blender > Edit > Preferences > Add-ons > (dropdown v) Install from Disk > pick this file > enable.
Use:     3D Viewport > N sidebar > "Ember" tab > Start Server.

Architecture (M05):
  Claude Code / your harness ──MCP(stdio)──► blender_mcp_server.py ──TCP JSON lines──► THIS add-on (inside Blender)

Why a socket and not MCP directly in Blender? Blender's Python is embedded, single-threaded UI, own
interpreter + packages. Keep Blender side dumb (whitelisted commands), put MCP logic outside.

Security lesson: commands are WHITELISTED. `run_python` exists but is OFF by default
(Preferences > Add-ons > Ember Bridge > Allow run_python). Arbitrary exec from an LLM = full control of
your machine as you. Enable only when watching.
"""
bl_info = {
    "name": "Ember Bridge (CatchUP M05)",
    "author": "CatchUP",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Ember",
    "description": "JSON socket server so an MCP server/agent can build Ember Crypt levels",
    "category": "Development",
}

import json
import math
import socket
import traceback

import bmesh
import bpy

HOST, PORT = "127.0.0.1", 9876
COLL = "Ember"
COLORS = {
    "wall": (0.18, 0.16, 0.15, 1), "floor": (0.35, 0.30, 0.26, 1), "door": (0.55, 0.30, 0.08, 1),
    "start": (0.1, 0.8, 0.2, 1), "exit": (0.1, 0.4, 0.95, 1), "enemy": (0.85, 0.1, 0.05, 1),
    "item": (0.95, 0.8, 0.1, 1), "prop": (0.6, 0.55, 0.5, 1), "ember": (1.0, 0.35, 0.0, 1),
}

_state = {"sock": None, "clients": {}, "running": False}


# ------------------------------------------------------------------ scene helpers
def _coll():
    c = bpy.data.collections.get(COLL)
    if not c:
        c = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(c)
    return c


def _mat(kind):
    name = f"ember_{kind}"
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
        m.diffuse_color = COLORS[kind]
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = COLORS[kind]
            if kind == "ember" and "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = COLORS[kind]
                bsdf.inputs["Emission Strength"].default_value = 5.0
    return m


def _mesh(shape, kind):
    name = f"ember_{shape}_{kind}"
    me = bpy.data.meshes.get(name)
    if me:
        return me
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    if shape == "cube":
        bmesh.ops.create_cube(bm, size=1.0)
    elif shape == "cone":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.5, radius2=0.0, depth=1.0)
    elif shape == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.5)
    elif shape == "cyl":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.5, radius2=0.5, depth=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(_mat(kind))
    return me


def _spawn(name, shape, kind, loc, scale=(1, 1, 1)):
    obj = bpy.data.objects.new(name, _mesh(shape, kind))
    obj.location, obj.scale = loc, scale
    _coll().objects.link(obj)
    return obj


# ------------------------------------------------------------------ whitelisted commands
def cmd_ping(**_):
    return {"pong": True, "blender": bpy.app.version_string}


def cmd_scene_info(**_):
    c = bpy.data.collections.get(COLL)
    objs = list(c.objects) if c else []
    kinds = {}
    for o in objs:
        k = o.name.split("_")[0]
        kinds[k] = kinds.get(k, 0) + 1
    return {"ember_objects": len(objs), "by_kind": kinds,
            "sample": [{"name": o.name, "loc": [round(v, 2) for v in o.location]} for o in objs[:15]]}


def cmd_clear(**_):
    c = bpy.data.collections.get(COLL)
    n = 0
    if c:
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
            n += 1
    return {"removed": n}


def cmd_build_level(map, enemies=(), items=(), tile=2.0, wall_height=3.0, **_):
    """map: list[str] legend '# . @ > D'. Grid (x,y) -> world (x*tile, -y*tile)."""
    cmd_clear()
    h, w = len(map), len(map[0])
    t = tile
    _spawn("floor_main", "cube", "floor", ((w - 1) * t / 2, -(h - 1) * t / 2, -0.05), (w * t, h * t, 0.1))
    counts = {"wall": 0, "door": 0}
    for y, row in enumerate(map):
        for x, ch in enumerate(row):
            wx, wy = x * t, -y * t
            if ch == "#":
                _spawn(f"wall_{x}_{y}", "cube", "wall", (wx, wy, wall_height / 2), (t, t, wall_height))
                counts["wall"] += 1
            elif ch == "D":
                _spawn(f"door_{x}_{y}", "cube", "door", (wx, wy, wall_height / 2), (t * 0.9, t * 0.3, wall_height * 0.9))
                counts["door"] += 1
            elif ch == "@":
                _spawn(f"start_{x}_{y}", "cyl", "start", (wx, wy, 0.05), (t * 0.7, t * 0.7, 0.1))
            elif ch == ">":
                _spawn(f"exit_{x}_{y}", "cyl", "exit", (wx, wy, 0.05), (t * 0.8, t * 0.8, 0.1))
    for e in enemies:
        _spawn(f"enemy_{e['id']}_{e['x']}_{e['y']}", "cone", "enemy", (e["x"] * t, -e["y"] * t, 0.75), (t * 0.6, t * 0.6, 1.5))
    for i in items:
        _spawn(f"item_{i['id']}_{i['x']}_{i['y']}", "sphere", "item", (i["x"] * t, -i["y"] * t, 0.5), (0.6, 0.6, 0.6))
    cmd_overview_camera(width=w * t, height=h * t)
    return {"built": f"{w}x{h}", **counts, "enemies": len(enemies), "items": len(items)}


def cmd_add_prop(kind, x, y, tile=2.0, **_):
    """Composite props from primitives. kind: pillar | coffin | brazier."""
    wx, wy = x * tile, -y * tile
    if kind == "pillar":
        _spawn(f"prop_pillar_{x}_{y}", "cyl", "prop", (wx, wy, 1.5), (0.8, 0.8, 3.0))
    elif kind == "coffin":
        _spawn(f"prop_coffin_{x}_{y}", "cube", "prop", (wx, wy, 0.3), (0.8, 1.8, 0.6))
    elif kind == "brazier":
        _spawn(f"prop_brazier_{x}_{y}", "cyl", "prop", (wx, wy, 0.5), (0.6, 0.6, 1.0))
        _spawn(f"prop_brazierfire_{x}_{y}", "sphere", "ember", (wx, wy, 1.15), (0.45, 0.45, 0.45))
    else:
        raise ValueError("kind must be pillar|coffin|brazier")
    return {"added": kind, "at": [x, y]}


def cmd_overview_camera(width=40.0, height=22.0, **_):
    scn = bpy.context.scene
    cam = bpy.data.objects.get("ember_cam")
    if not cam:
        cam = bpy.data.objects.new("ember_cam", bpy.data.cameras.new("ember_cam"))
        scn.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(width, height) * 1.1
    cam.location = (width / 2 - 1, -height / 2 + 1, 50)
    cam.rotation_euler = (0, 0, 0)
    scn.camera = cam
    if not bpy.data.objects.get("ember_sun"):
        sun = bpy.data.objects.new("ember_sun", bpy.data.lights.new("ember_sun", "SUN"))
        sun.rotation_euler = (math.radians(35), 0, math.radians(30))
        scn.collection.objects.link(sun)
    return {"camera": "ember_cam"}


def cmd_render_preview(path, res=900, **_):
    scn = bpy.context.scene
    scn.render.engine = "BLENDER_WORKBENCH"
    scn.render.resolution_x = res
    scn.render.resolution_y = int(res * 0.6)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return {"rendered": path}


def cmd_run_python(code, **_):
    prefs = bpy.context.preferences.addons.get(__name__)
    if not (prefs and prefs.preferences.allow_exec):
        raise PermissionError("run_python disabled. Enable in add-on preferences (risky).")
    scope = {"bpy": bpy, "result": None}
    exec(code, scope)
    return {"result": repr(scope.get("result"))}


COMMANDS = {n[4:]: f for n, f in globals().items() if n.startswith("cmd_")}


# ------------------------------------------------------------------ socket server (polled by timer)
def _handle(line):
    try:
        req = json.loads(line)
        fn = COMMANDS.get(req.get("cmd"))
        if not fn:
            return {"ok": False, "error": f"unknown cmd; available {sorted(COMMANDS)}"}
        return {"ok": True, "result": fn(**req.get("args", {}))}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-600:]}


def _poll():
    if not _state["running"]:
        return None
    s = _state["sock"]
    try:
        conn, _ = s.accept()
        conn.setblocking(False)
        _state["clients"][conn] = b""
    except BlockingIOError:
        pass
    for conn in list(_state["clients"]):
        try:
            data = conn.recv(65536)
            if not data:
                raise ConnectionResetError
            buf = _state["clients"][conn] + data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                conn.sendall((json.dumps(_handle(line.decode())) + "\n").encode())
            _state["clients"][conn] = buf
        except BlockingIOError:
            continue
        except Exception:
            conn.close()
            _state["clients"].pop(conn, None)
    return 0.1  # run again in 100ms (main thread -> safe to touch bpy)


def start():
    if _state["running"]:
        return
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(4)
    s.setblocking(False)
    _state.update(sock=s, running=True)
    bpy.app.timers.register(_poll, persistent=True)


def stop():
    _state["running"] = False
    for c in list(_state["clients"]):
        c.close()
    _state["clients"].clear()
    if _state["sock"]:
        _state["sock"].close()
        _state["sock"] = None


# ------------------------------------------------------------------ UI
class EMBER_OT_start(bpy.types.Operator):
    bl_idname = "ember.start"
    bl_label = "Start Server"

    def execute(self, context):
        start()
        self.report({"INFO"}, f"Ember Bridge listening on {HOST}:{PORT}")
        return {"FINISHED"}


class EMBER_OT_stop(bpy.types.Operator):
    bl_idname = "ember.stop"
    bl_label = "Stop Server"

    def execute(self, context):
        stop()
        return {"FINISHED"}


class EMBER_PT_panel(bpy.types.Panel):
    bl_label = "Ember Bridge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Ember"

    def draw(self, context):
        col = self.layout.column()
        col.label(text=f"{'RUNNING' if _state['running'] else 'stopped'}  {HOST}:{PORT}")
        col.operator("ember.stop" if _state["running"] else "ember.start")


class EmberPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__
    allow_exec: bpy.props.BoolProperty(name="Allow run_python (DANGEROUS: arbitrary code from agent)", default=False)

    def draw(self, context):
        self.layout.prop(self, "allow_exec")


CLASSES = (EMBER_OT_start, EMBER_OT_stop, EMBER_PT_panel, EmberPrefs)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    stop()
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
