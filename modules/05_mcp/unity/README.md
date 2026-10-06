# [v2] Unity bridge (replaces UE5 track)

```
 agent (OpenCode / Claude Code / lib harness)
   │ MCP stdio
   ▼
 unity_mcp_server.py ── validates level with game/ validator, refuses bad levels
   │ TCP 127.0.0.1:9877, JSON lines {"cmd","args":"<json string>"}
   ▼
 EmberBridge.cs (Editor, polled on EditorApplication.update = main thread)
   │
   ▼
 EmberLevelBuilder.cs ──► grey-box scene + playable PlayerAvatar + top-down camera
```

Same pattern as Blender (M05): dumb whitelisted command server **inside** the engine, smart MCP + validation **outside**. Engine #3 with zero changes to agents: that's MCP paying off.

## Install (Unity 2022.3 LTS or Unity 6)

1. Open (or create) a 3D project (URP or Built-in both fine).
2. Copy `EmberUnity/Assets/Ember/` into your project's `Assets/` → `Assets/Ember/Runtime/*.cs`, `Assets/Ember/Editor/*.cs`. Wait for compile.
3. Menu **Ember → Import Level JSON...** → pick `game/data/level_01.json` → scene builds. Press **Play**: WASD/arrows to move, bump enemies, grab the key, reach the exit.
4. Agent route: **Ember → Start Bridge** (or **Auto-start Bridge** to survive script reloads). Enable `unity` in `opencode.json` (`"enabled": true`), or approve it in Claude Code.
5. Ask the agent: *"unity_ping, then build level_01 in unity, add 3 braziers on floor tiles near the gravewarden, take a screenshot"*.
6. Optional NPC: add `MirelaChat` component to any GameObject → Play → **T** to talk (local Ollama). Set **Project Settings → Player → Other → Allow downloads over HTTP = Allowed in development builds**, or Unity blocks `http://localhost`.

Editor tip: **Preferences → General → Interaction Mode = No Throttling**, otherwise bridge calls lag while Unity is unfocused.

## Files

| File | Role |
|---|---|
| `Runtime/EmberData.cs` | `LevelData`/`Placement`: JsonUtility mirror of `game/content.py` Level schema |
| `Runtime/EmberLevelRuntime.cs` | on `EmberLevel` root: level data + grid↔world mapping + object lookup |
| `Runtime/EmberGridPlayer.cs` | grid movement, door/key, pickups, bump-attack (simplified rules) |
| `Runtime/MirelaChat.cs` | LLM NPC over Ollama `/api/chat` (UnityWebRequest + JsonUtility) |
| `Editor/EmberLevelBuilder.cs` | builds scene; menu items; props; screenshot to PNG |
| `Editor/EmberBridge.cs` | TCP JSON-lines server; whitelist: ping, scene_info, clear, build_level, add_prop, screenshot |

**Status:** Python/MCP side tested against a fake bridge. The C# was written for Unity 2022.3/6 APIs but **not compiled here** (no Unity in my sandbox). If the Console shows errors, paste them into your agent: *"fix this compile error in Assets/Ember/Editor/EmberBridge.cs"*. The Unity Console is the verifier, and that's a real loop.

## Production alternatives (read their code after building yours)

- **Unity's official MCP**: via the Unity CLI (`unity mcp`, Unity 6+). The older in-editor AI Assistant MCP is deprecated.
- **MCP for Unity** (CoplayDev, MIT, 2021.3+): many tools (scripts, assets, scene, console reading).
Compare their tool lists and security model with our 6-command whitelist.

## Exercises

- ★ Add `cmd focus_object(name)`: selects + frames object in Scene view (`Selection.activeObject`, `SceneView.lastActiveSceneView.FrameSelected()`).
- ★★ `cmd read_console`: return last N `Debug.Log` errors (hook `Application.logMessageReceived`). Agents can then fix compile/runtime errors in a loop **without you copy-pasting**. Biggest single upgrade to an engine bridge.
- ★★ Port `game/world.py` combat to `EmberGridPlayer` (hp/atk/def from `game/data/enemies.json` copied to `StreamingAssets`). Verify: same action list → same log in Python and Unity.
- ★★★ Give `MirelaChat` tools: port `lib/harness.py` loop to C# (native Ollama `tools` field, or prompt mode from M11). Shop state lives in C#; the model can only change it through tools.
