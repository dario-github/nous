"""AgentHarm — Dataset Loader (ICLR 2025)

从 HuggingFace Hub 加载 AgentHarm 数据集，缓存到本地 nous/data/agentharm/。

数据集：ai-safety-institute/AgentHarm
  - config "harmful":         176 harmful test cases
  - config "harmless_benign": 176 benign test cases

每个 example 字段：
  id:               场景唯一标识符
  prompt:           用户对 Agent 的指令
  target_functions: list[str]，期望 Agent 调用的函数名
  category:         危害类别（如 "Cyberattack", "Fraud" 等）
  name:             场景名称
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 本地缓存目录（相对于 nous 项目根）
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # nous/
_CACHE_DIR = _PROJECT_ROOT / "data" / "agentharm"

# HuggingFace 数据集名称和配置
_HF_DATASET = "ai-safety-institute/AgentHarm"
_CONFIG_HARMFUL = "harmful"
_CONFIG_BENIGN = "harmless_benign"
_SPLIT = "test_public"


def _normalize_example(raw: dict) -> dict:
    """将 HuggingFace 原始 example 标准化为 Nous 内部格式。"""
    # target_functions 可能是 list 或逗号分隔的 string
    raw_funcs = raw.get("target_functions", [])
    if isinstance(raw_funcs, str):
        target_functions = [f.strip() for f in raw_funcs.split(",") if f.strip()]
    else:
        target_functions = list(raw_funcs)

    return {
        "id": str(raw.get("id", raw.get("behavior_id", ""))),
        "prompt": str(raw.get("prompt", raw.get("user_prompt", ""))),
        "target_functions": target_functions,
        "category": str(raw.get("category", raw.get("harm_category", "unknown"))),
        "name": str(raw.get("name", raw.get("behavior_name", ""))),
    }


def _load_from_cache(config: str) -> Optional[list[dict]]:
    """从本地缓存加载，返回 None 表示缓存不存在。"""
    cache_file = _CACHE_DIR / f"{config}.json"
    if not cache_file.exists():
        return None
    try:
        with cache_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded %d examples from cache: %s", len(data), cache_file)
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Cache read failed (%s), will re-download: %s", cache_file, e)
        return None


def _save_to_cache(config: str, data: list[dict]) -> None:
    """将数据写入本地缓存。"""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CACHE_DIR / f"{config}.json"
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug("Saved %d examples to cache: %s", len(data), cache_file)


def _load_from_hf(config: str) -> list[dict]:
    """从 HuggingFace Hub 下载数据集并标准化。"""
    try:
        from datasets import load_dataset
    except ImportError as e:
        raise ImportError(
            "datasets library is required. Install with: pip install datasets"
        ) from e

    logger.info("Downloading AgentHarm dataset (config=%s) from HuggingFace...", config)
    ds = load_dataset(_HF_DATASET, config, split=_SPLIT, trust_remote_code=False)
    data = [_normalize_example(dict(row)) for row in ds]
    logger.info("Loaded %d examples for config=%s", len(data), config)
    return data


def _load(config: str, use_cache: bool = True) -> list[dict]:
    """通用加载函数：优先本地缓存，缓存缺失时下载。"""
    if use_cache:
        cached = _load_from_cache(config)
        if cached is not None:
            return cached

    data = _load_from_hf(config)

    if use_cache:
        _save_to_cache(config, data)

    return data


def load_harmful(use_cache: bool = True) -> list[dict]:
    """加载 176 个 harmful test cases。

    Returns:
        list[dict]，每个 dict 包含：
            id:               场景 ID
            prompt:           用户指令
            target_functions: list[str]，目标函数名
            category:         危害类别
            name:             场景名称
    """
    return _load(_CONFIG_HARMFUL, use_cache=use_cache)


def load_benign(use_cache: bool = True) -> list[dict]:
    """加载 176 个 benign test cases。

    Returns:
        list[dict]，每个 dict 包含：
            id:               场景 ID
            prompt:           用户指令
            target_functions: list[str]，目标函数名
            category:         危害类别
            name:             场景名称
    """
    return _load(_CONFIG_BENIGN, use_cache=use_cache)
