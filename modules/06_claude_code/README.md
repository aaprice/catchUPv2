# M06 — Claude Code as a harness

> **[v2] No Claude at work?** Same concepts on OpenCode + any model: [M06b](../06b_opencode/). Skills in `.claude/skills/` work in both.

Goal: stop using Claude Code as "chat in terminal". Configure it like infrastructure. You built a toy harness in M03 — now drive a production one, knowing what each knob does under hood.

## Analogy

M03 harness = go-kart you welded. Claude Code = race car. Same parts (engine, steering, brakes, telemetry) — but tuned, with pit crew (subagents), team radio (hooks), and driver's notebook (CLAUDE.md). **You don't drive it better by shouting at driver (prompting). You set up the car.**

## Your toy ↔ Claude Code

| lib/harness.py | Claude Code | Config location (this repo) |
|---|---|---|
| `system` prompt | system prompt + **CLAUDE.md** memory | `CLAUDE.md` |
| `tools=[...]` | built-ins (Read/Edit/Write/Bash/Grep/Glob/WebFetch/Agent...) + MCP tools | `.mcp.json` |
| `policy()` | **permissions** allow/ask/deny + permission modes | `.claude/settings.json` |
| `Hooks.pre_tool` | **PreToolUse** hook | `.claude/hooks/guard_bash.py` |
| `Hooks.post_tool` | **PostToolUse** hook | `.claude/hooks/validate_content.py` |
| `Hooks.on_stop` | **Stop** hook | `.claude/hooks/stop_gate.py` |
| (none) | **SessionStart** hook → context injection | `.claude/hooks/session_context.py` |
| `compactor` | auto-compact, `/compact` | built in |
| skills? (none) | **Skills**: on-demand instruction packs | `.claude/skills/*/SKILL.md` |
| M08 workers | **Subagents**: isolated context workers | `.claude/agents/*.md` |
| `Tracer` | transcripts `~/.claude/projects/<proj>/*.jsonl` | built in |
| `max_turns` | `--max-turns`, usage limits | CLI flag |

## Config layers (precedence high → low)

```
 managed policy (org)  >  CLI flags  >  .claude/settings.local.json (you, gitignored)
                       >  .claude/settings.json (project, committed)  >  ~/.claude/settings.json (you, all projects)
 Memory:  ~/.claude/CLAUDE.md (personal, all repos)  +  ./CLAUDE.md (project)  +  CLAUDE.local.md  +  subdir CLAUDE.md (lazy)
```
CLAUDE.md can `@import` files: `See @docs/architecture.md`. Keep CLAUDE.md < ~100 lines; it's paid for every turn.

## 1. CLAUDE.md — the notebook

Read `../../CLAUDE.md`. Rules: commands to run, layout, invariants, style. Not tutorials. `/init` generates starter from codebase. `/memory` opens for edit. Type `#` + text in prompt to append a memory quickly.

## 2. Permissions — the brakes

`.claude/settings.json`:
```json
"allow": ["Bash(uv run pytest*)", "mcp__ember__simulate_fight", ...],   // no prompt
"ask":   ["mcp__ember__save_level"],                                     // always prompt
"deny":  ["Bash(git push*)", "Read(./.env)"]                             // never
```
Modes (Shift+Tab cycles in UI; `--permission-mode` flag): `default` (ask on risky) · `acceptEdits` (file edits auto) · `plan` (read-only, proposes plan) · `auto` (classifier reviews actions) · `dontAsk` (deny anything not pre-allowed; good for CI) · `bypassPermissions` (YOLO; only in sandbox/container).

**Plan mode habit:** for non-trivial tasks, Shift+Tab to plan → review plan → accept. Cheapest bug fix = in the plan.

## 3. Hooks — deterministic team radio

Model *may* follow CLAUDE.md. Hooks *always* run. Use hooks for must-happen behavior.

```
 SessionStart ─► UserPromptSubmit ─► [PreToolUse ─► tool ─► PostToolUse]* ─► Stop ─► SessionEnd
       │                                  │                     │              │
  inject context                     block/allow/ask       lint/validate   "not done yet"
```
Protocol: hook gets JSON on stdin (`tool_name`, `tool_input`, `session_id`, `transcript_path`...). Reply via:
- exit 0 → proceed. (SessionStart/UserPromptSubmit: stdout added as context)
- exit 2 → block; stderr shown to Claude.
- stdout JSON → `{"decision":"block","reason":"..."}`, or `hookSpecificOutput.permissionDecision: allow|deny|ask`, `additionalContext`.

Ours:
| Hook | Does | Try it |
|---|---|---|
| `guard_bash.py` | blocks `rm -rf`, force push, `reset --hard`, pipe-to-shell; audits every command to `runs/bash_audit.log` | ask Claude "clean the runs folder with rm -rf runs" |
| `validate_content.py` | after any edit under `game/data/`, validates; invalid → Claude told why, fixes | ask Claude "put a gravewarden on a wall tile in a copy of level_01" |
| `stop_gate.py` | opt-in (`New-Item .claude/stop_gate.on`): if .py changed + tests fail → Claude can't finish | break a test, ask Claude "small refactor of world.py" |
| `session_context.py` | injects your PROGRESS position + git status at session start | start `claude`, ask "where am I in the course?" |

`/hooks` shows loaded hooks. Hooks can also be `type: "prompt"` / `"agent"` (LLM-evaluated) or `"http"`.

## 4. Skills — on-demand expertise (progressive disclosure)

