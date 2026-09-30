"""Stage 1e: filled DK abbreviations (John's ruling, 2026-09-29).

Inside a source passage DK often abbreviates a quotation of words it prints
in full elsewhere as "FIRST ... LAST" -- a printing economy, not the quoting
author's own cut. The site fills in the words between, drawn from DK's own
full text (the fragment's lines). Only cases a survey marked CERTAIN (the
quoting author quotes the whole run) are filled.

The locator file, sources/dk-abbreviations/fills.json, holds NO Greek -- only
where each abbreviation is and where its full text is:

  {"work", "column", "role", "n",   -- the source line (n + role are unique
                                       within a column)
   "at",                              -- char offset of the "..." in that line
   "left", "right",                   -- how many Greek words DK prints before
                                       and after the "..." (a word run may
                                       start on an earlier line of the column)
   "target": {"work", "column", "role",
              "from", "after",        -- the line (by n) and word index of the
                                         target word the FIRST run ends on
              "to", "before"}}        -- the line and word index of the
                                         target word the LAST run starts on

At build time the fill is the target's text strictly between those two words
(the lines between them, of the target's role, included; verse lines joined
with " / "). Word indices count Greek words as `words()` splits a line. The
two anchor words are checked against DK's printed last FIRST word and first
LAST word, ignoring accents, breathing, case, iota subscript/adscript, final
sigma, editorial brackets and elision (a short printed word cut with "." --
"π." for πυκνὸν -- matches any word it begins); a "says" word the quoting
author inserts ("φησίν") is not counted as printed. The anchors are stored,
not searched for, because a printed word can recur in the target (Critias
B25 opens with "ἦν" twice; Protagoras B1 ends two clauses with "ἔστιν"). Any
locator that no longer matches the text -- no "..." at `at`, a missing or
doubled line, an anchor word that does not match -- fails the build.

Output: build/stage1/dk_fills.json, {"work", "fills": {segment id: {line
index: [fill]}}}, each fill {start, end, text, kind, abbrev}: `start`/`end` span the "..." itself in
the line's text (the line text is never changed -- search, tokens and the DK
structure gate all read it); `text` is the supplied words (verse lines joined
with " / "); `kind` is "verse" or "prose"; `abbrev` is DK's printed "FIRST
... LAST" for the reader's hover note. stage7_emit attaches each list to its
line as `fills`. A work with no locators gets no file and no key.

A target in another work (a testimonium quoting a fragment) is read by
parsing that work's own Greek (stage1_greek.parse_spine, no writes).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .config import BUILD_DIR, SOURCES_DIR, Manifest

LOCATORS_PATH = SOURCES_DIR / "dk-abbreviations" / "fills.json"
MARK = "..."

_ELISION = "'ʼ᾽"
_GREEK = re.compile("[\u0370-\u03FF\u1F00-\u1FFF]")
_WORD = re.compile(r"[^\s.…—]+(?:\.(?!\.\.)[^\s.…—]+)*")
_BRACKETS = re.compile(r"[<>\[\]()†*⟨⟩{}]")
_SAYS = {"φησι", "φησιν", "φασι", "φασιν", "εφη"}


class DkFillError(ValueError):
    """A locator no longer matches the text."""


def _is_letter(c: str) -> bool:
    return unicodedata.category(c)[0] in "LM"


def words(text: str) -> List[Tuple[str, int, int]]:
    """Greek words in `text` as (word, start, end), punctuation trimmed (a
    trailing elision mark kept)."""
    out = []
    for m in _WORD.finditer(text):
        w, a = m.group(), m.start()
        s, off = w, 0
        while s and not _is_letter(s[0]):
            s, off = s[1:], off + 1
        while s and not _is_letter(s[-1]) and s[-1] not in _ELISION:
            s = s[:-1]
        while len(s) > 1 and s[-1] in _ELISION and not _is_letter(s[-2]):
            s = s[:-1]
        if s and _GREEK.search(s):
            out.append((s, a + off, a + off + len(s)))
    return out


def norm(word: str) -> Tuple[str, bool]:
    """(bare lower-case letters, elided?)."""
    w = unicodedata.normalize("NFD", _BRACKETS.sub("", word)).replace("\u0345", "ι")
    w = "".join(c for c in w if not unicodedata.combining(c)).lower().replace("ς", "σ")
    elided = w[-1:] in _ELISION
    return w.rstrip(_ELISION), elided


def _printed(text: str, word: Tuple[str, int, int]) -> Tuple[str, object]:
    """A printed word's match key. DK sometimes cuts a word to its first
    letters ("π." for πυκνὸν): a short word followed by a single "." matches
    any word it begins."""
    base, elided = norm(word[0])
    after = text[word[2]:word[2] + 3]
    if after[:1] == "." and after != MARK and len(base) <= 5:
        return base, "prefix"
    return base, elided


def _same(printed: Tuple[str, object], target: Tuple[str, bool]) -> bool:
    x, ex = printed
    y, ey = target
    if ex == "prefix":
        return bool(x) and y.startswith(x)
    if not x or not y:
        return False
    if x == y:
        return True
    if ex and y.startswith(x) and len(y) - len(x) <= 2:
        return True
    if ey and x.startswith(y) and len(x) - len(y) <= 2:
        return True
    return False


def _drop_says(keys: list) -> list:
    kept = [k for k in keys if k[0] not in _SAYS]
    return kept or keys


def _joined(lines: List[dict]) -> Tuple[str, List[int]]:
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line["text"]) + 1
    return " ".join(line["text"] for line in lines), offsets


def _find_line(lines: List[dict], n: int, role: Optional[str], where: str) -> int:
    hits = [i for i, line in enumerate(lines) if line["n"] == n and line.get("role") == role]
    if len(hits) != 1:
        raise DkFillError(f"{where}: {len(hits)} lines with n={n} role={role!r} (want exactly 1)")
    return hits[0]


def printed_words(lines: List[dict], loc: dict) -> Tuple[str, list, list, int]:
    """(DK's printed "FIRST ... LAST", FIRST keys, LAST keys, line index of the
    mark) for a locator, read from the source column's lines."""
    where = f"{loc['work']} {loc['column']} n={loc['n']}"
    li = _find_line(lines, loc["n"], loc.get("role"), where)
    text = lines[li]["text"]
    at = loc["at"]
    if text[at:at + len(MARK)] != MARK:
        raise DkFillError(f"{where}: no '{MARK}' at offset {at} (found {text[at:at + len(MARK)]!r})")
    joined, offsets = _joined(lines)
    mark = offsets[li] + at
    ws = words(joined)
    before = [w for w in ws if w[2] <= mark]
    after = [w for w in ws if w[1] >= mark + len(MARK)]
    k, m = loc["left"], loc["right"]
    if k < 1 or m < 1 or len(before) < k or len(after) < m:
        raise DkFillError(f"{where}: cannot take {k} words before and {m} after the '{MARK}'")
    left, right = before[-k:], after[:m]
    abbrev = joined[left[0][1]:right[-1][2]]
    return (abbrev,
            _drop_says([_printed(joined, w) for w in left]),
            _drop_says([_printed(joined, w) for w in right]),
            li)


