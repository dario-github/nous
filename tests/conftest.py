import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))  # allow `from _paths import ...`

from _paths import CLAWD_ROOT, ENTITIES_ROOT  # noqa: F401 — re-export