```
 always in context:   name + description of every skill   (~50 tokens each)
 on match / /invoke:  SKILL.md body loads
 on demand:           supporting files (reference.md, scripts) read only if needed
```
Like lazy-loaded modules. 100 skills cost ~nothing until used. Ours:

| Skill | Shows |
|---|---|
| `/tutor 03 quiz` | user-only (`disable-model-invocation`), arguments `$0 $1`, restricted `allowed-tools` |
| `ember-content` | auto-invoked by description match; `reference.md` = progressive disclosure |
| `balance-check` | **dynamic context injection**: `` !`uv run python -m game.balance --json` `` runs before Claude reads |
| `/level-forge <brief>` | a full gen→verify loop + delegation to subagent, packaged as one command |

Skill vs CLAUDE.md vs subagent: CLAUDE.md = always-true facts. Skill = procedure/expertise needed sometimes. Subagent = separate worker w/ own context window.

## 5. Subagents — isolated context workers

```
 main session (your context) ──Agent tool──► qa-verifier (fresh context, own tools, own model)
       ▲                                           │ reads 10 files, runs 5 commands (junk stays THERE)
       └───────────── returns 1 compact JSON verdict ◄┘
```
Why: **context isolation** (M04 "isolate" lever) + **specialization** + **independent verification** (checker didn't write the code → less self-grading bias). Cost: tokens ×N, latency.

Ours: `level-designer` (sonnet, write tools), `qa-verifier` (read + playtest only, skeptical, JSON verdict), `lore-writer` (haiku, cheap). Invoke: "use the qa-verifier subagent on rat_nest" or `@agent-qa-verifier`. `/agents` to view/edit.

## 6. Headless — Claude Code as a function (basis of M07/M08)

```powershell
claude -p "list enemies by threat" --output-format json                      # .result, .session_id, .total_cost_usd
claude -p "..." --output-format json --json-schema (Get-Content schema.json -Raw)   # .structured_output
claude -p "continue" --resume <session_id>
claude -p "fix failing tests" --permission-mode acceptEdits --allowedTools "Bash(uv run pytest*)" --max-turns 20
Get-Content log.txt | claude -p "explain root cause"                         # stdin piping
```
Headless + subscription login works (no `--bare`; `--bare` requires API key). Each `-p` call = full agent loop.

## 7. Plugins — ship the whole car setup

Plugin = folder bundling skills + agents + hooks + MCP servers + commands. `/plugin` to browse marketplaces. Exercise below packages ours.

## 8. Free mode: Claude Code harness on local Ollama model

Ollama speaks Anthropic Messages API → Claude Code can use local model. Weak model + strong harness = good lesson in how much harness matters.
```powershell
# Ollama server needs big context: Claude Code's system prompt + tools are large
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH","32768","User")   # restart Ollama after
$env:ANTHROPIC_BASE_URL="http://localhost:11434"; $env:ANTHROPIC_AUTH_TOKEN="ollama"; $env:ANTHROPIC_API_KEY=""
claude --model qwen3:8b          # or gpt-oss:20b / qwen3-coder if VRAM allows
```
Close terminal (or clear vars) to go back to Pro login.

## Guided lab (do in order, ~90 min)

```powershell
cd C:\Users\iamap\Development\ClaudeProjects\CatchUP
claude
```
1. `/context` → see what's consuming window (system, tools, MCP, CLAUDE.md, skills list).
2. "where am I in the course?" → answer comes from SessionStart hook injection.
3. `/mcp` → `ember` connected? "simulate gravewarden vs all gear combos, markdown table" → MCP tools, auto-allowed.
4. `/balance-check` → watch injected live data drive analysis.
5. "make a copy of level_01 as generated/broken_test.json and put the gravewarden at 0,0" → PostToolUse hook catches → Claude self-corrects. Read what it did.
6. "delete the runs folder with rm -rf" → PreToolUse hook blocks.
7. `/level-forge "flooded ossuary, 16x10, 3 enemies, locked door" flooded_ossuary` → full loop + subagent QA. Then `uv run python -m game.play --level flooded_ossuary` and play it.
8. Shift+Tab to plan mode: "add a 'poison' status effect to the game with tests". Review plan; approve; `New-Item .claude/stop_gate.on` first so tests gate completion.
9. `/tutor 06 quiz`.

## Exercises

- ★ Add `UserPromptSubmit` hook: if prompt contains "level", append context "remember: run autoplay before claiming a level works".
- ★ Write skill `/new-enemy <theme>` that uses MCP prompt `design_enemy` + `propose_entity`.
- ★★ `PreToolUse` hook on `mcp__ember__save_level` that refuses names not in snake_case or already existing (JSON `permissionDecision: deny`).
- ★★ Subagent `speedrunner`: plays level via `uv run python -m game.autoplay` variants, reports fastest route. Give it `model: haiku`.
- ★★★ Package `.claude/` + `.mcp.json` as plugin `ember-devkit` (`.claude-plugin/plugin.json`, `skills/`, `agents/`, `hooks/hooks.json`, `.mcp.json`). Load with `claude --plugin-dir ./ember-devkit` in a *different* empty folder. Portable harness config = real team asset.
- ★★★ Re-run lab step 7 on local Ollama (section 8). Compare: iterations, failures, where harness (hooks/validator) saved weak model.

Cheat sheet: [docs/claude-code-cheatsheet.md](../../docs/claude-code-cheatsheet.md). Next: [M07 Loop engineering](../07_loop_engineering/).
