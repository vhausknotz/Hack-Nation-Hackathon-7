"""The claims ledger: an append-only, signed, Merkle-logged record of every claim, review and challenge.

Nothing writes the graph directly. Contributions become claims here; the kernel (ledger/kernel.py)
checks them mechanically; reviews and challenges are attested events; trust policies
(ledger/policy.py) decide what each view shows; the graph is a projection of accepted claims.
See PLAN.md sections 1-5.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_DIR = ROOT / "data" / "ledger"
