from __future__ import annotations

import json
from pathlib import Path
import sys

from howtobot.inbound_triage import InMemoryLedger, REQUIRED_SCOPE, triage_batch


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run.py <events.json>", file=sys.stderr)
        return 2
    events = json.loads(Path(sys.argv[1]).read_text())
    results = triage_batch(events, granted_scopes={REQUIRED_SCOPE}, ledger=InMemoryLedger())
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
