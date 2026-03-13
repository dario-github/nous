"""Nous — MD 文件解析器 (M1.1)

解析 memory/entities/**/*.md 的 YAML frontmatter + "## 关系" 段落
→ Entity + Relation Pydantic 对象
"""
from pathlib import Path
from typing import Optional
import re
import time

import yaml

from nous.schema import Entity, Relation


# ── 辅助函数 ────────────────────────────────────────────────────────────────

# 跳过的文件（索引/概述文件）
_SKIP_STEMS = {"_overview", "_abstract"}

_ETYPE_MAP = {
    "people": "person",
    "projects": "project",
    "concepts": "concept",
    "events": "event",
    "resources": "resource",
}

# 关系行格式：`- RTYPE → target` 或 `- RTYPE: target`
_REL_PATTERN = re.compile(
    r"^\s*-\s+([A-Z_]+)\s*[→:]\s*(.+)$"
)

# 支持的关系类型集合
_VALID_RTYPES = {
    "WORKS_ON", "KNOWS", "DEPENDS_ON", "CAUSED_BY", "PART_OF",
    "OWNS", "LOCATED_IN", "RELATED_TO", "MENTIONS", "TRIGGERS",
    "USED_BY", "TARGETS",
}


def _etype_from_id(entity_id: str) -> str:
    """从 entity ID 中提取实体类型，格式 entity:{type}:{slug}"""
    parts = entity_id.split(":")
    return parts[1] if len(parts) >= 3 else "unknown"


def _infer_rtype(from_id: str, to_id: str) -> str:
    """
    根据 from/to 实体类型推断语义关系类型。

    规则（按优先级）：
      person  → project  : WORKS_ON
      person  → person   : KNOWS
      project → project  : DEPENDS_ON
      concept → project  : USED_BY
      *       → *        : RELATED_TO（回退）
    """
    from_type = _etype_from_id(from_id)
    to_type = _etype_from_id(to_id)

    if from_type == "person" and to_type == "project":
        return "WORKS_ON"
    if from_type == "person" and to_type == "person":
        return "KNOWS"
    if from_type == "project" and to_type == "project":
        return "DEPENDS_ON"
    if from_type == "concept" and to_type == "project":
        return "USED_BY"
    return "RELATED_TO"


def _infer_etype(path: Path) -> str:
    """从目录名推断实体类型"""
    return _ETYPE_MAP.get(path.parent.name, "concept")


def _make_slug(name: str) -> str:
    """从名称生成 slug（保留中文/英文，去除 [[]] wikilink 括号）"""
    name = name.strip()
    # 去掉 [[...]] 包装
    name = re.sub(r"\[\[(.+?)\]\]", r"\1", name)
    return name.strip()


