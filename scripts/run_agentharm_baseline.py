"""AgentHarm Baseline Runner — CLI 入口

用法：
    source ./.venv/bin/activate
    python nous/scripts/run_agentharm_baseline.py [--limit N] [--no-cache] [--verbose]

功能：
    1. 加载 AgentHarm harmful + benign 数据集
    2. 对每个 scenario 执行 Nous gate()
    3. 计算评测指标
    4. 写入报告到 nous/docs/agentharm-baseline-{date}.md
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保 src 在 Python path 中
_NOUS_ROOT = Path(__file__).parent.parent
_SRC_DIR = _NOUS_ROOT / "src"
sys.path.insert(0, str(_SRC_DIR))
sys.path.insert(0, str(_NOUS_ROOT))

from nous.benchmarks.agentharm.loader import load_harmful, load_benign
from nous.benchmarks.agentharm.runner import run_benchmark
from nous.benchmarks.agentharm.metrics import compute_metrics, format_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_agentharm_baseline")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AgentHarm benchmark against Nous gate() constraints"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of scenarios per split (for quick testing)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass local cache, re-download from HuggingFace",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-scenario progress",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_NOUS_ROOT / "docs",
        help="Directory to write the Markdown report",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_cache = not args.no_cache

    # ── Step 1: 加载数据 ──────────────────────────────────────────────
    logger.info("Loading AgentHarm dataset...")
    harmful_scenarios = load_harmful(use_cache=use_cache)
    benign_scenarios = load_benign(use_cache=use_cache)

    if args.limit:
        harmful_scenarios = harmful_scenarios[: args.limit]
        benign_scenarios = benign_scenarios[: args.limit]
        logger.info("Limited to %d scenarios per split", args.limit)

    logger.info(
        "Dataset: %d harmful, %d benign", len(harmful_scenarios), len(benign_scenarios)
    )

    # ── Step 2: 运行 benchmark ────────────────────────────────────────
    logger.info("Running gate() on harmful scenarios...")
    harmful_results = run_benchmark(
        harmful_scenarios, is_harmful=True, verbose=args.verbose
    )

    logger.info("Running gate() on benign scenarios...")
    benign_results = run_benchmark(
        benign_scenarios, is_harmful=False, verbose=args.verbose
    )

    all_results = harmful_results + benign_results

    # ── Step 3: 计算指标 ──────────────────────────────────────────────
    logger.info("Computing metrics...")
    metrics = compute_metrics(all_results)

    # 打印核心指标到 stdout
    print("\n" + "=" * 60)
    print("  AgentHarm Baseline Results")
    print("=" * 60)
    print(f"  Harmful block rate (TPR): {metrics['harmful_block_rate']:.1%}")
    print(f"  Benign false positive rate (FPR): {metrics['benign_fp_rate']:.1%}")
    print(f"  Tool-level block rate: {metrics['harmful_tool_block_rate']:.1%}")
    print(f"  Coverage gaps: {len(metrics['coverage_gaps'])} categories")
    if metrics["coverage_gaps"]:
        for gap in metrics["coverage_gaps"]:
            print(f"    ⚠️  {gap}")
    print("=" * 60 + "\n")

    # ── Step 4: 写报告 ────────────────────────────────────────────────
    date_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"agentharm-baseline-{date_str}.md"

    title = f"AgentHarm Baseline Report — {date_str}"
    report = format_report(metrics, title=title)

    # 追加 metadata header
    header_lines = [
        "---",
        f"date: {date_str}",
        f"harmful_scenarios: {len(harmful_scenarios)}",
        f"benign_scenarios: {len(benign_scenarios)}",
        f"tpr: {metrics['harmful_block_rate']:.4f}",
        f"fpr: {metrics['benign_fp_rate']:.4f}",
        "---",
        "",
    ]
    full_report = "\n".join(header_lines) + report

    output_path.write_text(full_report, encoding="utf-8")
    logger.info("Report written to: %s", output_path)
    print(f"📄 Report: {output_path}")


if __name__ == "__main__":
    main()
