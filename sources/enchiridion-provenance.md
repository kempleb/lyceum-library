# Enchiridion — provenance note

For John and the interoperability partner. Date: 2026-09-01.
Text: Epictetus, *Enchiridion* (the "Manual"). TLG author/work 0557.002.

## Principal source
Greek text is exported from the TLG's edition of H. Schenkl (ed.),
*Epicteti dissertationes ab Arriano digestae* (Leipzig: Teubner, 1916,
repr. 1965) — `manifests/enchiridion.yaml` `work.greek_edition`. Export
process: `docs/tlg-phi-export.md`. The exported XML's own `<sourceDesc>`
is checked verbatim against this edition string as a build gate
(`work.expected_sourcedesc`, same manifest).

English translations:

- **Primary** — W. A. Oldfather, Loeb Classical Library vol. II (London:
  Heinemann; New York: Putnam's, 1928). Scan: archive.org
  `in.ernet.dli.2015.185339`. Verification: `sources/INVENTORY.md`.
- **Secondary** — George Long, translated 1877; this scan a George Bell
  and Sons reprint (archive.org catalog date 1890). Scan: archive.org
  `discoursesofepic033057mbp`. Verification: `sources/INVENTORY.md`.

## Basis for publication (US rule: pre-1931 is public domain)
- **Oldfather**: published 1928, pre-1931 — US public domain.
- **Long**: published 1877 (this scan a 1890 reprint), far pre-1931 — US
  public domain regardless of which printing year governs.
- **Greek edition**: Schenkl (1916) is pre-1931, PD by date alone. But
  the served text is exported from the TLG's own licensed, locally-
  mounted database — never the printed book, never committed. Whether
  it inherits the edition's PD status or carries the TLG's own license
  is an open owner decision, not ruled in `sources/INVENTORY.md` or
  `CANON.md`. So `manifests/enchiridion.yaml` keeps Greek
  `source_license.status` at `unverified`, with a rationale field
  stating this.

## Verification method
`scripts/verify-lined-source.mjs` (renamed 2026-08-29 from
`verify-discourses-lineation.mjs`) runs a 7-check contract per work (wrap
rejoin correctness, hyphen positions, round-trip snapshot, token
conservation, indent totals). Enchiridion: 53 chapter columns, 598 body
`<l>` lines, 132 wraps, 0 unjoinable (`docs/lined-rollout-plan.md`).

Sigma-rejoin fix on record: Schenkl's print sets a line-final sigma (ς)
before a hyphen at 2 Enchiridion loci (ch. 31 §5, ch. 33 §12–13); naive
rejoin produced an impossible medial ς. Fixed by
`_fold_hyphen_final_sigma` (`pipeline/reader_pipeline/stage1_greek.py`);
verified by `verify-lined-source.mjs` checks 3–6 and
`pipeline/tests/test_stage1_lined_source.py` (zero medial-ς surfaces
survive). Full account: `docs/lined-source-plan.md`, "Correction
(2026-08-29): sigma-wrap medial-ς defect".

Chapter counts: Oldfather 53/53 exact; Long 53/53 after a deterministic
repair of a merged §50/51 in the printed edition, re-keyed to the modern
1–53 numbering (`sources/INVENTORY.md`, "Coverage anomaly").

## Not claimed
No claim that the TLG-exported Greek text is public domain — that
status is open, as above. No claim about any source beyond what is
stated here. Verification establishes textual fidelity to the cited
sources, not the correctness of those sources' own scholarship.
