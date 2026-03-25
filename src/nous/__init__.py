"""Nous — 本体论驱动的 Agent 决策引擎"""
__version__ = "0.0.1"

_db = None

def init(path: str = "nous.db"):
    from nous.db import NousDB
    global _db
    _db = NousDB(path)
    return _db

def get_db():
    if _db is None:
        raise RuntimeError("nous.init() not called")
    return _db

def query(datalog: str) -> list[dict]:
    return get_db().query(datalog)
