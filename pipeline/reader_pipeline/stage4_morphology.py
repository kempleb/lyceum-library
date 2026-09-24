"""Stage 4: morphological analyses for every corpus token.

Single targeted pass over Diogenes' greek-analyses.txt (115MB) or
latin-analyses.txt (Wave 2): only lines whose key is needed by some corpus
token are parsed and kept — the file is never loaded wholesale. All homonym
candidates are retained.

Keys prefixed '!' in the data (352 of ~950k) are Morpheus artifacts that
Diogenes' own query normalization can never produce; they are ignored.
(Confirmed Greek-only via a full-file grep; irrelevant to Latin.)

Unmatched tokens land in build/stage4/unmatched.json — the reviewable patch
file (expected ~2-5% of distinct forms).

Latin wiring (docs/wave2-latin-design.md §4, §6): latin-analyses.txt's
brace-group format is CONFIRMED identical to Greek's (verified read-only
against the real Diogenes file at
/Applications/Diogenes.app/Contents/dependencies/data/latin-analyses.txt —
same `{lemma_id flag form,lemma\tgloss\tparse}` shape, `parse_analysis_line`
below is reused unchanged). Diogenes' own Morpheus already resolves most
enclitic-suffixed forms as their own top-level keys (e.g. "virumque" and
"virtusque" are real keys in the file, each carrying full analyses) — the
`latin.lookup_variants` enclitic split (§4.1) is offered purely as a
FALLBACK candidate, tried only when the whole form itself is not a key,
exactly mirroring how Greek's diaeresis/capital variants are tried after the
exact key.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import latin as latin_mod
from .beta import lookup_variants as beta_lookup_variants
from .config import BUILD_DIR, Manifest

# The digit after the lemma id is a Morpheus flag (9 for ordinary words,
# 0/1 for proper names and rarities); proper-name groups also omit the
# "form," prefix and carry a blank gloss.
_GROUP = re.compile(r"\{(\d+) \d+ ([^\t}]*)\t([^\t}]*)\t([^}]*)\}")

# Morphological-analyses source file per work.language, resolved under
# manifest.diogenes_data(). Both 'grc' (Morpheus via Diogenes) and 'lat'
# (Wave 2) are wired up.
_ANALYSES_FILENAMES = {"grc": "greek-analyses.txt", "lat": "latin-analyses.txt"}

# A Beta Code key derived from an all-capitals Greek surface has no accent or
# breathing marks.  Keep the capital marker in this strip too: Morpheus uses
# it for capitalized forms, while token keys are lowercase.
_BETA_DIACRITICS = re.compile(r"[/\\=()|*]")


def _analyses_path(manifest: Manifest) -> Path:
    language = manifest.language
    if language not in _ANALYSES_FILENAMES:
        raise ValueError(f"unsupported work.language: {language!r}")
    return manifest.diogenes_data() / _ANALYSES_FILENAMES[language]


def _lookup_variants(language: str, key: str, capitalized: bool) -> list[str]:
    """Per-language analyses-key candidate list, in order (whole form first).
    Greek dispatches to beta.lookup_variants (diaeresis expansion + capital
    '*'-prefixed forms); Latin dispatches to latin.lookup_variants (enclitic
    -que/-ne/-ve split, then -- gated on `capitalized`, same as Greek --
    latin-analyses.txt's own capitalized-proper-name form: "Cicero",
    "Panaetio", "Athenis". Wave 2 Batch 1b review finding, item 2: Latin
    proper names USED TO carry no separate capital-key namespace here
    (to_latin_key always lowercases, memo §4.1), so every one of them
    missed until this fallback was wired up."""
    if language == "lat":
        return latin_mod.lookup_variants(key, capitalized)
    return beta_lookup_variants(key, capitalized)


def parse_analysis_line(value: str) -> list[dict]:
    out = []
    for lemma_id, form_lemma, gloss, parse in _GROUP.findall(value):
        form, comma, lemma = form_lemma.partition(",")
        if not comma:
            lemma = form
        out.append(
            {
                "lemma_id": int(lemma_id),
                "form": form,
                "lemma": lemma,
                "gloss": gloss,
                "parse": parse,
            }
        )
    return out


def collect_needed_keys(
    tokens_doc: dict, language: str = "grc"
) -> tuple[set[str], Counter, dict]:
    """All candidate analyses keys, token-key frequencies, and sample refs."""
    freq: Counter = Counter()
    samples: dict[str, dict] = {}
    for seg in tokens_doc["segments"]:
        for line in seg["lines"]:
            for tok in line["tokens"]:
                key = tok.get("k")
                if key is None:
                    continue
                freq[key] += 1
                capitalized = tok["t"][:1].isupper()
                if key not in samples:
                    samples[key] = {
                        "surface": tok["t"],
                        "ref": f"{seg['column']}{line['n']}",
                        "capitalized": capitalized,
                    }
                elif capitalized:
                    samples[key]["capitalized"] = True
    needed: set[str] = set()
    for key in freq:
        needed.update(_lookup_variants(language, key, samples[key]["capitalized"]))
    return needed, freq, samples


def _fold_beta_key(key: str) -> str:
    """Return the case-insensitive, accent/breathing-free Beta Code key."""
    return _BETA_DIACRITICS.sub("", key).casefold()


def _is_unaccented_beta_key(key: str) -> bool:
    return not _BETA_DIACRITICS.search(key)


def scan_analyses(
    path: Path, needed: set[str], fold_targets: set[str] | None = None
) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """Stream the morphology source for exact and all-caps fallback matches.

    ``fold_targets`` contains unaccented token keys.  The source is the
    widest morphology table available in this stage, so retain every accented
    source key that folds to each target rather than only the forms otherwise
    seen in this work.
    """
    found: dict[str, list[dict]] = {}
    folded: dict[str, list[dict]] = {key: [] for key in fold_targets or set()}
    folded_seen: dict[str, set[tuple]] = {key: set() for key in folded}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            key, _, value = line.partition("\t")
            folded_key = _fold_beta_key(key)
            if key not in needed and folded_key not in folded:
                continue
            parsed = parse_analysis_line(value)
            if key in needed:
                found[key] = parsed
            if folded_key in folded:
                for analysis in parsed:
                    # Morpheus repeats the same reading under orthographic
                    # variants (for example pe/ri and peri/).  ``form`` can
                    # differ even though the lemma id and emitted analysis
                    # are identical, so deduplicate on the semantic fields.
                    identity = (
                        analysis["lemma_id"],
                        analysis["lemma"],
                        analysis["gloss"],
                        analysis["parse"],
                    )
                    if identity not in folded_seen[folded_key]:
                        folded_seen[folded_key].add(identity)
                        folded[folded_key].append(analysis)
    return found, folded


def run(manifest: Manifest) -> Path:
    language = manifest.language
    tokens_doc = json.loads(
        (BUILD_DIR / "stage3" / "tokens.json").read_text(encoding="utf-8")
    )
    needed, freq, samples = collect_needed_keys(tokens_doc, language)
    # A no-lexicon work (`work.lexicon: false`, Wave 2 §4.2) has no token
    # carrying `k` at all, so `needed` is legitimately empty here — skip the
    # (multi-hundred-MB) analyses-file scan entirely rather than opening it
    # to match nothing.
    #
    # Blocker 1 fix (Sol): a LEXICON-ON work (`manifest.lexicon` — the
    # default) with zero keyed tokens is NOT the same shape as a declared
    # no-lexicon work — it's the old ZeroDivisionError symptom in disguise
    # (every token failed to key, or stage3's lexical gate silently produced
    # no keys at all for this language). The old `if needed` guard failed
    # OPEN for this case: it couldn't tell "declared no-lexicon" from
    # "lexicon-on but broken" apart, so a genuine extraction/tokenizer bug
    # would silently emit the same trivial-but-valid empty artifact a
    # legitimate no-lexicon work produces, with token_match_rate quietly
    # reported as `None` instead of failing the build. Fail loudly instead —
    # a genuine no-lexicon work must declare `work.lexicon: false`.
    if not manifest.lexicon:
        found = {}
    elif not needed:
        raise ValueError(
            f"{manifest.work_id}: work.lexicon is true but stage3 emitted "
            f"zero keyed tokens (work.language={language!r}) — either the "
            f"corpus text is empty or stage3's lexical gate is "
            f"misconfigured for this language; a genuine no-lexicon work "
            f"must declare work.lexicon: false instead of silently "
            f"producing no keys"
        )
    else:
        # The ordinary lookup remains exact/variant-first.  In the same
        # streaming pass, collect every accented source-table reading for
        # unaccented keys so an all-caps token can fall back only if ordinary
        # resolution fails below.
        fold_targets = {
            key for key in freq
            if language == "grc" and _is_unaccented_beta_key(key)
        }
        found, folded_matches = scan_analyses(
            _analyses_path(manifest), needed, fold_targets
        )

    if not manifest.lexicon:
        folded_matches = {}

    # Hand-reviewed overrides for forms Morpheus doesn't know (letter
    # labels in the Book V proportions, odd compounds).
    patch_path = manifest.path.parent / f"{manifest.work_id}-analyses-patch.json"
    patches: dict[str, list] = {}
    if patch_path.exists():
        patches = json.loads(patch_path.read_text(encoding="utf-8"))
        found.update({k: v for k, v in patches.items() if v})

    # Resolve each token key to the first variant with an analysis.
    resolved: dict[str, str] = {}
    unmatched: list[dict] = []
    for key, count in freq.most_common():
        hit = next(
            (
                v
                for v in _lookup_variants(language, key, samples[key]["capitalized"])
                if v in found
            ),
            None,
        )
        if hit is not None:
            resolved[key] = hit
        elif key in folded_matches and folded_matches[key]:
            # An all-caps token cannot attest one particular accentuation.
            # Ship every full-source-table match, marked for the reader UI;
            # never collapse a genuine homograph to one preferred reading.
            found[key] = [
                {**analysis, "foldedAccent": True}
                for analysis in folded_matches[key]
            ]
            resolved[key] = key
        else:
            unmatched.append(
                {
                    "key": key,
                    "surface": samples[key]["surface"],
                    "first_ref": samples[key]["ref"],
                    "count": count,
                    "analyses": [],  # patch slot: fill by hand to override
                }
            )

    analyses_out = {v: found[v] for v in sorted(set(resolved.values()))}
    out_dir = BUILD_DIR / "stage4"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "analyses.json"
    out.write_text(json.dumps(analyses_out, ensure_ascii=False), encoding="utf-8")
    (out_dir / "key_map.json").write_text(
        json.dumps(resolved, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "unmatched.json").write_text(
        json.dumps(unmatched, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    n_tokens = sum(freq.values())
    n_unmatched_tokens = sum(u["count"] for u in unmatched)
    summary = {
        "distinct_keys": len(freq),
        "distinct_matched": len(resolved),
        "distinct_unmatched": len(unmatched),
        "token_count": n_tokens,
        "tokens_unmatched": n_unmatched_tokens,
        # A declared no-lexicon work (see the `manifest.lexicon` branch
        # above) has zero keyed tokens -- n_tokens is legitimately 0, so the
        # rate is undefined rather than a ZeroDivisionError. A lexicon-on
        # work with n_tokens == 0 can no longer reach here at all -- the
        # branch above raises first -- so this `if n_tokens` no longer masks
        # that failure mode; it only ever fires for the legitimate case.
        "token_match_rate": round(1 - n_unmatched_tokens / n_tokens, 4) if n_tokens else None,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return out
