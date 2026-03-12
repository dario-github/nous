"""Nous — LLM 本体构建最小闭环 (M1.7)

流程：文本 → LLM 提取 → Pydantic 校验 → Proposal 队列 → 自动确认 → Entity 写入

注意：LLM 调用通过 subprocess 调 gemini CLI，实际调用留接口。
测试时通过 mock 替换 _call_llm。
"""
import json
import subprocess
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ValidationError

from nous.schema import Entity


# ── Pydantic 模型 ──────────────────────────────────────────────────────────


class EntityCandidate(BaseModel):
    """LLM 提取的原始实体候选（校验前）"""
    name: str
    type: str = "concept"           # person / project / concept / event / resource
    confidence: float = 0.8
    properties: dict = {}
    relations: list[dict] = []


class Proposal(BaseModel):
    """Entity 提案（写入 proposals 表前的内存对象）"""
    id: str
    entity_dict: dict               # 原始 LLM 输出 dict
    entity: Optional[dict] = None  # Pydantic 校验后的 Entity dict
    trigger_pattern: str = ""
    confidence: float = 0.0
    status: str = "pending"         # pending / confirmed / rejected
    created_at: float = 0.0
    reviewed_at: float = 0.0


# ── LLM 调用层（可替换 mock） ───────────────────────────────────────────────


