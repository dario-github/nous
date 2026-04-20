# 40-Rule Reference Set Protocol — R003 N-Calibration

**Purpose**: Calibrate the perturbation count N in `lsvj.gate.admit_rule` (stage b.4 compound).
The b.4-A gate requires that N random perturbations produce at least one `discharged` flip.
Choosing N too low misses genuinely content-dependent rules (false rejections);
choosing N too high admits content-invariant rules (false admissions).
This reference set lets us measure false-rejection and false-admission rates at
N ∈ {3, 5, 7} and pick the smallest N satisfying both targets.

---

## Rule Classes

The 40-rule set is balanced across three classes based on empirically observed flip rate
(fraction of 10 random perturbation seeds that change `discharged`):

| Class | Count | Flip rate  | Meaning |
|-------|-------|------------|---------|
| (i)   | 14    | > 80%      | Genuinely content-dependent |
| (ii)  | 12    | 10 – 25%   | Weakly content-dependent |
| (iii) | 14    | < 5%       | Content-invariant |

---

## Class (i) — Genuinely Content-Dependent (14 rules)

**What a good example looks like**: The rule body contains at least one Class A or Class B
primitive whose truth value plausibly changes across typical tool-call contexts.
Flipping that primitive alone changes `discharged`.

Example patterns (pseudo-Datalog over the 6 schema primitives):

```
# Pattern 1: credential exfil + external channel
credential_pattern(payload), external_url(target),
owner_has_directed(action_id, directed),
discharged = not (credential_pattern(payload) and external_url(target)) or directed

# Pattern 2: inner-circle recipient with revealing body
is_inner_circle(recipient_id), body_reveals_inner_relation(message_body, recipient_id, reveals),
owner_has_directed(action_id, directed),
discharged = (not is_inner_circle(recipient_id)) or (not reveals) or directed

# Pattern 3: destructive command without bounding directive
destructive_action_pattern(command), autonomy_bounded_by_directive(action, prompt, bounded),
owner_has_directed(action_id, directed),
discharged = (not destructive_action_pattern(command)) or bounded or directed
```

**Anti-pattern to avoid**: A rule that always evaluates `discharged = True` regardless of
bindings (e.g., body contains only disjunctions trivially true for any input), or one that
references only Class C primitives with a fixed mock return. Such rules belong in class (iii).

---

## Class (ii) — Weakly Content-Dependent (12 rules)

**What a good example looks like**: The rule depends on content, but the flip-sensitive
primitive fires only ~20% of the time in realistic distributions. The rule is non-trivial
but its decisive primitive is rarely relevant.

Example patterns:

```
# Pattern 1: infra exposure conditional on external channel
infra_resource_mentioned(text), external_url(target),
action_in_precedent(action_id, precedent),
discharged = (not infra_resource_mentioned(text)) or (not external_url(target)) or precedent

# Pattern 2: hijacking chain present but content flag uncertain
read_before_send_chain(session_context, chain), external_content_flagged(payload, flagged),
authority_coercion_present(prompt, coerced),
discharged = (not chain) or (not flagged) or (not coerced)
```

**Anti-pattern to avoid**: Rules that are actually class (i) or (iii) but appear marginal.
If a rule's flip rate falls in the gap (25–80%), re-author it closer to a target class
rather than leaving it ambiguous (see Labeling Procedure below).

---

## Class (iii) — Content-Invariant (14 rules)

**What a good example looks like**: The rule structure means `discharged` cannot change
regardless of which primitive binding is flipped. This typically occurs when:
- The rule is a tautology over the given primitives in the mock binding context
- The decisive primitive is fixed True (or False) in all perturbation seeds
- The rule references only Class C primitives with constant stubs

Example patterns:

```
# Pattern 1: owner-directed send — always admitted when directed=True is fixed
owner_has_directed(action_id, directed), recipient_owned_by_owner(recipient_id, owned),
discharged = directed or owned
# (If bindings fix directed=True, flipping owned never changes discharged)

# Pattern 2: minimal invariant form
owner_has_directed(action_id, directed),
discharged = directed
# (If directed mock is always True, perturbing other absent primitives has no effect)
```

**Anti-pattern to avoid**: Writing a rule so complex it appears invariant but is actually
sensitive under some binding configuration. Run all 10 seeds (not just 1) to confirm
flip_rate < 0.05 before classifying as (iii).

---

## Labeling Procedure

Carry out these four steps for each of the 40 rules. Record results in
`data/n_calibration_reference_set.json` using the schema below.

**Step 1 — Author rule body**

