"""Regression tests for tools/extract_haines_wikisource.py's HTML parsing.

No network: these exercise `_parse_book` on minimal synthetic HTML replicating
the exact structures Wikisource's rendered ProofreadPage output uses. The
verse-join case reproduces a real defect found in the Book 7 output (7.38
"things,For", 7.40 "corn,And", 7.41 "spurned,For", 7.44 "]:I might"):
lxml's text_content() joins text across a `<br/>` (and the empty inline-block
`wst-gap` spacer span Wikisource sets verse indents with) with NO whitespace,
gluing the last word of one verse line onto the first word of the next.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# tools/ is not a package; load the module directly by path.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
_spec = importlib.util.spec_from_file_location(
    "extract_haines_wikisource", _TOOLS / "extract_haines_wikisource.py")
_mod = importlib.util.module_from_spec(_spec)
sys.modules["extract_haines_wikisource"] = _mod
_spec.loader.exec_module(_mod)


def _wrap(body: str) -> str:
    """Minimal fetched-HTML shape: the prp-pages-output body div followed by
    the Footnotes heading marker `_isolate_body` cuts at."""
    return (
        '<div class="mw-parser-output">'
        '<div class="prp-pages-output" lang="en">'
        + body +
        '</div>'
        '<div class="mw-heading mw-heading2"><h2 id="Footnotes">Footnotes</h2></div>'
        '</div>'
    )


def test_br_and_gap_span_verse_join_keeps_word_boundary():
    # Replicates 7.38's exact structure: two verse lines inside one <p>,
    # separated by <br/> + an EMPTY inline-block wst-gap spacer span.
    html = _wrap(
        '<p>1. Chapter one opens.</p>'
        '<p>2. <i>It nought availeth to be wroth with things,</i><br />'
        '<span class="wst-gap __gap" style="display:inline-block; inline-size:2em"></span>'
        '<i>For they reck not of it.</i></p>'
    )
    out = _mod._parse_book(7, html)
    assert out["7.2"] == (
        "It nought availeth to be wroth with things, For they reck not of it."
    )


def test_bare_br_join_keeps_word_boundary():
    # 7.44's structure: text, <br/>, then the quoted passage -- no gap span.
    html = _wrap(
        '<p>1. Chapter one opens.</p>'
        '<p>2. [Citations from Plato]:<br /><i>I might fairly answer.</i></p>'
    )
    out = _mod._parse_book(7, html)
    assert out["7.2"] == "[Citations from Plato]: I might fairly answer."
