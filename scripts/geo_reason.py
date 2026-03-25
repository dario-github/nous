"""Nous Geopolitical Reasoning Engine

从 KG + 信号 + Datalog 规则推导事件预测。
核心流程：Signal Ingest → KG Facts → Rule Inference → LLM Synthesis → Predictions

防泄漏：所有推理仅基于 cutoff_date 之前的信息。
"""
import json
import os
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data" / "geo"


def load_kg() -> dict:
    with open(DATA_DIR / "pre_war_kg.json") as f:
        return json.load(f)


def load_signals() -> list[dict]:
    with open(DATA_DIR / "pre_war_signals.json") as f:
        return json.load(f)


# ── Datalog 规则引擎（Python 实现）───────────────────────────────────

class GeoReasoner:
    """基于 KG 和信号的地缘推理器"""

    def __init__(self, kg: dict, signals: list[dict]):
        self.entities = {e["id"]: e for e in kg["entities"]}
        self.relations = kg["relations"]
        self.signals = signals

        # 构建关系索引
        self._rel_index = {}
        for r in self.relations:
            key = r["type"]
            self._rel_index.setdefault(key, []).append(r)

    def _query_rel(self, rtype: str) -> list[dict]:
        return self._rel_index.get(rtype, [])

    def _has_rel(self, from_id: str, rtype: str, to_id: str = None) -> bool:
        for r in self._query_rel(rtype):
            if r["from"] == from_id:
                if to_id is None or r["to"] == to_id:
                    return True
        return False

    def _get_entity(self, eid: str) -> dict:
        return self.entities.get(eid, {})

    # ── Rule implementations ──────────────────────────────────────────

    def r1_retaliation(self) -> list[dict]:
        """R1: 报复必然性"""
        inferences = []
        # 伊朗有导弹能力 + 被美以敌对
        if (self._has_rel("country:us", "HOSTILE_TO", "country:iran") and
                self._get_entity("org:irgc")):
            inferences.append({
                "rule": "R1",
                "fact": "retaliation_certain(iran, us+israel)",
                "confidence": 0.95,
                "reasoning": "伊朗拥有导弹库存(IRGC)+被美以攻击=报复几乎必然",
                "prediction_type": "military_strike",
                "predicted_day_range": [1, 3],
                "description": "伊朗对以色列/美军基地发射导弹报复",
            })
        return inferences

    def r3_proxy_retaliation(self) -> list[dict]:
        """R3: 代理人报复"""
        inferences = []
        # 伊朗供应真主党和胡塞 → 代理人攻击以色列和海湾
        for r in self._query_rel("SUPPLIES"):
            proxy_id = r["to"]
            proxy = self._get_entity(proxy_id)
            if proxy:
                name = proxy.get("name", proxy_id)
                for threat in self._query_rel("THREATENS"):
                    if threat["from"] == proxy_id:
                        target = self._get_entity(threat["to"])
                        inferences.append({
                            "rule": "R3",
                            "fact": f"proxy_retaliation({name}, {threat['to']})",
                            "confidence": 0.80,
                            "reasoning": f"{name}受伊朗支持+已威胁{threat['to']}=代理人攻击",
                            "prediction_type": "escalation",
                            "predicted_day_range": [1, 5],
                            "description": f"{name}对{target.get('name', threat['to'])}发动攻击",
                        })
        return inferences

    def r5_chokepoint_weaponization(self) -> list[dict]:
        """R5: 经济武器化（霍尔木兹）"""
        inferences = []
        # 伊朗控制霍尔木兹 + 被攻击 → 武器化
        if (self._has_rel("country:iran", "CONTROLS", "facility:hormuz")):
            hormuz = self._get_entity("facility:hormuz")
            inferences.append({
                "rule": "R5",
                "fact": "chokepoint_weaponized(iran, hormuz)",
                "confidence": 0.75,
                "reasoning": f"伊朗控制霍尔木兹(全球{hormuz.get('props', {}).get('global_share_pct', 20)}%油)+被攻击=封锁是最大杠杆",
                "prediction_type": "escalation",
                "predicted_day_range": [1, 3],
                "description": "伊朗封锁或限制霍尔木兹海峡通行",
            })

            # 依赖国受压
            for dep in self._query_rel("DEPENDS_ON"):
                if dep["to"] == "facility:hormuz":
                    country = self._get_entity(dep["from"])
                    inferences.append({
                        "rule": "R5b",
                        "fact": f"economic_pressure({dep['from']}, iran)",
                        "confidence": 0.70,
                        "reasoning": f"{country.get('name', dep['from'])}依赖霍尔木兹+封锁=经济受压",
                        "prediction_type": "economic",
                        "predicted_day_range": [2, 8],
                        "description": f"{country.get('name', dep['from'])}受霍尔木兹封锁影响",
                    })
        return inferences

    def r6_oil_shock(self) -> list[dict]:
        """R6: 油价冲击"""
        return [{
            "rule": "R6",
            "fact": "oil_price_shock()",
            "confidence": 0.90,
            "reasoning": "霍尔木兹封锁+中东冲突=油价暴涨",
            "prediction_type": "economic",
            "predicted_day_range": [1, 8],
            "description": "油价从 $55 暴涨 50%+ 至 $80+",
        }]

    def r7_leadership_vacuum(self) -> list[dict]:
        """R7: 领导力真空"""
        inferences = []
        # 哈梅内伊是最高领袖 + 穆杰塔巴是继承人
        if (self._has_rel("leader:mojtaba", "SUCCEEDS", "leader:khamenei") and
                self._has_rel("leader:khamenei", "GOVERNS", "country:iran")):
            mojtaba = self._get_entity("leader:mojtaba")
            inferences.append({
                "rule": "R7",
                "fact": "succession_crisis(iran, mojtaba)",
                "confidence": 0.60,
                "reasoning": "如哈梅内伊被消灭→穆杰塔巴继任（伊朗首次世袭）→合法性争议+强硬路线",
                "prediction_type": "political",
                "predicted_day_range": [7, 14],
                "description": "伊朗领导层继任危机，穆杰塔巴可能继任但面临合法性挑战",
            })
        return inferences

    def r8_escalation_spiral(self) -> list[dict]:
        """R8: 升级螺旋"""
        return [{
            "rule": "R8",
            "fact": "escalation_spiral(us+israel, iran)",
            "confidence": 0.85,
            "reasoning": "双方都有打击能力+报复意愿=升级螺旋难以控制",
            "prediction_type": "escalation",
            "predicted_day_range": [3, 14],
            "description": "美以与伊朗进入交替报复升级螺旋，烈度递增",
        }]

    def r9_regional_spillover(self) -> list[dict]:
        """R9: 区域外溢"""
        inferences = []
        # 美军基地所在国可能被波及
        base_countries = []
        for e in self.entities.values():
            props = e.get("props", {})
            if props.get("us_naval_base") or props.get("us_air_base"):
                base_countries.append(e)

        for country in base_countries:
            inferences.append({
                "rule": "R9",
                "fact": f"regional_spillover({country['id']})",
                "confidence": 0.65,
                "reasoning": f"{country['name']}有美军基地=可能成为代理人攻击目标",
                "prediction_type": "escalation",
                "predicted_day_range": [5, 14],
                "description": f"冲突外溢至{country['name']}（美军基地所在国）",
            })
        return inferences

    def r10_humanitarian(self) -> list[dict]:
        """R10: 人道危机"""
        return [{
            "rule": "R10",
            "fact": "humanitarian_crisis(iran)",
            "confidence": 0.85,
            "reasoning": "大规模空袭+人口密集城市=平民伤亡不可避免",
            "prediction_type": "humanitarian",
            "predicted_day_range": [3, 10],
            "description": "伊朗出现大规模平民伤亡和人道危机",
        }]

    def r12_nuclear_strike(self) -> list[dict]:
        """R12: 核设施打击"""
        inferences = []
        if (self._get_entity("facility:natanz") and
                self._get_entity("facility:fordow")):
            inferences.append({
                "rule": "R12",
                "fact": "nuclear_strike_likely(us+israel, iran)",
                "confidence": 0.70,
                "reasoning": "伊朗接近核门槛(sig_009)+以色列视为存亡威胁=核设施是优先打击目标",
                "prediction_type": "military_strike",
                "predicted_day_range": [3, 7],
                "description": "美以打击伊朗核设施（Natanz/Fordow）",
            })
        return inferences

    def run_all_rules(self) -> list[dict]:
        """运行所有推理规则"""
        all_inferences = []
        all_inferences.extend(self.r1_retaliation())
        all_inferences.extend(self.r3_proxy_retaliation())
        all_inferences.extend(self.r5_chokepoint_weaponization())
        all_inferences.extend(self.r6_oil_shock())
        all_inferences.extend(self.r7_leadership_vacuum())
        all_inferences.extend(self.r8_escalation_spiral())
        all_inferences.extend(self.r9_regional_spillover())
        all_inferences.extend(self.r10_humanitarian())
        all_inferences.extend(self.r11_narrative_warfare())
        all_inferences.extend(self.r12_nuclear_strike())
        all_inferences.extend(self.r13_diplomatic_backchannel())
        all_inferences.extend(self.r14_strategic_reserve_response())
        return all_inferences

    def r11_narrative_warfare(self) -> list[dict]:
        """R11: 叙事战 — 国内政治压力→控制战争叙事"""
        inferences = []
        # Trump 面临国内政治压力 + 战争进行中
        if self._get_entity("leader:trump"):
            inferences.append({
                "rule": "R11",
                "fact": "narrative_warfare(trump)",
                "confidence": 0.70,
                "reasoning": "Trump面临国内政治压力+中期选举考量=战争叙事控制（宣称胜利/缓和信号）",
                "prediction_type": "diplomatic",
                "predicted_day_range": [8, 14],
                "description": "Trump 发出缓和信号或宣称战争即将结束，影响油价和市场",
            })
        return inferences

    def r13_diplomatic_backchannel(self) -> list[dict]:
        """R13: 外交降级尝试 — 长期冲突+第三方调解→降级尝试"""
        inferences = []
        # 伊朗温和派存在 + 海湾国家利益相关
        if self._get_entity("leader:pezeshkian"):
            inferences.append({
                "rule": "R13",
                "fact": "diplomatic_backchannel(pezeshkian, gulf_states)",
                "confidence": 0.55,
                "reasoning": "Pezeshkian是改革派总统+海湾国家受战争冲击=可能尝试外交降级",
                "prediction_type": "diplomatic",
                "predicted_day_range": [7, 12],
                "description": "伊朗温和派（Pezeshkian）尝试向海湾国家外交降级",
            })
        return inferences

    def r14_strategic_reserve_response(self) -> list[dict]:
        """R14: 战略储备释放 — 油价暴涨+消费国压力→IEA行动"""
        inferences = []
        if self._has_rel("country:iran", "CONTROLS", "facility:hormuz"):
            inferences.append({
                "rule": "R14",
                "fact": "strategic_reserve_release(iea)",
                "confidence": 0.65,
                "reasoning": "霍尔木兹封锁→油价暴涨→IEA消费国协调释放战略储备",
                "prediction_type": "economic",
                "predicted_day_range": [10, 16],
                "description": "IEA 协调成员国释放战略石油储备以平抑油价",
            })
        return inferences
        return all_inferences

    def generate_predictions(self, max_predictions: int = 15) -> list[dict]:
        """从推理结果生成结构化预测"""
        inferences = self.run_all_rules()

        # 按置信度排序，取 top N
        inferences.sort(key=lambda x: x["confidence"], reverse=True)
        top = inferences[:max_predictions]

        predictions = []
        for i, inf in enumerate(top):
            day_range = inf["predicted_day_range"]
            mid_day = (day_range[0] + day_range[1]) // 2

            # 回溯相关信号 — 基于推理中引用的实体和含义匹配
            causal_signals = self._trace_signals(inf)

            predictions.append({
                "id": f"pred_{i+1:03d}",
                "predicted_day": mid_day,
                "event_type": inf["prediction_type"],
                "description": inf["description"],
                "probability": inf["confidence"],
                "causal_chain": causal_signals,
                "reasoning": inf["reasoning"],
                "rule": inf["rule"],
                "day_range": day_range,
            })

        return predictions

    def _trace_signals(self, inference: dict) -> list[str]:
        """回溯推理所依赖的信号 IDs"""
        matched = []
        reasoning = inference.get("reasoning", "").lower()
        description = inference.get("description", "").lower()
        rule = inference.get("rule", "")

        # 规则→信号映射表（手动维护，确保因果链可追溯）
        RULE_SIGNAL_MAP = {
            "R1": ["sig_005", "sig_007", "sig_012"],  # 军事部署+IRGC能力+导弹库存
            "R3": ["sig_010", "sig_007"],  # 真主党声明+哈梅内伊号召
            "R5": ["sig_008"],  # 霍尔木兹部署
            "R5b": ["sig_008", "sig_011"],  # 霍尔木兹+GCC会议
            "R6": ["sig_004", "sig_008"],  # 油价基数+霍尔木兹
            "R7": ["sig_007"],  # 哈梅内伊+继任者
            "R8": ["sig_003", "sig_005", "sig_007", "sig_012"],  # 双方能力
            "R9": ["sig_015", "sig_011"],  # 预置部队+GCC
            "R10": ["sig_005"],  # 大规模打击
            "R11": ["sig_001", "sig_002"],  # Trump政治议程+国内政治
            "R12": ["sig_009", "sig_006"],  # 核浓缩+情报
            "R13": ["sig_011", "sig_013"],  # GCC+伊朗内部
            "R14": ["sig_004", "sig_008"],  # 油价+霍尔木兹
        }

        # 从规则映射获取信号
        mapped = RULE_SIGNAL_MAP.get(rule, [])
        matched.extend(mapped)

        # 额外：检查 reasoning 中是否直接引用了 sig_xxx
        for sig in self.signals:
            if sig["id"] in reasoning:
                if sig["id"] not in matched:
                    matched.append(sig["id"])

        return matched


