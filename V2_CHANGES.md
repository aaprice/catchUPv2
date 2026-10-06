# v2 changes (v1 = ../CatchUP, untouched)

## Model layer
- `lib/profiles.py` NEW: named engine profiles (qwen3-8b, qwen3.5-9b, gemma4-e4b/12b/26b/31b, gpt-oss-20b, qwen3-coder-30b, llamacpp, lmstudio, dgx-vllm, gemini). Select with `LLM_PROFILE`.
- `lib/llm.py`: `LLM(profile=, tool_mode=)`; **prompt-mode tool calling** (`_chat_prompt_tools`): tools described in prompt + JSON-schema-forced replies, parsed by harness. Same `Reply` out.
- `.env.example`: profile-first; DGX/llama.cpp/Gemini blocks.
- `tools/check_setup.py`: profile-aware VRAM recommendations; checks opencode/llama-server.
- `modules/01_raw_api/hello.py`, `modules/04_context_engineering/cache_demo.py`: model from profile.
- `tests/test_profiles.py` NEW: profile resolution + prompt-mode loop (no model needed).

## New module M11 (open models)
- `modules/11_open_models/README.md`: families, licenses/origin, serving stacks, native vs prompt tools, Gemma 4 field notes, context.
- `bakeoff.py`: tools% (M09 cases) + JSON% (M02) + tok/s per profile/tool-mode → winner line for `.env`.
- `serving/vllm_dgx.sh`, `serving/llamacpp_server.ps1`, `serving/offline_models.md`.

## Harness: OpenCode track (M06b)
- `AGENTS.md` NEW canonical rules; `CLAUDE.md` now `@AGENTS.md` + Claude specifics.
- `opencode.json` NEW: providers ollama / llamacpp / dgx, MCP (ember on, blender + unity off), permissions.
- `.opencode/agents/`: level-designer, qa-verifier, lore-writer, ralph. `.opencode/commands/`: tutor, balance-check, level-forge.
- `.opencode/plugins/ember-guard.js`: bash guard + audit + post-edit validation (reuses `.claude/hooks/validate_content.py`).
- `modules/07_loop_engineering/ralph/ralph_opencode.ps1`, `modules/08_multi_agent/studio_opencode.py`.
- `docs/opencode-cheatsheet.md`.

## Engines
- UE5 track REMOVED (`modules/10_capstone/ue5/`). Still in v1 if ever needed.
- `modules/05_mcp/unity/` NEW: `unity_mcp_server.py` + C# `EmberBridge` (TCP 9877), `EmberLevelBuilder` (menu import, props, screenshot), runtime `EmberGridPlayer` (playable), `MirelaChat` (Ollama NPC).
- `modules/10_capstone/godot/ember_import.gd` NEW: Godot 4 headless JSON→.tscn.
- `capstone/build.py`: `--unity`; report lists Unity/Godot commands. `.mcp.json` + `.claude/settings.json`: unity server.

## Not verified in my sandbox (no GPU/Unity/Godot/OpenCode there)
- C# (Unity) + GDScript: written against Unity 2022.3/6 and Godot 4 APIs, not compiled. Engine console = verifier.
- `opencode.json`/agents/commands/plugin: per opencode.ai docs (Oct 2026); plugin JS syntax-checked + guard logic unit-tested in Node.
- Real model quality: run the bake-off.