def target_run(lines: List[dict], target: dict, where: str) -> List[dict]:
    """The target's lines, in document order, from n=`from` to n=`to`
    (inclusive), keeping only the target's role."""
    a = _find_line(lines, target["from"], target.get("role"), where)
    b = _find_line(lines, target["to"], target.get("role"), where)
    if b < a:
        raise DkFillError(f"{where}: target line {target['to']} precedes {target['from']}")
    return [line for line in lines[a:b + 1] if line.get("role") == target.get("role")]


def gap_text(run: List[dict], target: dict, first: list, last: list, where: str) -> str:
    """The text of `run` strictly between word `after` of its first line and
    word `before` of its last line (verse lines joined with " / "), once
    those two words are checked against DK's printed last FIRST word and
    first LAST word."""
    head = words(run[0]["text"])
    tail = words(run[-1]["text"])
    a, b = target["after"], target["before"]
    if not (0 <= a < len(head)) or not (0 <= b < len(tail)):
        raise DkFillError(f"{where}: anchor word out of range")
    if not _same(first[-1], norm(head[a][0])) or not _same(last[0], norm(tail[b][0])):
        raise DkFillError(f"{where}: the printed words no longer match the target's words "
                          f"{a} and {b}")
    if len(run) == 1:
        if b <= a:
            raise DkFillError(f"{where}: the LAST word precedes the FIRST word")
        return run[0]["text"][head[a][2]:tail[b][1]].strip()
    pieces = [run[0]["text"][head[a][2]:]] + [line["text"] for line in run[1:-1]] + [run[-1]["text"][:tail[b][1]]]
    return " / ".join(p.strip() for p in pieces if p.strip())


