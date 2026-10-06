# SETUP v2 (Windows 11 — home PC or work workstation)

All commands = PowerShell in the repo root (`...\ClaudeProjects\catchUPv2`) unless noted.
**Work machine:** install only what your org approves. Everything here is open source except Claude Code (home only). For an offline/restricted box see [modules/11_open_models/serving/offline_models.md](modules/11_open_models/serving/offline_models.md).

## 1. Core tools

```powershell
winget install --id Git.Git -e                    # git + Git Bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # uv: Python env manager
winget install OpenJS.NodeJS.LTS                  # Node: OpenCode install + MCP Inspector
```
Restart terminal:
```powershell
git init -b main; git add -A; git commit -m "baseline"   # loops + worktrees need git (M07-08)
uv sync                                                  # .venv + pydantic, mcp, pytest
uv run pytest                                            # all green, no model needed
Copy-Item .env.example .env
```

## 2. Engine: pick a profile

```powershell
nvidia-smi --query-gpu=name,memory.total --format=csv
uv run python tools/check_setup.py        # lists profiles that fit your GPU + checks servers/models
```

| VRAM | Profile (`LLM_PROFILE=` in .env) | Pull |
|---|---|---|
| ≤ 8 GB | `gemma4-e4b` (prompt-mode tools) or `qwen3-8b` | `ollama pull gemma4:e4b` |
| 8–12 GB | `qwen3.5-9b`, `gemma4-12b` | `ollama pull qwen3.5:9b` |
| 16 GB | `gpt-oss-20b` | `ollama pull gpt-oss:20b` |
| 18–24 GB | **`gemma4-26b`** (MoE: best Gemma for agents) | `ollama pull gemma4:26b` |
| DGX | `dgx-vllm` (+ `DGX_URL`, `DGX_MODEL`) | `modules/11_open_models/serving/vllm_dgx.sh` |
| any, max reliability | `llamacpp` | `serving/llamacpp_server.ps1` with a GGUF |

Work note: some orgs restrict models by license or developer origin. Check before using Qwen at work; Gemma / gpt-oss are the usual safe picks. Then measure: `uv run python modules/11_open_models/bakeoff.py --profiles gemma4-e4b gemma4-26b gpt-oss-20b`.

```powershell
ollama pull nomic-embed-text            # embeddings for RAG (M04)
uv run python modules/01_raw_api/hello.py
```

**Context:** Ollama's default context is small and silently truncates. Our `lib/` sends `num_ctx` per request (`OLLAMA_NUM_CTX`, default 16384). Agent CLIs (OpenCode) can't do that through the OpenAI endpoint, so set the server default:
```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","32768","User")   # then restart Ollama
```

## 3. Harness

**Work / any model — OpenCode (M06b):**
```powershell
npm install -g opencode-ai
opencode            # in repo root: reads AGENTS.md, opencode.json, .opencode/, .claude/skills
```

**Home — Claude Code (M06), optional:**
```powershell
irm https://claude.ai/install.ps1 | iex
claude              # /login with Pro. Reads CLAUDE.md (-> AGENTS.md), .claude/, .mcp.json
```
Claude Code hooks run `uv run python ...` through Git Bash, so `uv` must be on PATH there (`uv --version` in Git Bash).

## 4. Engines (optional, M05/M10)

- **Unity** (2022.3 LTS / Unity 6): copy `modules/05_mcp/unity/EmberUnity/Assets/Ember/` into your project's `Assets/`. Menu **Ember**. Details: [unity README](modules/05_mcp/unity/README.md).
- **Godot 4** (recommended for agent loops, free/MIT): `winget install GodotEngine.GodotEngine` (or zip from godotengine.org). Headless importer in `modules/10_capstone/godot/`.
- **Blender** 4.2+: add-on `modules/05_mcp/blender/ember_blender_addon.py`.
- **GameMaker**: exercise only.

## 5. Sanity checklist

- [ ] `uv run pytest` green
- [ ] `uv run python tools/check_setup.py` → server up, profile model present
- [ ] `uv run python modules/01_raw_api/hello.py` prints a reply
- [ ] `opencode run "say hi"` prints a reply (or `claude -p "say hi"` at home)
- [ ] `ollama ps` shows model `100% GPU`
