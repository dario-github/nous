import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))  # allow `from _paths import ...`

from _paths import NOUS_WORKSPACE, ENTITIES_ROOT  # noqa: F401 — re-export
