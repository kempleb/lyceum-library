# DK citation-expansion dictionary

Deterministic expansion of DK source-citation heads (the abbreviated
quoting-author citations over fragments/testimonia) into reader-facing
English citations, plus dash-continuation resolution rules for the Greek
heads.

- `citation-heads-census.json` — Grok census over all 39 `*-fragments` /
  `*-testimonia` works: 2,039 columns, 1,974 parseable heads, 332 author
  abbreviation spellings, 629 author-work pairs, with examples and
  flagged anomalies.
- `citation-dictionary.json` — Opus-authored dictionary: 183 canonical
  authors folding the 332 spellings; 97.9% of heads resolvable (67.4%
  direct lookup, the rest via dash walk-back); 41 occurrences honestly
  flagged unmappable. See `meta` for coverage, dash-misparse tokens, and
  unmappable artifacts.
- `build_dict.py` — generator; reproduces the dictionary and its coverage
  numbers from the census.
- Conventions + dash-resolution rules: `docs/citation-conventions-memo.md`.

**Status: PROVISIONAL.** The memo's six convention choices (name form,
Latin titles, pseudo-author prefix, Doxographi page refs, apparatus
brackets, locus label vocabulary) await John's approval; nothing here is
wired into the pipeline or reader yet. Built 2026-07-24.
