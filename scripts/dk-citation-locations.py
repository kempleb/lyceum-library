"""Read-only adapter for the structure gate; uses the pipeline's own matcher.

This does not run pipeline stages or write data. JSON in/out keeps source text
out of command arguments and diagnostics.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from reader_pipeline.stage1_citation_expansion import (
    _load_dictionary, _load_adjudications, _DK_CROSS_REFERENCE, resolve_located_segments, citation_starts,
)

dictionary = _load_dictionary()
payload = json.load(sys.stdin)
by_work = {}
for record in payload["segments"]:
    by_work.setdefault(record["work"], []).append(record["seg"])
rulings = _load_adjudications()
resolved = {work: resolve_located_segments(dictionary, segments, work, rulings.get(work, {}))
            for work, segments in by_work.items()}
json.dump({
    "heads": [[{k: v for k, v in h.items() if k != "expanded"}
               for h in resolved[r["work"]][r["seg"]["id"]]] for r in payload["segments"]],
    "paragraphHits": [citation_starts(dictionary, text) for text in payload["paragraphs"]],
    "crossReferences": [bool(_DK_CROSS_REFERENCE.fullmatch(text)) for text in payload["expansions"]],
}, sys.stdout, ensure_ascii=False)
