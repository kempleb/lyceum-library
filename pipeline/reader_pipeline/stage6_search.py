"""Stage 6: build the search index for the Astro frontend.

Emits these files under build/stage6/ (source-language-neutral names, per
docs/wave2-latin-design.md §2/§6 — the index is a "source-language index vs
english.json" axis, not a Greek-only one):

  lemma.json — {fold(key, language): [[seg_idx, token_pos], ...]}
                 keyed by the token's dictionary HEADWORD (lemma), so a query
                 finds every inflected form of a word. fold() strips all
                 accents/marks (Greek: Beta Code diacritics; Latin: unifies
                 u/v and i/j — see fold() below), so wildcard prefix matching
                 works uniformly.

  form.json  — {fold(surface, language): [[seg_idx, token_pos], ...]}
                 keyed by the SURFACE form as written (the inflected token), so
                 a query can match the exact form rather than the whole lemma.

  english.json — {word: [seg_idx, ...]}
                 Lowercased, punctuation-stripped English words.
                 Phrase search is handled at query time via string inclusion
                 on the (small) English chunk texts in meta.json, so
                 positions are not stored here.

  meta.json    — [{id, book, column, head, tokens, english_head}]
                 Ordered list of segment metadata, indexed by seg_idx.
                 head: first line of text (for result preview).
                 tokens: space-joined fold token sequence (phrase search).
                 english_head: the FULL English chunk (name is legacy). Query
                   time uses it for exact-phrase verification and English
                   occurrence counting, so it must not be truncated.

  form_lemmata.json — {fold(surface, language): [fold(headword, language), ...]}
                 Surface-form -> headword(s) map, so the client's Lemma mode
                 (which today only matches a typed HEADWORD, since it looks
                 the folded query straight up in lemma.json — John, 2026-09-23
                 ruling) can also resolve a typed PRINTED FORM to the
                 headword(s) it inflects from and union their lemma.json
                 postings. Kept small: an entry exists only for a surface
                 fold that differs from EVERY headword it maps to — a form
                 whose fold already equals one of its own headwords needs no
                 entry, since the direct lemma.json lookup already covers it.
                 An ambiguous surface form (one whose token carries more than
                 one analysis with different lemmata) lists every headword.

All five files are copied to build/dist/<work>/search/ by stage7.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import latin as latin_mod
from .config import BUILD_DIR, Manifest

_FOLD = re.compile(r"[^a-z']")  # keep only base letters and apostrophe
_EN_WORD = re.compile(r"[a-z']+")


def fold_lemma(beta_key: str) -> str:
    """Strip all Beta Code diacritics; keep only base letters + apostrophe.
    Greek-specific — dispatched to via fold() below; Latin has its own fold
    (latin.fold) with different rules (u/v and i/j unification, memo §4.1)."""
    return _FOLD.sub("", beta_key.lower())


def fold(key: str, language: str) -> str:
    """Per-language search-fold dispatch (memo §2: generic index filenames
    and segment fields, but per-language fold functions). An unrecognized
    language raises rather than silently defaulting to the Greek fold (the
    same fail-loud posture as stage3's tokenize() and stage4's
    _analyses_path for an unsupported work.language)."""
    if language == "lat":
        return latin_mod.fold(key)
    if language == "grc":
        return fold_lemma(key)
    raise ValueError(f"unsupported language: {language!r}")


def run(manifest: Manifest) -> Path:
    language = manifest.language
    tokens_doc = json.loads(
        (BUILD_DIR / "stage3" / "tokens.json").read_text(encoding="utf-8")
    )
    key_map = json.loads(
        (BUILD_DIR / "stage4" / "key_map.json").read_text(encoding="utf-8")
    )
    analyses = json.loads(
        (BUILD_DIR / "stage4" / "analyses.json").read_text(encoding="utf-8")
    )
    # A genuinely Greek-only work (see stage7_emit.run's matching fallback)
    # has no english_chunks.json at all.
    english_path = BUILD_DIR / "stage1" / "english_chunks.json"
    english = (json.loads(english_path.read_text(encoding="utf-8"))
               if english_path.exists() else {"chunks": []})

    # Ordered segment list for index keys
    segments = tokens_doc["segments"]
    seg_idx = {s["id"]: i for i, s in enumerate(segments)}

    eng_by_id = {c["id"]: c for c in english["chunks"]}

    # Token fold sequences per segment — needed by the client for phrase search.
    # One space-separated string of fold lemma keys in document order.
    fold_seq_by_id: dict[str, str] = {}
    for seg in segments:
        folds = []
        for line in seg["lines"]:
            for tok in line["tokens"]:
                key = tok.get("k")
                stored = key_map.get(key) if key else None
                if stored:
                    lemmata = [a["lemma"] for a in analyses.get(stored, []) if a["lemma"]]
                    if lemmata:
                        folds.append(fold(lemmata[0], language))
                    else:
                        folds.append(fold(stored, language))
                elif key:
                    folds.append(fold(key, language))
        fold_seq_by_id[seg["id"]] = " ".join(folds)

    # -- Source-language inverted indexes -------------------------------------
    # Two parallel indexes, both fold(key, language) -> [(seg_idx, token_pos), ...]:
    #   lemma_posts: keyed by each token's dictionary headword(s) — "all forms".
    #   form_posts:  keyed by the token's surface form as written — "exact form".
    # form_lemmata: surface fold -> the set of headword folds it maps to (see
    #   the module docstring's form_lemmata.json entry) — built in the same
    #   pass since it needs each token's sf/fl pair together.
    lemma_posts: dict[str, list] = defaultdict(list)
    form_posts: dict[str, list] = defaultdict(list)
    form_lemmata: dict[str, set] = defaultdict(set)
    for seg in segments:
        si = seg_idx[seg["id"]]
        pos = 0
        for line in seg["lines"]:
            for tok in line["tokens"]:
                key = tok.get("k")
                sf = None
                if key:
                    sf = fold(key, language)  # surface form as written
                    if sf:
                        form_posts[sf].append([si, pos])
                stored = key_map.get(key) if key else None
                if stored:
                    for a in analyses.get(stored, []):
                        fl = fold(a["lemma"], language) if a["lemma"] else fold(stored, language)
                        if fl:
                            lemma_posts[fl].append([si, pos])
                            if sf:
                                form_lemmata[sf].add(fl)
                pos += 1

    # Deduplicate each index (a lemma may repeat from homonym analyses; a
    # surface key is added once per token but dedupe defensively).
    def _dedupe(posts: dict[str, list]) -> dict[str, list]:
        out: dict[str, list] = {}
        for fl, plist in posts.items():
            seen: set[tuple] = set()
            deduped = []
            for pair in plist:
                t = tuple(pair)
                if t not in seen:
                    seen.add(t)
                    deduped.append(pair)
            out[fl] = deduped
        return out

    lemma_idx = _dedupe(lemma_posts)
    form_idx = _dedupe(form_posts)

    # Keep form_lemmata.json small: an entry only for a surface fold that
    # differs from EVERY headword it maps to (module docstring). Values are
    # sorted for deterministic output; dict insertion order (first-seen
    # surface fold, document order) is left as-is, matching the other
    # indexes' style.
    #
    # HEADWORD PRECEDENCE (John, 2026-09-23 ruling item 2 — enforced on the
    # CLIENT side, shared/lib/search.ts's resolveFold): a surface fold can
    # coincidentally collide with an unrelated headword's own key (e.g.
    # Heraclitus "hmera" is itself a lemma.json headword AND is separately
    # listed here as a printed form of "hmeros"). This omission rule only
    # drops an entry that maps to ITSELF; it does not and should not try to
    # detect that cross-word collision here, because the client already
    # knows, at query time, whether the typed fold is a lemma.json key — if
    # so, it uses the direct lookup and never consults this map at all.
    form_lemmata_idx = {
        sf: sorted(lemmata)
        for sf, lemmata in form_lemmata.items()
        if sf not in lemmata
    }

    # -- English inverted index -----------------------------------------------
    # word -> sorted list of unique seg_idxs
    eng_posts: dict[str, set] = defaultdict(set)
    for seg in segments:
        eng = eng_by_id.get(seg["id"])
        if not eng:
            continue
        si = seg_idx[seg["id"]]
        for word in _EN_WORD.findall(eng["text"].lower()):
            eng_posts[word].add(si)
    english_idx = {w: sorted(idxs) for w, idxs in eng_posts.items()}

    # -- Segment metadata -----------------------------------------------------
    meta = []
    for seg in segments:
        # head: join first two lines of surface text
        lines = seg["lines"]
        head = " ".join(
            " ".join(t["t"] for t in l["tokens"])
            for l in lines[:2]
        )
        eng = eng_by_id.get(seg["id"])
        # Full English chunk (NOT truncated). Query-time exact-phrase
        # verification and English occurrence counting run against this, so a
        # cap (formerly [:500]) silently dropped matches and undercounted
        # repeats past the cut. It equals the emitted segment's english.text, so
        # char offsets found here map straight onto the rendered passage.
        english_head = eng["text"] if eng else ""
        meta.append(
            {
                "id": seg["id"],
                "book": seg["book"],
                "column": seg["column"],
                "head": head,
                "tokens": fold_seq_by_id.get(seg["id"], ""),
                "english_head": english_head,
            }
        )

    out_dir = BUILD_DIR / "stage6"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lemma.json").write_text(
        json.dumps(lemma_idx, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "form.json").write_text(
        json.dumps(form_idx, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "english.json").write_text(
        json.dumps(english_idx, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (out_dir / "form_lemmata.json").write_text(
        json.dumps(form_lemmata_idx, ensure_ascii=False), encoding="utf-8"
    )
    summary = {
        "lemmata": len(lemma_idx),
        "forms": len(form_idx),
        "english_terms": len(english_idx),
        "segments": len(meta),
        "form_lemmata": len(form_lemmata_idx),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return out_dir
