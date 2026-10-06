# M06b [v2] — OpenCode: the open-source harness (any model, work-friendly)

Goal: everything M06 taught with Claude Code, on a harness that runs **any model**: Ollama Gemma/Qwen/gpt-oss at your desk, or the DGX. Same concepts, different config files. If you did M06 at home, this module mostly maps them across.

## Why OpenCode

| Harness | License | Local models | MCP | Skills | Subagents | Hooks | Headless | Verdict |
|---|---|---|---|---|---|---|---|---|
| **OpenCode** | MIT | ✓ (any OpenAI-compatible) | ✓ | ✓ (reads `.claude/skills` too) | ✓ (markdown agents) | ✓ (JS plugins) | `opencode run` | **closest Claude Code twin → primary** |
| Goose (Block) | Apache-2.0 | ✓ | ✓ (MCP-native "extensions") | recipes | subrecipes | limited | `goose run` | good alt; strong MCP story |
| Codex CLI (OpenAI) | Apache-2.0 | ✓ `--oss` (Ollama) | ✓ | ✓ | – | – | `codex exec` | solid; fewer extension points |
| Aider | Apache-2.0 | ✓ | – | – | – | – | ✓ | great pair-programmer, not an agent platform |
| Claude Code | proprietary | via Ollama Anthropic API (M06 §8) | ✓ | ✓ | ✓ | ✓ | `claude -p` | home track |

Check your org's software approval for whichever you pick. All the patterns transfer.

## Concept map: Claude Code ↔ OpenCode (this repo)

| Concept | Claude Code (`M06`) | OpenCode (`M06b`) |
|---|---|---|
| Project memory | `CLAUDE.md` | `AGENTS.md` (canonical in v2; CLAUDE.md just imports it) |
| Config | `.claude/settings.json` | `opencode.json` (root) + `.opencode/` |
| Model | Anthropic only (or Ollama shim) | `"model": "ollama/qwen3.5:9b"`, `dgx/...`, `llamacpp/local` (switch: `/models`) |
| Permissions | `permissions.allow/ask/deny` | `"permission": {"bash": {"git push*": "deny"}}`, per agent too |
| MCP | `.mcp.json` | `"mcp"` in opencode.json (`"type":"local","command":[...]`) |
| MCP tool names | `mcp__ember__save_level` | `ember_save_level` |
| Skills | `.claude/skills/*/SKILL.md` | **same files** (OpenCode reads `.claude/skills`, `.opencode/skills`, `.agents/skills`) |
| Slash commands | skills w/ `$ARGUMENTS`, `` !`cmd` `` | `.opencode/commands/*.md` (`$ARGUMENTS`, `` !`cmd` ``, `@file`) |
| Subagents | `.claude/agents/*.md` (`tools:`) | `.opencode/agents/*.md` (`mode: subagent`, `permission:`) |
| PreToolUse hook | python, exit 2 = block | plugin `tool.execute.before`, `throw` = block |
| PostToolUse hook | JSON `decision:block` | plugin `tool.execute.after`, mutate `output.output` |
| Stop hook veto | ✓ | ✗ (use Ralph outer loop / explicit verify step) |
| Headless | `claude -p --output-format json --json-schema` | `opencode run -m <model> --agent <a> [--format json]` (no schema flag) |
| Plan mode | Shift+Tab | Tab to switch to built-in **Plan** agent |

Takeaway: harness = interchangeable shell around the same ideas. Skills (open Agent Skills format) and MCP servers move between harnesses unchanged. Hooks and agents need light translation.

## Setup

```powershell
npm install -g opencode-ai           # or see opencode.ai/docs for other installers
opencode --version
# Ollama context MUST be big for agent CLIs (system prompt + tools ≈ 10K+ tokens):
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","32768","User")   # restart Ollama after
ollama pull qwen3.5:9b                # tool-calling workhorse for OpenCode
ollama pull gemma4:e4b                # small_model (titles/summaries)
cd C:\Users\iamap\Development\ClaudeProjects\catchUPv2
opencode                              # TUI. /models to switch engine. Tab = Build/Plan agents
```

