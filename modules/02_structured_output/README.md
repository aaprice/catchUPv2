# M02 — Structured output

Goal: LLM output your code can trust. Foundation for tools (M03), MCP (M05), loops (M07), evals (M09).

## Analogy

Model = brilliant intern who writes in freehand. You need a **form** they fill in.
- *Prompt-only* = "please use the form" → usually does, sometimes scribbles in margin.
- *Constrained decoding* = form with boxes; pen physically can't write outside boxes. Syntax guaranteed.
- *Validation + retry* = clerk checks form, hands back with red marks: "price too low for power". Semantics enforced.

## How constrained decoding works

```
 JSON Schema ──► grammar (state machine) ──► at each token step, mask out tokens that would break grammar
                                                     │
 model logits: {"  : 0.4,  Sure : 0.3,  ` : 0.1 ...}  ▼  masked → only  {  allowed
```

Model literally cannot emit invalid JSON syntax. **But** schema keywords like `pattern`, `minimum`, cross-field rules ("value ≥ power×8"), uniqueness vs DB → not all enforced by every backend. So: **constrain, then validate, then feed errors back.**

## Single source of truth

`game/content.py` pydantic models → generate everything:

```python
Item.model_json_schema()      # → schema for LLM (format / response_format)
Item(**data)                  # → validation with precise errors
validate_json(Item, raw)      # → (obj, ["power: Input should be <= 20", ...])  errors phrased FOR the model
```

Same pattern as OpenAPI-first design. Change schema once → LLM prompt, validator, MCP tool, tests all update.

## The validate → feedback → retry loop

```
        ┌────────────── messages += [bad output, "Fix: - value too cheap..."] ◄──┐
        ▼                                                                        │
  LLM(schema) ──► parse ──► pydantic ──► business_rules() ──► errors? ──yes──────┘ (max N)
                                                              │no
                                                              ▼
                                                           accept
```

This little loop = embryo of **loop engineering** (M07). Generator + deterministic verifier + specific feedback + retry cap.

Key detail: **specific, actionable errors.** `"value 12 too cheap for power 4; need >= 32"` converges in 1 retry. `"invalid item"` may never converge.

## Run

```powershell
uv run python modules/02_structured_output/gen_items.py --mode prompt --n 8
uv run python modules/02_structured_output/gen_items.py --mode schema --n 8
uv run python modules/02_structured_output/gen_items.py --mode retry  --n 8 --save
```

Compare valid rates. Typical small local model: prompt ~50–80%, schema ~80–90% (syntax ok, rules broken), retry ~95–100%.

## Claude-side equivalents (for later)

- Claude API: `output_format` / strict tool schemas; or "tool trick": define tool `emit_item(schema)`, force `tool_choice`.
- Claude Code headless: `claude -p "..." --output-format json --json-schema '<schema>'` → `.structured_output`. Used in M08.

## Exercises

- ★ Add rule: description must mention theme word. Watch retry rate climb.
- ★ Lower temperature to 0.2 in `attempt()` — validity up, creativity down? Measure.
- ★★ `gen_enemies.py` for `Enemy` schema with rule: `threat` (hp//4 + atk*2 + def*2) between 8 and 30, loot ids must exist.
- ★★ Batch mode: ask for `list[Item]` of 5 in one call (wrap schema: `{"type":"object","properties":{"items":{"type":"array","items":<Item>}}}`). Cheaper per item; failure blast radius bigger. Tradeoff.
- ★★★ Make retry feedback *diff-style*: only failing fields + allowed ranges. Measure avg tries vs current.

Next: [M03 Tools + harness](../03_tool_use_and_harness/).
