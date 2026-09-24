"""Pipeline CLI: python -m reader_pipeline <stage>|all"""

from __future__ import annotations

import argparse
import json
import sys

from .config import BUILD_DIR, Manifest


def _stage1(manifest):
    # stage1 spine producer per work.language (Wave 2 Batch 1a: 'lat' ->
    # stage1_latin.py, Cicero's De Officiis — the first real PHI work).
    if manifest.language == "lat":
        from . import stage1_latin as stage1_producer
    else:
        from . import stage1_greek as stage1_producer

    spine_path = stage1_producer.run(manifest)
    spine = json.loads(spine_path.read_text(encoding="utf-8"))

    # build/stage1 is single-work scratch; drop any secondary-translation chunks
    # left by a previous work's build so stage7 never emits a stale overlay. It
    # is rewritten below only when this work declares english.secondary.
    for scratch in ("ross_chunks.json", "third_chunks.json", "third_footnotes.json",
                    "overlays.json", "paratext.json", "context_english.json",
                    "citation_expansion.json"):
        (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)

    # Source-passage English (docs/source-passage-english-scoping.md): an
    # additive, per-work sidecar (sources/<work>/context-english.json) that
    # a DK fragment/testimonia work may declare independently of its
    # english.primary model -- resolved here regardless of which dispatch
    # branch below the work's citation scheme takes. A work with no sidecar
    # file is completely unaffected (stage1_context_english.run returns None
    # and writes nothing).
    from . import stage1_context_english

    context_english_path = stage1_context_english.run(manifest, spine)
    if context_english_path is not None:
        context_english = json.loads(context_english_path.read_text(encoding="utf-8"))
        n_spans = sum(len(v) for v in context_english.values())
        print(f"  context_english: columns={len(context_english)} spans={n_spans}")

    # DK source-citation expansion (docs/citation-expansion-wiring-design.md):
    # an additive, per-work sidecar gated by `citation.expand_citations: true`
    # in the manifest. Resolved here regardless of the citation-scheme branch
    # below. A work that does not declare the flag is completely unaffected
    # (stage1_citation_expansion.run returns None and writes nothing; the
    # scratch file above is cleared per-work like context_english.json).
    from . import stage1_citation_expansion

    stage1_citation_expansion.run(manifest, spine)

    # Section-scheme works can opt into a parallel Perseus Stephanus TEI pass.
    # Others remain Greek-only, with stale English scratch removed.
    from . import scheme as scheme_mod
    sch = scheme_mod.for_manifest(manifest)
    if sch.verse_line_scheme:
        # verse-line (Lucretius' DRN): the Latin spine is built the same way
        # regardless. English is Munro's prose (Wave 2 Batch 2's English
        # task), wired through its own dedicated builder
        # (stage1_verse_line_english.py) because this scheme's column shape
        # (one segment per citable LINE, not per book-section) matches
        # neither existing English builder's assumptions -- see that
        # module's doc comment. A manifest that omits `english` entirely
        # still ships Latin-only (`work.no_english: true`, the De Officiis
        # Batch-1a staging), unchanged from before.
        n_lines = sum(len(s["lines"]) for s in spine["segments"])
        books = {s["book"] for s in spine["segments"]}
        if "english" in manifest.data:
            # Defensive backstop: preflight's schema gate (`_validate_manifest_
            # schema`) already rejects `work.no_english: true` combined with an
            # `english:` block as a schema error, but this dispatch decides
            # Latin-only vs. +english purely on "english" in manifest.data --
            # assert the manifests actually agree in case preflight was
            # bypassed (e.g. `astro build`/`reader_pipeline all` run directly).
            assert not (manifest.data.get("work") or {}).get("no_english"), (
                f"{manifest.work_id}: work.no_english is true but an english: "
                f"block is also present -- these are mutually exclusive "
                f"(should have failed preflight's schema gate)"
            )
            from . import stage1_verse_line_english

            eng_path, align_path = stage1_verse_line_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            print(f"stage1 ({manifest.language}+english, {sch.name}): "
                  f"segments={len(spine['segments'])} books={len(books)} lines={n_lines} "
                  f"unassigned={len(spine['unassigned_lines'])}")
            print(f"  english chunks={len(english['chunks'])} ({english['translation']})")
        else:
            for scratch in ("english_chunks.json", "alignment.json"):
                (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)
            print(f"stage1 ({manifest.language}-only, {sch.name}): "
                  f"segments={len(spine['segments'])} books={len(books)} lines={n_lines} "
                  f"unassigned={len(spine['unassigned_lines'])}")
        return
    if sch.numeric_section:
        # A numeric-section (book-section) work's translation-to-column
        # mapping is exactly 1:1 (see stage1_book_section_english's module
        # docstring) — it is neither the Perseus-Stephanus-TEI path above nor
        # the Bekker-chapter archive path below (both built for a different
        # citation scheme's shape), so it gets its own dedicated stage1 pass.
        #
        # A book-section work may also ship with NO `english` block at all
        # (Wave 2 Batch 1a: Cicero's De Officiis pilot is text/citation/
        # search only, no translation yet — the same declared-gap shape the
        # dk fragment_scheme branch below already supports for Greek-only
        # DK works, generalized here to book-section).
        n_lines = sum(len(s["lines"]) for s in spine["segments"])
        books = {s["book"] for s in spine["segments"]}
        if "english" in manifest.data:
            # MAJOR fix (Sol re-verification, 2026-07-21): this branch used
            # to dispatch to stage1_book_section_english unconditionally on
            # "english" in manifest.data, with NO check of primary.model at
            # all -- a typo'd model would still silently reach this
            # direct-map archive builder. preflight's schema gate now
            # enforces primary.model against an explicit enum before a
            # build ever reaches this dispatch (see preflight.py's
            # `_stephanus_like_dispatch`), so 'archive' is the only value
            # that should arrive here for this scheme -- asserted
            # explicitly rather than assumed, same posture as the
            # flat_numeric branch's own defensive check below, in case
            # preflight was bypassed (`astro build`/`reader_pipeline all`
            # run directly).
            primary = ((manifest.data.get("english") or {}).get("primary") or {})
            model = primary.get("model")
            # De Finibus English phase 3: `chapter_concordance` (Yonge's
            # chapter-keyed translation over a 5-book Latin spine,
            # `sources/yonge-finibus/`) is a second shape this scheme's
            # english block may declare, alongside "archive"'s 1:1
            # chapter/column mapping -- same dedicated builder De Fato's
            # flat-scheme branch below already dispatches to, generalized
            # to a multi-book work (see stage1_chapter_concordance_
            # english.py's own doc comment).
            if model == "chapter_concordance":
                from . import stage1_chapter_concordance_english

                eng_path, align_path = stage1_chapter_concordance_english.run(manifest, spine)
                english = json.loads(eng_path.read_text(encoding="utf-8"))
                alignment = json.loads(align_path.read_text(encoding="utf-8"))
                unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
                print(f"stage1 ({manifest.language}+english, {sch.name}): "
                      f"segments={len(spine['segments'])} books={len(books)} lines={n_lines} "
                      f"unassigned={len(spine['unassigned_lines'])}")
                print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                      f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
                return
            if model != "archive":
                raise ValueError(
                    f"{manifest.work_id}: unsupported english.primary.model "
                    f"{model!r} for the numeric-section/letter scheme's "
                    f"direct-map builder (stage1_book_section_english) -- "
                    f"expected 'archive' or 'chapter_concordance'; preflight's "
                    f"model enum should have caught this"
                )
            from . import stage1_book_section_english

            eng_path, align_path = stage1_book_section_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            alignment = json.loads(align_path.read_text(encoding="utf-8"))
            unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
            print(f"stage1 ({manifest.language}+english, {sch.name}): "
                  f"segments={len(spine['segments'])} books={len(books)} lines={n_lines} "
                  f"unassigned={len(spine['unassigned_lines'])}")
            print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                  f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
        else:
            for scratch in ("english_chunks.json", "alignment.json"):
                (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)
            print(f"stage1 ({manifest.language}-only, {sch.name}): "
                  f"segments={len(spine['segments'])} books={len(books)} lines={n_lines} "
                  f"unassigned={len(spine['unassigned_lines'])}")
        return
    if sch.flat_numeric:
        # Flat bookless scheme (Epictetus' Enchiridion): translation-to-
        # column mapping is 1:1 exactly like book-section (see
        # stage1_flat_english's module docstring), just without the dotted
        # book prefix. Like numeric_section above, this is its own dedicated
        # stage1 pass, not the has_sections/perseus_stephanus path below.
        #
        # A flat work may also ship with NO `english` block at all (Wave 2
        # Batch 3 round 2 — Cicero's Cato Maior/Laelius/De Fato/Lucullus/
        # Paradoxa Stoicorum, `work.no_english: true`, the numeric_section
        # branch's own De Officiis Batch-1a staging precedent, mirrored
        # here): every prior flat work (Enchiridion) always declared
        # `english`, so this branch used to call stage1_flat_english
        # unconditionally — it now checks "english" in manifest.data first,
        # exactly like the numeric_section/verse-line branches above.
        #
        # `english.primary.model: chapter_concordance` (De Fato — Yonge's
        # chapter-keyed translation, `sources/yonge-fato/`) is a THIRD flat
        # shape alongside "declares no english" / stage1_flat_english's 1:1
        # mapping: one translated chapter spans several Latin sections, so
        # it gets its own dedicated builder (stage1_chapter_concordance_
        # english.py — see that module's doc comment), checked first, same
        # posture as the has_sections branch's perseus_stephanus dispatch
        # below.
        n_lines = sum(len(s["lines"]) for s in spine["segments"])
        primary = ((manifest.data.get("english") or {}).get("primary") or {})
        if primary.get("model") == "chapter_concordance":
            from . import stage1_chapter_concordance_english

            eng_path, align_path = stage1_chapter_concordance_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            alignment = json.loads(align_path.read_text(encoding="utf-8"))
            unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
            print(f"stage1 ({manifest.language}+english, {sch.name}): segments={len(spine['segments'])} "
                  f"lines={n_lines} unassigned={len(spine['unassigned_lines'])}")
            print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                  f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
        elif "english" in manifest.data:
            # MAJOR 2 fix (Sol adversarial review): this branch used to
            # dispatch to stage1_flat_english for ANY primary.model other
            # than "chapter_concordance" -- a typo like "chapter_concordence"
            # would silently fall through here and skip every concordance
            # hash/anchor check the dedicated builder above performs.
            # preflight's schema gate (`_validate_section_manifest_schema`)
            # now enforces primary.model against an explicit enum ("archive"
            # or "chapter_concordance") before a build ever reaches this
            # dispatch, so "archive" is the only value that should arrive
            # here -- asserted explicitly rather than assumed, in case
            # preflight was bypassed (`astro build`/`reader_pipeline all` run
            # directly, same posture as the verse-line branch's own
            # defensive assert above).
            model = primary.get("model")
            if model != "archive":
                raise ValueError(
                    f"{manifest.work_id}: unsupported english.primary.model "
                    f"{model!r} for the flat 'section' scheme's direct-map "
                    f"builder (stage1_flat_english) -- expected 'archive'; "
                    f"preflight's model enum should have caught this"
                )
            from . import stage1_flat_english

            eng_path, align_path = stage1_flat_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            alignment = json.loads(align_path.read_text(encoding="utf-8"))
            unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
            print(f"stage1 ({manifest.language}+english, {sch.name}): segments={len(spine['segments'])} "
                  f"lines={n_lines} unassigned={len(spine['unassigned_lines'])}")
            print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                  f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
        else:
            for scratch in ("english_chunks.json", "alignment.json"):
                (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)
            print(f"stage1 ({manifest.language}-only, {sch.name}): segments={len(spine['segments'])} "
                  f"lines={n_lines} unassigned={len(spine['unassigned_lines'])}")
        return
    if sch.fragment_scheme:
        # dk (Diels-Kranz): checked BEFORE the has_sections branch below,
        # since dk also sets has_sections=True but its export shape has
        # nothing in common with stephanus' page>section nesting (the
        # A-testimonia ship Greek-only by design — no manifest `english`
        # block at all — see manifests/heraclitus-testimonia.yaml).
        # Bookless, so no book/page grouping to report either. A
        # B-fragments work's translation-to-column mapping is exactly the
        # flat `section` scheme's shape (one column IS the source key, no
        # dotted book prefix) — the dk column token itself ("B30") happens
        # to equal Burnet's own clean.json key, so stage1_flat_english's
        # existing builder is reused unchanged (see
        # manifests/heraclitus-fragments.yaml's `english` block).
        n_lines = sum(len(s["lines"]) for s in spine["segments"])
        has_english = "english" in manifest.data
        if has_english:
            primary = ((manifest.data.get("english") or {}).get("primary") or {})
            if primary.get("model") == "freeman":
                # Kathleen Freeman's Ancilla (docs/freeman-wave-design.md):
                # richer {kind, text} clean-JSON records plus a group-header
                # paratext sidecar -- its own dedicated builder, not the
                # plain-string direct-map stage1_flat_english uses for
                # 'archive'.
                from . import stage1_freeman_english

                eng_path, align_path = stage1_freeman_english.run(manifest, spine)
            else:
                from . import stage1_flat_english

                eng_path, align_path = stage1_flat_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            alignment = json.loads(align_path.read_text(encoding="utf-8"))
            unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
            print(f"stage1 (greek+english, dk): segments={len(spine['segments'])} "
                  f"lines={n_lines} unassigned={len(spine['unassigned_lines'])}")
            print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                  f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
        else:
            for scratch in ("english_chunks.json", "alignment.json", "paratext.json"):
                (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)
            print(f"stage1 (greek-only, dk): segments={len(spine['segments'])} "
                  f"lines={n_lines} unassigned={len(spine['unassigned_lines'])}")
        return
    if sch.has_sections:
        primary = ((manifest.data.get("english") or {}).get("primary") or {})
        if primary.get("model") == "perseus_stephanus":
            from . import stage1_stephanus_english

            eng_path, align_path = stage1_stephanus_english.run(manifest, spine)
            english = json.loads(eng_path.read_text(encoding="utf-8"))
            alignment = json.loads(align_path.read_text(encoding="utf-8"))
            unmatched = [p["segment"] for p in alignment["pairs"] if p["english"] is None]
            print(f"  english chunks={len(english['chunks'])} ({english['translation']}) "
                  f"unmatched={len(unmatched)} english_only={len(alignment['english_only'])}")
        else:
            for scratch in ("english_chunks.json", "alignment.json"):
                (BUILD_DIR / "stage1" / scratch).unlink(missing_ok=True)
        n_lines = sum(len(s["lines"]) for s in spine["segments"])
        n_speakers = sum(len(s.get("speakers", [])) for s in spine["segments"])
        # Stephanus columns are page+letter ("17a" -> page "17"); a flat
        # scheme's column ("5") IS the page — stripping its last char would
        # collapse "5" to "" and "10"/"12" both to "1".
        pages = ({s["column"] for s in spine["segments"]} if sch.flat_numeric
                 else {s["column"][:-1] for s in spine["segments"]})
        print(f"stage1 ({'greek+english' if primary.get('model') == 'perseus_stephanus' else 'greek-only'}, {scheme_mod.for_manifest(manifest).name}): "
              f"segments={len(spine['segments'])} pages={len(pages)} "
              f"lines={n_lines} speakers={n_speakers} "
              f"unassigned={len(spine['unassigned_lines'])}")
        return

    chapters_cfg = manifest.data.get("chapters", {})
    if chapters_cfg.get("source") in ("grc_tei", "explicit"):
        # Chapter-anchored archive English. Chapters come either from a grc TEI
        # text-aligned onto the spine (e.g. DA) or declared directly as Bekker
        # starts in the manifest (e.g. Categories, keyed from a Bekker-stamped
        # translation). The archive path then handles primary + optional
        # secondary/third translations, each with its own dense anchor gutter.
        from . import stage1_archive, stage1_chapters

        if chapters_cfg["source"] == "explicit":
            chapters = stage1_chapters.extract_chapters_explicit(
                spine, chapters_cfg["list"])
        else:
            chapters = stage1_chapters.extract_chapters_grc(
                spine, chapters_cfg["grc_tei"],
                chapters_cfg.get("chapter_subtype", "chapter"),
                chapters_cfg.get("book_subtype", "book"),
                chapters_cfg.get("chapter_marker", "div"),
                chapters_cfg.get("grc_book"),
                chapters_cfg.get("extra"),
            )
        # Some source TEIs use zero-based or discontinuous chapter labels.  A
        # chapter-anchored archive translation is numbered in reading order, so
        # a manifest may explicitly request that the extracted spine be
        # renumbered sequentially before its English Parts are attached.
        if chapters_cfg.get("chapter_renumber") == "sequential":
            for n, chapter in enumerate(chapters, 1):
                chapter["chapter"] = str(n)
        # Drop chapters from books the manifest doesn't carry — e.g. History of
        # Animals' spurious, untranslated Book X, whose grc chapter divs would
        # otherwise align past the spine's last assigned book.
        valid_books = {b["n"] for b in manifest.books}
        chapters = [c for c in chapters if c["book"] in valid_books]
        eng_path, align_path = stage1_archive.run(manifest, spine, chapters)
        english = json.loads(eng_path.read_text(encoding="utf-8"))
        how = "explicit" if chapters_cfg["source"] == "explicit" else "grc-aligned"
        print(f"  chapters: {len(chapters)} ({how}) "
              f"english chunks={len(english['chunks'])} ({english['translation']})")
    else:
        # Rackham primary + Ross secondary (EN). Chapters come from the English
        # TEI milestones by default, but if the manifest declares a grc TEI we
        # text-align chapter lines onto the spine (exact) and override.
        from . import stage1_english, stage1_ross

        override = None
        if chapters_cfg.get("grc_tei"):
            from . import stage1_chapters
            override = stage1_chapters.extract_chapters_grc(
                spine, chapters_cfg["grc_tei"],
                chapters_cfg.get("chapter_subtype", "chapter"),
                chapters_cfg.get("book_subtype", "book"),
                chapters_cfg.get("chapter_marker", "div"),
            )
            print(f"  chapters: {len(override)} (grc-aligned, overriding milestones)")
        eng_path, align_path = stage1_english.run(manifest, spine, override)
        english = json.loads(eng_path.read_text(encoding="utf-8"))
        # A second (unmarked) translation is optional. When the manifest declares
        # english.secondary, align it onto the spine via the Bekker-milestoned
        # primary as reference (writing the standoff map stage1_ross reads for
        # real ticks) then chunk it; otherwise the work ships primary-only.
        sec = (manifest.data.get("english") or {}).get("secondary")
        if sec:
            # Tier 0 chapter overlay (no gloss aligner). An archive secondary
            # whose "Part" divisions ARE the Bekker chapters (e.g. Rhetoric:
            # Freese primary on the perseus path, Roberts secondary) is placed
            # straight onto the grc-aligned chapter spine via build_overlay —
            # the same overlay the archive path builds — so a milestoned primary
            # can carry a chapter-anchored secondary without a gloss map. Used
            # only when no gloss map exists for this version (EN's Ross has one,
            # so it keeps the reference-aligner path below) and the grc chapter
            # override is present. build_overlay still honours an anchors.yaml
            # (Tier 1) if the secondary later gains one.
            from .stage1_ross import _load_align_map
            tier0 = (sec.get("model") == "archive"
                     and sec.get("chapter_marker")
                     and override is not None
                     and not _load_align_map(manifest.work_id, sec["id"]))
            if tier0:
                from . import stage1_archive
                ross = stage1_archive.build_overlay(spine, override, sec,
                                                    manifest.work_id)
                (BUILD_DIR / "stage1" / "ross_chunks.json").write_text(
                    json.dumps(ross, ensure_ascii=False, indent=1),
                    encoding="utf-8")
                placed = sum(1 for v in ross.values()
                             if any(p["text"].strip() for p in v))
                print(f"  ross (Tier 0 chapter overlay): segments_with_text="
                      f"{placed} pieces={sum(len(v) for v in ross.values())}")
            else:
                from .align.aligner import align as align_secondary
                from .align.reference import default_target

                version_id, prose = default_target(manifest.work_id)
                stats = align_secondary(manifest.work_id, version_id=version_id,
                                        target_prose=prose)
                print(f"  align({version_id}): chapters={stats['chapters']} "
                      f"anchors={stats['anchors']} tiers={stats['tiers']} "
                      f"review={stats['review']}")
                ross_path = stage1_ross.run(manifest, spine, english)
                ross = json.loads(ross_path.read_text(encoding="utf-8"))
                print(f"  ross: segments_with_text={len(ross)} "
                      f"pieces={sum(len(v) for v in ross.values())}")
        # A third translation (NE Ostwald) whose Markdown carries the Bekker
        # apparatus inline — parsed straight into a real per-line gutter, no
        # aligner needed (see stage1_ostwald). Writes third_chunks.json plus a
        # {N: html} footnote map that stage7 copies into the work's data dir.
        if (manifest.data.get("english") or {}).get("third"):
            from . import stage1_ostwald

            stage1_ostwald.run(manifest, spine, english)
        # Additional overlays (4th translation onward) — chapter-marker archive
        # overlays placed on the grc chapter spine, no aligner. Needs the grc
        # override; perseus-primary works without one carry none.
        from . import stage1_archive
        ov = stage1_archive.run_overlays(manifest, spine, override or [])
        if ov:
            print(f"  overlays: {', '.join(ov)} "
                  f"({sum(sum(len(v) for v in c.values()) for c in ov.values())} pieces)")
    n_lines = sum(len(s["lines"]) for s in spine["segments"])
    print(f"stage1: segments={len(spine['segments'])} lines={n_lines} "
          f"unassigned={len(spine['unassigned_lines'])}")
    align = json.loads(align_path.read_text(encoding="utf-8"))
    unmatched = [p["segment"] for p in align["pairs"] if p["english"] is None]
    print(f"  alignment pairs={len(align['pairs'])} unmatched={len(unmatched)} "
          f"english_only={len(align['english_only'])}")
    if unmatched:
        print(f"  unmatched segments: {unmatched[:10]}")


