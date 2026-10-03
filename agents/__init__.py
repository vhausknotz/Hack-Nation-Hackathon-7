"""Internal agents that contribute to the ledger exactly like outside contributors would.

Each agent has its own signing identity and manifest (model, tools, prompt versions). Every claim
goes through the kernel; every review is an attested event. See PLAN.md section 6.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "pipeline"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
