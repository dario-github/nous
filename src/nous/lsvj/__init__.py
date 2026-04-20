"""LSVJ-S — LLM-Synthesized Symbolically-Verified Judgments (M0 skeleton)

公开 API：
  schema:    PrimitiveSchema, Primitive, PrimitiveClass, Obligation, load_schema_from_yaml
  gate:      admit_rule, AdmissionResult, GateVerdict, MockEvaluator
  tracing:   decisive_primitives, GLOBAL_VACUOUS
  synthesis: SynthesisResult, build_synthesis_prompt, parse_synthesis_response,
             LSVJ_PROMPT_TEMPLATE, MockProposer
"""

from nous.lsvj.schema import (
    Obligation,
    Primitive,
    PrimitiveClass,
    PrimitiveSchema,
    load_schema_from_yaml,
)
from nous.lsvj.gate import (
    AdmissionResult,
    GateVerdict,
    MockEvaluator,
    admit_rule,
)
from nous.lsvj.tracing import (
    GLOBAL_VACUOUS,
    decisive_primitives,
)
from nous.lsvj.synthesis import (
    LSVJ_PROMPT_TEMPLATE,
    MockProposer,
    SynthesisResult,
    build_synthesis_prompt,
    parse_synthesis_response,
)

__all__ = [
    # schema
    "Obligation",
    "Primitive",
    "PrimitiveClass",
    "PrimitiveSchema",
    "load_schema_from_yaml",
    # gate
    "AdmissionResult",
    "GateVerdict",
    "MockEvaluator",
    "admit_rule",
    # tracing
    "GLOBAL_VACUOUS",
    "decisive_primitives",
    # synthesis
    "LSVJ_PROMPT_TEMPLATE",
    "MockProposer",
    "SynthesisResult",
    "build_synthesis_prompt",
    "parse_synthesis_response",
]