def _stage2(manifest):
    from . import stage2_validate

    stage2_validate.run(manifest)
    report = json.loads(
        (BUILD_DIR / "stage2" / "validation_report.json").read_text()
    )
    checks = " ".join(
        f"{name}={'ok' if c['ok'] else 'FAIL'}" for name, c in report["checks"].items()
    )
    print(f"stage2: {checks}")
    print(f"  overall: {'PASS' if report['ok'] else 'FAIL'}")
    if not report["ok"]:
        raise SystemExit("stage2 validation failed")


def _stage3(manifest):
    from . import stage3_tokenize

    out = stage3_tokenize.run(manifest)
    tokens = json.loads(out.read_text(encoding="utf-8"))
    n = sum(len(l["tokens"]) for s in tokens["segments"] for l in s["lines"])
    sigla = json.loads((BUILD_DIR / "stage3" / "sigla_log.json").read_text())
    failures = json.loads((BUILD_DIR / "stage3" / "key_failures.json").read_text())
    print(f"stage3: tokens={n} sigla_strips={len(sigla)} key_failures={len(failures)}")
    for fail in failures[:10]:
        print(f"  FAIL {fail['ref']}: {fail['token']} — {fail['error']}")


def _stage4(manifest):
    from . import stage4_morphology

    stage4_morphology.run(manifest)
    summary = json.loads((BUILD_DIR / "stage4" / "summary.json").read_text())
    print("stage4: " + " ".join(f"{k}={v}" for k, v in summary.items()))


