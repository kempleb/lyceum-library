"""Stage 2: validation of the Stage 1 spine, chunks, and alignment.

Checks:
  1. Column completeness and monotonic order across 1094a-1181b.
  2. Line-number gaps inside columns (book-boundary gaps are expected and
     verified against the manifest; anything else is flagged).
  3. Alignment coverage in both directions.
  4. Greek/English length-ratio outliers (> 1.5 SD from the mean ratio).
  5. Proper-name spot check: names that should co-occur in the same column
     in both languages.
  6. Sigla/character inventory of the Greek text: every non-Greek,
     non-expected character with counts and sample locations.

Emits build/stage2/validation_report.json and .md (human-readable).
"""

from __future__ import annotations

import json
import hashlib
import math
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import scheme as scheme_mod
from .config import BUILD_DIR, Manifest
from .refs import column_key, column_range, ref_key
from .stage3_tokenize import _SPINE_FILENAMES

def _base(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()

# Characters we expect in Bywater's text besides Greek letters.
EXPECTED_NON_GREEK = set(" .,·;'’ʼ—-()[]")


def _is_greek_letter(ch: str) -> bool:
    if not ch.isalpha():
        return False
    try:
        return "GREEK" in unicodedata.name(ch)
    except ValueError:
        return False


def _omit_declared_segment_ids(manifest: Manifest, segments: list[dict]) -> set[str]:
    """Segment ids whose column carries a `kind: "omit"` disposition in the
    manifest's own `citation.kind_overrides` (John's ruling 2026-07-23:
    "where she has no greek, we leave out" -- design note
    docs/freeman-wave-design.md §1(b)). `stage1_freeman_english.build_english`
    skips these columns entirely (no English chunk emitted), so
    `build_alignment` correctly reports them unmatched -- this derives the
    alignment allowance from that SAME declaration rather than a parallel,
    hand-maintained list, so a manifest that adds/removes an omit ruling
    never needs a second edit here to keep stage2 in sync."""
    overrides = (manifest.data.get("citation") or {}).get("kind_overrides")
    if not isinstance(overrides, dict):
        return set()
    omit_columns = {
        col for col, decl in overrides.items()
        if isinstance(decl, dict) and decl.get("kind") == "omit"
    }
    if not omit_columns:
        return set()
    return {seg["id"] for seg in segments if seg["column"] in omit_columns}


def _summary_suppressed_segment_ids(manifest: Manifest, segments: list[dict]) -> set[str]:
    """Segment ids named in the manifest's own `english.summary_suppressed`
    (John's ruling 2026-07-29: a Freeman précis already covered by a
    translated context-english source-passage span ships no Freeman English
    chunk at all -- see stage1_freeman_english.py gate 5).
    `stage1_freeman_english.build_english` skips these columns entirely, so
    `build_alignment` correctly reports them unmatched -- this derives the
    alignment allowance from that SAME declaration, same posture as
    `_omit_declared_segment_ids` above, rather than a second hand-maintained
    list."""
    suppressed = (manifest.data.get("english") or {}).get("summary_suppressed")
    if not isinstance(suppressed, list) or not suppressed:
        return set()
    columns = set(suppressed)
    return {seg["id"] for seg in segments if seg["column"] in columns}


def validate(manifest: Manifest, spine: dict, english: dict, alignment: dict) -> dict:
    report: dict = {"checks": {}}
    segments = spine["segments"]
    # Dispatch structural rules on the citation scheme instead of ad-hoc string
    # tests. "observed" schemes (busse, stephanus) carry irregular, per-work
    # column spans whose page numbers are not globally unique and whose interior
    # pages are not guaranteed to hold every section letter, so their expected
    # column set is the OBSERVED spine, never a rectangular page x side range;
    # editorial line-number gaps on those schemes are demoted (not failures).
    sch = scheme_mod.for_manifest(manifest)
    observed = sch.validation_mode == "observed"

    # --- 1. column completeness + monotonicity --------------------------
    seen_cols: list[str] = []
    for seg in segments:
        if seg["column"] not in seen_cols:
            seen_cols.append(seg["column"])
    expected = list(seen_cols) if observed else column_range(
        manifest.first_column, manifest.last_column, sch.range_sides)
    missing = sorted(set(expected) - set(seen_cols), key=lambda c: column_key(c, sch))
    extra = sorted(set(seen_cols) - set(expected), key=lambda c: column_key(c, sch))
    keys = [column_key(c, sch) for c in seen_cols]
    monotonic = all(a <= b for a, b in zip(keys, keys[1:]))
    # verse-line (Lucretius' DRN) is DELIBERATELY non-monotonic in document
    # order — editors reprint transposed blocks under their original line
    # numbers (design memo §3.3), so document order != citation order by
    # design, not defect. stage1_latin's own parse-time gate
    # (`_derive_transposed_blocks` vs. the manifest's declared
    # `citation.transpositions`) is the real drift tripwire for this;
    # citation-order monotonicity is instead asserted post-sort, against the
    # emitted dist data, by preflight's verse-line gate. `monotonic` is still
    # reported here for information, just not gated on.
    report["checks"]["columns"] = {
        "expected": len(expected),
        "found": len(seen_cols),
        "missing": missing,
        "extra": extra,
        "monotonic": monotonic,
        "ok": not missing and not extra and (monotonic or sch.verse_line_scheme),
    }

    # --- 1b. section-token order (observed schemes only) ----------------
    # The spine's columns must be STRICTLY increasing in ref order (17e before
    # 18a). Missing letters within a page or skipped pages are legal (works
    # start/end mid-page; interior pages need not carry every letter) and are
    # reported as info, honouring manifest-declared `expected_section_gaps`.
    # Skipped for a dk (Diels-Kranz) scheme: its column_key is a 3-tuple
    # (series, number, suffix), not the 2-tuple (page, letter) this
    # page/letter-contiguity check is shaped for, and dk's numbering has
    # real, EXPECTED non-contiguous gaps throughout (declared deletions like
    # B84/B109, not just at page boundaries) — the section_spine count+sha256
    # fingerprint immediately below (1c) is dk's actual completeness+order
    # gate (memo gate 2).
    # Skipped for verse-line the same way dk is skipped just below (and for
    # the same reason): this check assumes a (page, letter)-axis grammar —
    # verse-line's second component is a richer (number, suffix)/range
    # lineref with EXPECTED non-contiguous jumps (the transposed blocks
    # above), not a defect this page/letter-contiguity check is shaped to
    # describe.
    # `declared_gaps` is manifest data, not scheme-shaped, and is also needed
    # by the section_spine diagnostic below (1c) for fragment/verse-line
    # schemes (dk's "real, EXPECTED non-contiguous gaps" the comment above
    # describes) -- so it is computed unconditionally, unlike `letter_ix`
    # (below), which only makes sense for a genuine letter-axis scheme.
    declared_gaps = {
        (g["after"], g["next"])
        for g in manifest.data.get("expected_section_gaps", [])
        if isinstance(g, dict) and {"after", "next"} <= g.keys()
    }
    if observed and not sch.fragment_scheme and not sch.verse_line_scheme:
        letter_ix = {ch: i for i, ch in enumerate(sch.section_letters)}
        strictly_increasing = all(a < b for a, b in zip(keys, keys[1:]))
        section_gaps: list[dict] = []
        for (c_prev, k_prev), (c_next, k_next) in zip(
            zip(seen_cols, keys), zip(seen_cols[1:], keys[1:])
        ):
            (p0, l0), (p1, l1) = k_prev, k_next
            if sch.numeric_section:
                # book-section: sections are consecutive integers within a book
                # ("4.9" -> "4.10"), and any section starts the next book.
                contiguous = (p0 == p1 and l1 == l0 + 1) or (p1 == p0 + 1)
            else:
                contiguous = (
                    (p0 == p1 and letter_ix.get(l1, -99) == letter_ix.get(l0, -1) + 1)
                    or (p1 == p0 + 1)  # advancing to the next page is normal
                )
            if not contiguous:
                section_gaps.append({
                    "after": c_prev,
                    "next": c_next,
                    "expected": (c_prev, c_next) in declared_gaps,
                })
        report["checks"]["section_order"] = {
            "strictly_increasing": strictly_increasing,
            "gaps": section_gaps,  # informational
            "ok": strictly_increasing,
        }

    # --- 1c. immutable observed-section baseline -----------------------
    # Stephanus exports are irregular, so a rectangular range cannot establish
    # completeness.  Instead, compare the ordered section-token spine with the
    # verified per-work manifest fingerprint captured from stage 1.
    if sch.has_sections:
        baseline = manifest.data.get("section_spine") or {}
        expected_count = baseline.get("count")
        expected_sha256 = baseline.get("sha256")
        got_count = len(seen_cols)
        got_sha256 = hashlib.sha256(",".join(seen_cols).encode("utf-8")).hexdigest()
        count_ok = isinstance(expected_count, int) and got_count == expected_count
        hash_ok = (
            isinstance(expected_sha256, str)
            and len(expected_sha256) == 64
            and got_sha256 == expected_sha256.lower()
        )
        first_ok = bool(seen_cols) and seen_cols[0] == manifest.first_column
        last_ok = bool(seen_cols) and seen_cols[-1] == manifest.last_column

        first_diverging = None
        if not count_ok:
            # A digest-only baseline intentionally does not duplicate the full
            # token list. Pinpoint the first structurally suspicious observed
            # token: an undeclared within-page jump (the common deletion case),
            # or the first/last token when the boundary itself moved.
            if not first_ok and seen_cols:
                first_diverging = {"index": 0, "token": seen_cols[0]}
            else:
                for i, ((prev, pkey), (nxt, nkey)) in enumerate(
                    zip(zip(seen_cols, keys), zip(seen_cols[1:], keys[1:])), 1
                ):
                    if sch.numeric_section or sch.fragment_scheme:
                        # dk's column_key is a (series, number, suffix) triple
                        # (refs.py's column_key) — no letter axis, so its
                        # second component is already an int, same as
                        # numeric_section's, and the int-jump comparison below
                        # is meaningful for it too. `letter_ix` (built above
                        # only for genuine letter schemes) is never populated
                        # for dk, so this branch must not fall to the `else`.
                        same_page_jump = pkey[0] == nkey[0] and nkey[1] > pkey[1] + 1
                    else:
                        same_page_jump = (
                            pkey[0] == nkey[0]
                            and letter_ix.get(nkey[1], -99) > letter_ix.get(pkey[1], -1) + 1
                        )
                    if same_page_jump and (prev, nxt) not in declared_gaps:
                        first_diverging = {"index": i, "token": nxt, "after": prev}
                        break
                if first_diverging is None and seen_cols:
                    i = min(got_count, expected_count or got_count) - 1
                    first_diverging = {"index": max(i, 0), "token": seen_cols[max(i, 0)]}

        report["checks"]["section_spine"] = {
            "expected": {"count": expected_count, "sha256": expected_sha256},
            "got": {"count": got_count, "sha256": got_sha256},
            "count_match": count_ok,
            "hash_match": hash_ok,
            "first_column": {"expected": manifest.first_column,
                             "got": seen_cols[0] if seen_cols else None,
                             "ok": first_ok},
            "last_column": {"expected": manifest.last_column,
                            "got": seen_cols[-1] if seen_cols else None,
                            "ok": last_ok},
            "first_diverging_token": first_diverging,
            "ok": count_ok and hash_ok and first_ok and last_ok,
        }

    # --- 1d. book partition (section schemes) ---------------------------
    # The declared books MUST partition the observed spine: ordered and
    # non-overlapping by (page, letter), and every observed section falls in
    # exactly one book. A section outside every declared range is an ERROR (the
    # book table is missing coverage); a section claimed by two ranges means the
    # ranges overlap. Bekker/busse books are handled by the line-gap check.
    if sch.has_sections:
        from .refs import column_prefix_key

        ranges = [
            (b["n"], column_prefix_key(b["start"], sch), column_prefix_key(b["end"], sch))
            for b in manifest.books
        ]
        within = all(s <= e for _, s, e in ranges)
        ordered = all(a[2] < b[1] for a, b in zip(ranges, ranges[1:]))
        outside: list[str] = []
        overlapping: list[str] = []
        for col in seen_cols:
            k = column_prefix_key(col, sch)
            hits = [n for n, s, e in ranges if s <= k <= e]
            if not hits:
                outside.append(col)
            elif len(hits) > 1:
                overlapping.append(col)
        report["checks"]["book_partition"] = {
            "books": len(ranges),
            "ordered_non_overlapping": within and ordered,
            "sections_outside_any_book": outside,
            "sections_in_multiple_books": overlapping,
            "ok": within and ordered and not outside and not overlapping,
        }

    # --- 2. line-number gaps ---------------------------------------------
    # Expected gaps: between one book's end and the next book's start when
    # they share a column (Bekker numbering skips the heading lines). Only
    # line-bearing schemes declare book boundaries with a line number; section
    # schemes (stephanus) bound books by a page+letter column and demote all
    # intra-column line gaps below, so their book table is skipped here.
    expected_gaps = set()
    books = manifest.books
    if not observed:
        for prev, nxt in zip(books, books[1:]):
            e_page, e_side, e_line = ref_key(prev["end"])
            s_page, s_side, s_line = ref_key(nxt["start"])
            if (e_page, e_side) == (s_page, s_side):
                expected_gaps.add((f"{e_page}{e_side}", e_line, s_line))
    # Edition quirks declared in the manifest (e.g. a repeated line number).
    for g in manifest.data.get("expected_line_gaps", []):
        expected_gaps.add((g["column"], g["after"], g["next"]))
    gaps = []
    lines_by_col: dict[str, list[int]] = defaultdict(list)
    for seg in segments:
        lines_by_col[seg["column"]].extend(l["n"] for l in seg["lines"])
    for col, nums in lines_by_col.items():
        for a, b in zip(nums, nums[1:]):
            if b != a + 1:
                entry = {
                    "column": col,
                    "after_line": a,
                    "next_line": b,
                    "expected": (col, a, b) in expected_gaps,
                }
                gaps.append(entry)
    # observed schemes: line numbers are editorial (busse per-page numbering with
    # section headings dropped; stephanus lines restart per section and are not
    # user-facing citation targets), so intra-column line-number gaps are demoted
    # to non-failing warnings rather than treated as spine defects.
    if observed:
        for g in gaps:
            g["expected"] = True
    unexpected_gaps = [g for g in gaps if not g["expected"]]
    report["checks"]["line_gaps"] = {
        "gaps": gaps,
        "unexpected": unexpected_gaps,
        "ok": not unexpected_gaps,
    }

    # --- 3. alignment coverage -------------------------------------------
    unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
    # Columns the English TEI demonstrably cannot cover (Perseus omitted a Bekker
    # page milestone, or assigns a book-straddling column to a single book) are
    # declared in the manifest so they're surfaced but don't fail the build.
    allowed = set(manifest.data.get("alignment_allow_unmatched", []))
    # A column the manifest's own citation.kind_overrides declares `omit`
    # is ALSO a legitimate unmatched column (see _omit_declared_segment_ids)
    # -- derived from the SAME declaration stage1 already enforces, not a
    # second hand-maintained allowance list.
    allowed |= _omit_declared_segment_ids(manifest, segments)
    allowed |= _summary_suppressed_segment_ids(manifest, segments)
    unexpected_unmatched = [s for s in unmatched if s not in allowed]
    # A book-boundary edition mismatch is symmetric: the English TEI places a
    # book division a column off from the Greek, leaving both an unpaired Greek
    # segment and an unpaired English chunk. The allowance covers either side.
    unexpected_english_only = [s for s in alignment["english_only"] if s not in allowed]
    report["checks"]["alignment"] = {
        "pairs": len(alignment["pairs"]),
        "unmatched_segments": unmatched,
        "allowed_unmatched": sorted(allowed & (set(unmatched) | set(alignment["english_only"]))),
        "unexpected_unmatched": unexpected_unmatched,
        "english_only": alignment["english_only"],
        "unexpected_english_only": unexpected_english_only,
        "ok": not unexpected_unmatched and not unexpected_english_only,
    }

    # --- 4. length-ratio gate ----------------------------------------------
    # A chapter whose English/Greek character ratio falls far outside the healthy
    # spread signals extraction damage: a truncated chapter reads far too short, a
    # footnote/apparatus-contaminated one far too long. The bound is derived from
    # the healthy body of the distribution using robust statistics (median + MAD
    # of the log-ratio), which resist the very outliers being hunted — so a
    # handful of damaged chapters cannot inflate the spread and hide themselves.
    # When the manifest opts in via `length_ratio_gate` this is a HARD gate with a
    # named-chapter message; otherwise it stays informational, so a work whose
    # ratio profile has not been vetted is never failed silently. `exempt` columns
    # (genuinely terse chapters, cross-validated by eye) are dropped from BOTH the
    # statistics and the pass/fail test.
    eng_by_id = {c["id"]: c for c in english["chunks"]}
    gate_cfg = manifest.data.get("length_ratio_gate")
    exempt = set((gate_cfg or {}).get("exempt", []))
    max_z = float((gate_cfg or {}).get("max_robust_z", 6.0))
    ratios = []
    for seg in segments:
        eng = eng_by_id.get(seg["id"])
        if eng is None:
            continue
        glen = sum(len(l["text"]) for l in seg["lines"])
        elen = len(eng["text"])
        if glen and elen:
            ratios.append({"column": seg["column"], "ratio": elen / glen,
                           "greek_chars": glen, "english_chars": elen})
    logs = [math.log(r["ratio"]) for r in ratios if r["column"] not in exempt]
    # No paired English yet (e.g. a stephanus work whose English walker runs in a
    # separate pass) → nothing to compare; report an empty, passing check.
    if len(logs) < 2:
        report["checks"]["length_ratio"] = {
            "median": 0.0, "robust_sd": 0.0, "max_robust_z": max_z,
            "enforced": bool(gate_cfg), "exempt": sorted(exempt),
            "outliers": [], "failures": [], "ok": True,
        }
    else:
        med = statistics.median(logs)
        mad = statistics.median([abs(x - med) for x in logs])
        # robust SD from the MAD; fall back to plain SD if the MAD collapses
        # (near-identical ratios) so the z-score never divides by zero.
        robust_sd = 1.4826 * mad or statistics.pstdev(logs) or 1.0
        scored = []
        for r in ratios:
            z = (math.log(r["ratio"]) - med) / robust_sd
            scored.append({**r, "ratio": round(r["ratio"], 3), "robust_z": round(z, 2)})
        outliers = sorted((s for s in scored if abs(s["robust_z"]) > 3.5),
                          key=lambda s: -abs(s["robust_z"]))
        failures = [s for s in scored
                    if abs(s["robust_z"]) > max_z and s["column"] not in exempt]
        report["checks"]["length_ratio"] = {
            "median": round(math.exp(med), 3),
            "robust_sd": round(robust_sd, 4),
            "max_robust_z": max_z,
            "enforced": bool(gate_cfg),
            "exempt": sorted(exempt),
            "outliers": outliers,
            "failures": failures,
            "ok": (not failures) if gate_cfg else True,
        }

    # --- 5. proper-name spot check ------------------------------------------
    greek_text_by_col: dict[str, str] = defaultdict(str)
    eng_text_by_col: dict[str, str] = defaultdict(str)
    for seg in segments:
        greek_text_by_col[seg["column"]] += " ".join(l["text"] for l in seg["lines"])
    for c in english["chunks"]:
        eng_text_by_col[c["column"]] += c["text"]
    greek_base_by_col = {c: _base(t) for c, t in greek_text_by_col.items()}
    proper_names = [tuple(p) for p in manifest.data.get("proper_names", [])]
    name_results = []
    for grc, eng_name in proper_names:
        grc_cols = {c for c, t in greek_base_by_col.items() if grc in t}
        eng_cols = {c for c, t in eng_text_by_col.items() if eng_name in t}
        # English chunk boundaries sit exactly at milestones, but a sentence
        # begun late in one column is often translated as overflowing the
        # boundary; allow +/- one column of slack.
        def near(col, others):
            i = expected.index(col)
            window = set(expected[max(0, i - 1) : i + 2])
            return bool(window & others)

        only_greek = sorted(c for c in grc_cols if not near(c, eng_cols))
        only_english = sorted(c for c in eng_cols if not near(c, grc_cols))
        name_results.append(
            {
                "greek": grc,
                "english": eng_name,
                "greek_columns": len(grc_cols),
                "english_columns": len(eng_cols),
                "greek_without_english": only_greek,
                "english_without_greek": only_english,
            }
        )
    report["checks"]["proper_names"] = {
        "names": name_results,
        "ok": all(
            not n["greek_without_english"] and not n["english_without_greek"]
            for n in name_results
        ),
    }

    # --- 6. sigla / character inventory ------------------------------------
    inventory: dict[str, dict] = {}
    for seg in segments:
        for line in seg["lines"]:
            for ch in line["text"]:
                if _is_greek_letter(ch) or ch in EXPECTED_NON_GREEK:
                    continue
                entry = inventory.setdefault(
                    ch,
                    {
                        "char": ch,
                        "name": unicodedata.name(ch, "UNKNOWN"),
                        "count": 0,
                        "samples": [],
                    },
                )
                entry["count"] += 1
                if len(entry["samples"]) < 5:
                    entry["samples"].append(
                        {"ref": f"{seg['column']}{line['n']}", "text": line["text"][:80]}
                    )
    report["checks"]["sigla"] = {
        "characters": sorted(inventory.values(), key=lambda e: -e["count"]),
        "ok": True,  # informational
    }

    report["ok"] = all(c.get("ok") for c in report["checks"].values())
    return report


def _to_markdown(report: dict) -> str:
    c = report["checks"]
    lines = ["# Stage 2 validation report", ""]
    lines.append(f"Overall: {'PASS' if report['ok'] else 'FAIL'}")
    cols = c["columns"]
    lines += [
        "",
        "## Columns",
        f"- {cols['found']}/{cols['expected']} columns, monotonic: {cols['monotonic']}",
        f"- missing: {cols['missing'] or 'none'}; extra: {cols['extra'] or 'none'}",
        "",
        "## Line gaps",
        f"- {len(c['line_gaps']['gaps'])} gaps, "
        f"{len(c['line_gaps']['unexpected'])} unexpected",
    ]
    for g in c["line_gaps"]["gaps"]:
        marker = "expected (book boundary)" if g["expected"] else "**UNEXPECTED**"
        lines.append(
            f"  - {g['column']}: {g['after_line']} -> {g['next_line']} ({marker})"
        )
    if "section_order" in c:
        so = c["section_order"]
        lines += [
            "",
            "## Section order (observed scheme)",
            f"- strictly increasing: {so['strictly_increasing']}; "
            f"{len(so['gaps'])} section gaps (info)",
        ]
        for g in so["gaps"]:
            tag = "declared" if g["expected"] else "gap"
            lines.append(f"  - {g['after']} -> {g['next']} ({tag})")
    if "section_spine" in c:
        ss = c["section_spine"]
        lines += [
            "",
            "## Section spine baseline",
            f"- count: expected {ss['expected']['count']}, got {ss['got']['count']}; "
            f"sha256: expected {ss['expected']['sha256']}, got {ss['got']['sha256']}",
            f"- span: {ss['first_column']['got']}..{ss['last_column']['got']} "
            f"(expected {ss['first_column']['expected']}..{ss['last_column']['expected']})",
        ]
        if ss["first_diverging_token"]:
            lines.append(f"- first diverging token: {ss['first_diverging_token']}")
    if "book_partition" in c:
        bp = c["book_partition"]
        lines += [
            "",
            "## Book partition (section scheme)",
            f"- {bp['books']} books, ordered & non-overlapping: "
            f"{bp['ordered_non_overlapping']}",
            f"- sections outside any book: "
            f"{bp['sections_outside_any_book'] or 'none'}",
            f"- sections in multiple books: "
            f"{bp['sections_in_multiple_books'] or 'none'}",
        ]
    a = c["alignment"]
    lines += [
        "",
        "## Alignment",
        f"- {a['pairs']} pairs; unmatched segments: {a['unmatched_segments'] or 'none'}; "
        f"english-only: {a['english_only'] or 'none'}",
        "",
        "## Length ratios (english chars / greek chars)",
        f"- median {c['length_ratio']['median']}, robust sd(log) "
        f"{c['length_ratio']['robust_sd']}, "
        f"gate {'ENFORCED' if c['length_ratio']['enforced'] else 'informational'} "
        f"at |robust z| > {c['length_ratio']['max_robust_z']}"
        + (f", exempt {c['length_ratio']['exempt']}" if c['length_ratio']['exempt'] else ""),
    ]
    fails = c["length_ratio"].get("failures", [])
    if fails:
        lines.append(f"- **{len(fails)} FAILING chapter(s)** (extraction damage):")
        for o in fails:
            lines.append(
                f"  - **{o['column']}**: ratio {o['ratio']} (robust z {o['robust_z']}; "
                f"grc {o['greek_chars']}, eng {o['english_chars']})"
            )
    lines.append(f"- {len(c['length_ratio']['outliers'])} outlier(s) beyond 3.5 robust SD:")
    for o in c["length_ratio"]["outliers"][:15]:
        lines.append(
            f"  - {o['column']}: ratio {o['ratio']} (robust z {o['robust_z']}; "
            f"grc {o['greek_chars']}, eng {o['english_chars']})"
        )
    lines += ["", "## Proper names"]
    for n in c["proper_names"]["names"]:
        status = (
            "ok"
            if not n["greek_without_english"] and not n["english_without_greek"]
            else f"grc-only {n['greek_without_english']} eng-only {n['english_without_greek']}"
        )
        lines.append(
            f"- {n['greek']} / {n['english']}: grc in {n['greek_columns']} cols, "
            f"eng in {n['english_columns']} cols — {status}"
        )
    lines += ["", "## Non-Greek character inventory"]
    for e in c["sigla"]["characters"]:
        sample = e["samples"][0]["ref"] if e["samples"] else ""
        lines.append(
            f"- U+{ord(e['char']):04X} {e['char']!r} {e['name']} x{e['count']} "
            f"(e.g. {sample})"
        )
    return "\n".join(lines) + "\n"


def run(manifest: Manifest) -> Path:
    stage1 = BUILD_DIR / "stage1"
    # Per-language spine filename (shared with stage3/stage7 via the same
    # mapping — see stage3_tokenize._SPINE_FILENAMES's doc).
    spine_file = _SPINE_FILENAMES[manifest.language]
    spine = json.loads((stage1 / spine_file).read_text(encoding="utf-8"))
    # The English side may not be built yet (a stephanus work whose Stephanus TEI
    # walker runs as a separate pass). Validate the Greek spine alone in that case.
    eng_path = stage1 / "english_chunks.json"
    align_path = stage1 / "alignment.json"
    english = (json.loads(eng_path.read_text(encoding="utf-8"))
               if eng_path.exists() else {"chunks": []})
    alignment = (json.loads(align_path.read_text(encoding="utf-8"))
                 if align_path.exists() else {"pairs": [], "english_only": []})
    report = validate(manifest, spine, english, alignment)
    out_dir = BUILD_DIR / "stage2"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    md_path = out_dir / "validation_report.md"
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    return md_path
