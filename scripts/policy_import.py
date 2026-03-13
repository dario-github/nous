#!/usr/bin/env python3
"""M5.2 — 政策数据导入脚本

导入两会 2026 种子数据到 Cozo 数据库
"""
import json
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB


# ========== 种子数据 ==========

ORGANIZATIONS = [
    ["org_gov", "国务院", "national", "", {}],
    ["org_ndrc", "发改委", "ministry", "org_gov", {}],
    ["org_miit", "工信部", "ministry", "org_gov", {}],
    ["org_most", "科技部", "ministry", "org_gov", {}],
    ["org_mof", "财政部", "ministry", "org_gov", {}],
]

INDICATORS = [
    ["ind_gdp", "GDP增长率", "4.5-5%", "5%", "%", "down", {"target_2026": 4.75, "target_2025": 5.0}],
    ["ind_deficit", "财政赤字率", "4%", "3%", "%", "up", {"expansionary": True}],
    ["ind_rd", "研发经费占比", "2.8%", "2.6%", "%", "up", {"innovation_focus": True}],
    ["ind_defense", "国防预算增幅", "7.2%", "7.2%", "%", "stable", {"security_focus": True}],
]

SECTORS = [
    ["sec_ai", "人工智能", "", {"hot": True, "frontier": True}],
    ["sec_semi", "半导体", "", {"strategic": True, "supply_chain": True}],
    ["sec_compute", "算力", "sec_semi", {"demand_from": "sec_ai"}],
    ["sec_it", "信息技术", "", {"broad": True}],
    ["sec_energy", "新能源", "", {"carbon_focus": True}],
    ["sec_infra", "基建", "", {"fiscal_sensitive": True}],
    ["sec_chem", "化工", "", {"traditional": True}],
    ["sec_defense", "军工", "", {"security_related": True}],
    ["sec_bio", "生物医药", "", {"health_focus": True}],
    ["sec_satellite", "卫星互联网", "", {"emerging": True}],
]

POLICIES = [
    ["pol_ai_plus", "全面AI+", "national", "org_gov", "2026-03", "active", "政府工作报告", "推进人工智能+行动", {"ai_focus": True}],
    ["pol_fiscal", "积极财政政策", "national", "org_gov", "2026-03", "active", "政府工作报告", "赤字率4%，扩大基建投资", {"fiscal_expansion": True}],
    ["pol_ic", "集成电路重大项目", "ministry", "org_miit", "2026-03", "active", "工信部发文", "半导体产业扶持", {"semiconductor_focus": True}],
    ["pol_compute", "算力网络建设", "ministry", "org_ndrc", "2026-03", "active", "发改委规划", "东数西算工程深化", {"compute_focus": True}],
    ["pol_satellite", "卫星互联网推进", "ministry", "org_miit", "2026-03", "active", "工信部发文", "天地一体化信息网络", {"space_focus": True}],
]

MEASURES = [
    ["meas_ai_fund", "AI产业基金", "fund", "1000亿", "2026-2030", {"target": "AI产业化"}],
    ["meas_ic_mna", "芯片并购基金", "fund", "500亿", "2026-2030", {"target": "国产替代"}],
    ["meas_compute_subsidy", "算力使用补贴", "subsidy", "每年20%", "2026-2028", {"target": "降低企业成本"}],
    ["meas_rd_deduction", "研发加计扣除", "tax", "100%+", "2026-", {"target": "激励创新"}],
]

SECTOR_DEPENDS = [
    ["sec_ai", "sec_compute", "demand", "strong"],
    ["sec_ai", "sec_semi", "supply", "medium"],
    ["sec_compute", "sec_semi", "supply", "strong"],
    ["sec_satellite", "sec_semi", "supply", "medium"],
]

POLICY_TARGETS = [
    ["pol_ai_plus", "sec_ai", "direct", "全面部署"],
    ["pol_ai_plus", "sec_compute", "indirect", "需求拉动"],
    ["pol_ic", "sec_semi", "direct", "国产替代"],
    ["pol_compute", "sec_compute", "direct", "基建投资"],
    ["pol_satellite", "sec_satellite", "direct", "星座建设"],
    ["pol_fiscal", "sec_infra", "direct", "基建投资"],
]