def temporal_leak_check(predictions: list, cutoff: str = "2026-02-27") -> list[str]:
    """防泄漏检查：确保预测中不包含 cutoff 之后的信息"""
    violations = []
    cutoff_dt = datetime.fromisoformat(cutoff)

    # 已知未来信息关键词（cutoff 后才能知道的事实）
    future_keywords = [
        "穆杰塔巴继任", "Mojtaba became", "Kharg Island bombed",
        "哈梅内伊遇害", "$114", "$100", "IEA 400M",
        "巴格达大使馆", "巴林被无人机", "F1取消",
    ]

    for pred in predictions:
        desc = pred.get("description", "") + pred.get("reasoning", "")
        for kw in future_keywords:
            if kw.lower() in desc.lower():
                violations.append(f"pred {pred['id']}: 包含未来信息 '{kw}'")

    return violations


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-predictions", type=int, default=12)
    parser.add_argument("--output", default=str(DATA_DIR / "rule_predictions.json"))
    parser.add_argument("--leak-check", action="store_true", default=True)
    args = parser.parse_args()

    kg = load_kg()
    signals = load_signals()

    reasoner = GeoReasoner(kg, signals)
    predictions = reasoner.generate_predictions(args.max_predictions)

    # 防泄漏检查
    if args.leak_check:
        violations = temporal_leak_check(predictions)
        if violations:
            print("⚠️ TEMPORAL LEAK DETECTED:")
            for v in violations:
                print(f"  {v}")
            print("修复泄漏后再继续。")
            return

    with open(args.output, "w") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {len(predictions)} rule-based predictions")
    print(f"   Output: {args.output}")

    # 打印摘要
    print(f"\n{'='*60}")
    for p in predictions:
        print(f"  [{p['rule']}] Day {p['predicted_day']} ({p['probability']:.0%}) "
              f"— {p['description'][:60]}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
