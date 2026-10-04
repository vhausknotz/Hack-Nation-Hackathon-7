"""Read an organization page the way the kernel will see it, to choose a decision-carrying quote.

    python -m agents.community_coverage.probe <url> <term> [<term> ...]

Archives into the staging root (never the production ledger) and prints canonical-text lines that contain any
term, with their offsets, plus the redirect history. Discovery aid only: a printed line is not yet a candidate.
"""

import json
import re
import sys

from ledger import sources

from .fetch import fetch_and_archive
from .stage import ARCHIVE


def main(url: str, terms: list[str]) -> None:
    got = fetch_and_archive(url, ARCHIVE)
    print(json.dumps({k: v for k, v in got.to_dict().items() if k != "source"}, indent=1))
    if not got.ok:
        return
    text = sources.read_text(got.source, root=ARCHIVE) or ""
    print(f"title: {got.source['title']!r}  chars: {len(text)}  source: {got.source['source_id']}")
    pattern = re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE) if terms else None
    pos = 0
    for line in text.split("\n"):
        if line.strip() and (pattern is None or pattern.search(line)):
            print(f"[{pos}:{pos + len(line)}] {line[:600]}")
        pos += len(line) + 1


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
