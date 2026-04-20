"""LSVJ-S — Primitive Schema (M0)

原语词汇表：Pydantic v2 模型 + YAML 加载器。
三类原语：
  A: 纯 KG 关系查询（Cozo Datalog）
  B: 确定性字符串/正则/污点检测（host function）
  C: 密封 LLM 子预言机（M0 中用确定性存根）
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class PrimitiveClass(str, Enum):
    """原语分类：决定运行时评估机制。"""
    A = "A"  # KG 关系查询
    B = "B"  # 确定性 host function
    C = "C"  # 密封 LLM 子预言机


class Primitive(BaseModel):
    """单条原语声明。"""
    id: str
    # 字段名 class 是 Python 关键字，用 prim_class + alias 处理
    prim_class: PrimitiveClass = Field(alias="class")
    arity: int
    arg_types: list[str]
    description: str
    evaluator: str
    mock_for_m0: bool = False

    model_config = {"populate_by_name": True}


class PrimitiveSchema(BaseModel):
    """原语词汇表容器，提供查找辅助方法。"""
    primitives: list[Primitive]

    def by_id(self, prim_id: str) -> Optional[Primitive]:
        """按 id 查找原语，找不到返回 None。"""
        for p in self.primitives:
            if p.id == prim_id:
                return p
        return None

    def by_class(self, cls: PrimitiveClass) -> list[Primitive]:
        """返回指定类别的所有原语。"""
        return [p for p in self.primitives if p.prim_class == cls]

    def ids(self) -> list[str]:
        """返回所有原语 id 列表。"""
        return [p.id for p in self.primitives]


class Obligation(BaseModel):
    """合成义务：LLM 提议的 per-decision 规则体 + 裁决方向。

    rule_body: Datalog 规则体表达式字符串，例如
        "is_inner_circle(recipient_id), owner_has_directed(action_id),
         discharged = not is_inner_circle(recipient_id) or owner_has_directed(action_id)"
    decision: 裁决方向 allow/confirm/block
    """
    rule_body: str
    decision: str = Field(pattern="^(allow|confirm|block)$")


def load_schema_from_yaml(path: str) -> PrimitiveSchema:
    """从 YAML 文件加载 PrimitiveSchema。

    YAML 结构：
      primitives:
        - id: ...
          class: A|B|C
          arity: int
          arg_types: [...]
          description: ...
          evaluator: ...
          mock_for_m0: bool  # 可选

    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: YAML 解析失败
        pydantic.ValidationError: schema 结构不符合模型
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PrimitiveSchema.model_validate(data)