POLICY_IMPLEMENTS = [
    ["meas_ai_fund", "pol_ai_plus", "funded"],
    ["meas_ic_mna", "pol_ic", "funded"],
    ["meas_compute_subsidy", "pol_compute", "funded"],
    ["meas_rd_deduction", "pol_ai_plus", "supported"],
]

ORG_ISSUES = [
    ["org_gov", "pol_ai_plus"],
    ["org_gov", "pol_fiscal"],
    ["org_miit", "pol_ic"],
    ["org_ndrc", "pol_compute"],
    ["org_miit", "pol_satellite"],
]

POLICY_IMPACTS = [
    ["pol_fiscal", "ind_deficit", "positive", "+1%"],
    ["pol_ai_plus", "ind_rd", "positive", "+0.2%"],
    ["pol_fiscal", "ind_gdp", "positive", "+0.3%"],
]


# ========== Schema & Import Functions ==========

def create_policy_schema(db: NousDB):
    """创建 M5.1 设计的政策网络表"""
    schemas = [
        """:create policy { id: String => name: String, level: String, issuer: String,
            date: String, status: String, source: String, summary: String, props: Json, created_at: Float }""",
        """:create sector { id: String => name: String, parent: String?, props: Json, created_at: Float }""",
        """:create measure { id: String => name: String, type: String, amount: String?,
            duration: String?, props: Json, created_at: Float }""",
        """:create indicator { id: String => name: String, value_2026: String, value_2025: String?,
            unit: String, direction: String, props: Json, created_at: Float }""",
        """:create organization { id: String => name: String, level: String, parent: String?,
            props: Json, created_at: Float }""",
        """:create policy_targets { policy_id: String, sector_id: String => strength: String,
            mechanism: String?, created_at: Float }""",
        """:create policy_implements { measure_id: String, policy_id: String => status: String, created_at: Float }""",
        """:create policy_impacts { policy_id: String, indicator_id: String => direction: String,
            magnitude: String?, created_at: Float }""",
        """:create org_issues { org_id: String, policy_id: String => created_at: Float }""",
        """:create sector_depends { from_sector: String, to_sector: String => type: String,
            strength: String, created_at: Float }""",
        """:create policy_supersedes { new_policy: String, old_policy: String => created_at: Float }""",
    ]
    
    for schema in schemas:
        try:
            db.db.run(schema)
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "conflicts with an existing" in err_str:
                pass
            else:
                raise
    print("✅ Policy schema created")


