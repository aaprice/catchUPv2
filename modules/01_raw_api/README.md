# M01 — Raw API

Goal: strip all magic. LLM API = one HTTP POST. Everything else = layers.

## Wire format

```
POST /api/chat                                   (Ollama native)
POST /v1/chat/completions                        (OpenAI-compatible: Gemini, vLLM, LM Studio, Ollama too)
POST /v1/messages                                (Anthropic: Claude API; also Ollama supports it now)

{ model, messages:[{role, content}...], tools?, format/response_format?, temperature, max_tokens }
   ─────────────────────────────────►
   ◄─────────────────────────────────
{ message:{role:"assistant", content, tool_calls?}, usage:{in,out}, stop/done_reason }
```

Three dialects, same idea. `lib/llm.py` = adapter normalizing them into one `Reply`. Senior-dev mapping: JDBC drivers / ORM dialects.

| Concept | Anthropic Messages | OpenAI Chat | Ollama native |
|---|---|---|---|
| system prompt | top-level `system` field | `{"role":"system"}` msg | `{"role":"system"}` msg |
| tool call out | content block `tool_use` | `message.tool_calls[]` (args = JSON **string**) | `message.tool_calls[]` (args = **object**) |
| tool result in | user msg w/ `tool_result` block | `{"role":"tool","tool_call_id"}` | `{"role":"tool","tool_name"}` |
| structured out | tool trick / `output_format` | `response_format: json_schema` | `format: <schema>` |
| stop reason | `stop_reason: tool_use / end_turn` | `finish_reason: tool_calls / stop` | `done_reason` |

Small dialect differences = real bugs in real harnesses (args string vs object bit many people).

## Run

```powershell
uv run python modules/01_raw_api/hello.py               # raw urllib; prints request + response JSON
uv run python modules/01_raw_api/chat_memory.py         # talk to Mirela; /forget, /dump
uv run python modules/01_raw_api/sampling.py            # temperature sweep
```

## Code walkthrough

`hello.py` — zero deps, ~30 lines. Note:
- `messages` = full conversation. Server keeps nothing.
- `stream: false` → one JSON. Streaming = same tokens as NDJSON chunks (UX only; not smarter).
- Response has `prompt_eval_count` / `eval_count` = tokens in/out. Track these always.

`chat_memory.py` — the "memory" illusion:
```python
history.append({"role": "user", "content": user})
reply = llm.chat([{"role": "system", "content": SYSTEM}, *history])   # resend ALL
history.append({"role": "assistant", "content": reply.text})
```
Watch prompt tokens climb per turn → long chats cost quadratic-ish total tokens. Why harnesses compact (M04).

## Prompting essentials (only ones that matter)

1. **Be specific about output**: format, length, audience. "Max 40 words" beats "be concise".
2. **Give context, not commands**: *why* matters. "Player is level 1, so suggest cheap items" > "suggest cheap items".
3. **Examples (few-shot)** beat adjectives. One good example of desired JSON/voice > paragraph describing it.
4. **XML-ish tags** separate data from instructions: `<lore>...</lore>`, `<player_state>...</player_state>`. Also defends vs prompt injection somewhat.
5. **Put stable stuff first, volatile last** → prefix caching works (M04).
6. System prompt = role + rules + tools guidance. User msg = task + data.

## Exercises

- ★ `hello.py`: set `"stream": True`, read response line by line, print tokens as they arrive.
- ★ `chat_memory.py`: add `/tokens` showing cumulative tokens across all calls. Plot growth mentally: N turns → ~N²/2 tokens billed.
- ★★ Write `hello_openai.py`: same request to `http://localhost:11434/v1/chat/completions` (Ollama's OpenAI-compatible endpoint). Diff the response shape vs native.
- ★★ Rewrite Mirela's system prompt with 2 example exchanges (few-shot). Compare voice consistency over 10 turns.
- ★★★ Ollama also speaks Anthropic Messages API (`/v1/messages`). Send same request in Anthropic format (top-level `system`, `max_tokens` required). That's exactly what Claude Code sends → why M06 can point Claude Code at Ollama.

Next: [M02 Structured output](../02_structured_output/).
