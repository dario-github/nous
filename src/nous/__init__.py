"""Nous — 本体论驱动的 Agent 决策引擎"""
__version__ = "0.0.1"

from nous.db import NousDB
from nous.gap_detector import GapPattern, detect_gaps
from nous.outcome import OutcomeType, backfill_outcome, get_pending_outcomes
from nous.rule_proposer import propose_rule_fix, save_proposal
from nous.ttl import TTLAlert, check_rule_ttl

_db: NousDB | None = None


def init(path: str = "nous.db"):
    """初始化模块级数据库实例。path=':memory:' 用于测试。"""
    global _db
    _db = NousDB(path)
    return _db


def get_db() -> NousDB:
    """获取已初始化的 DB 实例；未调用 init() 则抛出 RuntimeError。"""
    if _db is None:
        raise RuntimeError("nous.init() not called")
    return _db


def query(datalog: str) -> list[dict]:
    """执行 Datalog 查询，返回 list[dict]。"""
    return get_db().query(datalog)
