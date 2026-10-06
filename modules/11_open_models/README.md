# M11 [v2] — Open models: Gemma & friends, serving, quirks, bake-off

Goal: run every module on models you're allowed to use at work. Pick engine with data, not hype.

Do this module **right after M03** if you're on the work track. Everything later assumes a working engine.

## Analogy

Harness = car you built (M03–M10). Model = engine. v1 bolted in a rented race engine (Claude). v2 = engine bay with standard mounts: drop in Gemma, Qwen, gpt-oss, DGX-served monster. Some engines need adapter plates (quirks). `lib/profiles.py` = the adapter-plate catalog.

## What changes when you leave Claude

| Concern | Claude | Open/local model | What you do |
|---|---|---|---|
| Reasoning per step | very strong | weaker (esp. < 20B) | smaller steps, more verifiers, tighter tools (M03, M07) |
| Tool calling | rock solid | depends on model **and** server template | profile `tool_mode`, prompt-mode fallback, evals |
| Context | 200K+ usable | 32K–256K advertised; VRAM-bound | set `num_ctx`; compaction (M04) matters more |
| Harness | Claude Code | OpenCode / your `lib/` (M06b) | same concepts, different config files |
| Cost | subscription limits | free after hardware | loops + multi-agent get cheap → run more of them |
| Data | leaves machine | stays on box/DGX | good for work data |

Main lesson: **weaker engine makes harness quality visible.** Everything M02–M09 taught (schemas, validators, hooks, loops, evals) earns more with local models.

## Model families (Oct 2026 — tags change; verify on ollama.com/library)

| Family | Maker / license | Sizes (Ollama tags) | Agent notes |
|---|---|---|---|
| **Gemma 4** | Google / Gemma Terms of Use | `gemma4:e2b`, `e4b`, `12b`, `26b` (MoE ~4B active), `31b` | native function calling, 128K–256K ctx, multimodal. **26B MoE = sweet spot**: near-31B quality at small-model speed (needs ~18GB) |
| **gpt-oss** | OpenAI / Apache-2.0 | `gpt-oss:20b`, `120b` | strong tool use + reasoning effort control; 120b great on DGX |
| **Qwen 3 / 3.5** | Alibaba / Apache-2.0 | `qwen3:8b`, `qwen3.5:9b`, `qwen3-coder:30b` | best small tool-callers; coder variants great in OpenCode |
| **Llama 3.x** | Meta / Llama license | `llama3.1:8b`, `llama3.3:70b` | solid, older |
| **Mistral / Devstral** | Mistral / mostly Apache-2.0 | various | Devstral built for coding agents |
| **Granite 4** | IBM / Apache-2.0 | various | enterprise-oriented, permissive |

**Work reality check:** some government orgs restrict models by **license** or **developer origin**. Ask before using Qwen or DeepSeek at work. Gemma, gpt-oss, Llama, Granite and Mistral are the usual picks when that applies. Home: use whatever wins your bake-off.

## Serving stacks

```
            same OpenAI-ish HTTP API out the front
 ┌─────────────┬──────────────────┬──────────────────────┬─────────────┐
 │ Ollama      │ llama.cpp server │ vLLM (DGX)           │ LM Studio   │
 │ easiest     │ max control      │ max throughput       │ GUI         │
 │ 1 user      │ --jinja templates│ many parallel agents │ quick tests │
 │ :11434      │ :8080            │ :8000                │ :1234       │
 └─────────────┴──────────────────┴──────────────────────┴─────────────┘
```
Profiles: `gemma4-*`/`qwen*`/`gpt-oss-20b` → Ollama. `llamacpp`, `dgx-vllm`, `lmstudio` → OpenAI-compatible. Scripts in `serving/`.

**DGX = your team's private model API.** `serving/vllm_dgx.sh` serves Gemma 4 / gpt-oss-120b with tool parsing. Then every module, OpenCode, and teammates point at `http://<dgx>:8000/v1`. M08 parallel fan-out gets real speedup: vLLM batches concurrent requests, Ollama mostly queues them.

