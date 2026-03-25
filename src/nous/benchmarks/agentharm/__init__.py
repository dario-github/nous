"""AgentHarm benchmark integration (ICLR 2025).

176 harmful + 176 benign test cases sourced from:
  ai-safety-institute/AgentHarm on HuggingFace Hub
"""
from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.adapter import scenario_to_tool_calls, FUNCTION_ACTION_MAP
from nous.benchmarks.agentharm.runner import run_benchmark, BenchmarkResult
from nous.benchmarks.agentharm.metrics import compute_metrics

__all__ = [
    "load_harmful",
    "load_benign",
    "scenario_to_tool_calls",
    "FUNCTION_ACTION_MAP",
    "run_benchmark",
    "BenchmarkResult",
    "compute_metrics",
]