def import_all_data(db: NousDB):
    """导入所有种子数据"""
    now = time.time()
    
    # Organizations
    for org in ORGANIZATIONS:
        db.db.run(
            "?[id, name, level, parent, props, created_at] <- [[$id, $name, $level, $parent, $props, $cat]] "
            ":put organization { id => name, level, parent, props, created_at }",
            {"id": org[0], "name": org[1], "level": org[2], "parent": org[3], "props": org[4], "cat": now}
        )
    print(f"✅ Imported {len(ORGANIZATIONS)} organizations")
    
    # Indicators
    for ind in INDICATORS:
        db.db.run(
            "?[id, name, value_2026, value_2025, unit, direction, props, created_at] <- [[$id, $name, $v26, $v25, $unit, $dir, $props, $cat]] "
            ":put indicator { id => name, value_2026, value_2025, unit, direction, props, created_at }",
            {"id": ind[0], "name": ind[1], "v26": ind[2], "v25": ind[3], "unit": ind[4], "dir": ind[5], "props": ind[6], "cat": now}
        )
    print(f"✅ Imported {len(INDICATORS)} indicators")
    
    # Sectors
    for sec in SECTORS:
        db.db.run(
            "?[id, name, parent, props, created_at] <- [[$id, $name, $parent, $props, $cat]] "
            ":put sector { id => name, parent, props, created_at }",
            {"id": sec[0], "name": sec[1], "parent": sec[2], "props": sec[3], "cat": now}
        )
    print(f"✅ Imported {len(SECTORS)} sectors")
    
    # Policies
    for pol in POLICIES:
        db.db.run(
            "?[id, name, level, issuer, date, status, source, summary, props, created_at] <- [[$id, $name, $level, $issuer, $date, $status, $source, $summary, $props, $cat]] "
            ":put policy { id => name, level, issuer, date, status, source, summary, props, created_at }",
            {"id": pol[0], "name": pol[1], "level": pol[2], "issuer": pol[3], "date": pol[4], 
             "status": pol[5], "source": pol[6], "summary": pol[7], "props": pol[8], "cat": now}
        )
    print(f"✅ Imported {len(POLICIES)} policies")
    
    # Measures
    for meas in MEASURES:
        db.db.run(
            "?[id, name, type, amount, duration, props, created_at] <- [[$id, $name, $type, $amount, $duration, $props, $cat]] "
            ":put measure { id => name, type, amount, duration, props, created_at }",
            {"id": meas[0], "name": meas[1], "type": meas[2], "amount": meas[3], 
             "duration": meas[4], "props": meas[5], "cat": now}
        )
    print(f"✅ Imported {len(MEASURES)} measures")
    
    # Sector dependencies
    for dep in SECTOR_DEPENDS:
        db.db.run(
            "?[from_sector, to_sector, type, strength, created_at] <- [[$from, $to, $type, $strength, $cat]] "
            ":put sector_depends { from_sector, to_sector => type, strength, created_at }",
            {"from": dep[0], "to": dep[1], "type": dep[2], "strength": dep[3], "cat": now}
        )
    print(f"✅ Imported {len(SECTOR_DEPENDS)} sector dependencies")
    
    # Policy targets
    for tgt in POLICY_TARGETS:
        db.db.run(
            "?[policy_id, sector_id, strength, mechanism, created_at] <- [[$pid, $sid, $strength, $mechanism, $cat]] "
            ":put policy_targets { policy_id, sector_id => strength, mechanism, created_at }",
            {"pid": tgt[0], "sid": tgt[1], "strength": tgt[2], "mechanism": tgt[3], "cat": now}
        )
    print(f"✅ Imported {len(POLICY_TARGETS)} policy targets")
    
    # Policy implements
    for imp in POLICY_IMPLEMENTS:
        db.db.run(
            "?[measure_id, policy_id, status, created_at] <- [[$mid, $pid, $status, $cat]] "
            ":put policy_implements { measure_id, policy_id => status, created_at }",
            {"mid": imp[0], "pid": imp[1], "status": imp[2], "cat": now}
        )
    print(f"✅ Imported {len(POLICY_IMPLEMENTS)} policy-implements relations")
    
    # Org issues
    for iss in ORG_ISSUES:
        db.db.run(
            "?[org_id, policy_id, created_at] <- [[$oid, $pid, $cat]] "
            ":put org_issues { org_id, policy_id => created_at }",
            {"oid": iss[0], "pid": iss[1], "cat": now}
        )
    print(f"✅ Imported {len(ORG_ISSUES)} org-issues relations")
    
    # Policy impacts
    for imp in POLICY_IMPACTS:
        db.db.run(
            "?[policy_id, indicator_id, direction, magnitude, created_at] <- [[$pid, $iid, $dir, $mag, $cat]] "
            ":put policy_impacts { policy_id, indicator_id => direction, magnitude, created_at }",
            {"pid": imp[0], "iid": imp[1], "dir": imp[2], "mag": imp[3], "cat": now}
        )
    print(f"✅ Imported {len(POLICY_IMPACTS)} policy-impacts relations")


def print_stats(db: NousDB):
    """打印导入统计"""
    print("\n" + "="*50)
    print("📊 导入统计")
    print("="*50)
    
    tables = [
        ("organization", "id"), ("indicator", "id"), ("sector", "id"), 
        ("policy", "id"), ("measure", "id"),
        ("policy_targets", "policy_id"), ("policy_implements", "measure_id"),
        ("policy_impacts", "policy_id"), ("org_issues", "org_id"),
        ("sector_depends", "from_sector"), ("policy_supersedes", "new_policy")
    ]
    
    total = 0
    for table, key in tables:
        try:
            rows = db.query(f"?[count({key})] := *{table}{{{key}}}")
            if rows:
                count = list(rows[0].values())[0]
                print(f"  {table:20s}: {count:3d}")
                total += count
        except Exception as e:
            print(f"  {table:20s}: error ({e})")
    
    print("-"*50)
    print(f"  {'总计':20s}: {total} 条记录")
    print("="*50)


def main():
    db_path = "nous.db"
    db = NousDB(db_path)
    
    print("🚀 M5.2 政策数据导入开始...\n")
    create_policy_schema(db)
    import_all_data(db)
    print_stats(db)
    db.close()
    print("\n✅ 导入完成")


if __name__ == "__main__":
    main()