## Tool calling: native vs prompt mode (new in v2)

```
 NATIVE                                        PROMPT MODE (lib/llm.py _chat_prompt_tools)
 tools ──► server chat template ──► model       tools ──► described in system prompt as TEXT
 model emits <tool_call> tokens                 schema forces reply: {"action":"call","calls":[...]}
 server PARSES ──► tool_calls[]                                    or {"action":"final","text":...}
 needs: model trained + server template right   needs: JSON-schema output only (every server has it)
 fast, standard                                 harness parses; works on ANY model; ~extra tokens
```
That's the M00 "tool calling demystified" box, now implemented by you. Native breaks when the template/parser is wrong: hand-made GGUF imports, new model + old server, streaming parser bugs. Prompt mode = your fallback. Same `Reply` comes out, so the harness doesn't change.

```powershell
$env:LLM_TOOL_MODE="prompt"; uv run python modules/03_tool_use_and_harness/shopkeeper.py
```

## Gemma 4 field notes

- **Thinking** is off by default. Turn on with `<|think|>` at the start of the system prompt. Keep old thinking out of history (our adapter strips `<think>`).
- **Sampling:** Google recommends temp 1.0 / top_p 0.95 / top_k 64 for chat. For tool use and judges, still go low (0.2–0.4); measure with the bake-off.
- **Known 2026 issues:** early Gemma 4 builds had tool-calling bugs (Google pushed fixed weights under the same name, so **re-pull**). Ollama's streaming put tool calls in a `reasoning` field, which broke OpenCode. Workarounds: disable thinking, update Ollama, use llama.cpp `--jinja`, or prompt mode. Our `lib/` uses non-streaming `/api/chat` and isn't hit by the streaming bug.
- **Long tool chains:** small Gemma drifts to prose after 3–4 sequential tool calls. Fixes: fewer, higher-level tools (M03 rule 1); stop-hook "you didn't finish" (M03); prompt mode.

## Context gotcha (again, it matters more now)

Ollama's default context is small and silently truncates. Our lib sends `num_ctx=16384`. OpenCode/agent CLIs carry 10K+ tokens of system prompt + tools, so they need **32K+** (`OLLAMA_CONTEXT_LENGTH=32768` server-wide). A model that "forgets the task" mid-run is truncated, not dumb.

## Bake-off

```powershell
uv run python modules/11_open_models/bakeoff.py --profiles qwen3-8b gemma4-e4b gemma4-26b gpt-oss-20b
uv run python modules/11_open_models/bakeoff.py --profiles gemma4-e4b --tool-modes native prompt
```
Prints tools %, JSON %, tok/s, and a winner line to paste into `.env`. Re-run when you change hardware, server, or quant. That's eval-driven engine choice (M09).

## Exercises

- ★ Bake-off at home on 3 models. Then the same profiles via llama.cpp (`llamacpp` profile + `serving/llamacpp_server.ps1`). Same weights, different server: any difference?
- ★ `gemma4-e4b` native vs prompt mode on `shopkeeper.py --gold 15`. Read both traces.
- ★★ Add profile `granite`/`devstral`/your DGX model to `lib/profiles.py`; bake it off.
- ★★ Gemma thinking A/B: prepend `<|think|>` to the shop_v2 system prompt (copy as shop_v3), compare M09 eval pass^k and latency.
- ★★★ Router: cheap model (e4b) for chit-chat turns, big model (26b/DGX) when tools are needed. Implement as a `RouterLLM` with the same `.chat()` interface. Measure cost/latency vs quality.
- ★★★ DGX: run `modules/08_multi_agent/studio_local.py` against `dgx-vllm` with 4 workers vs local Ollama. Plot wall time.

Next: back to the main route. Work track → [M06b OpenCode](../06b_opencode/).
