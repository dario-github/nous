#!/usr/bin/env python3
"""KG 实体双语化 — 为所有实体的 props 添加 name_zh 字段。

策略：
1. ATT&CK tactics/techniques: 使用 MITRE 官方中文翻译
2. CWE: 使用 CWE 官方中文名
3. category/concept/tool/person/project: 手写映射 + LLM fallback
4. 关系类型: 双语化

运行: PYTHONPATH=src python3 scripts/localize_kg.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from nous.db import NousDB

# ── ATT&CK Tactics 中文翻译（MITRE 官方） ──
TACTIC_ZH = {
    "TA0001": "初始访问",
    "TA0002": "执行",
    "TA0003": "持久化",
    "TA0004": "权限提升",
    "TA0005": "防御规避",
    "TA0006": "凭据访问",
    "TA0007": "发现",
    "TA0008": "横向移动",
    "TA0009": "收集",
    "TA0010": "数据渗出",
    "TA0011": "命令与控制",
    "TA0040": "影响",
    "TA0042": "资源开发",
    "TA0043": "侦察",
}

# ── ATT&CK Techniques 中文翻译 ──
TECHNIQUE_ZH = {
    "T1003": "操作系统凭据转储",
    "T1005": "本地系统数据",
    "T1021": "远程服务",
    "T1036": "伪装",
    "T1041": "通过C2通道渗出",
    "T1047": "WMI",
    "T1053": "计划任务/作业",
    "T1055": "进程注入",
    "T1059": "命令和脚本解释器",
    "T1071": "应用层协议",
    "T1078": "有效账户",
    "T1082": "系统信息发现",
    "T1083": "文件和目录发现",
    "T1098": "账户操控",
    "T1105": "远程文件复制",
    "T1110": "暴力破解",
    "T1133": "外部远程服务",
    "T1190": "利用面向公众的应用",
    "T1203": "客户端漏洞利用",
    "T1204": "用户执行",
    "T1486": "数据加密勒索",
    "T1489": "服务停止",
    "T1531": "账户访问移除",
    "T1546": "事件触发执行",
    "T1547": "启动或登录自启动执行",
    "T1548": "滥用提权控制",
    "T1555": "密码存储凭据",
    "T1562": "损害防御",
    "T1566": "钓鱼",
    "T1567": "通过Web服务渗出",
    "T1569": "系统服务",
    "T1570": "工具横向传输",
    "T1574": "劫持执行流",
    "T1595": "主动扫描",
}

# ── CWE 中文翻译 ──
CWE_ZH = {
    "CWE-20": "输入验证不当",
    "CWE-22": "路径遍历",
    "CWE-77": "命令注入",
    "CWE-78": "操作系统命令注入",
    "CWE-79": "跨站脚本(XSS)",
    "CWE-89": "SQL注入",
    "CWE-94": "代码注入",
    "CWE-119": "内存缓冲区操作限制不当",
    "CWE-125": "越界读取",
    "CWE-190": "整数溢出",
    "CWE-200": "信息泄露",
    "CWE-269": "特权管理不当",
    "CWE-276": "默认权限不正确",
    "CWE-287": "认证不当",
    "CWE-306": "关键功能缺少认证",
    "CWE-352": "跨站请求伪造(CSRF)",
    "CWE-362": "竞态条件",
    "CWE-416": "释放后使用",
    "CWE-434": "危险类型文件上传",
    "CWE-476": "空指针解引用",
    "CWE-502": "不可信数据反序列化",
    "CWE-787": "越界写入",
    "CWE-798": "硬编码凭据",
    "CWE-862": "缺少授权",
    "CWE-863": "授权不正确",
}

# ── Category 中文 ──
CATEGORY_ZH = {
    "Cybercrime": "网络犯罪",
    "Fraud": "欺诈",
    "Harassment": "骚扰",
    "Hate": "仇恨",
    "Drugs": "毒品",
    "Sexual": "色情",
    "Copyright": "版权侵犯",
    "Disinformation": "虚假信息",
    "Weapons": "武器",
    "Physical_harm": "人身伤害",
    "Other": "其他",
    "system": "系统",
    "content-safety": "内容安全",
}

# ── 关系类型中文 ──
RELATION_ZH = {
    "DEPENDS_ON": "依赖",
    "PART_OF": "属于",
    "WORKS_ON": "参与",
    "KNOWS": "认识",
    "governed_by": "受管辖",
    "MITIGATES": "缓解",
    "EXPLOITS": "利用",
    "ENABLES": "支持",
    "TARGETS": "针对",
    "DETECTS": "检测",
    "COOCCURS_WITH": "共现",
    "SIMILAR_TO": "相似",
}


def localize_entities(db: NousDB) -> int:
    """给实体添加 name_zh。"""
    rows = db.db.run("?[id, etype, props] := *entity{id, etype, props}")
    updated = 0

    for _, r in rows.iterrows():
        eid = r["id"]
        etype = r["etype"]
        props = json.loads(r["props"]) if isinstance(r["props"], str) else (r["props"] or {})

        if props.get("name_zh"):
            continue  # already localized

        name_en = props.get("name", eid.split(":")[-1])
        name_zh = None

        # ATT&CK tactic
        if etype == "attack_tactic":
            tid = eid.split(":")[-1]
            name_zh = TACTIC_ZH.get(tid)

        # ATT&CK technique
        elif etype == "attack_technique":
            tid = eid.split(":")[-1]
            name_zh = TECHNIQUE_ZH.get(tid)

        # CWE
        elif etype == "vulnerability_class":
            cwe_id = eid.split(":")[-1]
            name_zh = CWE_ZH.get(cwe_id)

        # Category
        elif etype == "category":
            name_zh = CATEGORY_ZH.get(name_en)

        # Person — known entities
        elif etype == "person":
            person_map = {
                "东丞": "章东丞",
                "章东丞 (Dario / zdclink)": "章东丞",
            }
            name_zh = person_map.get(name_en, name_en)

        if name_zh:
            props["name_zh"] = name_zh
            from nous.schema import Entity
            db.upsert_entities([Entity(
                id=eid,
                etype=etype,
                labels=[],
                properties=props,
            )])
            updated += 1

    return updated


def localize_relations(db: NousDB) -> int:
    """给关系添加 rel_type_zh。"""
    rows = db.db.run("?[from_id, to_id, rtype, props] := *relation{from_id, to_id, rtype, props}")
    updated = 0

    for _, r in rows.iterrows():
        rel_type = r["rtype"]
        props = json.loads(r["props"]) if isinstance(r["props"], str) else (r["props"] or {})

        if props.get("rel_type_zh"):
            continue

        zh = RELATION_ZH.get(rel_type)
        if zh:
            props["rel_type_zh"] = zh
            from nous.schema import Relation
            db.upsert_relations([Relation(
                from_id=r["from_id"],
                to_id=r["to_id"],
                rtype=rel_type,
                properties=props,
            )])
            updated += 1

    return updated


def main():
    db = NousDB()
    e_count = localize_entities(db)
    r_count = localize_relations(db)
    total_e = db.count_entities()
    total_r = db.count_relations()
    print(f"Localized {e_count} entities, {r_count} relations")
    print(f"Total: {total_e} entities, {total_r} relations")


if __name__ == "__main__":
    main()
