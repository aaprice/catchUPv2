# Glossary (terse; module where it lives)

| Term | Meaning | M |
|---|---|---|
| **Token** | sub-word unit; cost/limit/speed measured in it (~4 chars English) | 00 |
| **Context window** | max tokens model sees per call (prompt + output). Its whole "working memory" | 00 |
| **Stateless** | model keeps nothing between calls; client resends history | 01 |
| **System prompt** | top-of-context instructions; role + rules | 01 |
| **Temperature** | sampling randomness. 0 = near-deterministic | 01 |
| **Chat template** | how roles/tools get serialized into one string for model | 00 |
| **Structured output** | constrain output to JSON schema (constrained decoding) | 02 |
| **Tool / function calling** | model emits `{name, arguments}`; harness executes; result returned | 03 |
| **Agent** | LLM in loop choosing tools until done | 03 |
| **Workflow** | code-sequenced LLM steps (predictable) vs agent (model-sequenced) | 00, 10 |
| **Harness** | everything around model: loop, tools, permissions, hooks, context mgmt, UI | 03, 06 |
| **Harness engineering** | designing harness parts to make same model perform better | 03, 06 |
| **Permission policy** | allow / ask / deny per tool or command | 03, 06 |
| **Hook** | deterministic code at lifecycle points (pre/post tool, stop, session start) | 03, 06 |
| **Context engineering** | choosing what goes in window: write/select/compress/isolate | 04 |
| **Compaction** | summarize old history to free window | 04 |
| **Context rot** | quality drop as window fills with irrelevant stuff | 04 |
| **RAG** | retrieve relevant docs (via embeddings/search) into prompt | 04 |
| **Embedding** | vector representing meaning; cosine similarity = relatedness | 04 |
| **Agentic search** | model uses search tools iteratively (grep, search_lore) vs one-shot retrieval | 04 |
| **Prompt / prefix caching** | provider reuses computed prefix; stable-first ordering → cheaper/faster | 04 |
| **Memory file** | persistent markdown loaded each session (CLAUDE.md, NOTES.md) | 04, 06 |
| **MCP** | Model Context Protocol: standard client-server protocol for tools/resources/prompts | 05 |
| **MCP host / client / server** | app w/ LLM / connector per server / tool provider process | 05 |
| **stdio vs Streamable HTTP** | MCP transports: local subprocess vs network server | 05 |
| **Resource / Prompt (MCP)** | app-attached read-only data by URI / user-invoked template | 05 |
| **Tool poisoning** | malicious instructions hidden in tool descriptions | 05 |
| **CLAUDE.md** | Claude Code project memory file | 06 |
| **Skill** | on-demand instruction pack (SKILL.md + files); progressive disclosure | 06 |
| **Progressive disclosure** | load descriptions always, bodies on use, files on demand | 06 |
| **Subagent** | separate agent w/ own context/tools/model, invoked by main agent | 06, 08 |
| **Headless** | `claude -p` non-interactive; Claude Code as function | 06 |
| **Plugin** | bundle of skills+agents+hooks+MCP for Claude Code | 06 |
| **Plan mode** | read-only mode: research + propose before edits | 06 |
| **Loop engineering** | designing outer loops: goal + actor + verifier + feedback + state + stop | 07 |
| **Verifier** | anything that checks output: tests, validator, bot, critic | 07 |
| **Back-pressure** | automated checks that push agent back when wrong (tests, stop hooks) | 07 |
| **Evaluator-optimizer** | generator + LLM critic loop | 07 |
| **Ralph loop** | `while true: agent(PROMPT.md)` fresh context; state in files/git | 07 |
| **Reward hacking** | agent satisfies metric w/o real goal (edits tests) | 07 |
| **Orchestrator-workers** | planner dispatches subtasks to workers, merges | 08 |
| **Fan-out / fan-in** | parallel dispatch / gather results | 08 |
| **Maker-checker** | separate agent verifies artifact it didn't make | 08 |
| **Blackboard** | shared store agents read/write (dict, files, repo) | 08 |
| **Worktree isolation** | each agent edits own git worktree; no file conflicts | 08 |
| **Eval** | dataset + graders + metrics for AI behavior | 09 |
| **LLM-as-judge** | model grades outputs against rubric | 09 |
| **pass@k / pass^k** | any-of-k success (capability) / all-of-k success (reliability) | 09 |
| **Judge calibration** | measuring judge agreement vs human grades | 09 |
| **Agent SDK** | Claude Code's loop as Python/TS library | 08 |
| **Profile** [v2] | named engine config (provider + model + quirks) in `lib/profiles.py` | 11 |
| **Prompt-mode tool calling** [v2] | harness describes tools in prompt + forces JSON schema; parses calls itself | 11 |
| **Chat template / tool parser** | server-side code mapping messages↔model tokens; wrong one = broken native tools | 11 |
| **Quantization (Q4_K_M...)** | lower-precision weights → less VRAM; too low hurts tool/JSON reliability first | 11 |
| **MoE (mixture of experts)** | many params, few active per token (Gemma 4 26B ≈ 4B active) → big quality, small speed cost | 11 |
| **vLLM** | high-throughput inference server (batching); OpenAI-compatible; DGX choice | 11 |
| **llama.cpp / GGUF** | C++ inference engine / its single-file model format; `--jinja` = use model's chat template | 11 |
| **AGENTS.md** | harness-neutral project rules file (OpenCode, Codex, others) | 06b |
| **OpenCode** | open-source agentic coding harness; any model; agents/commands/plugins/MCP | 06b |
| **Plugin (OpenCode)** | JS/TS module subscribing to events (tool.execute.before/after) = hooks | 06b |
