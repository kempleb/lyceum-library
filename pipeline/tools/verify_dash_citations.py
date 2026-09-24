"""Verify expanded Diels-Kranz dash citations against the source author's own
text in the TLG (Greek) or PHI (Latin).

John's ruling, 2026-09-24: before an expanded DK dash citation goes live, check
it against the source text. DK prints a run of citations from one source with
dashes ("— —40"); the expansion stage turns each dash into a full reading
("STOB. II 15, 40"). This tool takes those readings, finds the fragment's own
Greek or Latin in the source author's text, and says whether it stands at the
locus the reading names.

    uv run python pipeline/tools/verify_dash_citations.py \\
        --readings build/dash-verify/survey.json \\
        --spines build/dk-spines \\
        --out-dir <dir>                 # verdicts.json + summary.md

Options: --reading-field (default "resolved") names the field that holds the
reading, so a later stage's output can be fed in unchanged; --overrides takes a
JSON map {"<work>:<segment>": "<reading>"} (or {"<work>:<segment>:<head>": ...}
when one segment has several dashes) that replaces the reading for those
records; --classes limits which survey classifications are checked.

Method per reading
  1. The source author's spec (SOURCES below) maps the reading to a TLG/PHI
     author, the work(s) to search and the expected locus, as named citation
     levels in that text's own scheme, e.g. Stobaeus [(book,2),(chapter,15),
     (section,40)], Simplicius in Phys. [(page,155),(line,30)].
  2. The passage DK prints after the dash is cut out of the DK spine and
     normalised (accents, breathings, case and punctuation dropped; iota
     subscript written as iota, to meet DK's adscript; final sigma folded).
  3. Overlapping 20-letter probes (about four words) are searched in the
     work's normalised letter stream; each hit carries the TLG citation where
     it starts.
  4. Verdict: CONFIRMED when enough probes hit at the expected locus (a
     neighbouring line within LINE_TOL counts, for a quotation DK cites from
     its first line); MISMATCH when they hit elsewhere; NOT-FOUND when no
     probe hits; NOT-IN-CORPUS and SCHEME-UNMAPPED come from the spec.

Corpus text is read at run time from a Diogenes XML export (made on demand
into --cache, which should sit under the gitignored build/). The outputs carry
loci, work titles and DK's own citation heads only, never corpus text.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import pickle
import re
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

REPO = Path(__file__).resolve().parents[2]
TEI = "{http://www.tei-c.org/ns/1.0}"
CORPUS_ROOT = Path(
    os.environ.get(
        "TLG_FILES_ROOT",
        "/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT/TLG Files",
    )
)
DIOGENES = Path("/Applications/Diogenes.app/Contents")

PROBE_LEN = 20  # letters per probe (about four Greek words)
PROBE_STEP = 5
MAX_PROBES = 80
LINE_TOL = 2  # a line-level locus may be off by this many lines
SHORT_LEN, SHORT_STEP = 12, 3  # second pass when 20-letter probes miss
SHORT_MISMATCH = 4  # short probes needed before a mismatch is claimed
WORD_PASS_MAX = 40  # letters: passages this short also get whole-word probes
VERDICTS = ("CONFIRMED", "CONFIRMED-PARTIAL", "WEAK", "MISMATCH", "NOT-FOUND",
            "NOT-IN-CORPUS", "SCHEME-UNMAPPED", "NOT-CHECKED")

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_GREEK_FOLD = {"ς": "σ", "ϲ": "σ", "ϑ": "θ", "ϕ": "φ", "ϐ": "β", "ϰ": "κ",
               "ϱ": "ρ", "ϖ": "π", "ϝ": "", "ϛ": "στ"}


def norm_greek(text: str) -> str:
    """Letters only, lower case, no accents or breathings; iota subscript (and
    prosgegrammeni) becomes a plain iota so TLG 'ῳ' meets DK's adscript 'ωι'.
    Elision marks and all punctuation vanish with the non-letters."""
    out = []
    for ch in unicodedata.normalize("NFD", text):
        if ch == "\u0345":  # combining ypogegrammeni
            out.append("ι")
            continue
        if unicodedata.combining(ch):
            continue
        ch = ch.lower()
        ch = _GREEK_FOLD.get(ch, ch)
        for c in ch:
            if "α" <= c <= "ω":
                out.append(c)
    return "".join(out)


def norm_latin(text: str) -> str:
    """Letters only, lower case, u/v and i/j merged."""
    s = unicodedata.normalize("NFD", text)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("v", "u").replace("j", "i")
    return re.sub(r"[^a-z]", "", s)


def normaliser(lang: str) -> Callable[[str], str]:
    return norm_latin if lang == "lat" else norm_greek


def word_probes(text: str, lang: str, min_len: int = 6) -> list[str]:
    """Distinct normalised words of at least `min_len` letters."""
    norm = normaliser(lang)
    out = []
    for w in text.split():
        n = norm(w)
        if len(n) >= min_len and n not in out:
            out.append(n)
    return out


class Probe(str):
    """A probe that knows which letters of the passage it covers
    ([start, end) in the normalised stream), so that two probes sharing
    letters are not counted as two pieces of evidence (review item 9).
    A plain str probe (a whole word) counts as independent."""

    start: int
    end: int

    def __new__(cls, text: str, start: int):
        p = super().__new__(cls, text)
        p.start, p.end = start, start + len(text)
        return p


def independent(probes: list[str], indices: set[int]) -> int:
    """How many of the probes at `indices` cover letters no other chosen
    probe covers: the most probes with pairwise disjoint spans (earliest
    end first). Probes without a span each count once."""
    spans = sorted((probes[i].end, probes[i].start) for i in indices
                   if isinstance(probes[i], Probe))
    n = sum(1 for i in indices if not isinstance(probes[i], Probe))
    last_end = -1
    for end, start in spans:
        if start >= last_end:
            n += 1
            last_end = end
    return n


def make_probes(norm: str, length: int = PROBE_LEN, step: int = PROBE_STEP,
                cap: int = MAX_PROBES) -> list[str]:
    """Overlapping fixed-length probes over a normalised letter stream. A text
    shorter than one probe is its own single probe (if at least 8 letters)."""
    if len(norm) < length:
        return [Probe(norm, 0)] if len(norm) >= 8 else []
    starts = list(range(0, len(norm) - length + 1, step))
    if starts[-1] != len(norm) - length:
        starts.append(len(norm) - length)
    if len(starts) > cap:  # spread the cap evenly over the passage
        idx = [round(i * (len(starts) - 1) / (cap - 1)) for i in range(cap)]
        starts = [starts[i] for i in sorted(set(idx))]
    seen, probes = set(), []
    for s in starts:
        p = norm[s:s + length]
        if p not in seen:
            seen.add(p)
            probes.append(Probe(p, s))
    return probes


# ---------------------------------------------------------------------------
# Loci
# ---------------------------------------------------------------------------

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def roman_to_int(s: str) -> Optional[int]:
    s = s.upper()
    if not s or any(c not in ROMAN for c in s):
        return None
    total, prev = 0, 0
    for c in reversed(s):
        v = ROMAN[c]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


GREEK_NUM = {"α": 1, "β": 2, "γ": 3, "δ": 4, "ε": 5, "ϛ": 6, "ϝ": 6, "ζ": 7,
             "η": 8, "θ": 9, "ι": 10, "κ": 20, "λ": 30, "μ": 40, "ν": 50}


def greek_numeral(s: str) -> Optional[int]:
    """'κβʹ' -> 22. None when s is not a Greek numeral."""
    s = s.strip().rstrip("\u0374\u02b9\u0384'").lower()
    if not s or any(c not in GREEK_NUM for c in s):
        return None
    return sum(GREEK_NUM[c] for c in s)


def split_num(v: str) -> tuple[Optional[int], str]:
    """'48a' -> (48, 'a'); 'p' -> (None, 'p')."""
    m = re.fullmatch(r"(\d+)(.*)", str(v).strip())
    if not m:
        return None, str(v).strip().lower()
    return int(m.group(1)), m.group(2).strip().lower()


def same_value(found: Optional[str], want: str) -> tuple[bool, str]:
    """Exact match, or same number with a letter suffix on one side only
    (TLG 'IV 48a' against DK '48'). Returns (match, note)."""
    if found is None:
        return False, ""
    f, w = str(found).strip().lower(), str(want).strip().lower()
    if f == w:
        return True, ""
    fn, fs = split_num(f)
    wn, ws = split_num(w)
    if fn is not None and fn == wn and (not fs or not ws):
        return True, f"TLG labels it {found}, reading has {want}"
    return False, ""


def within(found: Optional[str], want: str, tol: int) -> bool:
    fn, _ = split_num(found or "")
    wn, _ = split_num(want)
    if fn is None or wn is None:
        return False
    return abs(fn - wn) <= tol


LETTERS = "abcdefg"


def letter_near(found: Optional[str], want: str) -> bool:
    """Stephanus section letters: equal or neighbouring (B vs C)."""
    if not found:
        return False
    f, w = found.strip().lower(), want.strip().lower()
    if f not in LETTERS or w not in LETTERS:
        return f == w
    return abs(LETTERS.index(f) - LETTERS.index(w)) <= 1


@dataclass
class Locus:
    """Expected locus: ordered (level, value) pairs in the TLG/PHI scheme.
    A reading naming two places ('24. 25') becomes two Locus objects."""

    levels: list[tuple[str, str]]
    works: Optional[list[str]] = None  # work numbers ('001'); None = all
    fine: str = "exact"  # how to compare the finest level: exact | line | letter
    label: str = ""
    author: Optional[str] = None  # overrides the spec's author (Iambl. in Stob.)
    # None: `levels` is the whole citation. Otherwise: DK's printed reading
    # names a finer locus than the source's own text exposes to search (e.g.
    # Aëtius: book + chapter from the Placita headings, no section) -- these
    # are the level names actually checked; a match becomes CONFIRMED-PARTIAL,
    # never plain CONFIRMED (defect 4).
    checked: Optional[list[str]] = None

    def text(self) -> str:
        return self.label or ", ".join(f"{k} {v}" for k, v in self.levels)


def path_dict(path: tuple) -> dict[str, str]:
    """Citation path -> {lowercased level type: n}. Later levels of the same
    type win (Diogenes nests e.g. 'section' under 'Section' rarely)."""
    return {t.lower(): n for t, n in path}


def next_page(v: str) -> Optional[str]:
    """The page (or Bekker column) after v: '155' -> '156', '409a' -> '409b',
    '409b' -> '410a'."""
    n, suf = split_num(v)
    if n is None:
        return None
    if suf == "a":
        return f"{n}b"
    if suf == "b":
        return f"{n + 1}a"
    return None if suf else str(n + 1)


def match_locus(work: str, path: tuple, locus: Locus) -> tuple[bool, str, bool]:
    """Does one hit (work number, citation path) stand at the expected locus?
    Third element (defect 4): matched only through the +/- adjacency
    allowance (a nearby line/letter, or the passage running on to the next
    page) rather than exactly -- callers surface this as "adjacent": true."""
    if locus.works is not None and work not in locus.works:
        return False, "", False
    d = path_dict(path)
    if locus.fine == "line" and len(locus.levels) >= 2:
        # A passage DK cites from the foot of a page or column may run on
        # to the head of the next: '409a 32' is met by a hit at '409b 1'.
        (plvl, pwant), (llvl, lwant) = locus.levels[-2], locus.levels[-1]
        ln, _ = split_num(d.get(llvl) or "")
        wn, _ = split_num(lwant)
        if (d.get(plvl) is not None and ln is not None and wn is not None
                and d.get(plvl).lower() == (next_page(pwant) or "").lower()
                and ln <= LINE_TOL + 1 and wn >= 25
                and all(same_value(d.get(k), v)[0]
                        for k, v in locus.levels[:-2])):
            return True, f"passage runs on to {plvl} {d.get(plvl)}", True
    notes = []
    adjacent = False
    last = len(locus.levels) - 1
    for i, (lvl, want) in enumerate(locus.levels):
        found = d.get(lvl)
        if i == last and locus.fine == "line":
            if not within(found, want, LINE_TOL):
                return False, "", False
            fn, _ = split_num(found or "")
            wn, _ = split_num(want)
            if fn != wn:
                adjacent = True
            continue
        if i == last and locus.fine == "letter":
            if not letter_near(found, want):
                return False, "", False
            if (found or "").strip().lower() != want.strip().lower():
                adjacent = True
            continue
        ok, note = same_value(found, want)
        if not ok:
            return False, "", False
        if note:
            notes.append(note)
    return True, "; ".join(notes), adjacent


# ---------------------------------------------------------------------------
# Corpus: Diogenes export + normalised index
# ---------------------------------------------------------------------------


@dataclass
class WorkIndex:
    work: str  # '001'
    title: str
    letters: str
    starts: list[int]
    paths: list[tuple]

    def path_at(self, offset: int) -> tuple:
        i = bisect.bisect_right(self.starts, offset) - 1
        return self.paths[max(i, 0)]


def export_author(corpus: str, author: str, cache: Path) -> Path:
    """Diogenes XML export of one author (verse mode, so every edition line
    keeps its number) into cache/<corpus><author>/. Returns the XML dir."""
    out = cache / f"{corpus}{author}"
    xml_dir = out / "Diogenes-Resources" / "xml" / corpus
    done = out / ".export-complete"
    if done.exists():
        return xml_dir
    cfg = cache / "cfg"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "diogenes.prefs").write_text(
        f'tlg_dir "{CORPUS_ROOT / "TLG"}"\nphi_dir "{CORPUS_ROOT / "PHI"}"\n')
    env = {"Diogenes_Config_Dir": str(cfg), "PATH": "/usr/bin:/bin"}
    cmd = ["perl", "-I", str(DIOGENES / "server"), "-I",
           str(DIOGENES / "dependencies" / "CPAN"),
           str(DIOGENES / "server" / "xml-export.pl"),
           "-c", corpus, "-n", author, "-y", "-o", str(out)]
    log = cache / f"{corpus}{author}.log"
    with open(log, "w") as fh:
        subprocess.run(cmd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                       check=True)
    done.write_text("")  # an interrupted export is redone on the next run
    return xml_dir


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def index_xml(path: Path, lang: str, hooks: Optional[Callable] = None
              ) -> WorkIndex:
    """Walk a Diogenes TEI file: every text run is normalised and appended to
    one letter stream, and each run's start offset is tied to its citation
    path ((div type, n) ... plus ('line', n)). `hooks(el, path, state)` may
    return extra synthetic levels (used for the Placita's chapter heads)."""
    norm = normaliser(lang)
    root = ET.parse(path).getroot()
    title_el = root.find(f".//{TEI}title")
    title = (title_el.text or "").strip() if title_el is not None else ""
    body = root.find(f".//{TEI}body")
    letters: list[str] = []
    starts: list[int] = []
    paths: list[tuple] = []
    pos = 0
    state: dict = {}

    def emit(text: Optional[str], p: tuple):
        nonlocal pos
        if not text:
            return
        n = norm(text)
        if not n:
            return
        full = p + tuple(state.get("extra", ()))
        if not paths or paths[-1] != full:
            starts.append(pos)
            paths.append(full)
        letters.append(n)
        pos += len(n)

    def walk(el, p: tuple):
        tag = _local(el.tag)
        if tag == "div":
            p = p + ((el.get("type") or "div", el.get("n") or ""),)
        elif tag == "l":
            p = p + (("line", el.get("n") or ""),)
        if hooks:
            hooks(el, p, state)
        emit(el.text, p)
        for ch in el:
            walk(ch, p)
            emit(ch.tail, p)

    walk(body, ())
    m = re.search(r"(\d{3})\.xml$", path.name)
    return WorkIndex(m.group(1) if m else path.stem, title, "".join(letters),
                     starts, paths)


def placita_hooks(el, path, state):
    """Ps.-Plutarch's Placita (TLG 0094.003) carries Aëtius' book and chapter
    only as text: each book opens with a table of contents (div section
    'pin'), and each chapter with a head like 'κβʹ. Περὶ ...'. Track them as
    synthetic levels 'aet-book' and 'aet-chapter'."""
    tag = _local(el.tag)
    if tag == "div" and el.get("n") == "pin":
        state["book"] = state.get("book", 0) + 1
        state["in_pin"] = True
        state["chapter"] = None
    elif tag == "div" and el.get("type") == "Stephanus-page":
        pass
    elif tag == "div" and el.get("type") == "section" and el.get("n") != "pin":
        state["in_pin"] = False
    if tag == "label":
        txt = "".join(el.itertext()).strip()
        m = re.match(r"^([α-ωϛϝ]+)[\u0374\u02b9\u0384']\.", txt)
        if m and not state.get("in_pin"):
            n = greek_numeral(m.group(1))
            if n:
                state["chapter"] = n
    if state.get("book"):
        extra = [("aet-book", str(state["book"]))]
        if state.get("chapter"):
            extra.append(("aet-chapter", str(state["chapter"])))
        state["extra"] = extra


HOOKS = {("tlg", "0094", "003"): placita_hooks}


# ---------------------------------------------------------------------------
# Lexicon headwords (item 7)
# ---------------------------------------------------------------------------
# A lexicon dash ("—" before a word, in Harpocration, Hesychius, the Suda or
# the Etymologicum) is filled in as "s.v. <headword>", the headword taken
# from DK's passage. The check: is that headword an entry of the lexicon's
# TLG text? The TLG marks entries two ways: a div per entry whose lemma is
# the first spaced (letter-spacing) or lemma-marked run (Hesychius, the Suda,
# the Etymologicum Genuinum), or -- Harpocration, by page and line -- an
# indented line that opens "Lemma: ...".

_LEMMA_HEAD = re.compile(r"^\s*\[?\s*([^:·\[\]]{1,80}?)\s*[:·]")


def _clean_lemma(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip("[]").strip().rstrip(":·.,;").strip()


def extract_lemmas(path: Path) -> list[tuple[str, str]]:
    """(lemma, where) for each entry of a lexicon's Diogenes TEI file, in
    order; `where` names the entry ("entry 12", "Page 3, line 1")."""
    body = ET.parse(path).getroot().find(f".//{TEI}body")
    out: list[tuple[str, str]] = []
    entries = [d for d in body.iter(f"{TEI}div") if d.get("type") == "entry"]
    if entries:
        letter = ""
        for el in body.iter():
            if _local(el.tag) == "div" and (el.get("type") or "").startswith("Alphabetic"):
                letter = el.get("n") or ""
            if not (_local(el.tag) == "div" and el.get("type") == "entry"):
                continue
            for sub in el.iter():
                tag = _local(sub.tag)
                if (tag == "hi" and "letter-spacing" in (sub.get("rend") or "")) or \
                        (tag == "seg" and sub.get("type") == "lemma"):
                    lemma = _clean_lemma("".join(sub.itertext()))
                    if lemma:
                        where = f"entry {el.get('n')}" + (f" ({letter})" if letter else "")
                        out.append((lemma, where))
                    break
        return out
    page = ""
    first = True
    for el in body.iter():
        tag = _local(el.tag)
        if tag == "div" and el.get("type"):
            page = f"{el.get('type')} {el.get('n')}"
        if tag != "l":
            continue
        opens = first or (el.get("rend") or "").startswith("indent")
        first = False
        if not opens:
            continue
        m = _LEMMA_HEAD.match("".join(el.itertext()))
        if m and _clean_lemma(m.group(1)):
            out.append((_clean_lemma(m.group(1)), f"{page}, line {el.get('n')}"))
    return out


class LemmaIndex:
    """A lexicon's entries by normalised lemma (accents, breathings, case
    and punctuation dropped: norm_greek)."""

    def __init__(self, lemmas_by_work: dict[str, list[tuple[str, str]]], author: str):
        self.author = author
        self.entries = [(lemma, w, where, tuple(filter(None, map(norm_greek, lemma.split()))))
                        for w, lemmas in sorted(lemmas_by_work.items())
                        for lemma, where in lemmas]
        self.by_norm: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
        for lemma, w, where, words in self.entries:
            self.by_norm["".join(words)].append((lemma, w, where))

    def check(self, headword: str) -> dict:
        """CONFIRMED: an entry has this headword. WEAK: the headword opens a
        longer entry, or an entry's lemma opens the headword (word by word).
        NOT-FOUND: neither."""
        words = tuple(filter(None, map(norm_greek, headword.split())))
        exact = self.by_norm.get("".join(words), []) if words else []
        # Notes name entries by place only: the outputs never quote the TLG.
        if exact:
            _, w, where = exact[0]
            return {"verdict": "CONFIRMED", "found": f"{self.author}.{w}: {where}",
                    "note": "headword is an entry", "probes_at_locus": 0, "also": []}
        partial = [(w, where, len(lw) > len(words)) for lemma, w, where, lw in self.entries
                   if words and lw and lw != words
                   and (lw[:len(words)] == words or words[:len(lw)] == lw)]
        if partial:
            w, where, longer = partial[0]
            return {"verdict": "WEAK", "found": f"{self.author}.{w}: {where}",
                    "note": "no entry is the headword itself; "
                            + ("an entry opens with it" if longer else "an entry's lemma opens it")
                            + (f" ({len(partial)} such entries)" if len(partial) > 1 else ""),
                    "probes_at_locus": 0, "also": []}
        near = [f"{self.author}.{w}: {where}" for _, w, where, lw in self.entries
                if words and lw and "".join(lw)[:5] == "".join(words)[:5]][:3]
        return {"verdict": "NOT-FOUND", "found": "", "probes_at_locus": 0, "also": [],
                "note": "the headword is no entry of the lexicon"
                        + (f"; entries sharing its first five letters: {'; '.join(near)}" if near else "")}


class Corpus:
    def __init__(self, cache: Path):
        self.cache = cache
        self.mem: dict[tuple, dict[str, WorkIndex]] = {}

    def works(self, corpus: str, author: str, want: Optional[list[str]] = None
              ) -> dict[str, WorkIndex]:
        key = (corpus, author)
        have = self.mem.setdefault(key, {})
        xml_dir = export_author(corpus, author, self.cache)
        files = sorted(xml_dir.glob(f"{corpus}{author}[0-9][0-9][0-9].xml"))
        lang = "lat" if corpus == "phi" else "grc"
        for f in files:
            w = f.name[-7:-4]
            if want is not None and w not in want:
                continue
            if w in have:
                continue
            pk = self.cache / "index" / f"{corpus}{author}{w}.pickle"
            if pk.exists() and pk.stat().st_mtime >= f.stat().st_mtime:
                have[w] = WorkIndex(**pickle.loads(pk.read_bytes()))
                continue
            idx = index_xml(f, lang, HOOKS.get((corpus, author, w)))
            pk.parent.mkdir(parents=True, exist_ok=True)
            pk.write_bytes(pickle.dumps(idx.__dict__))
            have[w] = idx
        return {w: i for w, i in have.items() if want is None or w in want}

    def lemma_index(self, corpus: str, author: str, want: list[str]) -> LemmaIndex:
        """The entries of a lexicon's works (cached next to the text index)."""
        xml_dir = export_author(corpus, author, self.cache)
        lemmas = {}
        for w in want:
            f = xml_dir / f"{corpus}{author}{w}.xml"
            if not f.exists():
                continue
            pk = self.cache / "index" / f"{corpus}{author}{w}.lemmas.pickle"
            if pk.exists() and pk.stat().st_mtime >= f.stat().st_mtime:
                lemmas[w] = pickle.loads(pk.read_bytes())
                continue
            lemmas[w] = extract_lemmas(f)
            pk.parent.mkdir(parents=True, exist_ok=True)
            pk.write_bytes(pickle.dumps(lemmas[w]))
        return LemmaIndex(lemmas, author)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    probe: int
    work: str
    path: tuple


def find_hits(probes: list[str], works: dict[str, WorkIndex],
              max_per_probe: int = 25) -> list[Hit]:
    hits = []
    for pi, pr in enumerate(probes):
        n = 0
        for w, idx in works.items():
            start = 0
            while True:
                i = idx.letters.find(pr, start)
                if i < 0:
                    break
                hits.append(Hit(pi, w, idx.path_at(i)))
                n += 1
                if n >= max_per_probe:
                    break
                start = i + 1
            if n >= max_per_probe:
                break
    return hits


def fmt_path(work: str, title: str, path: tuple) -> str:
    parts = [f"{t} {n}" for t, n in path if n not in ("",)]
    return f"{work} {title[:40]}: " + ", ".join(parts)


def group_hits(hits: list[Hit], levels: list[str]) -> list[dict]:
    """Group hits by work + the given level names; a 'line' level becomes a
    range. Sorted by the number of distinct probes, best first."""
    groups: dict[tuple, dict] = {}
    for h in hits:
        d = path_dict(h.path)
        key_levels = [lv for lv in levels if lv != "line"]
        key = (h.work,) + tuple(d.get(lv) for lv in key_levels)
        g = groups.setdefault(key, {"work": h.work, "probes": set(),
                                    "levels": dict(zip(key_levels, key[1:])),
                                    "lines": set(), "sample": h.path})
        g["probes"].add(h.probe)
        if "line" in levels and d.get("line"):
            n, _ = split_num(d["line"])
            if n is not None:
                g["lines"].add(n)
    out = list(groups.values())
    out.sort(key=lambda g: -len(g["probes"]))
    return out


def needed(n_probes: int) -> int:
    """Distinct probes that must agree before the expected locus counts as
    found."""
    return 1 if n_probes <= 2 else 2


def mismatch_needed(n_probes: int) -> int:
    """A claim that the passage stands elsewhere needs more: a quarter of
    the probes, at least `needed` and at most 5."""
    return max(needed(n_probes), min(5, -(-n_probes // 4)))


# ---------------------------------------------------------------------------
# Source specs
# ---------------------------------------------------------------------------


class Unmapped(Exception):
    """The reading cannot be mapped to the corpus scheme (reason in args)."""


class NotInCorpus(Exception):
    pass


class Incomplete(Exception):
    """The reading is not a complete citation (e.g. 's.v. [headword]')."""


@dataclass
class Spec:
    corpus: str  # 'tlg' | 'phi'
    author: str
    parse: Callable[[str], list[Locus]]
    # When the reading's scheme cannot be mapped, still search these works of
    # the author (None = all) and name where the passage stands, as a note.
    annotate: Optional[list[str]] | bool = False
    # Searched when the main works yield nothing: (author, works); a hit there
    # is reported as SCHEME-UNMAPPED with its locus (Aëtius in Stobaeus).
    fallback: Optional[tuple[str, list[str]]] = None
    # A lexicon: its works (TLG work numbers) whose entries an "s.v. <word>"
    # reading is checked against (LemmaIndex.check).
    lexicon: Optional[list[str]] = None


def strip_label(reading: str) -> str:
    """Drop the source abbreviation ('STOB.', 'ARISTOT.') and editor tails."""
    r = reading.strip()
    r = re.sub(r"\[[^\]]*\]", " ", r)
    r = re.sub(r"\((?:Staehlin|Stähl|D\.|Us\.|I+ \d)[^)]*\)", " ", r)
    return r


def nums(s: str) -> list[str]:
    """Roman numerals and numbers (with a letter suffix) in order: 'II 31,
    39' -> ['2', '31', '39']; '7c' stays '7c'."""
    out = []
    for tok in re.findall(r"\b([IVXLC]+|\d+[a-z]?)\b", s):
        r = roman_to_int(tok) if re.fullmatch(r"[IVXLC]+", tok) else None
        out.append(str(r) if r is not None else tok)
    return out


def after(reading: str, pattern: str) -> str:
    m = re.search(pattern, reading, flags=re.I)
    if not m:
        raise Unmapped(f"work not recognised in '{reading}'")
    return reading[m.end():]


def drop_pages(s: str) -> str:
    """Remove edition page refs like 'p. 208, 13' and trailing editor names."""
    s = re.sub(r"\bp\.\s*\d+[a-z]?(?:\s*,\s*\d+)?", " ", s)
    s = re.sub(r"\b(Hense|Wachsm\.?|Diels2?|K\.|St\.|Kö\.)\b", " ", s)
    return s


def levels_from(names: list[str], values: list[str]) -> list[tuple[str, str]]:
    if len(values) < len(names):
        raise Unmapped(f"expected {len(names)} numbers, got {values}")
    return list(zip(names, values[:len(names)]))


# --- per-source parsers ----------------------------------------------------


def p_stobaeus(reading: str) -> list[Locus]:
    r = strip_label(reading)
    r = re.sub(r"^\s*STOB(?:AEUS|\.)?\s*", "", r, flags=re.I)
    flor = bool(re.search(r"Flor\.", r))
    # "(Flor.)", "Ecl.", "(Ecl. eth.)"; Hense's title marker "III t. 1, 27".
    r = re.sub(r"\(?(Flor|Ecl)\.(?:\s*eth\.)?\)?", " ", r)
    r = re.sub(r"\bt\.\s*(?=\d)", "", r)
    r = drop_pages(r)
    if "?" in r:
        raise Unmapped("reading marked uncertain (?)")
    # 'III 29, 63. 83a' -> book 3, chapter 29, sections 63 or 83a
    m = re.match(r"\s*([IVX]+)\s+(\d+[a-z]?)\s*,\s*([\d a-z.]+)", r)
    if m:
        book = str(roman_to_int(m.group(1)))
        chap = m.group(2)
        secs = [s for s in re.split(r"[.\s]+", m.group(3)) if s]
        return [Locus([("book", book), ("chapter", chap), ("section", s)],
                      ["001"], label=f"{m.group(1)} {chap}, {s}") for s in secs]
    m = re.match(r"\s*([IVX]+)\s+(\d+[a-z]?)\s*$", r)
    if m and flor:
        # DK's 'Flor. I 176' is Meineke's Florilegium, chapter I section 176:
        # Meineke's chapters 1-42 are Wachsmuth-Hense book III, same numbers.
        chap = roman_to_int(m.group(1))
        if chap and chap <= 42:
            return [Locus([("book", "3"), ("chapter", str(chap)),
                           ("section", m.group(2))], ["001"],
                          label=f"(Flor. = W-H) III {chap}, {m.group(2)}")]
    raise Unmapped(f"cannot read book/chapter/section in '{reading}'")


def p_aetius(reading: str) -> list[Locus]:
    r = re.sub(r"^\s*A[EË]T\.\s*", "", strip_label(reading), flags=re.I)
    m = re.match(r"\s*([IVX]+)\s+(\d+)(?:\s*,\s*(\d+[a-z]?))?", r)
    if not m:
        raise Unmapped(f"cannot read book/chapter in '{reading}'")
    book, chap = str(roman_to_int(m.group(1))), m.group(2)
    sec = f" (section {m.group(3)} unchecked)" if m.group(3) else ""
    checked = ["aet-book", "aet-chapter"] if m.group(3) else None
    return [Locus([("aet-book", book), ("aet-chapter", chap)], ["003"],
                  label=f"{m.group(1)} {chap}{sec}", checked=checked)]






def p_diogenes(reading: str) -> list[Locus]:
    r = after(strip_label(reading), r"DIOG\.")
    out = []
    for m in re.finditer(r"([IVX]+)\s+(\d+)", r):
        out.append(Locus([("book", str(roman_to_int(m.group(1)))),
                          ("section", m.group(2))], ["001"],
                         label=f"{m.group(1)} {m.group(2)}"))
    if not out:
        raise Unmapped(f"cannot read book/section in '{reading}'")
    return out


def p_aristotle(reading: str) -> list[Locus]:
    m = re.search(r"(\d{2,4})\s*([ab])\s*(\d+)", reading)
    if not m:
        raise Unmapped(f"no Bekker page/column/line in '{reading}'")
    page = f"{m.group(1)}{m.group(2)}"
    return [Locus([("bekker-page", page), ("line", m.group(3))], None,
                  fine="line", label=f"{page} {m.group(3)}")]


PLUTARCH_LIVES = {r"Pericl": "012", r"Coriol": "016"}


def p_plutarch(reading: str) -> list[Locus]:
    m = re.search(r"p\.\s*(\d{1,4})\s*([A-Fa-f])(?:\s+([A-Fa-f])\b)?", reading)
    if m:
        page = m.group(1)
        out = [Locus([("stephanus-page", page), ("section", m.group(2).upper())],
                     None, fine="letter", label=f"{page} {m.group(2).upper()}")]
        if m.group(3):
            out.append(Locus([("stephanus-page", page),
                              ("section", m.group(3).upper())], None,
                             fine="letter", label=f"{page} {m.group(3).upper()}"))
        return out
    if re.search(r"libid", reading):
        v = nums(after(reading, r"aegr\."))
        return [Locus([("section", v[0])], ["143"])]
    for pat, work in PLUTARCH_LIVES.items():
        if re.search(pat, reading):
            v = nums(after(reading, pat + r"\w*\."))
            return [Locus([("chapter", v[0])], [work])]
    raise Unmapped(f"no Stephanus page or known Life in '{reading}'")


PLATO_WORKS = {  # TLG 0059 work numbers
    r"Gorg\.": "023", r"Meno": "024", r"Phileb\.": "010",
    r"Hipp\.? ?ma(?:i|ior|j)": "025", r"Hipp\.? ?min": "026",
    r"Theaet\.": "006", r"Apol\.": "002", r"Prot(?:ag)?\.": "022",
    r"Euthyd\.": "021", r"Lach\.": "019", r"Charmid\.": "018",
    r"Parm\.": "009", r"PHAEDR\.|Phaedr\.": "012",
}


def p_plato(reading: str) -> list[Locus]:
    work = next((w for pat, w in PLATO_WORKS.items()
                 if re.search(pat, reading)), None)
    if not work:
        raise Unmapped(f"Plato work not recognised in '{reading}'")
    m = re.search(r"(\d{2,3})\s*([A-Ea-e])(?:\s*([A-Ea-e])\b)?", reading)
    if not m:
        raise Unmapped(f"no Stephanus page/letter in '{reading}'")
    page = m.group(1)
    letters = [m.group(2)] + ([m.group(3)] if m.group(3) else [])
    return [Locus([("stephanus-page", page), ("section", L.lower())], [work],
                  fine="letter", label=f"{page} {L.upper()}") for L in letters]


def p_simplicius(reading: str) -> list[Locus]:
    work = "001" if re.search(r"de caelo", reading, re.I) else "004"
    r = re.sub(r"^.*?(Phys\.|de caelo)", "", reading, flags=re.I)
    m = re.search(r"(\d+)\s*,\s*(\d+)", r)
    if not m:
        raise Unmapped(f"no CAG page, line in '{reading}'")
    return [Locus([("page", m.group(1)), ("line", m.group(2))], [work],
                  fine="line", label=f"{m.group(1)}, {m.group(2)}")]


def p_clement(reading: str) -> list[Locus]:
    """TLG: book, chapter, section, subsection; Stählin's sections run on
    through each book, which is what DK cites, so the chapter is skipped."""
    r = re.sub(r"\(.*?\)", " ", reading)
    for pat, work, name in ((r"Str(?:om)?\.", "004", "Strom."),
                            (r"Paed\.", "002", "Paed.")):
        if re.search(pat, r):
            v = nums(after(r, pat))
            return [Locus([("book", v[0]), ("section", v[1])], [work],
                          label=f"{name} book {v[0]}, section {v[1]}")]
    if re.search(r"Protr\.", r):
        v = nums(after(r, r"Protr\."))
        return [Locus([("section", v[0])], ["001"],
                      label=f"Protr. section {v[0]}")]
    raise Unmapped(f"Clement work not recognised in '{reading}'")


def p_hippolytus(reading: str) -> list[Locus]:
    v = nums(after(reading, r"HIPPOL\."))
    return [Locus([("book", v[0]), ("chapter", v[1])], ["060"])]


CICERO_WORKS = {r"nat\. ?d": "050", r"de div\.": "053", r"Ac\. ?pr\.": "046",
                r"Orat\.": "040"}


def p_cicero(reading: str) -> list[Locus]:
    """PHI numbers Cicero by book and running section only, so DK's
    'I 10, 26' (book, chapter, section) is checked as book 1, section 26."""
    for pat, work in CICERO_WORKS.items():
        if re.search(pat, reading):
            v = nums(re.sub(r"\(.*?\)", " ", after(reading, pat)))
            if work in ("046", "040"):  # Lucullus, Orator: section only
                return [Locus([("section", v[-1])], [work])]
            return [Locus([("book", v[0]), ("section", v[-1])], [work])]
    raise Unmapped(f"Cicero work not recognised in '{reading}'")


def p_aelian(reading: str) -> list[Locus]:
    work = "002" if re.search(r"V\. ?H\.", reading) else "001"
    v = nums(re.sub(r"^.*?[HV]\. ?[HN]\.", "", reading))
    return [Locus([("book", v[0]), ("section", v[1])], [work],
                  label=f"{'VH' if work == '002' else 'NA'} {v[0]}, {v[1]}")]


def p_gnomologium(reading: str) -> list[Locus]:
    if not re.search(r"Vatic", reading, re.I):
        raise NotInCorpus("only the Gnomologium Vaticanum is in the TLG")
    m = re.search(r"n\.\s*(\d+)", reading)
    if not m:
        raise Unmapped(f"no saying number in '{reading}'")
    return [Locus([("sententia", m.group(1))], ["001"])]


def p_theophrastus(reading: str) -> list[Locus]:
    if re.search(r"c(?:aus)?\.\s*p(?:l|lant)\.", reading):
        v = nums(re.sub(r"^.*?pl(?:ant)?\.", "", reading))
        work = "002" if v[0] == "1" else "014"
        return [Locus([("book", v[0]), ("chapter", v[1]), ("section", v[2])],
                      [work])]
    for pat, frag, name in ((r"de odor\.", "4", "De odoribus"),
                            (r"de vertig\.", "8", "De vertigine")):
        if re.search(pat, reading):
            v = nums(after(reading, pat))
            return [Locus([("fragment", frag), ("section", v[0])], ["010"],
                          label=f"{name} (Wimmer fr. {frag}) {v[0]}")]
    raise Unmapped(f"Theophrastus work not recognised in '{reading}'")


def p_sextus(reading: str) -> list[Locus]:
    v = nums(after(reading, r"adv\. ?math\."))
    return [Locus([("book", v[0]), ("section", v[1])], ["002"])]


def p_page_line(work: str, name: str):
    def parse(reading: str) -> list[Locus]:
        m = re.search(r"p\.\s*(\d+)\s*,\s*(\d+)", reading)
        if not m:
            raise Unmapped(f"no page, line in '{reading}'")
        return [Locus([("page", m.group(1)), ("line", m.group(2))], [work],
                      fine="line", label=f"{name} p. {m.group(1)}, "
                                         f"{m.group(2)}")]
    return parse


def p_iamblichus(reading: str) -> list[Locus]:
    if re.search(r"Stob\. ?Ecl\.", reading):
        inner = after(reading, r"Stob\. ?Ecl\.").strip(" ]")
        return [Locus(lc.levels, lc.works, lc.fine, lc.label, author="2037")
                for lc in p_stobaeus("STOB. " + inner)]
    if re.search(r"de myst\.", reading):
        v = nums(after(reading, r"de myst\."))
        return [Locus([("chapter", v[0]), ("section", v[1])], ["006"],
                      label=f"De mysteriis {v[0]}, {v[1]}")]
    if re.search(r"in Nic\.", reading):
        return p_page_line("004", "in Nic.")(reading)
    raise Unmapped(f"Iamblichus work not recognised in '{reading}'")


def p_levels(prefix: str, work: str, names: list[str], fine: str = "exact"):
    """Generic: the numbers after `prefix`, read as the given levels."""
    def parse(reading: str) -> list[Locus]:
        v = nums(drop_pages(re.sub(r"\(.*?\)", " ", after(reading, prefix))))
        return [Locus(levels_from(names, v), [work], fine=fine)]
    return parse


def p_proclus(reading: str) -> list[Locus]:
    if re.search(r"in Parm\.", reading):
        return p_page_line("008", "in Parm. (Cousin)")(reading)
    if re.search(r"in Hes\. ?Opp\.", reading):
        # Proclus on the Works and Days survives in the scholia; TLG 5025.002
        # (Pertusi, 'scholia vetera partim Procli') is divided by Hesiod verse.
        v = nums(after(reading, r"Opp\."))
        return [Locus([("page-verse", v[0])], ["002"], author="5025",
                      label=f"schol. Hes. Op. {v[0]} (Pertusi)")]
    raise Unmapped(f"Proclus work not recognised in '{reading}'")


def p_aristophanes(reading: str) -> list[Locus]:
    if re.search(r"Vesp\.", reading):
        v = nums(after(reading, r"Vesp\."))
        return [Locus([("line", v[0])], ["004"], fine="line",
                      label=f"Wasps {v[0]}")]
    raise Unmapped("comic fragment cited by Kock's number; the TLG numbers "
                   "Aristophanes' fragments by Kassel-Austin")


def no_corpus(reason: str):
    def parse(reading: str) -> list[Locus]:
        raise NotInCorpus(reason)
    return parse


def unmapped(reason: str):
    def parse(reading: str) -> list[Locus]:
        raise Unmapped(reason)
    return parse


def p_scholia(reading: str) -> list[Locus]:
    if re.search(r"PIND", reading):
        raise Unmapped("scholia to Pindar: DK's 'Nem. 7, 53' is Drachmann's "
                       "scholion number; not mapped to the TLG division")
    raise Unmapped("scholia to the Iliad: DK cites the verse the note is on "
                   "(N 137); not mapped to the TLG's scholia divisions")


# Keyed by the survey's `source_author`. TLG/PHI work numbers were read off
# the Diogenes export titles (2026-09-24).
SOURCES: dict[str, Spec] = {
    "Stobaeus": Spec("tlg", "2037", p_stobaeus),
    "Aëtius": Spec("tlg", "0094", p_aetius, fallback=("0528", ["001", "002"])),
    "Julius Pollux": Spec("tlg", "0542",
                          p_levels(r"POLL\.", "001", ["book", "section"])),
    "Aristotle": Spec("tlg", "0086", p_aristotle),
    "Plutarch": Spec("tlg", "0007", p_plutarch),
    "Plato": Spec("tlg", "0059", p_plato),
    "Simplicius": Spec("tlg", "4013", p_simplicius),
    "Clement of Alexandria": Spec("tlg", "0555", p_clement),
    "Diogenes Laertius": Spec("tlg", "0004", p_diogenes),
    "Hippolytus": Spec("tlg", "2115", p_hippolytus),
    "Cicero": Spec("phi", "0474", p_cicero),
    "Aelian": Spec("tlg", "0545", p_aelian),
    # Bekker's Anecdota Graeca and the gnomologia have no author (John's
    # ruling, 2026-09-24; content review item 4): the stage's entry carries
    # only the work, which names the spec.
    **{f"Gnomologium {name}": Spec("tlg", "2945", p_gnomologium)
       for name in ("Vaticanum", "Parisinum", "Vindobonense", "Monacense Latinum")},
    "Anecdota Graeca": Spec("tlg", "4289", unmapped(
        "DK cites Bekker's Anecdota (Lex. VI) by page and line; the TLG gives "
        "this lexicon from Bachmann's edition, with his pages"),
        annotate=True),
    "Theophrastus": Spec("tlg", "0093", p_theophrastus),
    "Sextus Empiricus": Spec("tlg", "0544", p_sextus),
    "Iamblichus": Spec("tlg", "2023", p_iamblichus),
    "Theologumena Arithmeticae": Spec("tlg", "2023",
                                      p_page_line("005", "Theol. arithm.")),
    "Marcus Aurelius": Spec("tlg", "0562", p_levels(
        r"ANTON\.", "001", ["book", "chapter"])),
    "Athenaeus": Spec("tlg", "0008", unmapped(
        "DK cites Casaubon's page and letter; the TLG numbers Athenaeus by "
        "Kaibel's book and paragraph"), annotate=True),
    "Proclus": Spec("tlg", "4036", p_proclus),
    "Aristophanes": Spec("tlg", "0019", p_aristophanes, annotate=True),
    "Origen": Spec("tlg", "2042", p_levels(r"Cels\.", "001",
                                           ["book", "section"])),
    "Herodotus": Spec("tlg", "0016", p_levels(r"HEROD(?:OT)?\.", "001",
                                              ["book", "section"])),
    "Xenophon": Spec("tlg", "0032", p_levels(
        r"Hell\.", "001", ["book", "chapter", "section"])),
    "Eustathius": Spec("tlg", "4083", unmapped(
        "DK cites the Rome edition's page (1713); the TLG gives Stallbaum's "
        "volume and page"), annotate=["003"]),
    "Dionysius of Alexandria (in Eusebius)": Spec("tlg", "2018", p_levels(
        r"P\. ?E\.", "001", ["book", "chapter", "section"])),
    "Galen": Spec("tlg", "0057", unmapped(
        "DK cites book and chapter; the TLG cites Galen by Kühn's volume, "
        "page and line")),
    "Philodemus": Spec("tlg", "1595", unmapped(
        "DK cites Kemke's De musica (book, column, page, line); the TLG's "
        "Philodemus is a different edition")),
    "Philo of Alexandria": Spec("tlg", "0018", unmapped(
        "DK cites Mangey's page (473); the TLG numbers Philo by section"),
        annotate=True),
    "Eusebius": Spec("tlg", "2018", no_corpus(
        "the Chronicle's Greek is lost; it survives in Armenian and in "
        "Jerome's Latin, neither in the TLG or PHI")),
    "Soranus": Spec("tlg", "0565", p_levels(
        r"Gynaec\.", "001", ["book", "chapter"])),
    "Plotinus": Spec("tlg", "2000", p_levels(
        r"Enn\.", "001", ["ennead", "chapter", "section"])),
    "Porphyry": Spec("tlg", "2034", p_levels(r"Pyth\.", "002", ["section"])),
    "John Tzetzes": Spec("tlg", "9022", unmapped(
        "DK cites Hermann's page of the Exegesis in Iliadem; the TLG's "
        "edition is numbered differently"), annotate=True),
    "Aristocritus": Spec("tlg", "", no_corpus(
        "the Tübingen Theosophia is not in the TLG")),
    "Aelius Aristides": Spec("tlg", "0284", unmapped(
        "DK's 'II 50' for the Ars rhetorica ascribed to Aristides is not the "
        "TLG's division (book, chapter, section, subsection)"),
        annotate=["056"]),
    "Photius": Spec("tlg", "4040", unmapped(
        "DK cites Reitzenstein's page and line; the TLG lexicon is numbered "
        "by entry")),
    "Herodian (grammarian)": Spec("tlg", "0087", unmapped(
        "cited through Theognostus, the Etymologicum Genuinum or the "
        "Epimerismi by Cramer's pages; the TLG numbers these differently")),
    "Scholia (Pindar, Apollonius, Homer)": Spec("tlg", "5026", p_scholia),
    "Columella": Spec("phi", "0845", p_levels(
        r"COLUM\.", "002", ["book", "chapter", "section"])),
    "Censorinus": Spec("phi", "", no_corpus("Censorinus is not in the PHI")),
    "Democrates": Spec("tlg", "", no_corpus(
        "the Democrates sayings exist in the TLG only inside DK's own "
        "Democritus (1304), which would check DK against itself")),
    # Lexica: an "s.v. <headword>" reading is checked against the entries
    # (item 7). TLG 1389.001 Harpocration (Dindorf); 4085.002-003 Hesychius
    # (Latte alpha-omicron, Schmidt pi-omega); 9010.001 the Suda (Adler);
    # 4097.001-003 the Etymologicum Genuinum (only parts are in the TLG).
    "Harpocration": Spec("tlg", "1389", unmapped("lexicon entry"), lexicon=["001"]),
    "Hesychius": Spec("tlg", "4085", unmapped("lexicon entry"), lexicon=["002", "003"]),
    "Suda": Spec("tlg", "9010", unmapped("lexicon entry"), lexicon=["001"]),
    "Etymologicum": Spec("tlg", "4097", unmapped("lexicon entry"),
                         lexicon=["001", "002", "003"]),
}


# ---------------------------------------------------------------------------
# DK passages
# ---------------------------------------------------------------------------


def load_spines(spine_dir: Path) -> dict[tuple[str, str], str]:
    """(work, segment) -> the segment's lines joined into one string."""
    out = {}
    for f in sorted(spine_dir.glob("*.json")):
        d = json.loads(f.read_text())
        for s in d["segments"]:
            seg = s["id"].split(":")[-1]
            out[(f.stem, seg)] = " ".join(l["text"] for l in s["lines"])
    return out


def passage_for(seg_text: str, head: str, heads: list[str]) -> str:
    """The stretch of the segment that follows `head`, up to the next dash
    head of the same segment (a composite testimonium carries several)."""
    i = seg_text.find(head)
    if i < 0:
        return seg_text
    start = i + len(head)
    end = len(seg_text)
    for h in heads:
        if h == head:
            continue
        j = seg_text.find(h, start)
        if 0 <= j < end:
            end = j
    # DK also chains loci without a dash ('... ἥλιον. 21, 3 (D. 351) ...');
    # the passage for this reading stops at the next such locus.
    m = NEXT_LOCUS.search(seg_text, start, end)
    if m:
        end = m.start()
    return seg_text[start:end]


NEXT_LOCUS = re.compile(r"(?:[IVX]+\s+)?\b\d+[a-z]?\s*,\s*\d+[a-z]?\b")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

INCOMPLETE = re.compile(r"\[headword\]|\[no number printed\]|\(\?\)")


def describe_group(g: dict, works: dict[str, WorkIndex], author: str) -> str:
    title = works[g["work"]].title if g["work"] in works else ""
    parts = [f"{k} {v}" for k, v in g["levels"].items() if v is not None]
    if g["lines"]:
        lo, hi = min(g["lines"]), max(g["lines"])
        parts.append(f"line {lo}" if lo == hi else f"lines {lo}-{hi}")
    if not parts:  # levels not present at the hit: fall back to its path
        parts = [f"{t} {n}" for t, n in g["sample"]]
    return f"{author}.{g['work']} {title[:45]}: " + ", ".join(parts)


def full_levels(path: tuple) -> list[str]:
    return [t.lower() for t, _ in path]


def evaluate(loci: list[Locus], hits: list[Hit], probes: list[str],
             works: dict[str, WorkIndex], author: str) -> dict:
    n_probes = len(probes)
    need = needed(n_probes)
    best = None
    for lc in loci:
        ok_probes, notes, adj_probes = set(), set(), set()
        for h in hits:
            ok, note, adj = match_locus(h.work, h.path, lc)
            if ok:
                ok_probes.add(h.probe)
                if note:
                    notes.add(note)
                if adj:
                    adj_probes.add(h.probe)
        if best is None or len(ok_probes) > len(best[1]):
            best = (lc, ok_probes, notes, adj_probes)
    lc, ok_probes, notes, adj_probes = best
    levels = [k for k, _ in lc.levels]
    groups = group_hits(hits, levels)
    # Hits outside any unit of the expected scheme (a heading, a table of
    # contents) are not a competing locus.
    groups = [g for g in groups if all(v is not None
                                       for v in g["levels"].values())] or groups

    def rivals(exclude: set) -> list[str]:
        """Other places with enough probes, most independent evidence first,
        each with its raw and independent probe count (Sol review finding
        1: a rival is weighed against the locus by independent probes)."""
        cands = [g for g in groups if len(g["probes"]) >= need
                 and (g["work"], tuple(g["levels"].items())) not in exclude]
        cands.sort(key=lambda g: -independent(probes, g["probes"]))
        return [f"{describe_group(g, works, author)} [{len(g['probes'])} probes, "
                f"{independent(probes, g['probes'])} independent]" for g in cands]

    # Review item 9: probes that overlap are one stretch of the passage, so
    # only probes with disjoint spans count toward the threshold. Enough
    # overlapping probes but too few disjoint ones is a lesser confirmation.
    indep = independent(probes, ok_probes)
    if len(ok_probes) >= need:
        matched = [h for h in hits if h.probe in ok_probes
                   and match_locus(h.work, h.path, lc)[0]]
        mg = group_hits(matched, levels)
        found_desc = describe_group(mg[0], works, author) if mg else lc.text()
        note = "; ".join(sorted(notes))
        exact_lines = []
        if lc.fine in ("line", "letter"):
            want = lc.levels[-1][1]
            got = sorted({str(path_dict(h.path).get(levels[-1]))
                          for h in hits if h.probe in ok_probes
                          and match_locus(h.work, h.path, lc)[0]},
                         key=lambda x: (split_num(x)[0] or 0, x))
            if want not in got and want.lower() not in [str(x).lower()
                                                        for x in got]:
                exact_lines.append(f"passage starts at {levels[-1]} "
                                   f"{', '.join(map(str, got[:3]))}")
        found = found_desc
        match_keys = {(g["work"], tuple(g["levels"].items())) for g in mg}
        others = rivals(match_keys)
        # Defect 4: a lone probe shorter than a full PROBE_LEN-letter probe is
        # too little evidence for a full CONFIRMED, whatever `needed()` (which
        # only counts probes, never their length) allowed through -- two
        # independent probes, or one full-length one, is the floor. Checked
        # ahead of CONFIRMED-PARTIAL: weak evidence is the more urgent flag.
        max_len = max((len(probes[i]) for i in ok_probes), default=0)
        verdict = "CONFIRMED"
        overlap = ""
        if indep < need:
            verdict = "WEAK"
            overlap = (f"the {len(ok_probes)} probes at the locus overlap: "
                       f"{indep} independent")
        elif indep < 2 and max_len < PROBE_LEN:
            verdict = "WEAK"
        elif lc.checked:
            verdict = "CONFIRMED-PARTIAL"
        result = {"verdict": verdict, "found": found,
                  "probes_at_locus": len(ok_probes), "independent_at_locus": indep,
                  "note": "; ".join(x for x in [note] + exact_lines + [overlap] if x),
                  "also": others[:2]}
        if verdict == "CONFIRMED-PARTIAL":
            result["checked"] = lc.checked
        if adj_probes:  # adj_probes is always a subset of ok_probes
            result["adjacent"] = True
        return result
    if groups and len(groups[0]["probes"]) >= mismatch_needed(n_probes):
        g = groups[0]
        note = f"{len(g['probes'])} of {n_probes} probes there"
        near = near_miss(g, lc)
        if near:
            note += f"; {near}"
        if ok_probes:
            note += f"; {len(ok_probes)} probes at the reading's locus"
        return {"verdict": "MISMATCH", "found": describe_group(g, works, author),
                "probes_at_locus": len(ok_probes), "independent_at_locus": indep,
                "note": note, "also": rivals({(g["work"], tuple(g["levels"].items()))})[:2]}
    if groups:
        g = groups[0]
        return {"verdict": "NOT-FOUND", "found": "",
                "probes_at_locus": len(ok_probes),
                "note": f"weak: {len(g['probes'])} of {n_probes} probes, at "
                        f"{describe_group(g, works, author)}", "also": []}
    return {"verdict": "NOT-FOUND", "found": "", "probes_at_locus": 0,
            "note": f"0 of {n_probes} probes found", "also": []}


def near_miss(g: dict, lc: Locus) -> str:
    """'near miss' when the found group differs from the expected locus only
    in its finest level, by at most 2."""
    pairs = [(k, v) for k, v in lc.levels if k != "line"]
    if not pairs or lc.fine != "exact":
        return ""
    *head, (last, want) = pairs
    if not all(same_value(g["levels"].get(k), v)[0] for k, v in head):
        return ""
    fn, _ = split_num(g["levels"].get(last) or "")
    wn, _ = split_num(want)
    if fn is None or wn is None or fn == wn or abs(fn - wn) > 2:
        return ""
    return f"near miss: {last} {fn} against the reading's {wn}"


def best_place(hits: list[Hit], works: dict[str, WorkIndex], author: str,
               n_probes: int) -> tuple[str, int]:
    """Where the passage stands, at the finest division of its hits, and how
    many distinct probes put it there."""
    if not hits:
        return "", 0
    groups = group_hits(hits, full_levels(hits[0].path))
    g = groups[0]
    if len(g["probes"]) < needed(n_probes):
        return "", 0
    return (f"{describe_group(g, works, author)} [{len(g['probes'])} probes]",
            len(g["probes"]))


def verify(rec: dict, reading: str, spec: Optional[Spec], passage: str,
           corpus: Corpus) -> dict:
    out = {"verdict": None, "expected": "", "found": "", "note": "",
           "probes": 0, "probes_at_locus": 0, "also": []}
    if INCOMPLETE.search(reading or ""):
        out.update(verdict="NOT-CHECKED",
                   note="reading is not a complete citation")
        return out
    if spec is None:
        out.update(verdict="SCHEME-UNMAPPED",
                   note="no source spec for this author")
        return out
    if spec.lexicon is not None and "s.v." in (reading or ""):
        headword = reading.split("s.v.", 1)[1].strip()
        if re.search(r"ETYM", reading) and not re.search(r"GEN", reading):
            out.update(verdict="SCHEME-UNMAPPED",
                       note="only the Etymologicum Genuinum's entries are checked")
            return out
        out["expected"] = f"s.v. {headword}"
        out.update(corpus.lemma_index(spec.corpus, spec.author, spec.lexicon).check(headword))
        return out
    lang = "lat" if spec.corpus == "phi" else "grc"
    probes = make_probes(normaliser(lang)(passage))
    out["probes"] = len(probes)
    try:
        loci = spec.parse(reading)
    except NotInCorpus as e:
        out.update(verdict="NOT-IN-CORPUS", note=str(e))
        return out
    except (Unmapped, IndexError, AttributeError) as e:
        reason = str(e) if isinstance(e, Unmapped) else \
            f"could not read the locus in '{reading}'"
        out.update(verdict="SCHEME-UNMAPPED", note=reason)
        if spec.annotate and probes:
            want = None if spec.annotate is True else list(spec.annotate)
            works = corpus.works(spec.corpus, spec.author, want)
            place, _ = best_place(find_hits(probes, works), works,
                                  spec.author, len(probes))
            out["found"] = place
            if not place:
                out["note"] += "; passage not located in the TLG text"
        return out
    out["expected"] = " | ".join(lc.text() for lc in loci)
    if not probes:
        out.update(verdict="NOT-FOUND",
                   note="DK prints no source text after this dash")
        return out
    author = loci[0].author or spec.author
    want = sorted({w for lc in loci for w in (lc.works or [])}) or None
    if any(lc.works is None for lc in loci):
        want = None
    works = corpus.works(spec.corpus, author, want)
    hits = find_hits(probes, works)
    res = evaluate(loci, hits, probes, works, author)
    if res["verdict"] == "NOT-FOUND":
        # Second pass for short or dialect-variant passages (DK's Ionic
        # against the TLG edition's spelling): 12-letter probes. They may
        # confirm the expected locus, but a mismatch needs more of them.
        short = make_probes(normaliser(lang)(passage), SHORT_LEN, SHORT_STEP)
        res2 = evaluate(loci, find_hits(short, works), short, works,
                        author)
        if res2["verdict"] in ("CONFIRMED", "CONFIRMED-PARTIAL", "WEAK"):
            res = res2
            res["note"] = "; ".join(filter(None, [
                f"short probes: {res2['probes_at_locus']} of {len(short)} "
                f"12-letter probes at the locus", res2["note"]]))
        elif res2["verdict"] == "MISMATCH" and \
                res2["probes_at_locus"] == 0 and \
                int(res2["note"].split()[0]) >= SHORT_MISMATCH:
            res = res2
            res["note"] = "short probes: " + res2["note"]
        elif res2["verdict"] == "MISMATCH":
            res["note"] += (f"; short probes: {res2['probes_at_locus']} at "
                            f"the reading's locus, more at {res2['found']}")
        elif "weak" in res2["note"]:
            res["note"] += f"; short probes: {res2['note']}" + (
                f" at {res2['found']}" if res2["found"] else "")
    if res["verdict"] == "NOT-FOUND" and \
            len(normaliser(lang)(passage)) < WORD_PASS_MAX:
        # Third pass for a gloss of a word or two (Pollux and the like):
        # whole words of 6+ letters. It only ever confirms -- almost always
        # WEAK (a single word is far short of PROBE_LEN), by design.
        words = word_probes(passage, lang)
        res3 = evaluate(loci, find_hits(words, works), words, works,
                        author)
        if res3["verdict"] in ("CONFIRMED", "CONFIRMED-PARTIAL", "WEAK"):
            res = res3
            res["note"] = "; ".join(filter(None, [
                f"word probes: {res3['probes_at_locus']} of {len(words)} "
                f"words at the locus", res3["note"]]))
    if res["verdict"] not in ("CONFIRMED", "CONFIRMED-PARTIAL", "WEAK") \
            and spec.fallback:
        fb_author, fb_works = spec.fallback
        fworks = corpus.works(spec.corpus, fb_author, fb_works)
        place, n = best_place(find_hits(probes, fworks), fworks, fb_author,
                              len(probes))
        primary = int(res["note"].split()[0]) if res["verdict"] == \
            "MISMATCH" and res["note"][:1].isdigit() else 0
        if place and n > primary:
            dk_page = re.search(r"\(D\.\s*(\d+)", rec.get("head", ""))
            res = {"verdict": "SCHEME-UNMAPPED", "found": place,
                   "probes_at_locus": 0, "also": [],
                   "note": "not in the Placita; found only in the Stobaeus "
                           "column of Diels' Doxographi, whose pages carry no "
                           "Aëtius chapter numbers"
                           + (f" (DK prints D. {dk_page.group(1)})"
                              if dk_page else "")}
    out.update(res)
    return out


def run(records: list[dict], field_name: str, overrides: dict,
        spines: dict, corpus: Corpus, classes: set[str],
        author_field: str = "source_author") -> list[dict]:
    heads_by_seg = defaultdict(list)
    for r in records:
        heads_by_seg[(r["work"], r["segment"])].append(r.get("head", ""))
    results = []
    for r in records:
        cls = r.get("classification", "")
        if classes and cls not in classes:
            continue
        key2 = f"{r['work']}:{r['segment']}"
        key3 = f"{key2}:{r.get('head', '')}"
        reading = overrides.get(key3, overrides.get(key2, r.get(field_name)))
        seg_text = spines.get((r["work"], r["segment"]), "")
        passage = passage_for(seg_text, r.get("head", ""),
                              heads_by_seg[(r["work"], r["segment"])])
        spec = SOURCES.get(r.get(author_field, ""))
        t0 = time.time()
        v = verify(r, reading or "", spec, passage, corpus)
        results.append({
            "work": r["work"], "segment": r["segment"],
            "head": r.get("head", ""), "classification": cls,
            "source_author": r.get(author_field, ""),
            "reading": reading, "overridden": reading != r.get(field_name),
            "group": "unclear" if cls == "UNCLEAR" else "main",
            **v, "seconds": round(time.time() - t0, 2)})
    return results


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def summary_md(results: list[dict], elapsed: float, source: str) -> str:
    lines = ["# DK dash citations checked against the TLG/PHI",
             "", f"Readings: `{source}`. {len(results)} records; run took "
             f"{elapsed:.0f} s. Corpus text is not quoted here; each locus is "
             "the TLG/PHI's own citation.", ""]
    for grp, title in (("main", "FITS, FITS-BUT-NO-LOCUS, MISFIT"),
                       ("unclear", "UNCLEAR (survey's best reading)")):
        rs = [r for r in results if r["group"] == grp]
        if not rs:
            continue
        lines += [f"## {title}: verdicts by source author", "",
                  "| Source | " + " | ".join(VERDICTS) + " | Total |",
                  "|---|" + "---:|" * (len(VERDICTS) + 1)]
        by = defaultdict(Counter)
        for r in rs:
            by[r["source_author"]][r["verdict"]] += 1
        tot = Counter()
        for a in sorted(by, key=lambda a: -sum(by[a].values())):
            c = by[a]
            tot.update(c)
            lines.append(f"| {a} | " + " | ".join(
                str(c[v] or "") for v in VERDICTS) + f" | {sum(c.values())} |")
        lines.append("| **All** | " + " | ".join(
            f"**{tot[v]}**" for v in VERDICTS) + f" | **{sum(tot.values())}** |")
        lines.append("")
    for verdict in ("MISMATCH", "NOT-FOUND", "SCHEME-UNMAPPED",
                    "NOT-IN-CORPUS"):
        rs = [r for r in results if r["verdict"] == verdict]
        if not rs:
            continue
        lines += [f"## {verdict} ({len(rs)})", ""]
        if verdict in ("SCHEME-UNMAPPED", "NOT-IN-CORPUS"):
            reasons = defaultdict(list)
            for r in rs:
                reasons[(r["source_author"],
                         re.sub(r"'.*?'", "…", r["note"]))].append(r)
            for (a, note), group in sorted(reasons.items()):
                ids = ", ".join(f"{r['work']} {r['segment']}" for r in group)
                lines.append(f"- **{a}** ({len(group)}): {note}. {ids}")
                for r in group:
                    if r.get("found"):
                        lines.append(f"  - {r['work']} {r['segment']} "
                                     f"`{r['reading']}` → found at "
                                     f"{r['found']}")
            lines.append("")
            continue
        lines += ["| Work | Frag. | DK head | Reading | Found | Note |",
                  "|---|---|---|---|---|---|"]
        for r in rs:
            tag = " (UNCLEAR)" if r["group"] == "unclear" else ""
            lines.append(
                f"| {r['work']} | {r['segment']}{tag} | "
                f"`{r['head'][:30]}` | {r['reading']} | {r['found']} | "
                f"{r['note']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--readings", required=True, type=Path)
    ap.add_argument("--reading-field", default="resolved")
    ap.add_argument("--author-field", default="source_author")
    ap.add_argument("--spines", type=Path, default=REPO / "build" / "dk-spines")
    ap.add_argument("--overrides", type=Path)
    ap.add_argument("--classes", default="FITS,FITS-BUT-NO-LOCUS,MISFIT,UNCLEAR")
    ap.add_argument("--cache", type=Path,
                    default=REPO / "build" / "dash-verify" / "cache")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--only-author",
                    help="restrict to these source authors (comma-separated)")
    a = ap.parse_args(argv)
    records = json.loads(a.readings.read_text())
    if a.only_author:
        keep = set(a.only_author.split(","))
        records = [r for r in records if r.get(a.author_field) in keep]
    overrides = json.loads(a.overrides.read_text()) if a.overrides else {}
    spines = load_spines(a.spines)
    t0 = time.time()
    results = run(records, a.reading_field, overrides, spines,
                  Corpus(a.cache), set(filter(None, a.classes.split(","))),
                  a.author_field)
    elapsed = time.time() - t0
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "verdicts.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1))
    (a.out_dir / "summary.md").write_text(
        summary_md(results, elapsed, str(a.readings)))
    print(json.dumps(Counter(r["verdict"] for r in results)),
          f"{elapsed:.0f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
