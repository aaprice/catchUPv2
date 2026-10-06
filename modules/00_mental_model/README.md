# M00 — Mental model

Goal: correct picture of what LLM *is*, so every later trick feels obvious, not magic.

## 1. LLM = pure function

```
             ┌──────────────────────────┐
 tokens ───► │  f(weights, context)     │ ───► probability for every possible next token
             └──────────────────────────┘
                        │ sample one
                        ▼
              append to context, repeat until <end>
```

- **Weights frozen** at inference. Model learns nothing from your chat.
- **Stateless.** No memory between calls. "Chat" = client resends entire history every call.
- **Autoregressive.** Generates one token at a time, each conditioned on everything before.

Analogy: **amnesiac contractor (Memento).** Brilliant, but forgets everything when you leave room. Every visit you hand over notebook (context). Notebook contents = all they know about your job. Notebook has page limit (context window). Messy notebook → worse work. *Context engineering* = curating notebook.

## 2. Tokens

Unit of everything: cost, speed, limits.
- English ≈ 4 chars/token. Code, JSON, non-English, odd identifiers → more tokens.
- `"gravewarden"` might be 3 tokens: `grave` `ward` `en`. Model sees pieces, not letters → why LLMs miscount letters.
- Context window = max tokens in (prompt + output). Local `qwen3:8b`: up to 32K+ (VRAM bound). Claude: 200K–1M.

## 3. Roles are just formatted text

API "messages" → server applies **chat template** → one long string. qwen3 (ChatML) roughly:

```
<|im_start|>system
You are Mirela, ember-merchant...<|im_end|>
<|im_start|>user
What's cheapest heal?<|im_end|>
<|im_start|>assistant
```

Model continues from `assistant` line. That's it. **System prompt** = text at top, model trained to weight it heavily.

**Tool calling demystified:** tool schemas get pasted into template as text. Model trained to emit special block, e.g.

```
<tool_call>{"name": "list_stock", "arguments": {}}</tool_call>
```

Server parses → returns structured `tool_calls`. Model never executes anything. **Your code** runs tool, pastes result back as `tool` message, calls model again. M03 builds this.

## 4. Sampling

- `temperature` 0 → near-deterministic (always top token). 0.7–1.0 → varied/creative.
- Same prompt ≠ same output (unless temp 0 + same seed + same hardware, and even then not guaranteed on cloud). → **You test with evals, not single runs** (M09).
- Content generation: temp ~0.8. Tool use / extraction / judging: temp 0–0.3.

## 5. Why it lies

Training objective = *plausible* continuation, not *true*. Fluency ≠ accuracy.
Fixes (whole course is these):
- **Ground** — give real data in context (tools M03, RAG M04).
- **Constrain** — schema (M02), tool validation (M03).
- **Verify** — code checks, tests, second agent (M07–M09).

## 6. The compounding-error law (most important number in course)

Per-step reliability *p*, task with *n* dependent steps → success ≈ *pⁿ*.

| p | n=5 | n=20 | n=50 |
|---|---|---|---|
| 0.99 | 95% | 82% | 61% |
| 0.95 | 77% | 36% | 8% |
| 0.90 | 59% | 12% | 0.5% |

Long autonomous tasks die by compounding. Cures = what senior devs already know from distributed systems: **checkpoints, validation at boundaries, retries, idempotency, isolation.** Agent engineering = reliability engineering on stochastic components.

## 7. What "agent" means (vocabulary that'll matter)

| Term | Definition |
|---|---|
| **Workflow** | Your code drives; LLM called at fixed steps (pipeline). Predictable. |
| **Agent** | LLM decides next step in loop with tools until done. Flexible, less predictable. |
| **Harness** | Everything around model: loop, tools, permissions, context mgmt, hooks, UI. Claude Code = harness. |
| **Loop** (2026 usage) | Outer automation running agents repeatedly against verifiable goal + stop condition. |

Rule from Anthropic's *Building Effective Agents*: use simplest thing that works. Workflow before agent; single agent before multi-agent.

```
 simple ──────────────────────────────────────────────────────────► complex
 one call → chain → router → tool-using agent → agent in loop → multi-agent
 cheap, predictable                                     expensive, flexible, needs evals
```

## Self-check
1. Model "remembered" your name 10 messages ago. Where did memory live?
2. Why does JSON from model sometimes break, and what two mechanisms fix it? (M02)
3. 20-step task, 95% per step. Expected success? What do you add?
4. Difference: workflow vs agent vs harness?

Answers: (1) client resent history in context. (2) unconstrained sampling; constrained decoding + validate/retry. (3) ~36%; verification/checkpoints/retries. (4) see table.

Next: [M01 Raw API](../01_raw_api/).
