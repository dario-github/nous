"""Shared path constants for Nous tests."""
import os
from pathlib import Path


def _detect_workspace_root() -> Path:
    """Detect nous workspace root. Checks NOUS_WORKSPACE env, then parent heuristic."""
    env = os.environ.get("NOUS_WORKSPACE")
    if env:
        return Path(env).resolve()
    # nous/ is typically inside nous/
    candidate = Path(__file__).parent.parent.parent
    if (candidate / "memory" / "entities").exists():
        return candidate
    return Path(".")  # fallback


NOUS_WORKSPACE = _detect_workspace_root()
ENTITIES_ROOT = NOUS_WORKSPACE / "memory" / "entities"