def _call_llm(prompt: str) -> str:
    """
    调用 gemini CLI 提取实体。返回 JSON 字符串。

    实际环境通过 subprocess 调 gemini，测试时 mock 此函数。
    """
    cmd = [
        "gemini",
        "-p",
        prompt,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gemini CLI failed: {result.stderr}")
    return result.stdout.strip()


_EXTRACT_PROMPT_TEMPLATE = """从以下文本中提取实体和关系，以 JSON 格式输出。

文本：
{text}

输出格式（严格 JSON，不要 markdown 包装）：
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "person|project|concept|event|resource",
      "confidence": 0.0-1.0,
      "properties": {{}},
      "relations": [
        {{"to": "目标实体名", "type": "关系类型", "confidence": 0.9}}
      ]
    }}
  ]
}}

只输出 JSON，不要解释。"""


# ── 核心函数 ────────────────────────────────────────────────────────────────


def extract_entities_from_text(text: str) -> list[dict]:
    """
    调用 LLM 从文本提取实体和关系。

    返回 list[dict]，每个 dict 包含 name/type/confidence/properties/relations。
    LLM 调用通过 _call_llm(prompt)，可被 mock 替换。
    """
    prompt = _EXTRACT_PROMPT_TEMPLATE.format(text=text)

    raw = _call_llm(prompt)

    # 清理可能的 markdown code fence
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 返回非法 JSON: {e}\n原始输出: {raw[:200]}") from e

    entities = data.get("entities", [])
    return entities


def propose_entity(entity_dict: dict, db=None) -> Proposal:
    """
    Pydantic 校验 entity_dict → 写入 proposals 表 → 返回 Proposal。

    db: NousDB 实例（如果为 None，只返回内存对象，不写 DB）
    """
    # Pydantic 校验
    try:
        candidate = EntityCandidate(**entity_dict)
    except ValidationError as e:
        raise ValueError(f"实体校验失败: {e}") from e

    # 构建 Entity dict
    slug = candidate.name.lower().replace(" ", "_").replace("/", "_")[:64]
    entity_id = f"entity:{candidate.type}:{slug}"
    entity = Entity(
        id=entity_id,
        etype=candidate.type,
        labels=[candidate.name],
        properties=candidate.properties,
        confidence=candidate.confidence,
        source="llm_ontology",
    )

    # 构建 Proposal
    proposal = Proposal(
        id=f"prop:{uuid.uuid4().hex[:8]}",
        entity_dict=entity_dict,
        entity=entity.model_dump(),
        trigger_pattern="llm_extract",
        confidence=candidate.confidence,
        status="pending",
        created_at=time.time(),
    )

    # 写入 DB proposals 表
    if db is not None:
        try:
            db.db.run(
                "?[id, constraint_draft, trigger_pattern, confidence, "
                "status, created_at, reviewed_at] "
                "<- [[$id, $cd, $tp, $conf, $status, $cat, $rat]] "
                ":put proposal {id => constraint_draft, trigger_pattern, "
                "confidence, status, created_at, reviewed_at}",
                {
                    "id": proposal.id,
                    "cd": proposal.entity,
                    "tp": proposal.trigger_pattern,
                    "conf": proposal.confidence,
                    "status": proposal.status,
                    "cat": proposal.created_at,
                    "rat": proposal.reviewed_at,
                },
            )
        except Exception as e:
            raise RuntimeError(f"写入 proposal 失败: {e}") from e

    return proposal


def confirm_proposal(proposal_id: str, db) -> Entity:
    """
    从 proposals 表取出 proposal → 写入 entity 表 → 返回 Entity。

    db: NousDB 实例
    """
    # 从 DB 查询 proposal
    rows = db._query_with_params(
        "?[id, constraint_draft, confidence, status] := "
        "*proposal{id, constraint_draft, confidence, status}, id = $pid",
        {"pid": proposal_id},
    )

    if not rows:
        raise ValueError(f"Proposal {proposal_id!r} 不存在")

    row = rows[0]
    if row["status"] != "pending":
        raise ValueError(f"Proposal {proposal_id!r} 状态为 {row['status']!r}，不可确认")

    entity_data = row["constraint_draft"]

    # 重建 Entity 并写入
    entity = Entity(**entity_data)
    db.upsert_entities([entity])

    # 更新 proposal 状态为 confirmed
    db.db.run(
        "?[id, constraint_draft, trigger_pattern, confidence, "
        "status, created_at, reviewed_at] := "
        "*proposal{id, constraint_draft, trigger_pattern, confidence, "
        "created_at}, status = $status, reviewed_at = $rat, id = $pid "
        ":put proposal {id => constraint_draft, trigger_pattern, "
        "confidence, status, created_at, reviewed_at}",
        {
            "pid": proposal_id,
            "status": "confirmed",
            "rat": time.time(),
        },
    )

    return entity


def ingest_text(text: str, db=None, auto_confirm_threshold: float = 0.9) -> dict:
    """
    完整闭环：提取 → propose → 自动确认（confidence > threshold）→ 写入。

    返回 dict：{
        "extracted": int,     # 提取到的实体数
        "proposed": int,      # 写入 proposal 的数量
        "confirmed": int,     # 自动确认的数量
        "proposals": list[str],  # proposal id 列表
        "entities": list[str],   # 已写入 entity id 列表
        "errors": list[str],
    }
    """
    result = {
        "extracted": 0,
        "proposed": 0,
        "confirmed": 0,
        "proposals": [],
        "entities": [],
        "errors": [],
    }

    # Step 1: 提取
    try:
        candidates = extract_entities_from_text(text)
    except Exception as e:
        result["errors"].append(f"提取失败: {e}")
        return result

    result["extracted"] = len(candidates)

    # Step 2: propose 每个实体
    proposals = []
    for candidate in candidates:
        try:
            proposal = propose_entity(candidate, db=db)
            proposals.append(proposal)
            result["proposed"] += 1
            result["proposals"].append(proposal.id)
        except Exception as e:
            result["errors"].append(f"propose 失败 {candidate.get('name', '?')}: {e}")

    # Step 3: 自动确认高置信度实体
    for proposal in proposals:
        if proposal.confidence >= auto_confirm_threshold:
            if db is not None:
                try:
                    entity = confirm_proposal(proposal.id, db)
                    result["confirmed"] += 1
                    result["entities"].append(entity.id)
                except Exception as e:
                    result["errors"].append(f"confirm 失败 {proposal.id}: {e}")
            else:
                # 无 DB 时直接记录（测试用）
                if proposal.entity:
                    result["confirmed"] += 1
                    result["entities"].append(proposal.entity.get("id", ""))

    return result
