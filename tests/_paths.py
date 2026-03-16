"""Shared path constants for Nous tests."""
import os
from pathlib import Path


def _detect_clawd_root() -> Path:
    """Detect clawd workspace root. Checks CLAWD_ROOT env, then parent heuristic."""
    env = os.environ.get("CLAWD_ROOT")
    if env:
        return Path(env).resolve()
    # nous/ is typically inside clawd/
    candidate = Path(__file__).parent.parent.parent
    if (candidate / "memory" / "entities").exists():
        return candidate
    return Path("/home/yan/clawd")  # fallback


CLAWD_ROOT = _detect_clawd_root()
ENTITIES_ROOT = CLAWD_ROOT / "memory" / "entities"
