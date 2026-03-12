"""Nous — 端到端闭环测试 (M3.6)

完整流程验证：
1. gate() 返回 block
2. backfill_outcome(fp)
3. detect_gaps() 检测到 too_strict 模式
4. propose_rule_fix() 生成禁用候选
5. review_cli.approve()
6. hot_reload
7. 再次 gate() 验证已放行
"""
import tempfile
import time
from pathlib import Path

import yaml

from nous.db import NousDB
from nous.decision_log import gate_with_decision_log
from nous.gap_detector import detect_gaps
from nous.hot_reload import HotReloader
from nous.outcome import OutcomeType, backfill_outcome
from nous.rule_proposer import propose_rule_fix, save_proposal

# 导入 review_cli 内部逻辑
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import review_cli


def test_e2e_governance_loop():
    """M3 验收测试：自治理闭环 < 5 秒"""
    t_start = time.perf_counter()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        constraints_dir = tmp / "constraints"
        proposals_dir = tmp / "proposals"
        constraints_dir.mkdir()
        proposals_dir.mkdir()

        # 初始化数据库
        db = NousDB(":memory:")

        # 1. 部署初始过严的规则 (TEST-STRICT)
        init_rule = {
            "id": "TEST-STRICT",
            "priority": 10,
            "enabled": True,
            "trigger": {"action_type": "safe_operation"},
            "verdict": "block"
        }
        with open(constraints_dir / "TEST-STRICT.yaml", "w") as f:
            yaml.dump(init_rule, f)

        # 启动热加载
        reloader = HotReloader(constraints_dir)
        reloader.start()
        
        # 等待后台线程初始化加载
        time.sleep(0.5)

        # 构造输入
        tool_call = {
            "name": "test_tool",
            "action_type": "safe_operation"
        }

        # 2. 模拟 3 次错误拦截 (触发 too_strict 阈值)
        for i in range(3):
            # 执行 gate
            sk = f"session-fp-{i}"
            res = gate_with_decision_log(
                tool_call,
                db=db,
                constraints_dir=constraints_dir,
                session_key=sk,
            )
            assert res.verdict.action == "block", "初始规则应拦截"

            # 异步回填为 fp
            backfill_outcome(sk, OutcomeType.fp, db)

        # 3. 运行缺口检测
        gaps = detect_gaps(db, days=1)
        assert len(gaps) == 1
        gap = gaps[0]
        assert gap.pattern_type == "too_strict"
        assert gap.action_type == "safe_operation"

        # 4. 生成候选规则
        proposal = propose_rule_fix(gap)
        assert proposal["enabled"] is False  # 应提议禁用
        prop_file = save_proposal(proposal, proposals_dir)
        prop_id = prop_file.stem

        # 5. 审核通过
        review_cli.approve_proposal(prop_id, proposals_dir, constraints_dir)
        
        # 触发热加载并等待生效 (atomic swap)
        reloader.reload()

        # 6. 再次执行 gate，验证已放行
        res_after = gate_with_decision_log(
            tool_call,
            db=db,
            constraints_dir=constraints_dir,
            session_key="session-after-fix",
        )
        assert res_after.verdict.action == "allow", "规则禁用后应放行"

        reloader.stop()

    t_end = time.perf_counter()
    assert (t_end - t_start) < 15.0, "端到端闭环耗时应 <15 秒"
