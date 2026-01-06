from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the import path when tests are run from the repo root.
PROJECT_SRC: Path = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))
