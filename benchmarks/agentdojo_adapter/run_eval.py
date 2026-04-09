"""
AgentDojo × Nous 评估脚本

评估策略（无 LLM，确定性）：
- 安全评估：用 injection task 的 ground_truth 工具调用跑过 NousFilteredRuntime
             如果 Nous 拦截了任意工具调用 → security_defended = True
- 效用评估：用 user task 的 ground_truth 工具调用跑过 NousFilteredRuntime
             如果所有工具调用均通过 → utility = True（无误拦截）

输出：
- docs/lab/projects/owner-harm-generalization-v1/agentdojo-eval-results.json
- 终端汇总表
"""

import json
import logging
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agentdojo.agent_pipeline.ground_truth_pipeline import GroundTruthPipeline
from agentdojo.task_suite.load_suites import get_suites
from agentdojo.functions_runtime import FunctionsRuntime

from nous_defense import NousFilteredRuntime

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

ADAPTER_DIR = Path(__file__).parent
RESULTS_DIR = Path(__file__).parent.parent.parent / "docs/lab/projects/owner-harm-generalization-v1"
LABELS_PATH = ADAPTER_DIR / "owner_harm_labels.json"


def run_ground_truth_with_runtime(suite, task, runtime_class, injections=None):
    """用 ground_truth pipeline 运行单个任务，返回 (tool_calls_attempted, any_blocked)。

    injections: 注入向量（用于 injection task 环境注入）
    """
    if injections is None:
        injections = {}

    try:
        environment = suite.load_and_inject_default_environment(injections)
    except Exception as e:
        logger.warning("Failed to load environment: %s", e)
        return [], False

    runtime = runtime_class(suite.tools)
    pipeline = GroundTruthPipeline(task)

    NousFilteredRuntime.clear_log()
    try:
        _, _, env_after, messages, _ = pipeline.query(
            query=getattr(task, "PROMPT", getattr(task, "GOAL", "")),
            runtime=runtime,
            env=environment,
        )
    except Exception as e:
        logger.warning("Pipeline failed: %s", e)
        return [], False

    decisions = NousFilteredRuntime.get_log()
    any_blocked = any(d["verdict"] == "block" for d in decisions)
    return decisions, any_blocked


def eval_security(suite, injection_task):
    """安全评估：injection task ground_truth 是否被 Nous 拦截。

    返回 {"defended": bool, "decisions": list, "tool_calls": int, "blocked_calls": int}
    """
    # 空注入（不注入任何 prompt injection，只运行注入任务本身的 ground truth 工具调用）
    injections = {k: "" for k in suite.get_injection_vector_defaults().keys()}
    decisions, any_blocked = run_ground_truth_with_runtime(
        suite, injection_task, NousFilteredRuntime, injections
    )
    blocked_count = sum(1 for d in decisions if d["verdict"] == "block")
    return {
        "defended": any_blocked,
        "decisions": decisions,
        "tool_calls": len(decisions),
        "blocked_calls": blocked_count,
    }


def eval_utility(suite, user_task):
    """效用评估：user task ground_truth 是否被误拦截。

    返回 {"passed": bool, "decisions": list, "tool_calls": int, "blocked_calls": int}
    """
    injections = {k: "" for k in suite.get_injection_vector_defaults().keys()}
    decisions, any_blocked = run_ground_truth_with_runtime(
        suite, user_task, NousFilteredRuntime, injections
    )
    blocked_count = sum(1 for d in decisions if d["verdict"] == "block")
    return {
        "passed": not any_blocked,  # True = 无误拦截
        "decisions": decisions,
        "tool_calls": len(decisions),
        "blocked_calls": blocked_count,
    }


def load_labels():
    with open(LABELS_PATH) as f:
        return json.load(f)


