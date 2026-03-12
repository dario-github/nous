"""Nous — Pydantic v2 数据模型
M0 冻结版本，metadata 字段预留 1.1 扩展
M2.1 新增：Constraint 模型
"""
from pydantic import BaseModel, Field
from typing import Optional
import time


class Entity(BaseModel):
    """知识图谱实体节点"""
    id: str              # entity:{type}:{slug}
    etype: str           # person/project/concept/event/resource
    labels: list[str] = []
    properties: dict = {}
    metadata: dict = {}
    confidence: float = 1.0
    source: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0

    def __init__(self, **data):
        if 'created_at' not in data or data['created_at'] == 0.0:
            data['created_at'] = time.time()
        if 'updated_at' not in data or data['updated_at'] == 0.0:
            data['updated_at'] = data.get('created_at', time.time())
        super().__init__(**data)


class Relation(BaseModel):
    """知识图谱有向关系边"""
    from_id: str
    to_id: str
    rtype: str           # WORKS_ON/KNOWS/DEPENDS_ON 等
    properties: dict = {}
    confidence: float = 1.0
    source: str = ""
    created_at: float = 0.0

    def __init__(self, **data):
        if 'created_at' not in data or data['created_at'] == 0.0:
            data['created_at'] = time.time()
        super().__init__(**data)


class Constraint(BaseModel):
    """
    决策图谱约束规则（M2.1）。
    对应 ontology/constraints/*.yaml 每一条规则。
    """
    id: str                              # T3 / T5 / T10 / T11 / T12
    name: str = ""                       # 可读名称
    priority: int = 50                   # 越小越高，block 默认 100
    enabled: bool = True
    trigger: dict = Field(default_factory=dict)   # 触发条件字典
    verdict: str = "block"               # block/confirm/warn/rewrite/require/delegate
    reason: str = ""                     # 触发原因描述
    rewrite_params: Optional[dict] = None  # T11 之类的重写参数
    metadata: dict = Field(default_factory=dict)
    created_at: float = 0.0

    def __init__(self, **data):
        if 'created_at' not in data or data['created_at'] == 0.0:
            data['created_at'] = time.time()
        super().__init__(**data)
