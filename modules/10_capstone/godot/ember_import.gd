# [v2] Godot 4 HEADLESS level importer: Ember level JSON -> .tscn scene file. No editor, no GUI.
#
#   godot --headless --path <your_godot_project> --script res://ember_import.gd -- <abs/path/level.json> res://ember_level.tscn
#
# Why this matters for agents: the whole build step is ONE shell command with an exit code.
# An agent (OpenCode/Claude Code/your harness) can run it, read stdout, open the .tscn (plain text!), and loop.
# Copy this file into your Godot project root first.
extends SceneTree

const TILE := 2.0
const WALL_H := 3.0
const COLORS := {
	"wall": Color(0.18, 0.16, 0.15), "floor": Color(0.35, 0.30, 0.26), "door": Color(0.55, 0.30, 0.08),
	"start": Color(0.1, 0.8, 0.2), "exit": Color(0.1, 0.4, 0.95), "enemy": Color(0.85, 0.1, 0.05),
	"item": Color(0.95, 0.8, 0.1),
}
var _mats := {}


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 2:
		printerr("usage: ... -- <level.json> <res://out.tscn>")
		quit(2)
		return
	var text := FileAccess.get_file_as_string(args[0])
	var lv = JSON.parse_string(text)
	if typeof(lv) != TYPE_DICTIONARY or not lv.has("map"):
		printerr("ERROR: not an Ember level json: ", args[0])
		quit(1)
		return
	var root := Node3D.new()
	root.name = "EmberLevel"
	var rows: Array = lv["map"]
	var h := rows.size()
	var w := String(rows[0]).length()
	_box(root, "Floor", Vector3((w - 1) * TILE / 2.0, -0.05, (h - 1) * TILE / 2.0), Vector3(w * TILE, 0.1, h * TILE), "floor")
	var walls := 0
	for y in h:
		var row := String(rows[y])
		for x in w:
			var c := row[x]
			var p := Vector3(x * TILE, 0, y * TILE)   # Godot: +Z toward camera; grid y -> +Z keeps map orientation top-down
			match c:
				"#":
					_box(root, "Wall_%d_%d" % [x, y], p + Vector3(0, WALL_H / 2.0, 0), Vector3(TILE, WALL_H, TILE), "wall")
					walls += 1
				"D":
					_box(root, "Door_%d_%d" % [x, y], p + Vector3(0, WALL_H * 0.45, 0), Vector3(TILE * 0.9, WALL_H * 0.9, TILE * 0.3), "door")
				"@":
					_box(root, "Start_%d_%d" % [x, y], p + Vector3(0, 0.05, 0), Vector3(TILE * 0.7, 0.1, TILE * 0.7), "start")
				">":
					_box(root, "Exit_%d_%d" % [x, y], p + Vector3(0, 0.05, 0), Vector3(TILE * 0.8, 0.1, TILE * 0.8), "exit")
	for e in lv.get("enemies", []):
		_box(root, "Enemy_%s_%d_%d" % [e["id"], int(e["x"]), int(e["y"])], Vector3(e["x"] * TILE, 0.75, e["y"] * TILE), Vector3(1, 1.5, 1), "enemy")
	for it in lv.get("items", []):
		_box(root, "Item_%s_%d_%d" % [it["id"], int(it["x"]), int(it["y"])], Vector3(it["x"] * TILE, 0.3, it["y"] * TILE), Vector3(0.6, 0.6, 0.6), "item")

	var cam := Camera3D.new()
	cam.name = "TopCamera"
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.size = max(w, h) * TILE * 1.1
	cam.position = Vector3(w * TILE / 2.0 - 1, 40, h * TILE / 2.0 - 1)
	cam.rotation_degrees = Vector3(-90, 0, 0)
	_add(root, cam)
	var sun := DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-55, 30, 0)
	_add(root, sun)

	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err == OK:
		err = ResourceSaver.save(packed, args[1])
	if err != OK:
		printerr("ERROR saving scene: ", err)
		quit(1)
		return
	print("EMBER_OK built %s %dx%d walls=%d -> %s" % [lv.get("name", "?"), w, h, walls, args[1]])
	root.free()
	quit(0)


func _box(root: Node3D, node_name: String, pos: Vector3, size: Vector3, kind: String) -> void:
	var mi := MeshInstance3D.new()
	mi.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = _mat(kind)
	mi.position = pos
	_add(root, mi)


func _add(root: Node3D, n: Node) -> void:
	root.add_child(n)
	n.owner = root          # REQUIRED: only nodes owned by root get saved by PackedScene.pack


func _mat(kind: String) -> StandardMaterial3D:
	if not _mats.has(kind):
		var m := StandardMaterial3D.new()
		m.albedo_color = COLORS[kind]
		_mats[kind] = m
	return _mats[kind]
