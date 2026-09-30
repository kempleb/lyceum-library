# Pending: Forster's Problemata (not read by the build)

`problemata-forster.json` holds E. S. Forster's translation (The Works of
Aristotle vol. VII, Oxford 1927) of the five Problemata passages DK quotes
(Anaxagoras A69, A74; Empedocles A17, A69; Democritus A151), prepared
2026-09-26 from John's OCR and checked word by word against the page scans
(archive.org `worksofaristotle0007unse_o7n4`), with proposed spans.

On hold by John's call until the DK page structure is right. To ship: merge
`alternate.forster` into `../alternates.json`, add the `spans` to each work's
`context-english.json`, rebuild. The pipeline already supports it
(pseudo-Aristotle, Problemata, alternates only; commit 87b2a70).

Grok's check (2026-09-26): A74, Empedocles A17 pass; Anaxagoras A69 and
Democritus A151 bolds disputed (see below); Empedocles A69 is a reading
difference (Forster διὰ, DK καὶ) for John to rule on the page.
- Anaxagoras A69: Forster follows several readings that differ from DK's
  Greek (κίνησιν/κένωσιν, εἰ/ἤ, and others); the bold has gaps there. Grok
  wanted two gaps bolded ("driving the air forcibly …", "in itself").
- Democritus A151: "moulds" renders Bekker's τύπους; DK prints τόπους.
  Left unbolded; Grok's claim that it renders τόπους is wrong.