def fill_kind(target_manifest_data: dict, target: dict, n_lines: int) -> str:
    """'verse' where the target lines are verse: a verse DK work's numbered
    text lines (citation.lines, outside its prose_columns), or two or more
    lines of verse quoted in a source passage. Otherwise 'prose'."""
    citation = target_manifest_data.get("citation") or {}
    if target.get("role") == "text":
        verse = bool(citation.get("lines")) and target["column"] not in (citation.get("prose_columns") or [])
    else:
        verse = n_lines > 1
    return "verse" if verse else "prose"


def resolve(loc: dict, source_lines: List[dict], target_lines: List[dict],
            target_manifest_data: dict) -> Tuple[int, dict]:
    """(source line index, fill) for one locator."""
    target = loc["target"]
    where = (f"{loc['work']} {loc['column']} n={loc['n']} -> "
             f"{target['work']} {target['column']} {target['from']}-{target['to']}")
    abbrev, first, last, li = printed_words(source_lines, loc)
    run = target_run(target_lines, target, where)
    kind = fill_kind(target_manifest_data, target, len(run))
    if kind == "prose" and len(run) > 1:
        raise DkFillError(f"{where}: a prose target must be one line")
    text = gap_text(run, target, first, last, where)
    if not text:
        raise DkFillError(f"{where}: nothing between the printed words")
    return li, {"start": loc["at"], "end": loc["at"] + len(MARK), "text": text,
                "kind": kind, "abbrev": abbrev}


def load_locators(path: Path = LOCATORS_PATH) -> List[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["fills"]


def _default_spine_for(work: str) -> Tuple[dict, dict]:
    from . import stage1_greek

    manifest = Manifest.for_work(work)
    xml_path = stage1_greek.run_export(manifest)
    return stage1_greek.parse_spine(xml_path, manifest), manifest.data


def build(manifest: Manifest, spine: dict, locators: List[dict],
          spine_for: Callable[[str], Tuple[dict, dict]] = _default_spine_for) -> Dict[str, Dict[str, list]]:
    """{segment id: {line index: [fill]}} for this work's locators."""
    mine = [loc for loc in locators if loc["work"] == manifest.work_id]
    if not mine:
        return {}
    others: Dict[str, Tuple[dict, dict]] = {}

    def segs_of(work: str) -> Tuple[Dict[str, dict], dict]:
        if work == manifest.work_id:
            sp, data = spine, manifest.data
        else:
            if work not in others:
                others[work] = spine_for(work)
            sp, data = others[work]
        return {seg["column"]: seg for seg in sp["segments"]}, data

    out: Dict[str, Dict[str, list]] = {}
    for loc in mine:
        src_segs, _ = segs_of(loc["work"])
        tgt_segs, tgt_data = segs_of(loc["target"]["work"])
        src = src_segs.get(loc["column"])
        tgt = tgt_segs.get(loc["target"]["column"])
        if src is None or tgt is None:
            raise DkFillError(f"{loc['work']} {loc['column']} -> {loc['target']['work']} "
                              f"{loc['target']['column']}: column not found")
        li, fill = resolve(loc, src["lines"], tgt["lines"], tgt_data)
        out.setdefault(src["id"], {}).setdefault(str(li), []).append(fill)
    for by_line in out.values():
        for fills in by_line.values():
            fills.sort(key=lambda f: f["start"])
    return out


def run(manifest: Manifest, spine: dict) -> Optional[Path]:
    fills = build(manifest, spine, load_locators())
    if not fills:
        return None
    n = sum(len(f) for by_line in fills.values() for f in by_line.values())
    print(f"  dk_fills: {n} abbreviations filled in {len(fills)} columns")
    out_path = BUILD_DIR / "stage1" / "dk_fills.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"work": manifest.work_id, "fills": fills}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    return out_path