DGX: run `modules/11_open_models/serving/vllm_dgx.sh`, set user env `DGX_URL=http://<dgx>:8000/v1`, pick `dgx/...` in `/models`.

**Gemma 4 in OpenCode:** early Ollama + Gemma 4 + OpenCode combos dropped tool calls (thinking/"reasoning" field in streamed chunks; OpenCode issue #20995). If tools silently don't fire with `gemma4:*`: update Ollama + OpenCode and re-pull the model; else serve Gemma via **llama.cpp `--jinja`** (`llamacpp/local`) or the DGX vLLM `gemma4` parser; else use qwen3.5/gpt-oss for agent work and Gemma via our `lib/` (prompt mode). Verify with the lab below, not by vibes.

## Files in this repo

```
AGENTS.md                       rules (shared by every harness)
opencode.json                   providers (ollama, llamacpp, dgx), MCP (ember on; blender/unity off), permissions
.opencode/agents/               level-designer, qa-verifier, lore-writer (subagents), ralph (primary, locked-down)
.opencode/commands/             /tutor, /balance-check, /level-forge
.opencode/plugins/ember-guard.js  bash guard + audit log + post-edit content validation (reuses .claude/hooks/validate_content.py)
.claude/skills/                 ember-content, tutor, ... (read by OpenCode too)
```

## Guided lab (~60–90 min, mirrors M06)

```powershell
opencode
```
1. `/models` → pick `ollama/qwen3.5:9b`. Ask: "what are the project rules?" → answer comes from AGENTS.md.
2. "list ember MCP tools, then simulate gravewarden vs every weapon+armor combo as a table" → MCP. (`opencode mcp list` from shell = status.)
3. `/balance-check` → live data injected via `` !`cmd` ``.
4. "copy level_01 to game/data/generated/broken_test.json with the gravewarden at 0,0" → plugin appends `[ember-validate] ... INVALID` to the write result → model fixes it. Look for it.
5. "clean runs folder with rm -rf runs" → plugin blocks. `runs/bash_audit.log` shows the attempt.
6. `/level-forge flooded ossuary 16x10 3 enemies locked door, flooded_ossuary` → subagent loop. Then `@qa-verifier check flooded_ossuary`.
7. Switch to `gemma4:e4b` and repeat step 6. Count iterations + failures. Then `dgx/...` if you have it. **Same harness, three engines.** Write 3 lines on where the harness saved the weak model.
8. Plan agent (Tab): "add a 'poison' status effect with tests". Review the plan, switch to Build, let it work, run `uv run pytest`.
9. `/tutor 06 quiz`.

## Headless + loops on OpenCode

```powershell
opencode run -m ollama/qwen3.5:9b "list enemies by threat"                       # one-shot
pwsh modules/07_loop_engineering/ralph/ralph_opencode.ps1 -MaxIters 2            # Ralph on local model
uv run python modules/08_multi_agent/studio_opencode.py --workers 2               # fan-out (orchestrator validates JSON itself)
```

## Exercises

- ★ Port `.claude/hooks/session_context.py` to a plugin: on `session.created`, log progress position (see plugin docs for injecting context).
- ★ Add `.opencode/commands/verify.md`: runs pytest + autoplay via `` !`...` `` and asks the model to fix failures = manual "Stop hook".
- ★★ Give `level-designer` a different model (frontmatter `model: ollama/gemma4:26b`) than the main agent. Cheap orchestrator, strong worker, or reverse? Measure.
- ★★ Goose: install, register same `ember` MCP server as an extension, run lab step 2. Third harness, same server.
- ★★★ Build a `ember-devkit` bundle: skills + agents + plugin + MCP config that installs into BOTH Claude Code (plugin) and OpenCode (`~/.config/opencode/`). Portable team asset for your M&S team at work.

Next: [M07 Loop engineering](../07_loop_engineering/) (use `ralph_opencode.ps1`).
