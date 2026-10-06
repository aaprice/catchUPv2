# Claude Code cheat sheet (terse)

Verify against `/help` and https://code.claude.com/docs — features ship weekly.

## Slash commands (most useful)
| cmd | does |
|---|---|
| `/init` | generate CLAUDE.md from repo |
| `/memory` | edit memory files. `#text` in prompt = quick add |
| `/context` | what's using context window |
| `/compact [focus]` | summarize history now. `/clear` = fresh start (prefer between tasks) |
| `/model` | switch sonnet/opus/haiku. `/effort` reasoning effort |
| `/mcp` | server status, tools, auth |
| `/agents` | create/edit subagents |
| `/hooks` | view hooks |
| `/permissions` | view/edit allow/deny |
| `/rewind` | checkpoint rollback (code + convo) |
| `/resume` | pick old session. CLI: `claude -c` (continue last), `claude -r` |
| `/plugin` | marketplaces, install plugins |
| `/cost`, `/usage` | spend / plan limits |
| `/loop` | rerun a prompt on interval / self-paced (loops, M07) |

## Keys
Shift+Tab = cycle permission modes (incl. plan) · Esc = interrupt · Esc Esc = rewind menu · Ctrl+B = background task · `@file` = attach file · `!cmd` = run shell directly

## Files
```
CLAUDE.md / CLAUDE.local.md          memory (project / personal-gitignored)
~/.claude/CLAUDE.md                  memory for all projects
.claude/settings.json                permissions, hooks, env (committed)
.claude/settings.local.json          personal overrides (gitignored)
.claude/skills/<name>/SKILL.md       skills (+ supporting files)
.claude/agents/<name>.md             subagents
.mcp.json                            project MCP servers
```

## Headless
```powershell
claude -p "task" [--output-format text|json|stream-json] [--json-schema '<schema>']
       [--allowedTools "Read,Edit,Bash(uv run pytest*)"] [--permission-mode acceptEdits|plan|dontAsk|auto]
       [--max-turns N] [--model haiku] [--resume <id> | --continue] [--append-system-prompt "..."]
       [--agents '<json>'] [--mcp-config file.json]
```
json output fields: `result`, `session_id`, `total_cost_usd`, `num_turns`, `structured_output` (with schema).

## Permission rule syntax
`Bash(npm test)` exact · `Bash(git diff *)` prefix (space before `*`) · `Read(./secrets/**)` · `Edit(src/**)` · `mcp__server__tool` · `mcp__server` (all tools of server) · `WebFetch(domain:docs.python.org)`

## Hook exit codes
0 ok (stdout JSON parsed; SessionStart/UserPromptSubmit stdout → context) · 2 block (stderr → Claude) · other = non-blocking error

## Subagent frontmatter
`name`, `description` (when to use — routing!), `tools`, `model` (sonnet|opus|haiku|inherit|id), `permissionMode`, `maxTurns`, `skills`, `mcpServers`, `isolation: worktree`, `background`

## Skill frontmatter
`name`, `description`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `context: fork` + `agent`, `paths`
Body substitutions: `$ARGUMENTS`, `$0..$N`, `${CLAUDE_SKILL_DIR}`. Injection: `` !`command` ``.