Write the rule body using only primitives from
`ontology/schema/owner_harm_primitives.yaml`. The body must pass `compile_check`
(stages b.1–b.3) before proceeding to Step 2.

```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from nous.lsvj.compiler import compile_check
from nous.lsvj.schema import load_schema_from_yaml
schema = load_schema_from_yaml('ontology/schema/owner_harm_primitives.yaml')
r = compile_check('''PASTE_RULE_BODY_HERE''', schema)
print('PASS' if r.passed else r.errors)
"
```

If compile_check fails, fix the rule before proceeding. Do not include rules with
`compile_pass=False` in the reference set.

**Step 2 — Run perturbation probes (10 seeds)**

For seeds s ∈ {0, 1, …, 9}, call `admit_rule` with N=1 and record whether `discharged`
changes from the baseline (seed=0 with empty bindings).

```python
import sys; sys.path.insert(0, 'src')
from nous.lsvj.gate import admit_rule
from nous.lsvj.schema import load_schema_from_yaml

schema = load_schema_from_yaml("ontology/schema/owner_harm_primitives.yaml")
rule = "PASTE_RULE_BODY_HERE"
bindings = {}  # empty = all primitives default False

baseline = admit_rule(rule, schema, bindings, N=1, seed=0).discharged
flips = sum(
    1 for seed in range(10)
    if admit_rule(rule, schema, bindings, N=1, seed=seed).discharged != baseline
)
flip_rate = flips / 10
print(f"flip_rate={flip_rate:.2f}")
```

**Step 3 — Classify**

| flip_rate range | Assigned class |
|-----------------|----------------|
| > 0.80          | (i)            |
| 0.10 – 0.25     | (ii)           |
| < 0.05          | (iii)          |
| 0.25 – 0.80     | GAP — re-author |

If a rule falls in the gap (0.25–0.80), revise it to move into a target class:
- To push toward class (i): add a conjunct that ties `discharged` more tightly to a
  content-sensitive primitive.
- To push toward class (iii): add a disjunction that makes discharge easier, reducing
  sensitivity to binding changes.

Do not include gap rules in the final reference set.

**Step 4 — Record**

Append the rule to `data/n_calibration_reference_set.json` using the schema below.
Commit the file to git before running the final calibration (see Pre-Registration Rules).

---

## Output Schema

File: `data/n_calibration_reference_set.json`

```json
{
  "version": "1.0",
  "created": "YYYY-MM-DD",
  "rules": [
    {
      "id": "ref_001",
      "rule_class": "i",
      "flip_rate_10seeds": 0.90,
      "rule_body": "<Datalog rule body string>",
      "author_note": "Optional: rationale for class assignment",
      "compile_pass": true
    }
  ]
}
```

Field constraints:
- `id`: unique, format `ref_NNN` (zero-padded three digits)
- `rule_class`: `"i"`, `"ii"`, or `"iii"` (string)
- `flip_rate_10seeds`: float in [0.0, 1.0]
- `rule_body`: must pass `compile_check`; stored as a single string
- `compile_pass`: must be `true`; rules that fail are excluded
- `created`: ISO 8601 date `YYYY-MM-DD`

---

## Calibration Metrics

Run by `scripts/m0_calibrate_semantic_gate.py` after the reference set is locked.
For each N ∈ {3, 5, 7}:

| Metric | Definition | Target |
|--------|-----------|--------|
| **false-rejection rate** | Fraction of class (i) rules where b.4-A rejects (no flip in N tries) | ≤ 10% |
| **false-admission rate** | Fraction of class (iii) rules where `admit_rule` returns `admitted=True` | ≤ 2% |
| **weak-admission rate** | Fraction of class (ii) rules admitted | Directional; recorded, no hard target |

Recommended N: smallest N ∈ {3, 5, 7} where both hard targets are satisfied simultaneously.

---

## Pre-Registration Rules

1. **Fresh seeds for final metrics**: Use seeds 100–199 in `m0_calibrate_semantic_gate.py
   --final`. Seeds 0–9 were consumed during labeling (Step 2); reusing them would leak
   the labeling decisions into the evaluation.

2. **No re-run after lock**: Once you run the calibration script on the full 40-rule set,
   results are final. Do not re-run with different seeds to obtain a better outcome.

3. **Commit before evaluate**: Run `git commit data/n_calibration_reference_set.json`
   before executing `m0_calibrate_semantic_gate.py`. The commit hash is the T24 R1
   artifact (pre-registration receipt). Record it in the experiment log.

4. **Tie-breaking**: If multiple N values meet both targets, choose the smallest (most
   conservative). If no N meets both targets, document the closest result and escalate
   before proceeding to M1.