def _stage5(manifest):
    from . import stage5_lsj

    out_dir = stage5_lsj.run(manifest)
    summary = json.loads((out_dir / "summary.json").read_text())
    print("stage5: " + " ".join(f"{k}={v}" for k, v in summary.items()))


def _stage6(manifest):
    from . import stage6_search

    out_dir = stage6_search.run(manifest)
    summary = json.loads((out_dir / "summary.json").read_text())
    print("stage6: " + " ".join(f"{k}={v}" for k, v in summary.items()))


def _stage7(manifest):
    from . import stage7_emit

    out_dir = stage7_emit.run(manifest)
    man = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"stage7: {out_dir}")
    print(f"  books={len(man['books'])} token_keys={man['analyses']['token_keys']} "
          f"lsj_entries={man['lsj']['lsj_entries_kept']}")


_STAGES = {
    "stage1": _stage1,
    "stage2": _stage2,
    "stage3": _stage3,
    "stage4": _stage4,
    "stage5": _stage5,
    "stage6": _stage6,
    "stage7": _stage7,
}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reader_pipeline")
    parser.add_argument("stage", choices=[*_STAGES, "all"])
    parser.add_argument(
        "--work", default="EN",
        help="work slug = manifest filename stem (default: EN)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="use manifests/<work>-public.yaml when present",
    )
    args = parser.parse_args(argv)
    manifest = Manifest.for_work(args.work, public=args.public)
    if args.public:
        print(f"manifest: {manifest.path.relative_to(manifest.path.parents[1])}")
    if args.stage == "all":
        for fn in _STAGES.values():
            fn(manifest)
    else:
        _STAGES[args.stage](manifest)


if __name__ == "__main__":
    sys.exit(main())
