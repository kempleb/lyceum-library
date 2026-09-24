// Lyceum: mounted-corpus form_lemmata.json (John's Lemma-mode ruling,
// 2026-09-23). Covers corpus-adapter/search.mjs's buildFormLemmata(),
// which derives each mounted work's surface->headword map straight from
// that work's OWN token analyses (book-NN.json + analyses.json), mirroring
// pipeline/reader_pipeline/stage6_search.py's form_lemmata_idx rule: an
// entry survives only when it has at least one headword fold and the
// surface fold differs from every one of them; an ambiguous surface (more
// than one headword across its occurrences) keeps them all, sorted. Plus
// adaptSearchFiles() wiring it in end to end.
//
// Fixed 2026-09-23 (Sol re-review #1): buildFormLemmata() used to take a
// CORPUS-WIDE surface->headword map (merged across every mounted work) and
// restrict it to whichever of its headwords happened to also be one of
// THIS work's own lemma.json keys. That is a weaker check than "this
// work's own tokens actually produced this surface->headword pair": if
// another work in the corpus mapped the same surface to a headword this
// work also happens to have (from an unrelated token), the intersection
// kept that false link. Deriving directly from this work's own token
// analyses, as stage6_search.py does for native works, cannot produce a
// link no token in the work actually has -- see the cross-work test below.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { buildFormLemmata, adaptSearchFiles } from '../lib/corpus-adapter/search.mjs';

function tmpDir() {
  return mkdtempSync(join(tmpdir(), 'form-lemmata-test-'));
}

// Fold stand-in for these tests: identity, lowercased -- exercises
// buildFormLemmata()'s own logic (grouping, ambiguity, the self-map
// omission rule) without pulling in the real greekFold/latinFold bundle.
const identityFold = (s) => s.toLowerCase();

function book(segments) {
  return [{ book: 1, segments }];
}

function seg(id, tokens) {
  return { id, greek: [{ tokens }] };
}

test('buildFormLemmata derives surface->headword pairs from the work\'s own tokens', () => {
  const bookData = book([
    // sf1: two occurrences, two different lemmata -> ambiguous, both kept
    seg('s1', [{ k: 'sf1' }, { k: 'sf1' }]),
    // sf2: one occurrence, lemma differs from surface -> kept
    seg('s2', [{ k: 'sf2' }]),
    // same: lemma equals surface fold -> omitted (direct lemma.json lookup covers it)
    seg('s3', [{ k: 'same' }]),
    // noanalysis: key has no entry in analyses.json -> no groups -> omitted
    seg('s4', [{ k: 'noanalysis' }]),
  ]);
  const analyses = {
    sf1: [{ lemma: 'head1' }, { lemma: 'head2' }],
    sf2: [{ lemma: 'head1' }],
    same: [{ lemma: 'same' }],
  };

  const result = buildFormLemmata(bookData, analyses, identityFold);

  assert.deepEqual(result, {
    sf1: ['head1', 'head2'],
    sf2: ['head1'],
  });
});

test('buildFormLemmata: a group with no lemma falls back to the key itself (matches stage6_search.py)', () => {
  const bookData = book([seg('s1', [{ k: 'bareform' }])]);
  const analyses = { bareform: [{}] }; // no `lemma` field
  const result = buildFormLemmata(bookData, analyses, identityFold);
  // fl falls back to fold(key) === fold('bareform') === sf -> self-map, omitted
  assert.deepEqual(result, {});
});

test('buildFormLemmata does not produce a false cross-work link', () => {
  // Work W has surface `s` analysed as headword A in its OWN tokens only.
  // W separately has its own unrelated headword B (from surface `t`) --
  // exactly the shape that tripped the old corpus-wide-map intersection,
  // since B was one of W's own lemma.json keys even though no token in W
  // ever analysed `s` as B. Nothing here represents another work at all:
  // buildFormLemmata() only ever sees this work's own bookData/analyses,
  // so a link to a headword this work's own tokens never produced for `s`
  // is structurally impossible -- this test pins that property.
  const bookData = book([
    seg('s1', [{ k: 's' }]), // s -> A only, in this work
    seg('s2', [{ k: 't' }]), // t -> B, unrelated surface, same work
  ]);
  const analyses = {
    s: [{ lemma: 'A' }],
    t: [{ lemma: 'B' }],
  };

  const result = buildFormLemmata(bookData, analyses, identityFold);

  // t -> ['b'] is a legitimate entry (this work's own token t IS analysed
  // as headword B); the property under test is that s's entry stays ['a']
  // and never picks up 'b' just because B is also one of this work's own
  // headwords elsewhere.
  assert.deepEqual(result, { s: ['a'], t: ['b'] });
  assert.deepEqual(result.s, ['a'], 'must not include a link to B for surface s');
});

test('adaptSearchFiles writes form_lemmata.json unconditionally, derived from bookData/analyses', async () => {
  const searchDir = tmpDir();
  const bookData = [
    {
      book: 1,
      segments: [
        {
          id: 's1',
          greek: [{ tokens: [{ t: 'πᾶσα', k: 'pasa' }] }],
          english: { text: 'every' },
        },
      ],
    },
  ];
  const analyses = { pasa: [{ lemma: 'pas' }] };

  writeFileSync(join(searchDir, 'greek_form.json'), JSON.stringify({ pasa: [[0, 0]] }), 'utf8');
  writeFileSync(join(searchDir, 'greek_lemma.json'), JSON.stringify({ pas: [[0, 0]] }), 'utf8');
  writeFileSync(
    join(searchDir, 'meta.json'),
    JSON.stringify([{ id: 's1', book: 1, column: 'a' }]),
    'utf8',
  );
  writeFileSync(join(searchDir, 'english.json'), JSON.stringify({ every: [0] }), 'utf8');

  await adaptSearchFiles(searchDir, bookData, analyses, 'grc');

  const outPath = join(searchDir, 'form_lemmata.json');
  assert.ok(existsSync(outPath), 'form_lemmata.json should be written');
  const written = JSON.parse(readFileSync(outPath, 'utf8'));
  assert.deepEqual(written, { pasa: ['pas'] });
});

test('adaptSearchFiles writes an empty form_lemmata.json when no surface differs from its headword', async () => {
  const searchDir = tmpDir();
  const bookData = [
    {
      book: 1,
      segments: [
        {
          id: 's1',
          greek: [{ tokens: [{ t: 'καί', k: 'kai/' }] }],
          english: { text: 'and' },
        },
      ],
    },
  ];
  const analyses = { 'kai/': [{ lemma: 'kai/' }] }; // surface fold == lemma fold -> omitted

  writeFileSync(join(searchDir, 'greek_form.json'), JSON.stringify({ 'kai': [[0, 0]] }), 'utf8');
  writeFileSync(join(searchDir, 'greek_lemma.json'), JSON.stringify({ 'kai': [[0, 0]] }), 'utf8');
  writeFileSync(
    join(searchDir, 'meta.json'),
    JSON.stringify([{ id: 's1', book: 1, column: 'a' }]),
    'utf8',
  );
  writeFileSync(join(searchDir, 'english.json'), JSON.stringify({ and: [0] }), 'utf8');

  await adaptSearchFiles(searchDir, bookData, analyses, 'grc');

  const outPath = join(searchDir, 'form_lemmata.json');
  assert.ok(existsSync(outPath), 'form_lemmata.json should still be written (empty object)');
  const written = JSON.parse(readFileSync(outPath, 'utf8'));
  assert.deepEqual(written, {});
});
