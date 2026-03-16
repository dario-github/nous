"""Phase 0: 地缘推理数据准备

从 iran-war-tracker.md 和 memory 中提取结构化信号和事件，
划分 train/val/test，生成 JSON 数据文件。

时间切分：
  情报期: ≤2/27（背景知识，用于构建 KG）
  训练窗口: Day 1-8（2/28-3/7）
  验证窗口: Day 9-12（3/8-3/11）
  测试窗口: Day 13-17（3/12-3/16）
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path(__file__).parent.parent / "data" / "geo"

# ── 开战前情报信号（≤2/27）──────────────────────────────────────────────

PRE_WAR_SIGNALS = [
    {
        "id": "sig_001",
        "timestamp": "2026-02-20",
        "source_type": "intelligence",
        "source_credibility": 0.85,
        "content": "以色列空军在塞浦路斯 Akrotiri 基地进行大规模联合演习，F-35 编队演练远程突袭路线",
        "entities": ["israel", "akrotiri", "f35"],
        "signal_type": "military_posture",
        "implications": ["force_projection", "iran_strike_rehearsal"],
    },
    {
        "id": "sig_002",
        "timestamp": "2026-02-22",
        "source_type": "news",
        "source_credibility": 0.90,
        "content": "NVIDIA 完成对 OpenAI 300 亿美元投资，为 pre-IPO 做准备。科技板块稳定",
        "entities": ["nvidia", "openai"],
        "signal_type": "economic",
        "implications": ["market_stability", "tech_sector_normal"],
    },
    {
        "id": "sig_003",
        "timestamp": "2026-02-24",
        "source_type": "official",
        "source_credibility": 0.95,
        "content": "Trump 政府对伊朗实施新一轮制裁，冻结 IRGC 关联资产。Hegseth: 'all options on the table'",
        "entities": ["trump", "iran", "irgc", "hegseth"],
        "signal_type": "diplomatic",
        "implications": ["escalation_signal", "military_option_signaled"],
    },
    {
        "id": "sig_004",
        "timestamp": "2026-02-25",
        "source_type": "data",
        "source_credibility": 0.95,
        "content": "油价 WTI $55/桶，处于近年低位。美国 SPR 储备充足。OPEC 维持现有产量",
        "entities": ["oil_wti", "spr", "opec"],
        "signal_type": "economic",
        "implications": ["low_oil_price_buffer", "spr_available_for_release"],
    },
    {
        "id": "sig_005",
        "timestamp": "2026-02-25",
        "source_type": "intelligence",
        "source_credibility": 0.80,
        "content": "美军 CENTCOM 增派 USS Lincoln 航母打击群至波斯湾，B-2 轰炸机前置部署到迪戈加西亚",
        "entities": ["centcom", "uss_lincoln", "b2", "diego_garcia", "persian_gulf"],
        "signal_type": "military_posture",
        "implications": ["force_buildup", "strike_preparation"],
    },
    {
        "id": "sig_006",
        "timestamp": "2026-02-26",
        "source_type": "news",
        "source_credibility": 0.85,
        "content": "以色列 Mossad 据报已完成对伊朗高价值目标的情报收集。Netanyahu 发表'存亡之战'演讲",
        "entities": ["mossad", "netanyahu", "iran"],
        "signal_type": "political",
        "implications": ["intelligence_complete", "political_will_signaled"],
    },
    {
        "id": "sig_007",
        "timestamp": "2026-02-26",
        "source_type": "official",
        "source_credibility": 0.90,
        "content": "伊朗最高领袖哈梅内伊发表强硬讲话: '任何侵略都将遭到毁灭性回击'。IRGC 进入高度戒备",
        "entities": ["khamenei", "irgc", "iran"],
        "signal_type": "political",
        "implications": ["deterrence_rhetoric", "military_alert_elevated"],
    },
    {
        "id": "sig_008",
        "timestamp": "2026-02-27",
        "source_type": "data",
        "source_credibility": 0.95,
        "content": "霍尔木兹海峡日均通过 1700 万桶原油（全球 20%）。伊朗海军在海峡部署快艇和水雷",
        "entities": ["hormuz_strait", "iran_navy"],
        "signal_type": "military_posture",
        "implications": ["chokepoint_vulnerability", "mine_warfare_capability"],
    },
    {
        "id": "sig_009",
        "timestamp": "2026-02-27",
        "source_type": "intelligence",
        "source_credibility": 0.75,
        "content": "伊朗 Natanz 和 Fordow 核设施加速浓缩活动，铀浓缩度接近 60%（武器级为 90%）",
        "entities": ["natanz", "fordow", "nuclear_program"],
        "signal_type": "military_posture",
        "implications": ["nuclear_threshold_approaching", "strike_urgency"],
    },
    {
        "id": "sig_010",
        "timestamp": "2026-02-27",
        "source_type": "news",
        "source_credibility": 0.85,
        "content": "真主党领导层宣布'如果伊朗遭到攻击，全面北方战争将启动'。以色列北部疏散令发布",
        "entities": ["hezbollah", "lebanon", "israel_north"],
        "signal_type": "military_posture",
        "implications": ["multi_front_threat", "second_front_ready"],
    },
    {
        "id": "sig_011",
        "timestamp": "2026-02-27",
        "source_type": "official",
        "source_credibility": 0.90,
        "content": "海湾合作委员会紧急会议：沙特、UAE、巴林、科威特、卡塔尔、阿曼讨论安全局势。会后未发联合声明",
        "entities": ["gcc", "saudi", "uae", "bahrain", "kuwait", "qatar", "oman"],
        "signal_type": "diplomatic",
        "implications": ["gulf_concern", "no_unified_position"],
    },
    {
        "id": "sig_012",
        "timestamp": "2026-02-27",
        "source_type": "data",
        "source_credibility": 0.90,
        "content": "伊朗军事能力: Fateh-110/Zolfaghar 短程导弹 1000+ 枚，Shahab-3 中程 200+，无人机 Shahed-136 大量库存。防空: S-300/Bavar-373",
        "entities": ["iran_missiles", "shahed_136", "s300", "bavar_373"],
        "signal_type": "military_posture",
        "implications": ["retaliation_capability", "asymmetric_warfare_tools"],
    },
    {
        "id": "sig_013",
        "timestamp": "2026-02-25",
        "source_type": "data",
        "source_credibility": 0.95,
        "content": "伊朗经济: GDP $400B，通胀 45%+，失业率 ~11%。制裁下外汇储备有限。石油出口 150 万桶/日（Kharg Island 占 90%）",
        "entities": ["iran_economy", "kharg_island"],
        "signal_type": "economic",
        "implications": ["economic_fragility", "kharg_strategic_value"],
    },
    {
        "id": "sig_014",
        "timestamp": "2026-02-26",
        "source_type": "news",
        "source_credibility": 0.80,
        "content": "Anthropic 拒绝五角大楼最后通牒，成为首家拒绝美国军方合同的美国 AI 公司。ARR 暴涨",
        "entities": ["anthropic", "pentagon"],
        "signal_type": "political",
        "implications": ["tech_military_tension", "domestic_politics_factor"],
    },
    {
        "id": "sig_015",
        "timestamp": "2026-02-27",
        "source_type": "intelligence",
        "source_credibility": 0.70,
        "content": "美军特种部队已在伊拉克库尔德地区预置。第五舰队在巴林母港进入最高戒备",
        "entities": ["special_forces", "kurdistan", "fifth_fleet", "bahrain"],
        "signal_type": "military_posture",
        "implications": ["ground_preparation", "naval_readiness"],
    },
]

# ── 训练集事件: Day 1-8 (2/28-3/7) ──────────────────────────────────────

TRAIN_EVENTS = [
    {
        "id": "evt_001", "date": "2026-02-28", "day": 1,
        "event_type": "military_strike",
        "description": "美以联合空袭伊朗，最高领袖哈梅内伊在以色列空袭中遇害",
        "severity": 5, "actors": ["US", "Israel"],
        "targets": ["Tehran", "military_facilities", "Khamenei"],
        "consequences": ["leadership_decapitation", "retaliation_cycle_initiated"],
        "category": "military_escalation",
    },
    {
        "id": "evt_002", "date": "2026-03-01", "day": 2,
        "event_type": "military_strike",
        "description": "多战线展开：伊朗对以色列发射导弹报复，霍尔木兹海峡被伊朗海军封锁",
        "severity": 5, "actors": ["Iran", "IRGC"],
        "targets": ["Israel", "Hormuz_Strait"],
        "consequences": ["multi_front_war", "oil_chokepoint_blocked", "global_supply_shock"],
        "category": "retaliation",
    },
    {
        "id": "evt_003", "date": "2026-03-01", "day": 2,
        "event_type": "escalation",
        "description": "真主党从黎巴嫩向以色列北部发射火箭弹，以色列地面部队进入南黎巴嫩",
        "severity": 4, "actors": ["Hezbollah", "Israel"],
        "targets": ["northern_israel", "southern_lebanon"],
        "consequences": ["second_front_opened", "civilian_displacement"],
        "category": "military_escalation",
    },
    {
        "id": "evt_004", "date": "2026-03-02", "day": 3,
        "event_type": "economic",
        "description": "油价暴涨。WTI 从 $55 跳涨至 $75+。全球市场恐慌，韩国股市两日跌 19%",
        "severity": 4, "actors": ["global_markets"],
        "targets": ["oil_markets", "equity_markets"],
        "consequences": ["energy_crisis_signal", "recession_fears"],
        "category": "economic_shock",
    },
    {
        "id": "evt_005", "date": "2026-03-04", "day": 5,
        "event_type": "military_strike",
        "description": "美以打击伊朗核设施（Natanz/Fordow），核科学家被暗杀",
        "severity": 5, "actors": ["US", "Israel", "Mossad"],
        "targets": ["Natanz", "Fordow", "nuclear_scientists"],
        "consequences": ["nuclear_program_setback", "escalation_to_strategic_targets"],
        "category": "military_escalation",
    },
    {
        "id": "evt_006", "date": "2026-03-04", "day": 5,
        "event_type": "escalation",
        "description": "库尔德武装在叙利亚北部趁乱推进，高加索局势外溢",
        "severity": 3, "actors": ["Kurdish_forces", "Syria"],
        "targets": ["northern_syria"],
        "consequences": ["conflict_spillover", "regional_destabilization"],
        "category": "spillover",
    },
    {
        "id": "evt_007", "date": "2026-03-06", "day": 7,
        "event_type": "humanitarian",
        "description": "Minab 学校空袭争议引发国际谴责。Trump 叙事控制：归因伊朗使用人体盾牌",
        "severity": 4, "actors": ["US", "media"],
        "targets": ["Minab_school"],
        "consequences": ["international_condemnation", "narrative_warfare"],
        "category": "humanitarian",
    },
    {
        "id": "evt_008", "date": "2026-03-07", "day": 8,
        "event_type": "economic",
        "description": "油价 WTI 收 $90.90，周涨 36%（1983 年来最大单周涨幅）",
        "severity": 4, "actors": ["global_markets"],
        "targets": ["oil_markets"],
        "consequences": ["energy_crisis_confirmed", "inflation_fears"],
        "category": "economic_shock",
    },
]

# ── 验证集事件: Day 9-12 (3/8-3/11) ─────────────────────────────────────

VAL_EVENTS = [
    {
        "id": "evt_009", "date": "2026-03-08", "day": 9,
        "event_type": "diplomatic",
        "description": "Pezeshkian 向海湾邻国道歉（部分降级尝试），但军事行动未停",
        "severity": 3, "actors": ["Iran", "Pezeshkian"],
        "targets": ["Gulf_states"],
        "consequences": ["de_escalation_attempt", "execution_gap"],
        "category": "diplomacy",
    },
    {
        "id": "evt_010", "date": "2026-03-09", "day": 10,
        "event_type": "political",
        "description": "穆杰塔巴·哈梅内伊正式继任最高领袖（伊朗首次世袭），就任后即下令攻击",
        "severity": 5, "actors": ["Mojtaba_Khamenei", "Iran"],
        "targets": ["Iran_domestic"],
        "consequences": ["succession_crisis", "hardline_continuation", "legitimacy_contested"],
        "category": "political_transition",
    },
    {
        "id": "evt_011", "date": "2026-03-09", "day": 10,
        "event_type": "economic",
        "description": "油价 WTI 盘中触及 $114.9，以色列首次打击伊朗石油设施",
        "severity": 5, "actors": ["Israel", "global_markets"],
        "targets": ["Iran_oil_facilities"],
        "consequences": ["oil_infrastructure_targeted", "price_spike"],
        "category": "economic_shock",
    },
    {
        "id": "evt_012", "date": "2026-03-10", "day": 11,
        "event_type": "diplomatic",
        "description": "Trump 称战争 'very soon' 结束。油价从 $114 暴跌回 $95（市场解读缓和信号）",
        "severity": 4, "actors": ["Trump"],
        "targets": ["global_markets"],
        "consequences": ["ceasefire_signal", "oil_price_volatility"],
        "category": "de_escalation_signal",
    },
    {
        "id": "evt_013", "date": "2026-03-11", "day": 13,
        "event_type": "economic",
        "description": "IEA 全票通过释放 4 亿桶战略储备（史上最大）。能源部长乌龙帖→油价暴跌→否认→删帖",
        "severity": 4, "actors": ["IEA", "Wright"],
        "targets": ["oil_markets", "SPR"],
        "consequences": ["spr_release", "market_chaos", "credibility_damage"],
        "category": "economic_intervention",
    },
]

# ── 测试集事件: Day 13-17 (3/12-3/16) ───────────────────────────────────

TEST_EVENTS = [
    {
        "id": "evt_014", "date": "2026-03-12", "day": 14,
        "event_type": "military_strike",
        "description": "伊朗无人船炸毁巴斯拉油轮，伊拉克暂停港口。Brent 首破 $100",
        "severity": 5, "actors": ["Iran"],
        "targets": ["Basra_tanker", "Iraq_port"],
        "consequences": ["oil_shipping_disrupted", "brent_100_breached"],
        "category": "escalation",
    },
    {
        "id": "evt_015", "date": "2026-03-13", "day": 15,
        "event_type": "military_strike",
        "description": "美军轰炸 Kharg Island 军事目标。Trump: 'totally obliterated crown jewel'",
        "severity": 5, "actors": ["US"],
        "targets": ["Kharg_Island"],
        "consequences": ["strategic_oil_facility_hit", "escalation_peak"],
        "category": "military_escalation",
    },
    {
        "id": "evt_016", "date": "2026-03-13", "day": 15,
        "event_type": "escalation",
        "description": "伊朗对沙特发射 24+ 无人机，阿曼 Duqm/Salalah 被击中。法军首次阵亡",
        "severity": 5, "actors": ["Iran"],
        "targets": ["Saudi_Arabia", "Oman", "France"],
        "consequences": ["gulf_states_under_attack", "nato_ally_casualty"],
        "category": "regional_spillover",
    },
    {
        "id": "evt_017", "date": "2026-03-14", "day": 16,
        "event_type": "military_strike",
        "description": "德黑兰亲政府集会遭空袭。美增派 5000 海军陆战队。美军死亡升至 13 人",
        "severity": 5, "actors": ["US", "Israel"],
        "targets": ["Tehran_rally", "Hormuz"],
        "consequences": ["civilian_target_controversy", "force_escalation"],
        "category": "military_escalation",
    },
    {
        "id": "evt_018", "date": "2026-03-15", "day": 17,
        "event_type": "escalation",
        "description": "美驻巴格达大使馆遭导弹袭击，紧急撤离令。巴林首都被无人机攻击。科威特机场雷达被毁",
        "severity": 5, "actors": ["Iran_proxies", "Iran"],
        "targets": ["Baghdad_embassy", "Manama", "Kuwait_airport"],
        "consequences": ["embassy_attack", "gulf_capitals_under_fire", "civilian_casualties"],
        "category": "regional_war",
    },
    {
        "id": "evt_019", "date": "2026-03-15", "day": 17,
        "event_type": "diplomatic",
        "description": "Sacks(白宫AI沙皇)呼吁'declare victory and get out'。Hegseth 同日宣布最大规模打击。鸽鹰分歧明确化",
        "severity": 3, "actors": ["Sacks", "Hegseth", "Trump"],
        "targets": ["US_domestic_politics"],
        "consequences": ["internal_policy_split", "exit_debate"],
        "category": "political_dynamics",
    },
]

# ── KG 初始实体（开战前可知）───────────────────────────────────────────

PRE_WAR_KG = {
    "entities": [
        {"id": "country:us", "type": "country", "name": "United States", "props": {"gdp_t": 28, "military_rank": 1}},
        {"id": "country:iran", "type": "country", "name": "Iran", "props": {"gdp_b": 400, "pop_m": 88, "inflation_pct": 45}},
        {"id": "country:israel", "type": "country", "name": "Israel", "props": {"military_rank": 18, "nuclear": True}},
        {"id": "country:saudi", "type": "country", "name": "Saudi Arabia", "props": {"oil_export_mbd": 7.5}},
        {"id": "country:uae", "type": "country", "name": "UAE", "props": {}},
        {"id": "country:bahrain", "type": "country", "name": "Bahrain", "props": {"us_naval_base": True}},
        {"id": "country:kuwait", "type": "country", "name": "Kuwait", "props": {}},
        {"id": "country:qatar", "type": "country", "name": "Qatar", "props": {"us_air_base": True}},
        {"id": "leader:trump", "type": "leader", "name": "Donald Trump", "props": {"role": "US President"}},
        {"id": "leader:khamenei", "type": "leader", "name": "Ali Khamenei", "props": {"role": "Supreme Leader of Iran", "age": 86}},
        {"id": "leader:netanyahu", "type": "leader", "name": "Benjamin Netanyahu", "props": {"role": "Israel PM"}},
        {"id": "leader:pezeshkian", "type": "leader", "name": "Masoud Pezeshkian", "props": {"role": "Iran President", "orientation": "moderate"}},
        {"id": "leader:mojtaba", "type": "leader", "name": "Mojtaba Khamenei", "props": {"role": "Son of Supreme Leader", "orientation": "hardline"}},
        {"id": "leader:hegseth", "type": "leader", "name": "Pete Hegseth", "props": {"role": "US Defense Secretary"}},
        {"id": "org:irgc", "type": "military_unit", "name": "IRGC", "props": {"type": "revolutionary_guard", "loyalty": "supreme_leader"}},
        {"id": "org:centcom", "type": "military_unit", "name": "CENTCOM", "props": {"aor": "middle_east"}},
        {"id": "org:idf", "type": "military_unit", "name": "IDF", "props": {}},
        {"id": "org:mossad", "type": "military_unit", "name": "Mossad", "props": {"type": "intelligence"}},
        {"id": "org:hezbollah", "type": "military_unit", "name": "Hezbollah", "props": {"base": "Lebanon", "patron": "Iran"}},
        {"id": "org:houthis", "type": "military_unit", "name": "Houthis", "props": {"base": "Yemen", "patron": "Iran"}},
        {"id": "org:fifth_fleet", "type": "military_unit", "name": "US Fifth Fleet", "props": {"base": "Bahrain"}},
        {"id": "facility:hormuz", "type": "economic_asset", "name": "Strait of Hormuz", "props": {"oil_flow_mbd": 17, "global_share_pct": 20}},
        {"id": "facility:kharg", "type": "facility", "name": "Kharg Island", "props": {"iran_oil_export_pct": 90, "type": "oil_terminal"}},
        {"id": "facility:natanz", "type": "facility", "name": "Natanz", "props": {"type": "nuclear_enrichment"}},
        {"id": "facility:fordow", "type": "facility", "name": "Fordow", "props": {"type": "nuclear_enrichment", "underground": True}},
        {"id": "facility:parchin", "type": "facility", "name": "Parchin", "props": {"type": "nuclear_research"}},
        {"id": "asset:spr", "type": "economic_asset", "name": "US Strategic Petroleum Reserve", "props": {"capacity_mb": 700}},
    ],
    "relations": [
        {"from": "country:us", "to": "country:israel", "type": "ALLIED_WITH"},
        {"from": "country:us", "to": "country:iran", "type": "HOSTILE_TO"},
        {"from": "country:israel", "to": "country:iran", "type": "HOSTILE_TO"},
        {"from": "country:iran", "to": "org:hezbollah", "type": "SUPPLIES"},
        {"from": "country:iran", "to": "org:houthis", "type": "SUPPLIES"},
        {"from": "country:iran", "to": "facility:hormuz", "type": "CONTROLS"},
        {"from": "country:iran", "to": "facility:kharg", "type": "CONTROLS"},
        {"from": "country:iran", "to": "facility:natanz", "type": "CONTROLS"},
        {"from": "org:fifth_fleet", "to": "country:bahrain", "type": "LOCATED_AT"},
        {"from": "org:centcom", "to": "country:qatar", "type": "LOCATED_AT"},
        {"from": "leader:khamenei", "to": "org:irgc", "type": "GOVERNS"},
        {"from": "leader:khamenei", "to": "country:iran", "type": "GOVERNS"},
        {"from": "leader:mojtaba", "to": "leader:khamenei", "type": "SUCCEEDS"},
        {"from": "country:saudi", "to": "facility:hormuz", "type": "DEPENDS_ON"},
        {"from": "country:uae", "to": "facility:hormuz", "type": "DEPENDS_ON"},
        {"from": "country:kuwait", "to": "facility:hormuz", "type": "DEPENDS_ON"},
        {"from": "facility:kharg", "to": "country:iran", "type": "PART_OF"},
        {"from": "org:hezbollah", "to": "country:israel", "type": "THREATENS"},
        {"from": "org:houthis", "to": "facility:hormuz", "type": "THREATENS"},
    ],
}


def generate_all():
    """生成所有数据文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 信号
    with open(DATA_DIR / "pre_war_signals.json", "w") as f:
        json.dump(PRE_WAR_SIGNALS, f, indent=2, ensure_ascii=False)

    # 事件 splits
    with open(DATA_DIR / "train_events.json", "w") as f:
        json.dump(TRAIN_EVENTS, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / "val_events.json", "w") as f:
        json.dump(VAL_EVENTS, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / "test_events.json", "w") as f:
        json.dump(TEST_EVENTS, f, indent=2, ensure_ascii=False)

    # KG
    with open(DATA_DIR / "pre_war_kg.json", "w") as f:
        json.dump(PRE_WAR_KG, f, indent=2, ensure_ascii=False)

    # 元信息
    meta = {
        "created": datetime.utcnow().isoformat() + "Z",
        "cutoff_date": "2026-02-27",
        "war_start": "2026-02-28",
        "train_window": "Day 1-8 (2026-02-28 to 2026-03-07)",
        "val_window": "Day 9-12 (2026-03-08 to 2026-03-11)",
        "test_window": "Day 13-17 (2026-03-12 to 2026-03-16)",
        "total_signals": len(PRE_WAR_SIGNALS),
        "total_train_events": len(TRAIN_EVENTS),
        "total_val_events": len(VAL_EVENTS),
        "total_test_events": len(TEST_EVENTS),
        "kg_entities": len(PRE_WAR_KG["entities"]),
        "kg_relations": len(PRE_WAR_KG["relations"]),
    }
    with open(DATA_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {meta['total_signals']} signals, "
          f"{meta['total_train_events']} train / {meta['total_val_events']} val / "
          f"{meta['total_test_events']} test events")
    print(f"   KG: {meta['kg_entities']} entities, {meta['kg_relations']} relations")
    print(f"   Output: {DATA_DIR}")


if __name__ == "__main__":
    generate_all()
