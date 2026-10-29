# TLG / PHI export recipe

Source-text export from the local Diogenes installation, for both the TLG Greek
corpus and the PHI Latin corpus. Corpus source text is never committed to this
repo — this recipe is how the pipeline's stage 1 gets it out of Diogenes and into
the build.

**Never modify `/Applications/Diogenes.app` itself** — its bundled
dependencies/data carry the stage-4/5 morphology data (`greek-analyses.txt`,
`latin-analyses.txt`, LSJ, Lewis & Short) that later pipeline stages depend on.

## TLG (Greek) — verified recipe, inherited from plato-reader

**UPDATE 2026-08-29 — Diogenes.app is now 4.7.2, and `-y`/`-Y` are NATIVE.**
The installed app updated from 4.5 to 4.7.2 at some point after this recipe
was written. `xml-export.pl` (`getopts ('alprho:c:sn:N:vdetxPyY')`, `is_work_verse`
at ~line 2452) now supports `-y`/`-Y` out of the box — **step 1 below (copy +
patch) is obsolete and must be skipped.** The 4.5-era
`docs/diogenes-xml-export-y.patch` mis-applied against 4.7.2 (it half-landed
inside `write_file`) and was removed 2026-10-09; git history keeps it. Stock
4.7.2 `-y` reproduces the patched script's output exactly.
Use the installed script directly (or an unpatched copy of it — never modify
`/Applications/Diogenes.app` itself either way).

**Calibration evidence (2026-08-29, orchestrator ruling):** before trusting
the native 4.7.2 `-y` path for real work, TLG author 0557 (Epictetus,
Discourses + Enchiridion) was re-exported with the native script and diffed
against the live known-good exports in `build/export/Diogenes-Resources/xml/tlg/`
(the ones the shipped Discourses/Enchiridion lineation was built from). Result:
**byte-identical body content** (`<l>` count, `<div>` count, `@rend` indent
distributions, and a SHA-256 of the body after stripping two known header
lines all matched exactly). The only diffs were two cosmetic header-string
classes, present on every file: the generator-version string
(`"Diogenes (version 4.5)"` → `"(version 4.7.2)"`) and an author floruit
annotation Diogenes' 4.7.2 author database adds (`"Epictetus Phil."` →
`"Epictetus Phil. (c. A.D. 1-2)"`). Verdict: **PASS** — the native path is
trusted for export, unpatched.

<details>
<summary>Historical (4.5-era, superseded): copy + patch xml-export.pl</summary>

The installed Diogenes.app was v4.5. Its `xml-export.pl` had **no `-y`
verse-mode flag**, and neither the script nor `Base.pm` read a `TLG_DIR` env
var directly — the corpus path came from a Diogenes prefs file.

1. Copy `/Applications/Diogenes.app/Contents/server/xml-export.pl` to a
   writable scratch location and apply `docs/diogenes-xml-export-y.patch`
   (adds the `-y`/`-Y` verse-mode flags — the only relevant 4.5→4.7 delta).
   Also copy `tei_all.rnc` next to the patched script.
2. Create a scratch config dir containing a `diogenes.prefs` file with one
   line:
   ```
   tlg_dir "/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT/TLG Files/TLG"
   ```
3. Run:
   ```
   Diogenes_Config_Dir=<scratch-config> PATH=/usr/bin:/bin \
     perl -I /Applications/Diogenes.app/Contents/server \
          -I /Applications/Diogenes.app/Contents/dependencies/CPAN \
          xml-export-local-y.pl -c tlg -n 0059 -y -o <outdir>
   ```
   → `<outdir>/Diogenes-Resources/xml/tlg/tlg0059NNN.xml` (author 0059 = Plato,
   41 files, given as the worked example; substitute the target author's TLG
   number).

</details>

**Current recipe (4.7.2, native, no patch step):**

1. Create a scratch config dir containing a `diogenes.prefs` file with one
   line (unchanged):
   ```
   tlg_dir "/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT/TLG Files/TLG"
   ```
2. Run the INSTALLED script directly (or an unpatched copy of it), no patch:
   ```
   Diogenes_Config_Dir=<scratch-config> PATH=/usr/bin:/bin \
     perl -I /Applications/Diogenes.app/Contents/server \
          -I /Applications/Diogenes.app/Contents/dependencies/CPAN \
          /Applications/Diogenes.app/Contents/server/xml-export.pl \
          -c tlg -n 0059 -y -o <outdir>
   ```
   → `<outdir>/Diogenes-Resources/xml/tlg/tlg0059NNN.xml`, identical in body
   content to the patched-4.5 output (calibration above).

Use `-y` for verse works (hexameter Presocratics, Lucretius later); omit it
for prose. `-Y` is the inverse flag per the patch (forces prose-mode
line-breaking) — use only if a work's verse/prose default needs overriding.

