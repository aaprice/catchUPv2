# M10 — Capstone: "Ember Crypt: One Level", built by agents

Goal: integrate everything. You direct; agents build; verifiers gate; you ship one polished level + engine blockout.

## Pipeline

```
 pitch ─► [studio: multi-agent] ─► new enemies/items/lore
               │
               ▼
          [forge: gen→verify→critic loop] ─► level JSON
               │
               ▼
          [GATES: validator · bot playtest · balance]  ── fail ──► loop again / fix with Claude Code
               │ pass
               ▼
   play in terminal · Blender blockout (MCP) · Unity playable grey-box (MCP) · Godot .tscn (headless) · REPORT.md
```
`capstone/build.py` = **workflow** (code-sequenced) wrapping **agents** (LLM inside each step). Deterministic skeleton, agentic muscles.

## Run (local track — free)

```powershell
uv run python capstone/build.py --pitch "frost-bitten crypt wing where the Long Winter never ended" --name frost_wing
uv run python -m game.play --level frost_wing
type capstone\REPORT_frost_wing.md
```

## Run (agent-harness track — OpenCode at work, Claude Code at home)

Same pipeline, but you drive with skills/subagents/MCP, interactive (`opencode` or `claude`):
```
opencode   # or: claude
> Read capstone/build.py to understand our pipeline. Then, WITHOUT running it, do the same with your own tools:
  1) design 2 new enemies + 1 item for theme "fungal ossuary" (validate via ember MCP, save to game/data/generated/enemies_fungal.json / items_fungal.json)
  2) /level-forge "fungal ossuary 18x10 using the new enemies, locked door" fungal_ossuary
  3) qa-verifier subagent on fungal_ossuary
  4) build it in Unity (unity MCP) or Blender, screenshot/render, look at it, add 4 props for atmosphere, render again
  5) write capstone/REPORT_fungal_ossuary.md
```
Compare with local track: quality, iterations, your interventions, usage spent.

## Engines

**Blender:** add-on from M05 running → `uv run python capstone/build.py ... --blender`, or via Claude Code `blender` MCP.

**Unity [v2, replaces UE5]:**
1. Copy `modules/05_mcp/unity/EmberUnity/Assets/Ember/` into your Unity project's `Assets/` (setup: [unity README](../05_mcp/unity/README.md)).
2. Direct: **Ember → Import Level JSON...** → `game/data/generated/<name>.json` → Play (WASD).
3. Agent route: **Ember → Start Bridge**, then `uv run python capstone/build.py ... --unity` or ask your agent "build <name> in unity, add braziers, screenshot".
4. Stretch: agent ports full combat rules to C# and proves parity against the Python sim (see unity README exercises).

**Godot 4 (recommended engine for agent work):** a free, MIT-licensed ~100MB download; text scene files (`.tscn`); GDScript; **runs headless from the CLI**. That last one is the agent superpower: build, test, even run the game with no GUI, so the agent gets an exit code + text output = a perfect verifier.
```powershell
# copy modules/10_capstone/godot/ember_import.gd into a Godot 4 project folder, then:
godot --headless --path C:\path\to\godot_project --script res://ember_import.gd -- C:\...\catchUPv2\game\data\level_01.json res://ember_level.tscn
```
Prints `EMBER_OK ...` on success. Open `ember_level.tscn` in the editor, or read it as text. Next steps for an agent: GDScript grid player, GUT unit tests run headless, and a loop where the agent edits `.gd` → runs headless tests → fixes.

| Engine | Agent-friendliness | Why |
|---|---|---|
| **Godot** | ★★★★★ | text scenes, headless CLI, tiny, open source, fast iteration |
| Unity | ★★★½ | C# great for LLMs; but YAML scenes w/ GUIDs, editor needed, domain reloads; bridge/MCP required |
| Blender | ★★★★ | full Python API; MCP bridge easy (M05) |
| Unreal | ★★ | heavy, binary assets, Blueprints opaque to text models (v1 track removed) |
| GameMaker | ★★½ | GML is text, project JSON-ish; no headless build loop |

**GameMaker (exercise):** agent writes `ember_room_loader` GML script: reads level JSON (`json_parse` on file contents) at room start, `instance_create_layer` walls/doors/enemies by grid × 32px. Give your agent (OpenCode/Claude Code) your GM project folder (`GameMakerProjects/...`), let it create script + objects, you run in GM. Verifier = you playing.

## Assignment (rubric — grade yourself, or `/tutor 10 review`)

| Criterion | Bar |
|---|---|
| Level passes all gates | validator ✓, bot wins w/ ≥5 hp, no balance flags |
| Uses ≥2 agent-made enemies + 1 item | from studio, lore-consistent |
| Loop evidence | trace shows ≥1 failed iteration fixed by feedback |
| Eval evidence | levelgen funnel + shopkeeper eval numbers before/after one change you made |
| Harness evidence | one hook or skill YOU wrote that caught a real problem |
| Engine | Blender render, Unity screenshot, or Godot .tscn of blockout |
| Write-up | REPORT: what agents did well, where they failed, what verifier saved you |

## Level-ups after capstone

- Swap Ollama for DGX-served bigger model (`LLM_PROVIDER=openai`, vLLM) → rerun evals. Data-driven model choice.
- Turn `.claude/` + `.mcp.json` into plugin; use it in a real work repo (OneSAF scenario files? Same pattern: schemas + validator + MCP + loop).
- Give Unity `MirelaChat` real tools (port harness loop to C#) — real tool-using LLM NPC in an engine.
- Read: Anthropic *Building Effective Agents*; Claude Code docs (hooks, skills, subagents); MCP spec; Hamel Husain on evals; Geoffrey Huntley on Ralph; Addy Osmani on loop engineering.

Done? Tick PROGRESS.md. You're caught up.