def _make_entity_id(etype: str, slug: str) -> str:
    """生成规范 entity ID: entity:{type}:{slug}"""
    return f"entity:{etype}:{slug}"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    从 MD 文本中提取 YAML frontmatter。
    返回 (frontmatter_dict, body_without_frontmatter)
    """
    if not text.startswith("---"):
        return {}, text

    # 找到第二个 ---
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 4:].strip()  # skip closing ---\n

    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}

    return fm, body


def _parse_relations_section(body: str, from_id: str, source: str, slug_to_id: dict) -> list[Relation]:
    """
    解析 MD body 中的 "## 关系" 段落。

    支持格式：
      - WORKS_ON → entity:project:nous
      - WORKS_ON → nous          (slug，自动解析)
      - WORKS_ON: entity:project:nous

    返回 Relation 列表。
    """
    relations: list[Relation] = []
    in_section = False
    now = time.time()

    for line in body.splitlines():
        heading = line.strip()

        # 进入 "## 关系" 段落
        if re.match(r"^##\s*关系", heading):
            in_section = True
            continue

        # 遇到下一个 ## 标题，退出
        if in_section and re.match(r"^##\s+", heading) and not re.match(r"^##\s*关系", heading):
            break

        if not in_section:
            continue

        m = _REL_PATTERN.match(line)
        if not m:
            continue

        rtype = m.group(1).strip().upper()
        target_raw = m.group(2).strip()

        # 去掉行内注释 (role: xxx)
        # 格式可能是：entity:person:dongcheng (role: mentor)
        target_raw = target_raw.split("(")[0].strip()

        # 如果 target 已经是完整 entity ID
        if target_raw.startswith("entity:"):
            to_id = target_raw
        else:
            # 尝试从 slug_to_id map 查找
            slug = _make_slug(target_raw)
            to_id = slug_to_id.get(slug, f"entity:unknown:{slug}")

        if rtype not in _VALID_RTYPES:
            rtype = "RELATED_TO"

        relations.append(Relation(
            from_id=from_id,
            to_id=to_id,
            rtype=rtype,
            source=source,
            created_at=now,
        ))

    return relations


def _parse_related_field(
    related_raw,
    from_id: str,
    source: str,
    slug_to_id: dict,
) -> list[Relation]:
    """
    将 frontmatter 中的 `related:` 字段转换为 RELATED_TO 关系。

    related 字段格式：
      - 字符串列表：[席涔, 米菈]
      - 单个字符串：席涔
    """
    relations: list[Relation] = []
    now = time.time()

    if related_raw is None:
        return relations

    if isinstance(related_raw, str):
        items = [related_raw]
    elif isinstance(related_raw, list):
        items = related_raw
    else:
        items = []

    for item in items:
        slug = _make_slug(str(item))
        if not slug:
            continue
        to_id = slug_to_id.get(slug, f"entity:unknown:{slug}")
        rtype = _infer_rtype(from_id, to_id)
        relations.append(Relation(
            from_id=from_id,
            to_id=to_id,
            rtype=rtype,
            source=source,
            created_at=now,
        ))

    return relations


# ── 主函数 ───────────────────────────────────────────────────────────────────

def parse_entity_file(
    path: Path,
    slug_to_id: Optional[dict] = None,
) -> tuple[Entity, list[Relation]]:
    """
    解析单个 MD 文件 → (Entity, Relation列表)

    path: MD 文件绝对路径
    slug_to_id: {slug: entity_id} 预构建映射，用于解析关系目标
    """
    if slug_to_id is None:
        slug_to_id = {}

    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)

    etype = fm.get("type", _infer_etype(path))
    # 规范化 etype
    if etype not in {"person", "project", "concept", "event", "resource"}:
        etype = _infer_etype(path)

    slug = path.stem
    entity_id = _make_entity_id(etype, slug)
    source = f"memory/entities/{path.parent.name}/{path.name}"

    # 处理时间戳
    now = time.time()

    def _parse_ts(val) -> float:
        if val is None:
            return now
        if isinstance(val, (int, float)):
            return float(val)
        # YAML 可能解析为 datetime.date 对象
        try:
            import datetime
            if isinstance(val, datetime.date):
                return float(datetime.datetime.combine(val, datetime.time()).timestamp())
        except Exception:
            pass
        return now

    created_at = _parse_ts(fm.get("created_at"))
    updated_at = _parse_ts(fm.get("updated_at", fm.get("created_at")))

    # Entity.properties: frontmatter 中除了系统字段之外的所有内容
    _system_keys = {"type", "created_at", "updated_at", "related", "source"}
    props = {k: v for k, v in fm.items() if k not in _system_keys}

    # 提取标题作为 name（MD 中第一行 # 标题）
    name = None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip()
            break

    if name:
        props.setdefault("name", name)
    else:
        props.setdefault("name", slug)

    entity = Entity(
        id=entity_id,
        etype=etype,
        labels=[etype],
        properties=props,
        metadata={"file_path": str(path), "fm_source": fm.get("source", "")},
        confidence=1.0,
        source=source,
        created_at=created_at,
        updated_at=updated_at,
    )

    # 解析关系
    relations: list[Relation] = []

    # 1. 来自 frontmatter related 字段
    relations.extend(
        _parse_related_field(fm.get("related"), entity_id, source, slug_to_id)
    )

    # 2. 来自 "## 关系" 段落
    relations.extend(
        _parse_relations_section(body, entity_id, source, slug_to_id)
    )

    return entity, relations


def build_slug_to_id_map(root: Path) -> dict[str, str]:
    """
    预扫描目录，构建 {slug: entity_id} 映射。
    用于关系解析时的目标 ID 解析。
    """
    mapping: dict[str, str] = {}
    for md_file in root.rglob("*.md"):
        if md_file.stem in _SKIP_STEMS:
            continue
        etype = _infer_etype(md_file)
        slug = md_file.stem
        entity_id = _make_entity_id(etype, slug)
        mapping[slug] = entity_id
    return mapping


def scan_entities_dir(root: Path) -> list[tuple[Entity, list[Relation]]]:
    """
    递归扫描 entities/ 目录，解析所有 MD 文件。

    返回 [(Entity, [Relation]), ...] 列表。
    """
    # 预构建 slug → entity_id 映射
    slug_to_id = build_slug_to_id_map(root)

    results: list[tuple[Entity, list[Relation]]] = []
    errors: list[str] = []

    for md_file in sorted(root.rglob("*.md")):
        if md_file.stem in _SKIP_STEMS:
            continue
        try:
            entity, relations = parse_entity_file(md_file, slug_to_id)
            results.append((entity, relations))
        except Exception as e:
            errors.append(f"SKIP {md_file}: {e}")

    if errors:
        import sys
        for err in errors:
            print(f"[parser] {err}", file=sys.stderr)

    return results
