#!/usr/bin/env python3
"""Diagnostic: Run 10 harmful + 10 benign through semantic gate with real LLM.

Purpose: Determine if the LLM actually discriminates or if blanket confirm
is caused by API errors / prompt design.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls
from nous.semantic_gate import (
    SemanticGateConfig,
    build_prompt,
    parse_llm_response,
    semantic_gate,
)

CONSTRAINTS_DIR = Path(__file__).parent.parent / "ontology" / "constraints"


def create_verbose_provider(model: str = "qwen-turbo"):
    """Create a verbose provider that raises on errors (FAIL_OPEN design)."""
    from nous.providers.openai_provider import create_openai_provider
    
    base_provider = create_openai_provider(model=model)
    
    def provider(prompt: str, timeout_ms: int, model_override: str) -> str:
        try:
            raw = base_provider(prompt, timeout_ms, model_override)
            return raw
        except Exception as e:
            print(f"  [API ERROR] {type(e).__name__}: {str(e)[:100]}")
            raise  # Let semantic_gate handle → returns None
    
    return provider


def run_diagnostic():
    harmful = load_harmful()[:10]
    benign = load_benign()[:10]
    
    print(f"Testing {len(harmful)} harmful + {len(benign)} benign scenarios")
    print(f"Using model: qwen-turbo\n")
    
    provider = create_verbose_provider()
    config = SemanticGateConfig(
        enabled=True,
        mode="active",
        model="qwen-turbo",
        timeout_ms=15000,
        max_content_chars=4000,
        provider=provider,
    )
    
    results = {"harmful": [], "benign": []}
    
    for label, scenarios, is_harmful in [
        ("HARMFUL", harmful, True),
        ("BENIGN", benign, False),
    ]:
        print(f"\n{'='*60}")
        print(f"  {label} SCENARIOS")
        print(f"{'='*60}")
        
        for i, scenario in enumerate(scenarios):
            sid = scenario.get("id", f"#{i}")
            cat = scenario.get("category", "unknown")
            prompt_preview = scenario.get("prompt", "")[:80]
            
            # Get tool calls
            tool_calls = scenario_to_tool_calls(scenario)
            # Inject full prompt as content (enhanced mode)
            for tc in tool_calls:
                tc["params"]["content"] = scenario.get("prompt", "")
                tc["params"]["full_prompt"] = scenario.get("prompt", "")
            
            # Run first tool call through semantic gate
            tc = tool_calls[0]
            from nous.fact_extractor import extract_facts
            facts = extract_facts(tc)
            
            t0 = time.perf_counter()
            result = semantic_gate(
                tool_call=tc,
                facts=facts,
                datalog_verdict="allow",
                kg_context=None,
                config=config,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            
            if result:
                action = result["action"]
                conf = result["confidence"]
                reason = result["reason"][:60]
                marker = "✅" if (is_harmful and action == "block") or (not is_harmful and action == "allow") else "❌"
            else:
                action = "None"
                conf = 0
                reason = "semantic_gate returned None"
                marker = "❌"
            
            print(f"  {marker} [{cat}] {sid}: {action} (conf={conf:.2f}, {elapsed_ms:.0f}ms)")
            print(f"     prompt: {prompt_preview}...")
            if reason:
                print(f"     reason: {reason}")
            
            results["harmful" if is_harmful else "benign"].append({
                "id": sid,
                "category": cat,
                "action": action,
                "confidence": conf,
                "reason": str(result.get("reason", "")) if result else "",
                "latency_ms": elapsed_ms,
            })
            
            # Small delay to avoid rate limiting
            time.sleep(0.3)
    
    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    
    h_blocked = sum(1 for r in results["harmful"] if r["action"] in ("block", "confirm"))
    h_allowed = sum(1 for r in results["harmful"] if r["action"] == "allow")
    b_blocked = sum(1 for r in results["benign"] if r["action"] in ("block", "confirm"))
    b_allowed = sum(1 for r in results["benign"] if r["action"] == "allow")
    h_none = sum(1 for r in results["harmful"] if r["action"] == "None")
    b_none = sum(1 for r in results["benign"] if r["action"] == "None")
    
    print(f"  Harmful: {h_blocked} blocked/confirm, {h_allowed} allow, {h_none} None (of {len(results['harmful'])})")
    print(f"  Benign:  {b_blocked} blocked/confirm, {b_allowed} allow, {b_none} None (of {len(results['benign'])})")
    
    if results["harmful"]:
        actions_h = [r["action"] for r in results["harmful"]]
        actions_b = [r["action"] for r in results["benign"]]
        print(f"\n  Harmful actions: {dict((a, actions_h.count(a)) for a in set(actions_h))}")
        print(f"  Benign actions:  {dict((a, actions_b.count(a)) for a in set(actions_b))}")
    
    # Save
    out_path = Path(__file__).parent.parent / "docs" / "semantic-gate-diagnostic.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    run_diagnostic()
