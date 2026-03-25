#!/usr/bin/env python3
"""M5.3 — 政策推理引擎

加载 Datalog 规则并执行推理，输出受益/冲突/高优先级行业
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nous.db import NousDB


def load_rules():
    """加载 Datalog 规则文件"""
    rules_path = Path(__file__).parent.parent / "ontology" / "rules" / "policy_rules.dl"
    with open(rules_path, 'r') as f:
        return f.read()


def query_rule(db: NousDB, rule_name: str, datalog: str):
    """执行单个规则查询"""
    try:
        results = db.query(datalog)
        return results
    except Exception as e:
        return [{"error": str(e)}]


def run_r1_policy_propagation(db: NousDB):
    """R1: 政策传导 - 上游供应链受益"""
    query = """
    ?[policy_id, sector_id, strength, mechanism] :=
        *policy_targets{policy_id, sector_id: direct_sector, strength: direct_strength, mechanism: direct_mech},
        *sector_depends{from_sector: direct_sector, to_sector: sector_id, type: "supply", strength: supply_strength},
        strength = concat("indirect_", supply_strength),
        mechanism = concat("supply_chain_from_", direct_mech)
    """
    return db.query(query)


def run_r2_fiscal_expansion(db: NousDB):
    """R2: 财政扩张 - 赤字率>3.5%→基建受益"""
    query = """
    ?[sector_id, sector_name, reason, confidence] :=
        *indicator{id: "ind_deficit", value_2026: v26, direction: "up"},
        *sector{id: "sec_infra", name: sector_name},
        sector_id = "sec_infra",
        reason = "fiscal_expansion_deficit_4%",
        confidence = 0.85
    """
    return db.query(query)


def run_r3_policy_conflict(db: NousDB):
    """R3: 政策冲突检测"""
    # 简化版：检查同一行业是否有多个政策
    query = """
    ?[sector_id, count(policy_id)] :=
        *policy_targets{policy_id, sector_id}
    """
    return db.query(query)


def run_r4_superseded_policies(db: NousDB):
    """R4: 已过期政策"""
    query = """
    ?[old_policy, new_policy] :=
        *policy_supersedes{new_policy, old_policy}
    """
    return db.query(query)


def run_r5_fund_flow(db: NousDB):
    """R5: 资金传导 - 产业基金流向"""
    query = """
    ?[sector_id, fund_name, policy_name, fund_amount] :=
        *measure{id: measure_id, name: fund_name, type: "fund", amount: fund_amount},
        *policy_implements{measure_id, policy_id},
        *policy{id: policy_id, name: policy_name},
        *policy_targets{policy_id, sector_id}
    """
    return db.query(query)


def run_r6_multi_org_priority(db: NousDB):
    """R6: 多部委协同 - 高优先级行业"""
    query = """
    ?[sector_id, count(org_id)] :=
        *policy_targets{policy_id, sector_id},
        *org_issues{org_id, policy_id}
    """
    return db.query(query)


def run_r7_gdp_down_defensive(db: NousDB):
    """R7: GDP下调→防御板块受益"""
    # Cozo 不支持 || 在条件中，用多个查询合并
    query_defense = """
    ?[sector_id, sector_name, reason] :=
        *indicator{id: "ind_gdp", direction: "down"},
        *sector{id: "sec_defense", name: sector_name},
        sector_id = "sec_defense",
        reason = "GDP_down_defensive_benefit"
    """
    query_energy = """
    ?[sector_id, sector_name, reason] :=
        *indicator{id: "ind_gdp", direction: "down"},
        *sector{id: "sec_energy", name: sector_name},
        sector_id = "sec_energy",
        reason = "GDP_down_defensive_benefit"
    """
    query_infra = """
    ?[sector_id, sector_name, reason] :=
        *indicator{id: "ind_gdp", direction: "down"},
        *sector{id: "sec_infra", name: sector_name},
        sector_id = "sec_infra",
        reason = "GDP_down_defensive_benefit"
    """
    return db.query(query_defense) + db.query(query_energy) + db.query(query_infra)


def run_r8_ai_plus_chain(db: NousDB):
    """R8: AI+ 全链传导"""
    query = """
    ?[sector_id, sector_name, target_type] :=
        *policy{id: "pol_ai_plus"},
        *policy_targets{policy_id: "pol_ai_plus", sector_id},
        *sector{id: sector_id, name: sector_name},
        target_type = "direct"
    """
    direct = db.query(query)
    
    # 间接受益（上游）
    query2 = """
    ?[sector_id, sector_name, target_type] :=
        *policy_targets{policy_id: "pol_ai_plus", sector_id: ai_sector},
        *sector_depends{from_sector: ai_sector, to_sector: sector_id},
        *sector{id: sector_id, name: sector_name},
        target_type = "indirect_supply"
    """
    indirect = db.query(query2)
    return direct + indirect


def run_r9_self_control(db: NousDB):
    """R9: 自主可控政策"""
    query = """
    ?[sector_id, sector_name, policy_name] :=
        *policy{id: policy_id, name: policy_name, summary: summary},
        (str_includes(summary, "国产替代") || str_includes(summary, "自主可控")),
        *policy_targets{policy_id, sector_id},
        *sector{id: sector_id, name: sector_name}
    """
    return db.query(query)


def run_r10_national_priority(db: NousDB):
    """R10: 国务院政策优先"""
    query = """
    ?[sector_id, national_policy, ministry_policy] :=
        *policy{id: national_policy, level: "national"},
        *policy{id: ministry_policy, level: "ministry"},
        *policy_targets{policy_id: national_policy, sector_id},
        *policy_targets{policy_id: ministry_policy, sector_id},
        national_policy != ministry_policy
    """
    return db.query(query)


def print_results():
    """打印所有推理结果"""
    db = NousDB("nous.db")
    
    print("\n" + "="*60)
    print("🧠 M5.3 政策推理结果")
    print("="*60)
    
    # R1: 政策传导
    print("\n📌 R1: 政策传导（供应链上游受益）")
    r1 = run_r1_policy_propagation(db)
    for row in r1[:5]:
        print(f"   {row.get('policy_id', 'N/A')} → {row.get('sector_id', 'N/A')} "
              f"({row.get('strength', 'N/A')})")
    if len(r1) > 5:
        print(f"   ... 共 {len(r1)} 条传导关系")
    
    # R2: 财政扩张
    print("\n📌 R2: 财政扩张受益")
    r2 = run_r2_fiscal_expansion(db)
    for row in r2:
        print(f"   {row.get('sector_name', 'N/A')}: {row.get('reason', 'N/A')} "
              f"(置信度: {row.get('confidence', 'N/A')})")
    
    # R5: 资金传导
    print("\n📌 R5: 产业基金流向")
    r5 = run_r5_fund_flow(db)
    for row in r5:
        print(f"   {row.get('fund_name', 'N/A')}({row.get('fund_amount', 'N/A')}) → "
              f"{row.get('policy_name', 'N/A')} → {row.get('sector_id', 'N/A')}")
    
    # R6: 多部委协同
    print("\n📌 R6: 多部委关注行业（高优先级）")
    r6 = run_r6_multi_org_priority(db)
    r6_sorted = sorted(r6, key=lambda x: x.get('count', 0), reverse=True)
    for row in r6_sorted[:5]:
        if row.get('count', 0) >= 1:
            print(f"   {row.get('sector_id', 'N/A')}: {row.get('count', 0)} 个部委关注")
    
    # R7: 防御板块
    print("\n📌 R7: GDP下调受益（防御板块）")
    r7 = run_r7_gdp_down_defensive(db)
    for row in r7:
        print(f"   {row.get('sector_name', 'N/A')}: {row.get('reason', 'N/A')}")
    
    # R8: AI+ 传导
    print("\n📌 R8: AI+ 全产业链受益")
    r8 = run_r8_ai_plus_chain(db)
    direct = [r for r in r8 if r.get('target_type') == 'direct']
    indirect = [r for r in r8 if r.get('target_type') != 'direct']
    print(f"   直接受益: {len(direct)} 个行业")
    for row in direct:
        print(f"      → {row.get('sector_name', 'N/A')}")
    print(f"   间接受益: {len(indirect)} 个行业")
    for row in indirect:
        print(f"      → {row.get('sector_name', 'N/A')}")
    
    # R9: 自主可控
    print("\n📌 R9: 自主可控政策受益")
    r9 = run_r9_self_control(db)
    for row in r9:
        print(f"   {row.get('sector_name', 'N/A')} ← {row.get('policy_name', 'N/A')}")
    
    # R10: 政策优先级
    print("\n📌 R10: 政策优先级（国务院 > 部委）")
    r10 = run_r10_national_priority(db)
    unique_sectors = set()
    for row in r10:
        unique_sectors.add(row.get('sector_id', ''))
    print(f"   {len(unique_sectors)} 个行业受国务院政策主导")
    for sector in list(unique_sectors)[:3]:
        print(f"      → {sector}")
    
    # 汇总
    print("\n" + "="*60)
    print("📊 推理汇总")
    print("="*60)
    print(f"   供应链传导受益: {len(r1)} 条")
    print(f"   财政扩张受益: {len(r2)} 个行业")
    print(f"   产业基金覆盖: {len(r5)} 条")
    print(f"   多部委关注: {sum(1 for r in r6 if r.get('count', 0) >= 1)} 个行业")
    print(f"   防御板块受益: {len(r7)} 个行业")
    print(f"   AI+ 链受益: {len(r8)} 个行业")
    print(f"   自主可控受益: {len(r9)} 个行业")
    print(f"   国务院主导: {len(unique_sectors)} 个行业")
    print("="*60)
    
    db.close()


def main():
    print("🚀 M5.3 政策推理引擎启动...")
    print_results()
    print("\n✅ 推理完成")


if __name__ == "__main__":
    main()