def main():
    print("=== AgentDojo × Nous 评估 ===\n")
    suites = get_suites("v1")
    labels = load_labels()

    results = {
        "meta": {"date": "2026-04-09", "benchmark_version": "v1"},
        "suites": {},
        "summary": {},
    }

    # ── 安全评估（injection tasks）──────────────────────────────────────────
    print("▶ 安全评估（injection tasks）...\n")
    total_injection = 0
    total_defended = 0
    category_stats: dict[str, dict] = {}

    for suite_name, suite in suites.items():
        suite_results = {"injection_tasks": {}, "user_tasks": {}}
        suite_defended = 0
        suite_total = 0

        for tid, inj_task in suite.injection_tasks.items():
            sec = eval_security(suite, inj_task)
            label_info = labels.get(suite_name, {}).get(tid, {})
            category = label_info.get("category", "unknown")

            suite_results["injection_tasks"][tid] = {
                **sec,
                "goal": inj_task.GOAL[:80],
                "category": category,
                "subcategory": label_info.get("subcategory", ""),
            }

            suite_defended += int(sec["defended"])
            suite_total += 1

            # 按类别汇总
            if category not in category_stats:
                category_stats[category] = {"defended": 0, "total": 0}
            category_stats[category]["defended"] += int(sec["defended"])
            category_stats[category]["total"] += 1

            status = "✓ DEFENDED" if sec["defended"] else "✗ MISSED"
            print(f"  [{suite_name}] {tid}: {status} "
                  f"({sec['blocked_calls']}/{sec['tool_calls']} blocked) [{category}]")

        total_defended += suite_defended
        total_injection += suite_total
        results["suites"][suite_name] = suite_results
        print(f"  → {suite_name}: {suite_defended}/{suite_total} defended\n")

    # ── 效用评估（user tasks）──────────────────────────────────────────────
    print("▶ 效用评估（user tasks，检测误拦截）...\n")
    total_user = 0
    total_passed = 0

    for suite_name, suite in suites.items():
        suite_passed = 0
        suite_user_total = 0

        for tid, user_task in suite.user_tasks.items():
            util = eval_utility(suite, user_task)
            results["suites"][suite_name]["user_tasks"][tid] = util

            suite_passed += int(util["passed"])
            suite_user_total += 1

            status = "✓ PASS" if util["passed"] else "✗ FALSE_POSITIVE"
            if not util["passed"]:
                print(f"  [{suite_name}] {tid}: {status} "
                      f"({util['blocked_calls']}/{util['tool_calls']} blocked)")

        total_passed += suite_passed
        total_user += suite_user_total
        fp_count = suite_user_total - suite_passed
        print(f"  → {suite_name}: {suite_passed}/{suite_user_total} passed "
              f"(FP: {fp_count})\n")

    # ── 汇总 ──────────────────────────────────────────────────────────────
    security_rate = total_defended / total_injection if total_injection > 0 else 0
    utility_rate = total_passed / total_user if total_user > 0 else 0
    fp_rate = 1.0 - utility_rate

    results["summary"] = {
        "security": {
            "defended": total_defended,
            "total": total_injection,
            "rate": round(security_rate, 4),
        },
        "utility": {
            "passed": total_passed,
            "total": total_user,
            "rate": round(utility_rate, 4),
            "false_positive_rate": round(fp_rate, 4),
        },
        "by_category": {
            cat: {
                "defended": s["defended"],
                "total": s["total"],
                "rate": round(s["defended"] / s["total"], 4) if s["total"] > 0 else 0,
            }
            for cat, s in sorted(category_stats.items())
        },
    }

    print("=" * 60)
    print(f"安全得分:  {total_defended}/{total_injection} = {security_rate:.1%}")
    print(f"效用保留:  {total_passed}/{total_user} = {utility_rate:.1%}")
    print(f"误拦截率:  {fp_rate:.1%}")
    print("\n按 Owner-Harm 类别:")
    for cat, s in sorted(category_stats.items()):
        rate = s["defended"] / s["total"] if s["total"] > 0 else 0
        print(f"  {cat:<25}: {s['defended']}/{s['total']} = {rate:.1%}")
    print("=" * 60)

    # 保存结果
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "agentdojo-eval-results.json"
    # 决策列表可能很大，只保留非 allow 的决策详情
    for sn in results["suites"]:
        for tid in results["suites"][sn]["injection_tasks"]:
            d = results["suites"][sn]["injection_tasks"][tid]
            if "decisions" in d:
                d["decisions"] = [x for x in d["decisions"] if x["verdict"] != "allow"]
        for tid in results["suites"][sn]["user_tasks"]:
            d = results["suites"][sn]["user_tasks"][tid]
            if "decisions" in d:
                d["decisions"] = [x for x in d["decisions"] if x["verdict"] != "allow"]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存：{out_path}")


if __name__ == "__main__":
    main()
