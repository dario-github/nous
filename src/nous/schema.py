"""Nous — Pydantic v2 数据模型
M0 冻结版本，metadata 字段预留 1.1 扩展
"""
from pydantic import BaseModel
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