**Per-invocation, not per-work (learned on Parmenides, 2026-07-16):** `-y`/`-Y`
apply to *every* work of the author(s) passed via `-n` — there is no per-work
CLI override, and the script's internal `%verse_auths`/`%verse_works` tables +
hyphen-density heuristic (`is_work_verse`) misclassify authors they don't know
(the heuristic calls Parmenides' hexameter Fragmenta prose). For a mixed
author (e.g. Parmenides: prose Testimonia 001 + verse Fragmenta 002), run TWO
invocations into two outdirs — one plain, one with `-y` — and take each work's
file from the correct outdir.

**The pipeline does this itself (2026-10-09).** Each TLG/PHI manifest declares
`work.export_verse_mode: true|false`; stage 1 exports the author into
`build/export-raw/verse` (with `-y`) or `build/export-raw/plain` (without) and
copies only that work's file into `build/export`. The values reproduce the
exports the release was built from. Diogenes 4.5 silently ignored `-y`, so most
saved TLG files are plain-mode; only Lives, Empedocles/Parmenides/Xenophanes
Fragmenta, and five Cicero works (De Divinatione, De Finibus, De Legibus, De
Officiis, Tusculan Disputations — exported with the old patched script) are
`true`. De Rerum Natura is `false`: its saved file matches the plain export.
A fresh 4.7.2 export differs from the saved 4.5 PHI files only where 4.5 printed
"." for the PHI text's "!".

## PHI (Latin) — extension for Wave 2

For the held Aeneid, extract the lines from a verified Diogenes TEI file with:

```
cd pipeline
uv run python -m reader_pipeline.handoff_phi_latin \
  --phi-author 0690 --phi-work 003 \
  --expect-sourcedesc 'P. Vergilius Maro. Aeneis (P. Vergili Maronis Opera, ed. R. A. B. Mynors, 1972).  (0690: 003)' \
  --out ../build/handoff/phi0690003.latin.json
```

Add `--xml <path>` to read an existing export, or `--phi-dir <path>` to set
the PHI corpus location for a new export. The JSON stays under ignored
`build/`; do not commit its Latin text.

PHI export follows the same script and scratch-prefs mechanism as TLG above
(native 4.7.2 `-y`/`-Y`, no patch step — see the UPDATE at the top of this
doc), with these deltas:

- **Corpus flag:** `-c phi` instead of `-c tlg`.
- **No Beta Code decode.** PHI text is plain Latin already — the Beta Code
  decode layer that TLG export needs (Greek accented text encoded in Beta
  Code) is bypassed entirely for Latin. Stage 1 for Latin is simpler, not
  symmetric, at this step.
- **Local PHI location:**
  `/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT/TLG Files/PHI`
  (744 files, including `AUTHTAB.DIR`), alongside the TLG folder at
  `…/TLG Files/TLG`.
- **Prefs/env resolution:** current manifests resolve the corpus location via
  the `TLG_DIR` env var (or the scratch `diogenes.prefs` `tlg_dir` line, per
  the TLG recipe above — verify which one is actually load-bearing for the
  installed 4.5 build before relying on either). EMPIRICAL UPDATE (Wave 2
  groundwork, 2026-07-17): the same `tlg_dir`-keyed prefs mechanism resolved
  the PHI corpus fine for a real `-c phi -n 0550` export — no separate
  `PHI_DIR` wiring was needed for exporting. A symmetric env var may still be
  wanted when the Latin pipeline reads PHI paths automatically; for manual
  exports, the existing recipe just works with `-c phi`.
  **CORRECTION (2026-08-29, native 4.7.2 re-export probe):** this does NOT
  hold in general — `Diogenes::Base` resolves `phi` corpus reads via a
  *separate* `{phi_dir}` hash key (`cdrom_dir = phi_dir` when `type eq 'phi'`,
  `Base.pm:557/608`), independent of `{tlg_dir}`. Pointing `tlg_dir` (whether
  via the prefs file or the `TLG_DIR` env var) at the PHI folder and running
  `-c phi -n 0474` fails: `Could not open lat0474.idt`. What works: set
  `phi_dir` — either a `phi_dir "…/TLG Files/PHI"` line in `diogenes.prefs`,
  or the `PHI_DIR` env var (mirrors `TLG_DIR`'s precedence, `Base.pm:505-509`,
  confirmed to take precedence over the prefs file). The 0550 case that
  worked in 2026-07-17 was not re-investigated; treat that report as
  unverified for the general case and use `phi_dir`/`PHI_DIR` going forward.
- **Author numbering:** PHI author IDs follow the PHI numbering scheme (not
  TLG's), keyed via `AUTHTAB.DIR` — verify the target author's PHI number
  before export, the same way TLG author numbers are verified via Diogenes
  author search.

### Deferred to Wave 2 (Latin-specific pipeline notes, not export-recipe items)

These affect later pipeline stages (tokenization, morphology lookup), not the
export step above, and are flagged here only so they aren't lost before Wave 2
starts:

- **u/v and i/j normalization** — PHI Latin text needs orthographic
  normalization before hitting `latin-analyses.txt` (Morpheus Latin), since
  classical texts mix u/v and i/j conventions inconsistently.
- **Enclitic splitting** (`-que`, `-ne`, `-ve`) — needed before dictionary
  lookup, the Latin analogue of the Greek pipeline's
  `beta.lookup_variants`; skipping it silently degrades click-to-parse
  coverage rather than erroring, so it's easy to miss until spot-checking
  turns up unparsed words.
