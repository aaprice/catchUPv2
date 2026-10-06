# OpenCode cheat sheet (terse) — verify vs `opencode --help` / opencode.ai/docs

## TUI
| key / cmd | does |
|---|---|
| Tab | switch primary agent (Build ⇄ Plan, + custom primaries like `ralph`) |
| `/models` | switch provider/model (ollama/..., llamacpp/local, dgx/...) |
| `/init` | create/improve AGENTS.md |
| `/compact` | summarize session |
| `/undo` `/redo` | revert/redo last changes |
| `/sessions` | switch session · `/new` new session |
| `@agent-name` | invoke subagent · `@file` attach file |
| `/<command>` | custom command from `.opencode/commands/` |
| `!cmd` | run shell directly |

## Files
```
AGENTS.md                         rules (CLAUDE.md fallback if absent)
opencode.json                     model, provider, mcp, permission, agent overrides  (project root)
~/.config/opencode/opencode.json  global
.opencode/agents/*.md             agents (mode: primary|subagent|all, permission:, model:, temperature:)
.opencode/commands/*.md           commands ($ARGUMENTS, $1, !`cmd`, @file; agent:, subtask:)
.opencode/plugins/*.js|ts         hooks: tool.execute.before/after, session.*, file.edited, event
.opencode/skills | .claude/skills | .agents/skills   SKILL.md (name + description required)
```

## CLI
```powershell
opencode run "prompt" -m ollama/qwen3.5:9b [--agent qa-verifier] [-f file] [--format json] [-c | -s <id>]
opencode mcp list                 # MCP status
opencode serve --port 4096        # headless HTTP API (drive from scripts/other agents)
opencode models                   # list available models
```

## Config snippets
```json
"provider": { "ollama": { "npm": "@ai-sdk/openai-compatible", "options": { "baseURL": "http://localhost:11434/v1" },
              "models": { "gemma4:26b": { "name": "Gemma 4 26B" } } } }
"mcp": { "ember": { "type": "local", "command": ["uv","run","python","modules/05_mcp/ember_mcp_server.py"], "enabled": true } }
"permission": { "bash": { "*": "ask", "uv run pytest*": "allow", "git push*": "deny" }, "edit": "ask" }
```
`{env:VAR}` substitutes env vars in config values. MCP tools appear as `<server>_<tool>`.

## Local-model gotchas
- Tool calls not firing → raise Ollama context (`OLLAMA_CONTEXT_LENGTH=32768`), try another model (qwen3.5/gpt-oss), or serve via llama.cpp `--jinja`.
- Gemma 4 via Ollama streaming: thinking/"reasoning" chunks can hide tool calls (issue #20995) → update, disable thinking, or llama.cpp/vLLM.
