# Cozo → Lark Fork Decision (M0/W2)

**Date**: 2026-04-19
**Decision authority**: Opus 4.7 main session (per user "自动推进" authorization)
**Origin**: EXPERIMENT_PLAN.md R004 (W2 pilot fork criterion)

---

## Question

`grammar-constrained synthesis pilot (R002)` requires the LLM to emit valid Datalog-body text with ≥99% parse-rate. The primary path was XGrammar + Lark EBNF generated from Cozo's pest PEG grammar. Fork criterion per EXPERIMENT_PLAN: if ≥1 Cozo PEG construct fails to round-trip to Lark within 2 days of engineering, commit to post-hoc parse+retry as primary path.

## Evidence

- **Cozo grammar source**: `cozo-core/src/cozoscript.pest`, ~280–320 lines pest PEG grammar.
- **No direct left recursion**: iteration `()*` used instead of self-referential recursion. Good for Lark conversion.
- **Blocker constructs**: `PUSH` / `POP` / `PEEK` (stack-based raw-string delimiter tracking), `${}` (compound token with string interpolation), `@` atomic tokens, `_{}` silent rules. Of these, **PUSH/POP raw string is non-standard EBNF** and would require a custom Lark transformer/tokenizer layer. Other operators (`~`, `!()`, `_{}`) have clean Lark analogs.
- **Estimated 2-day engineering budget**: 85% of Cozo grammar converts trivially (sequences, alternations, repetitions). The remaining 15% (raw-string + compound tokens) has unbounded risk — could take 2 days alone, could take 1 week.

## Decision

**Fork Option B**: **write a LSVJ-obligation subset grammar directly in Lark**, do not attempt to convert full Cozo grammar.

### Why subset, not full Cozo

The LSVJ-S obligation vocabulary is intentionally **much narrower** than full Cozo:
- Only one rule shape: `?[discharged] := body, discharged = head_expr`
- Only one head name: `discharged`
- Body: conjunction of primitive calls, each primitive declared in our 6-primitive schema
- Head expression: boolean over primitive return bindings, using `not`, `or`, `and`
- Literals: identifiers, strings, numbers (no datetime, no JSON, no vector)
- No recursion, no FTS, no triggers, no schema DDL, no imperative blocks

A Lark EBNF covering this subset is approximately **25–30 productions** (vs 280+ for full Cozo), with **no PUSH/POP**, **no compound tokens**, **no atomic-rule tricks**. Estimated engineering: **1 day** (well within 2-day W2 budget).

### Grammar sketch (to be finalized in R001+)

```ebnf
// Top-level obligation shape
obligation: "?[" "discharged" "]" ":=" body "," "discharged" "=" head_expr

// Body: conjunction of primitive calls
body: primitive_call ("," primitive_call)*

primitive_call: IDENTIFIER "(" arg_list? ")"
arg_list: arg ("," arg)*
arg: IDENTIFIER | STRING | NUMBER | BOOLEAN

// Head: boolean expression over primitive result bindings
head_expr: or_expr
or_expr: and_expr ("or" and_expr)*
and_expr: not_expr ("and" not_expr)*
not_expr: ("not")? atom
atom: IDENTIFIER | "(" head_expr ")" | BOOLEAN

// Terminals
IDENTIFIER: /[a-z_][a-z0-9_]*/i
STRING: /"[^"]*"/
NUMBER: /-?\d+(\.\d+)?/
BOOLEAN: "true" | "false"
WHITESPACE: /[ \t\r\n]+/ (ignored)
```

This subset **is a valid Cozo program** — anything that parses our Lark grammar also parses Cozo's pest grammar. So runtime execution by `pycozo` continues to work unchanged.

### XGrammar compatibility

XGrammar accepts Lark EBNF grammars directly (common pattern in 2025–2026 constrained-decoding tooling). DeepSeek-V3.2 is OpenAI-compatible and supports grammar-constrained decoding via vendor structured-output + grammar parameter. If vendor native grammar support is unavailable, post-hoc retry (≤3× max) on parse failure is the documented fallback.

### Engineering steps (M0/W2 execution order)

1. **Write Lark EBNF file** `src/nous/lsvj/obligation.lark` (~1 engineering day)
2. **Add Lark parser wrapper** to `src/nous/lsvj/compiler.py`: `parse_with_lark(rule_text) → ParsedRule`. Retain existing regex-based parser as fallback for graceful degradation.
3. **Add grammar to synthesis prompt**: when DeepSeek-V3.2 supports structured output, pass grammar as JSON Schema transform or raw Lark string; otherwise include as in-prompt specification.
4. **Test**: 500-call R002 pilot using Lark-enforced generation; measure parse-rate. Target ≥99%. If <99% after 1 day of prompt+grammar iteration, commit to post-hoc retry path.
5. **Document outcome** in this file under "Result" section after R002 runs.

## Tradeoffs

| Aspect | Subset Lark (chosen) | Full Cozo Lark | Post-hoc retry only |
|---|---|---|---|
| Engineering time | ~1 day | 2–7 days (PUSH/POP risk) | 0 days |
| Parse rate ceiling | High (~100% when grammar-constrained) | High (same) | Medium (~95–99%, model-dependent) |
| Runtime grammar cost | Small (one parse + map to Cozo) | Small (direct pass) | Retry overhead (≤3 extra calls) |
| Brittleness | Low (grammar freeze) | Medium (PUSH/POP edge cases) | High (depends on LLM prompt iteration) |
| Future extensibility | Moderate (add productions as new primitives arise) | High (full Cozo) | High (prompt only) |
| LSVJ-S paper claim clarity | Strong ("grammar-constrained synthesis") | Strong | Weak ("retry-based adaptation") |

Subset grammar wins on engineering risk + paper claim. Extensibility can be revisited in M2+ if primitives require richer Datalog constructs (e.g., aggregates, recursive rules).

## Result

Will be filled in after R002 pilot execution.
- Parse rate at N=500: _TBD_
- Median generation latency: _TBD_
- Recommended for M1+: _TBD (subset grammar / expand / drop to retry)_

---

*Follows fork criterion in EXPERIMENT_PLAN.md "Run Order and Milestones — M0 Sanity (W1–W3) / R004". If R002 pilot shows parse rate <99% on the subset grammar, escalate to user decision before investing further W2 time.*
