// Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 3, 8).
//
// assertNoPrivate() is the mechanical gate behind the plan's "Private text:
// absent from their build/dist for Cat (verified)" probe finding: every
// registry translation marked `private: true` must carry no rendered text
// in ANY mounted book-NN.json for that work. It throws (naming every
// violation found) rather than silently filtering -- private text belongs
// to their own build's exclusion step (already verified to hold, per the
// probe), and this only confirms the invariant survives the mount.
//
// Field-name mapping (fixed schema field names in the legacy book-NN.json
// segment shape, NOT translator-id-derived -- confirmed against a live
// mounted segment: EE's rackham/secondary is private and its segments carry
// no "ross" key at all, while Cat's taylor/secondary is NOT private and
// its segments DO carry "ross" -- so "ross" is a fixed field name that
// holds whichever translation currently occupies the secondary slot, not a
// literal reference to the translator named Ross):
//   slot "english"   -> segment.english.text
//   slot "secondary" -> segment.ross[].text
//   slot "third"     -> segment.third[].text
//   slot "overlay"   -> segment.overlays[translation.id][].text
// "column" is not part of the legacy aristotle registry's slot vocabulary
// and is rejected loudly rather than silently skipped.

const SLOT_FIELDS = new Set(['english', 'secondary', 'third', 'overlay']);

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function chunkArrayHasText(chunks) {
  return Array.isArray(chunks) && chunks.some((c) => hasText(c?.text));
}

/**
 * @param {Array<{book: number, segments: Array<object>}>} bookData - every
 *   book-NN.json for the work, parsed, each with its filename for reporting.
 * @param {object} registryWork - the corpora/aristotle/registry.yaml work
 *   entry (translations[] with {id, slot, private?}).
 * @throws if any private translation's slot carries rendered text anywhere.
 */
export function assertNoPrivate(bookData, registryWork) {
  const privateTranslations = (registryWork.translations ?? []).filter((t) => t.private);
  if (privateTranslations.length === 0) return;

  const violations = [];

  for (const t of privateTranslations) {
    if (!SLOT_FIELDS.has(t.slot)) {
      throw new Error(
        `assertNoPrivate: ${registryWork.id}: translation ${t.id} declares private:true ` +
          `with unrecognized slot ${JSON.stringify(t.slot)} (expected one of ${[...SLOT_FIELDS].join('|')})`,
      );
    }

    for (const book of bookData) {
      for (const seg of book.segments ?? []) {
        let violated = false;
        if (t.slot === 'english') {
          violated = hasText(seg.english?.text);
        } else if (t.slot === 'secondary') {
          violated = chunkArrayHasText(seg.ross);
        } else if (t.slot === 'third') {
          violated = chunkArrayHasText(seg.third);
        } else if (t.slot === 'overlay') {
          violated = chunkArrayHasText(seg.overlays?.[t.id]);
        }
        if (violated) {
          violations.push(
            `${registryWork.id} book ${book.book ?? '?'} segment ${seg.id}: ` +
              `private translation ${t.id} (slot ${t.slot}) has rendered text`,
          );
        }
      }
    }
  }

  if (violations.length > 0) {
    throw new Error(
      `assertNoPrivate: ${violations.length} private-text violation(s):\n` +
        violations.map((v) => `  - ${v}`).join('\n'),
    );
  }
}
