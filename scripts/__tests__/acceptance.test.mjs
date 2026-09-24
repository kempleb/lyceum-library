import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  collectionMismatchReason, failLine, fetchManifestIndex, foreignRequests, indexLookups, instRefMatchesAddress,
  landingBodyTextFailReason, mergeCatalog, negativeUnknownTranslation, normalizeWhitespace, parseArgs, passLine,
  READABLE_TEXT_STRIP_SELECTORS, resolveManifestUrl, scanForCredentials, searchPhraseFor, selectInactiveWork,
  selectWorkIds, skipLine, splitAddress, staleProbeSkipReason, startsWithOpening, stripColPrefix, summarize,
  unknownTranslationProblems, validateFixtureShape,
} from '../acceptance.mjs';

// ── parseArgs ────────────────────────────────────────────────────────────

test('parseArgs reads origin/data-origin/works/fixture', () => {
  const args = parseArgs([
    '--origin', 'http://localhost:8787',
    '--data-origin', 'http://localhost:8787',
    '--works', 'EN,heraclitus-fragments',
    '--fixture', '/tmp/fixture.json',
  ]);
  assert.equal(args.origin, 'http://localhost:8787');
  assert.equal(args.dataOrigin, 'http://localhost:8787');
  assert.deepEqual(args.works, ['EN', 'heraclitus-fragments']);
  assert.equal(args.fixture, '/tmp/fixture.json');
  assert.equal(args.help, false);
});

test('parseArgs defaults works to null (every Active work)', () => {
  const args = parseArgs(['--origin', 'http://x', '--data-origin', 'http://x']);
  assert.equal(args.works, null);
});

test('parseArgs defaults drafts to false, and --drafts sets it true', () => {
  const off = parseArgs(['--origin', 'http://x', '--data-origin', 'http://x']);
  assert.equal(off.drafts, false);
  const on = parseArgs(['--origin', 'http://x', '--data-origin', 'http://x', '--drafts']);
  assert.equal(on.drafts, true);
});

test('parseArgs --help sets help and needs no other flags', () => {
  const args = parseArgs(['--help']);
  assert.equal(args.help, true);
});

test('parseArgs rejects an unknown flag', () => {
  assert.throws(() => parseArgs(['--bogus']), /unknown argument/);
});

// ── validateFixtureShape ─────────────────────────────────────────────────

function validFixture() {
  return {
    schema_version: 1,
    works: {
      EN: {
        edition: 'Bywater (OCT, 1894)',
        reviewed_by: null,
        passages: [
          { position: 'first', address: '/read/aristotle/nicomachean-ethics/book-1#col-1094a', language: 'grc', opening: 'πᾶσα τέχνη' },
          { position: 'middle', address: '/read/aristotle/nicomachean-ethics/book-5#col-1138a', language: 'grc', opening: 'περὶ δὲ δικαιοσύνης' },
          { position: 'last', address: '/read/aristotle/nicomachean-ethics/book-10#col-1181b', language: 'grc', opening: 'ἀλλὰ μὴν' },
        ],
      },
    },
  };
}

test('validateFixtureShape accepts a well-formed fixture', () => {
  const { ok, errors } = validateFixtureShape(validFixture());
  assert.equal(ok, true);
  assert.deepEqual(errors, []);
});

test('validateFixtureShape rejects a non-object', () => {
  assert.equal(validateFixtureShape(null).ok, false);
  assert.equal(validateFixtureShape([1, 2]).ok, false);
});

test('validateFixtureShape rejects the wrong schema_version', () => {
  const f = validFixture();
  f.schema_version = 2;
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('schema_version')));
});

test('validateFixtureShape rejects a passage with a bad position', () => {
  const f = validFixture();
  f.works.EN.passages[0].position = 'penultimate';
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('position')));
});

test('validateFixtureShape rejects a missing opening', () => {
  const f = validFixture();
  delete f.works.EN.passages[0].opening;
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('opening')));
});

// Sol review, finding 4: a fixture with only one passage, or with three
// passages all marked 'first', used to pass as "three passages" -- the
// shape check only required a nonempty array.
test('validateFixtureShape rejects a fixture with only one passage', () => {
  const f = validFixture();
  f.works.EN.passages = [f.works.EN.passages[0]];
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes("exactly one 'middle'")));
  assert.ok(errors.some((e) => e.includes("exactly one 'last'")));
});

test('validateFixtureShape rejects duplicate positions even with three entries', () => {
  const f = validFixture();
  f.works.EN.passages[1].position = 'first';
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes("exactly one 'first' passage, found 2")));
  assert.ok(errors.some((e) => e.includes("exactly one 'middle' passage, found 0")));
});

test('validateFixtureShape accepts reviewed_by as a string', () => {
  const f = validFixture();
  f.works.EN.reviewed_by = 'John Boyer';
  assert.equal(validateFixtureShape(f).ok, true);
});

test('validateFixtureShape rejects reviewed_by as a number', () => {
  const f = validFixture();
  f.works.EN.reviewed_by = 42;
  assert.equal(validateFixtureShape(f).ok, false);
});

// John, 2026-09-23: search-finds must search for a phrase set per sample
// passage, not the first three words of `opening` -- a passage's opening
// can start with a source citation or title (Heraclitus B1's "SEXT. adv.
// math. VII 132 ...", Seneca's "AD LVCILIVM EPISTVLAE ..."), so the fixture
// carries an optional `search` string per passage.
test('validateFixtureShape accepts a passage with a search string', () => {
  const f = validFixture();
  f.works.EN.passages[0].search = 'πᾶσα τέχνη';
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, true);
  assert.deepEqual(errors, []);
});

test('validateFixtureShape accepts a passage with no search field at all', () => {
  const f = validFixture();
  assert.equal(validateFixtureShape(f).ok, true);
});

test('validateFixtureShape reports a non-object passage instead of throwing', () => {
  const f = validFixture();
  f.works.EN.passages[1] = 'not a passage';
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('passages[1]')));
});

test('validateFixtureShape rejects a passage with an empty search string', () => {
  const f = validFixture();
  f.works.EN.passages[0].search = '';
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('search')));
});

test('validateFixtureShape rejects a passage with a non-string search', () => {
  const f = validFixture();
  f.works.EN.passages[0].search = 42;
  const { ok, errors } = validateFixtureShape(f);
  assert.equal(ok, false);
  assert.ok(errors.some((e) => e.includes('search')));
});

// ── searchPhraseFor ──────────────────────────────────────────────────────

test('searchPhraseFor uses passage.search when present', () => {
  const passage = { opening: 'AD LVCILIVM EPISTVLAE MORALES LIBER PRIMVS', search: 'Ita fac, mi' };
  assert.equal(searchPhraseFor(passage), 'Ita fac, mi');
});

test('searchPhraseFor falls back to the first three words of opening when search is absent', () => {
  const passage = { opening: 'Πᾶσα τέχνη καὶ πᾶσα μέθοδος' };
  assert.equal(searchPhraseFor(passage), 'Πᾶσα τέχνη καὶ');
});

// ── mergeCatalog ─────────────────────────────────────────────────────────

test('mergeCatalog: live wins over seed for a shared id', () => {
  const live = { works: [{ id: 'w1', editorial: { description: 'live desc', state: 'active' }, facts: {} }], collections: [] };
  const seed = { works: [{ id: 'w1', editorial: { description: 'seed desc', state: 'draft' }, facts: {} }], collections: [] };
  const { works } = mergeCatalog(live, seed);
  assert.equal(works.get('w1').description, 'live desc');
  assert.equal(works.get('w1').state, 'active');
});

test('mergeCatalog: a seed-only work is kept in allWorks with its own state', () => {
  const live = { works: [], collections: [] };
  const seed = { works: [{ id: 'w2', editorial: { state: 'draft' }, facts: {} }], collections: [] };
  const { allWorks } = mergeCatalog(live, seed);
  assert.equal(allWorks.get('w2').state, 'draft');
});

// Codex Sol re-verification of 8131f40, item 1: mergeCatalog used to keep a
// work of ANY state in `works`, so a dropped (non-active, non-kept-draft)
// work would still be checked as if the catalog served it. `works` now
// applies the same keep() rule as collections; `allWorks` is the unfiltered
// view SKIP messages read to name the dropped state.
test('mergeCatalog: a draft work is absent from works without includeDrafts', () => {
  const live = { works: [{ id: 'w1', editorial: { state: 'draft' }, facts: {} }], collections: [] };
  const { works, allWorks } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(works.has('w1'), false);
  assert.equal(allWorks.get('w1').state, 'draft');
});

test('mergeCatalog: a draft work is present in works with includeDrafts: true', () => {
  const live = { works: [{ id: 'w1', editorial: { state: 'draft' }, facts: {} }], collections: [] };
  const { works } = mergeCatalog(live, { works: [], collections: [] }, { includeDrafts: true });
  assert.equal(works.has('w1'), true);
  assert.equal(works.get('w1').state, 'draft');
});

test('mergeCatalog: a retired (neither active nor draft) work is absent from works even with includeDrafts', () => {
  const live = { works: [{ id: 'w1', editorial: { state: 'retired' }, facts: {} }], collections: [] };
  const { works, allWorks } = mergeCatalog(live, { works: [], collections: [] }, { includeDrafts: true });
  assert.equal(works.has('w1'), false);
  assert.equal(allWorks.get('w1').state, 'retired');
});

test('mergeCatalog: an active work is always kept in works', () => {
  const live = { works: [{ id: 'w1', editorial: { state: 'active' }, facts: {} }], collections: [] };
  const { works } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(works.has('w1'), true);
});

test('mergeCatalog: collections merge live-wins by id, and defaultPreset reads presentation.theme.preset', () => {
  const live = {
    works: [],
    collections: [{ id: 'c1', name: 'Live Name', state: 'active' }],
    presentation: { theme: { preset: 'parchment' }, presets: { parchment: {} } },
  };
  const seed = {
    works: [],
    collections: [
      { id: 'c1', name: 'Seed Name', state: 'active' },
      { id: 'c2', name: 'Seed Only', state: 'active' },
    ],
  };
  const { collections, defaultPreset } = mergeCatalog(live, seed);
  assert.equal(collections.get('c1'), 'Live Name');
  assert.equal(collections.get('c2'), 'Seed Only');
  assert.equal(defaultPreset, 'parchment');
});

// P2 finding: mergeCatalog used to keep every collection regardless of
// state, while parseCatalog (shared/lib/lyceum-catalog-source.ts) drops a
// draft collection unless includeDrafts is set -- a work linked to a draft
// collection would pass mergeCatalog's own check for a collection the
// rendered page never shows. Mirrored via the same keep() rule, driven by
// the script's --drafts flag.
test('mergeCatalog: excludes a draft collection without includeDrafts', () => {
  const live = { works: [], collections: [{ id: 'c1', name: 'Draft Collection', state: 'draft' }] };
  const { collections } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(collections.has('c1'), false);
});

test('mergeCatalog: includes a draft collection with includeDrafts: true', () => {
  const live = { works: [], collections: [{ id: 'c1', name: 'Draft Collection', state: 'draft' }] };
  const { collections } = mergeCatalog(live, { works: [], collections: [] }, { includeDrafts: true });
  assert.equal(collections.get('c1'), 'Draft Collection');
});

test('mergeCatalog: a collection with no state defaults to draft, same as parseCatalog', () => {
  const live = { works: [], collections: [{ id: 'c1', name: 'No State' }] };
  const { collections } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(collections.has('c1'), false);
});

// Sol review, finding 2: mergeCatalog used to keep any editorial.preset (or
// presentation.theme.preset) string verbatim; parseCatalog
// (shared/lib/lyceum-catalog-source.ts) drops a preset name absent from the
// live catalog's own presentation.presets. Mirrored here for both a work's
// own preset and the catalog-wide default.
test('mergeCatalog: drops a work preset absent from presentation.presets', () => {
  const live = {
    works: [{ id: 'w1', editorial: { preset: 'nonexistent', state: 'active' }, facts: {} }],
    collections: [],
    presentation: { presets: { parchment: {} } },
  };
  const { works } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(works.get('w1').preset, '');
});

test('mergeCatalog: keeps a work preset present in presentation.presets', () => {
  const live = {
    works: [{ id: 'w1', editorial: { preset: 'parchment', state: 'active' }, facts: {} }],
    collections: [],
    presentation: { presets: { parchment: {} } },
  };
  const { works } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(works.get('w1').preset, 'parchment');
});

test('mergeCatalog: drops defaultPreset when presentation.presets is absent entirely', () => {
  const live = {
    works: [], collections: [], presentation: { theme: { preset: 'parchment' } },
  };
  const { defaultPreset } = mergeCatalog(live, { works: [], collections: [] });
  assert.equal(defaultPreset, '');
});

// ── indexLookups / selectWorkIds ─────────────────────────────────────────

function sampleIndex() {
  return {
    corpus_version: 'v1',
    manifests: [
      { work: 'lyceum:aristotle.nicomachean-ethics', path: '/EN/manifest.lyceum.json', sha256: 'a' },
      { work: 'lyceum:heraclitus.fragments', path: '/heraclitus-fragments/manifest.lyceum.json', sha256: 'b' },
    ],
  };
}

test('indexLookups derives the short id from each entry\'s own path', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  assert.equal(shortIdToEntry.get('EN').work, 'lyceum:aristotle.nicomachean-ethics');
  assert.equal(lyceumKeyToShortId.get('lyceum:heraclitus.fragments'), 'heraclitus-fragments');
});

test('selectWorkIds with explicit --works checks a work already kept in mergedWorks', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  const mergedWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'active' }],
  ]);
  const out = selectWorkIds({ explicitWorks: ['EN'], mergedWorks, lyceumKeyToShortId, shortIdToEntry });
  assert.deepEqual(out, [{ displayId: 'EN', lyceumKey: 'lyceum:aristotle.nicomachean-ethics', shortId: 'EN', manifestEntry: shortIdToEntry.get('EN') }]);
});

test('selectWorkIds with an explicit id absent from the manifest index -> SKIP entry', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  const out = selectWorkIds({ explicitWorks: ['nonexistent'], mergedWorks: new Map(), lyceumKeyToShortId, shortIdToEntry });
  assert.deepEqual(out, [{ displayId: 'nonexistent', skip: 'not built in this release' }]);
});

// Codex Sol re-verification of 8131f40, item 1 consequence: a --works id
// that names a real, built catalog work mergeCatalog's own keep rule
// dropped (not active, draft without --drafts) must SKIP naming the state,
// not fail or silently vanish from the run.
test('selectWorkIds with an explicit id mergeCatalog dropped -> SKIP naming the state', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  const mergedWorks = new Map(); // filtered: the draft work below was dropped
  const allWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'draft' }],
  ]);
  const out = selectWorkIds({ explicitWorks: ['EN'], mergedWorks, allWorks, lyceumKeyToShortId, shortIdToEntry });
  assert.deepEqual(out, [{ displayId: 'EN', skip: 'not active in the catalog (state draft)' }]);
});

test('selectWorkIds with an explicit id built but absent from the catalog entirely is still checked', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  const mergedWorks = new Map();
  const allWorks = new Map(); // not in the catalog at all, not just filtered out
  const out = selectWorkIds({ explicitWorks: ['EN'], mergedWorks, allWorks, lyceumKeyToShortId, shortIdToEntry });
  assert.deepEqual(out, [{ displayId: 'EN', lyceumKey: 'lyceum:aristotle.nicomachean-ethics', shortId: 'EN', manifestEntry: shortIdToEntry.get('EN') }]);
});

test('selectWorkIds with no --works: every Active catalog work, built or not', () => {
  const { shortIdToEntry, lyceumKeyToShortId } = indexLookups(sampleIndex());
  const mergedWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'active' }],
    ['lyceum:heraclitus.fragments', { state: 'draft' }], // not active: excluded
    ['lyceum:caesar.civil-war', { state: 'active' }], // active but no manifest entry: SKIP
  ]);
  const out = selectWorkIds({ explicitWorks: null, mergedWorks, lyceumKeyToShortId, shortIdToEntry });
  assert.deepEqual(out, [
    { displayId: 'EN', lyceumKey: 'lyceum:aristotle.nicomachean-ethics', shortId: 'EN', manifestEntry: shortIdToEntry.get('EN') },
    { displayId: 'lyceum:caesar.civil-war', skip: 'not built in this release' },
  ]);
});

// ── selectInactiveWork ────────────────────────────────────────────────────

test('selectInactiveWork with no --drafts picks the first non-active work, draft or not', () => {
  const mergedWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'active' }],
    ['lyceum:heraclitus.fragments', { state: 'draft' }],
  ]);
  const result = selectInactiveWork(mergedWorks, false);
  assert.deepEqual(result, ['lyceum:heraclitus.fragments', { state: 'draft' }]);
});

test('selectInactiveWork with drafts=true skips a draft work', () => {
  const mergedWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'active' }],
    ['lyceum:heraclitus.fragments', { state: 'draft' }],
  ]);
  const result = selectInactiveWork(mergedWorks, true);
  assert.equal(result, null);
});

test('selectInactiveWork with drafts=true picks a non-draft, non-active work when one exists', () => {
  const mergedWorks = new Map([
    ['lyceum:aristotle.nicomachean-ethics', { state: 'active' }],
    ['lyceum:heraclitus.fragments', { state: 'draft' }],
    ['lyceum:caesar.civil-war', { state: 'retired' }],
  ]);
  const result = selectInactiveWork(mergedWorks, true);
  assert.deepEqual(result, ['lyceum:caesar.civil-war', { state: 'retired' }]);
});

// ── foreignRequests / scanForCredentials ─────────────────────────────────

test('foreignRequests flags a request whose host is neither origin nor data-origin', () => {
  const urls = [
    'http://localhost:8787/read/x',
    'http://localhost:8787/data/x/manifest.lyceum.json',
    'https://fonts.googleapis.com/css',
    'https://lyceuminstitute.org/wp-content/plugin.js',
  ];
  const offenders = foreignRequests(urls, 'localhost:8787', 'localhost:8787');
  assert.deepEqual(offenders, ['https://fonts.googleapis.com/css', 'https://lyceuminstitute.org/wp-content/plugin.js']);
});

test('foreignRequests allows a distinct data-origin host', () => {
  const urls = ['https://data.lyceum.institute/releases/x/manifest.lyceum.json'];
  const offenders = foreignRequests(urls, 'library.lyceum.institute', 'data.lyceum.institute');
  assert.deepEqual(offenders, []);
});

test('foreignRequests ignores an unparsable URL rather than flagging it', () => {
  const offenders = foreignRequests(['not a url'], 'localhost:8787', 'localhost:8787');
  assert.deepEqual(offenders, []);
});

test('scanForCredentials finds the configured token value', () => {
  const hits = scanForCredentials('<script>const t = "secret-abc"</script>', 'secret-abc');
  assert.deepEqual(hits, ['LYCEUM_PUBLISH_TOKEN value']);
});

test('scanForCredentials finds the literal env-assignment string even with no token configured', () => {
  const hits = scanForCredentials('LYCEUM_PUBLISH_TOKEN=whatever', undefined);
  assert.deepEqual(hits, ['LYCEUM_PUBLISH_TOKEN=']);
});

test('scanForCredentials finds a bare Authorization: Bearer string', () => {
  const hits = scanForCredentials('fetch(url, {headers: {Authorization: Bearer xyz}})', undefined);
  assert.deepEqual(hits, ['Authorization: Bearer']);
});

test('scanForCredentials finds nothing in ordinary page text', () => {
  assert.deepEqual(scanForCredentials('<h1>Nicomachean Ethics</h1>', 'secret-abc'), []);
});

// ── startsWithOpening / normalizeWhitespace ──────────────────────────────

test('normalizeWhitespace collapses runs of whitespace and trims', () => {
  assert.equal(normalizeWhitespace('  a\n\tb   c  '), 'a b c');
});

test('startsWithOpening ignores whitespace differences between rendered text and the fixture', () => {
  assert.equal(startsWithOpening('πᾶσα   τέχνη\nκαὶ πᾶσα μέθοδος...', 'πᾶσα τέχνη καὶ'), true);
});

test('startsWithOpening is false when the rendered text starts differently', () => {
  assert.equal(startsWithOpening('something else entirely', 'πᾶσα τέχνη'), false);
});

// ── resolveManifestUrl ───────────────────────────────────────────────────

test('resolveManifestUrl resolves entry.path against where the index was fetched from', () => {
  const url = resolveManifestUrl(
    { path: '/EN/manifest.lyceum.json', url: 'https://pub-example.r2.dev/EN/manifest.lyceum.json' },
    'http://localhost:8787/data/manifests/index.json',
  );
  assert.equal(url, 'http://localhost:8787/data/EN/manifest.lyceum.json');
});

test('resolveManifestUrl matches data_root+path when the index itself was fetched from the data root', () => {
  const url = resolveManifestUrl(
    { path: '/EN/manifest.lyceum.json' },
    'https://data.lyceum.institute/releases/v1/manifests/index.json',
  );
  assert.equal(url, 'https://data.lyceum.institute/releases/v1/EN/manifest.lyceum.json');
});

// ── splitAddress / stripColPrefix / instRefMatchesAddress ────────────────
// Sol review, finding 16: pure helpers behind the DOM/redirect/search-match
// decisions, split out so they're unit-testable without a browser.

test('splitAddress splits on the first # into path and fragment', () => {
  assert.deepEqual(splitAddress('/read/aristotle/nicomachean-ethics/book-1#col-1094a'),
    { path: '/read/aristotle/nicomachean-ethics/book-1', fragment: 'col-1094a' });
});

test('splitAddress with no # returns a null fragment', () => {
  assert.deepEqual(splitAddress('/read/aristotle/nicomachean-ethics/book-1'),
    { path: '/read/aristotle/nicomachean-ethics/book-1', fragment: null });
});

test('stripColPrefix strips a leading col- case-insensitively and lowercases the rest', () => {
  assert.equal(stripColPrefix('col-1094A'), '1094a');
  assert.equal(stripColPrefix('COL-B30'), 'b30');
});

test('stripColPrefix leaves a fragment with no col- prefix alone but lowercases it', () => {
  assert.equal(stripColPrefix('B30'), 'b30');
});

// ── READABLE_TEXT_STRIP_SELECTORS ─────────────────────────────────────────
// Sol review, 2026-09-23: findColumnText's readableText() (runs inside
// page.evaluate, so not directly unit-testable) only stripped .line-num
// before comparing a matched column's text against a passage's opening
// words. shared/components/Reader.svelte renders other gutter/decorative
// text inside the same column that can lead a passage's real opening words:
// .bk-num (Bekker-number gutter, e.g. Reader.svelte:3026-3031, 3071-3076)
// and, more seriously, the hidden chapter-title spacer at Reader.svelte:3744
// (`<div class="overlay-chapter-title overlay-chapter-title-spacer"
// aria-hidden="true">{spacerTitle}</div>`) that keeps the Greek and English
// columns the same height -- its aria-hidden title text was exactly what
// the 2026-09-23 rehearsal found leading the comparison. The selector list
// itself is pulled out as exported data (rather than left inline in the
// page.evaluate string) so its membership is unit-testable without a DOM;
// the actual stripping still has to run in-browser against the live clone.
test('READABLE_TEXT_STRIP_SELECTORS strips line numbers, Bekker numbers, and hidden decorative nodes', () => {
  assert.deepEqual(READABLE_TEXT_STRIP_SELECTORS, ['.line-num', '.bk-num', '[aria-hidden="true"]']);
});

test('instRefMatchesAddress matches an href whose path and loc column agree with the address', () => {
  const href = '/read/aristotle/nicomachean-ethics/book-1?loc=1094a:15';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1#col-1094a'), true);
});

test('instRefMatchesAddress is case-insensitive on the loc column', () => {
  const href = '/read/aristotle/nicomachean-ethics/book-1?loc=1094A';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1#col-1094a'), true);
});

test('instRefMatchesAddress rejects a different work path', () => {
  const href = '/read/plato/republic/book-1?loc=1094a:15';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1#col-1094a'), false);
});

test('instRefMatchesAddress rejects a matching path but a different loc column', () => {
  const href = '/read/aristotle/nicomachean-ethics/book-1?loc=1138a:1';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1#col-1094a'), false);
});

test('instRefMatchesAddress with no fragment matches on path alone', () => {
  const href = '/read/aristotle/nicomachean-ethics/book-1?loc=anything';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1'), true);
});

// Grok review finding B: `href.startsWith(path)` matched a longer sibling
// route whose id has the shorter one as a text prefix (letter-1 / letter-10,
// book-1 / book-10) -- the character right after `path` must end the path
// segment ('?', '#', or nothing), not continue it.
test('instRefMatchesAddress rejects letter-10 as a match for letter-1', () => {
  const href = '/read/seneca/epistulae-morales/letter-10?loc=1:1';
  assert.equal(instRefMatchesAddress(href, '/read/seneca/epistulae-morales/letter-1#col-1'), false);
});

test('instRefMatchesAddress rejects book-10 as a match for book-1', () => {
  const href = '/read/aristotle/nicomachean-ethics/book-10?loc=1094a';
  assert.equal(instRefMatchesAddress(href, '/read/aristotle/nicomachean-ethics/book-1#col-1094a'), false);
});

test('instRefMatchesAddress still matches letter-1 itself', () => {
  const href = '/read/seneca/epistulae-morales/letter-1?loc=1:1';
  assert.equal(instRefMatchesAddress(href, '/read/seneca/epistulae-morales/letter-1#col-1'), true);
});

// ── unknownTranslationProblems ────────────────────────────────────────────
// Sol review, finding 10: the caller now SKIPs when the checked-entry set
// is empty (see negativeUnknownTranslation), rather than this pure function
// silently returning no problems. That empty-population rule itself is
// exercised via the async wrapper's behaviour, covered below.

test('unknownTranslationProblems flags a default_translation absent from the manifest', () => {
  const entries = [{ lyceumKey: 'lyceum:aristotle.en', shortId: 'EN' }];
  const mergedWorks = new Map([['lyceum:aristotle.en', { defaultTranslation: 'rackham-en' }]]);
  const manifestFetchByShortId = new Map([['EN', { translations: [{ id: 'ross-en' }] }]]);
  const problems = unknownTranslationProblems(entries, mergedWorks, manifestFetchByShortId);
  assert.equal(problems.length, 1);
  assert.match(problems[0], /rackham-en/);
});

test('unknownTranslationProblems is silent when the default_translation is present', () => {
  const entries = [{ lyceumKey: 'lyceum:aristotle.en', shortId: 'EN' }];
  const mergedWorks = new Map([['lyceum:aristotle.en', { defaultTranslation: 'ross-en' }]]);
  const manifestFetchByShortId = new Map([['EN', { translations: [{ id: 'ross-en' }] }]]);
  assert.deepEqual(unknownTranslationProblems(entries, mergedWorks, manifestFetchByShortId), []);
});

test('unknownTranslationProblems skips an entry with no default_translation or no fetched manifest', () => {
  const entries = [
    { lyceumKey: 'lyceum:a', shortId: 'A' },
    { lyceumKey: 'lyceum:b', shortId: 'B' },
  ];
  const mergedWorks = new Map([
    ['lyceum:a', { defaultTranslation: '' }],
    ['lyceum:b', { defaultTranslation: 'x-en' }],
  ]);
  const manifestFetchByShortId = new Map(); // neither manifest was fetched
  assert.deepEqual(unknownTranslationProblems(entries, mergedWorks, manifestFetchByShortId), []);
});

// ── negativeUnknownTranslation ────────────────────────────────────────────
// Grok review finding E(16b): the empty-checked-set rule (Sol review finding
// 10, already applied inside negativeUnknownTranslation) had no direct test
// -- exercised here against the async function itself rather than just its
// pure unknownTranslationProblems helper.

test('negativeUnknownTranslation SKIPs (not PASS) when the checked-entry set is empty', async () => {
  const line = await negativeUnknownTranslation([], new Map(), new Map());
  assert.equal(line, 'SKIP negative:unknown-translation-reported: no active work had its manifest fetched to check');
});

test('negativeUnknownTranslation PASSes when the checked set is nonempty and clean', async () => {
  const entries = [{ lyceumKey: 'lyceum:aristotle.en', shortId: 'EN' }];
  const mergedWorks = new Map([['lyceum:aristotle.en', { defaultTranslation: 'ross-en' }]]);
  const manifestFetchByShortId = new Map([['EN', { translations: [{ id: 'ross-en' }] }]]);
  const line = await negativeUnknownTranslation(entries, mergedWorks, manifestFetchByShortId);
  assert.equal(line, 'PASS negative:unknown-translation-reported');
});

// ── staleProbeSkipReason ──────────────────────────────────────────────────
// Grok review finding A/E(16c), tightened by a follow-up Grok review of
// commit 43e8323: whether the stale-revision half of negative:publish-rejects
// is safe to run, decided from the served catalog.snapshot.json response's
// x-catalog-source header alone (pure, no fetch). This is now an allowlist
// -- only the exact value 'kv' (loadLiveCatalog's stored-catalog source, see
// catalog-runtime.ts ~line 248) proceeds; everything else, including an
// absent header, SKIPs with a reason that says what is actually known.

test('staleProbeSkipReason proceeds only when the header is exactly kv', () => {
  assert.equal(staleProbeSkipReason('kv'), null);
});

test('staleProbeSkipReason skips when the header is absent, with a reason naming what is unknown', () => {
  assert.match(staleProbeSkipReason(null), /x-catalog-source absent/);
  assert.match(staleProbeSkipReason(undefined), /x-catalog-source absent/);
});

test('staleProbeSkipReason skips on fixture-fallback, with the empty-store reason', () => {
  assert.match(staleProbeSkipReason('fixture-fallback'), /catalog store empty or unreadable/);
});

test('staleProbeSkipReason skips on fixture, with the empty-store reason', () => {
  assert.match(staleProbeSkipReason('fixture'), /catalog store empty or unreadable/);
});

test('staleProbeSkipReason skips on any other value, naming the value seen', () => {
  assert.equal(staleProbeSkipReason('r2'), 'x-catalog-source=r2 is not the stored-catalog value');
});

// ── landingBodyTextFailReason ─────────────────────────────────────────────
// Follow-up Grok review of commit 43e8323: checkLanding used to fall back to
// document.body.innerText when main.lp-body was missing, reopening the
// whole-page false PASS finding D fixed. The null-means-FAIL decision is
// pulled out of the page.evaluate call so it is testable without a browser.

test('landingBodyTextFailReason fails when main.lp-body is missing', () => {
  assert.equal(landingBodyTextFailReason(null), 'no main.lp-body');
});

test('landingBodyTextFailReason passes through an empty-but-present element', () => {
  assert.equal(landingBodyTextFailReason(''), null);
});

test('landingBodyTextFailReason passes through real text', () => {
  assert.equal(landingBodyTextFailReason('some content'), null);
});

// ── collectionMismatchReason ────────────────────────────────────────────
// checkLanding's landing-renders check now reads
// [data-collections] [data-collection-id] instead of scanning main's whole
// text for each collection name; this is the pure comparison behind that.

test('collectionMismatchReason passes when the rendered set matches exactly', () => {
  const rendered = [{ id: 'greek', name: 'Greek' }, { id: 'aristotle', name: 'Aristotle' }];
  const expected = [{ id: 'greek', name: 'Greek' }, { id: 'aristotle', name: 'Aristotle' }];
  assert.equal(collectionMismatchReason(rendered, expected), null);
});

test('collectionMismatchReason passes when both are empty', () => {
  assert.equal(collectionMismatchReason([], []), null);
});

// P3 finding: the page promises editorial.collection_ids order (Landing.astro
// renders `collections` in workCollections' own order); a comparison that
// ignored order let a reversed rendering pass. Order now matters.
test('collectionMismatchReason fails when order differs from editorial.collection_ids', () => {
  const rendered = [{ id: 'aristotle', name: 'Aristotle' }, { id: 'greek', name: 'Greek' }];
  const expected = [{ id: 'greek', name: 'Greek' }, { id: 'aristotle', name: 'Aristotle' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /order mismatch/);
});

test('collectionMismatchReason fails when the page is missing an expected id', () => {
  const rendered = [{ id: 'greek', name: 'Greek' }];
  const expected = [{ id: 'greek', name: 'Greek' }, { id: 'aristotle', name: 'Aristotle' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /missing collection 'aristotle'/);
});

test('collectionMismatchReason fails on a duplicated rendered id, even if it otherwise matches', () => {
  const rendered = [{ id: 'greek', name: 'Greek' }, { id: 'greek', name: 'Greek' }];
  const expected = [{ id: 'greek', name: 'Greek' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /more than once/);
});

test('collectionMismatchReason passes when no collections are expected and there is no container at all', () => {
  const reason = collectionMismatchReason([], [], { hasContainer: false });
  assert.equal(reason, null);
});

test('collectionMismatchReason fails when no collections are expected but an empty container is rendered', () => {
  const reason = collectionMismatchReason([], [], { hasContainer: true });
  assert.match(reason, /empty \[data-collections\]/);
});

test('collectionMismatchReason fails when the page renders an id the catalog does not expect', () => {
  const rendered = [{ id: 'greek', name: 'Greek' }, { id: 'stoics', name: 'Stoics' }];
  const expected = [{ id: 'greek', name: 'Greek' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /unexpected collection 'stoics'/);
});

test('collectionMismatchReason fails when a name does not match', () => {
  const rendered = [{ id: 'greek', name: 'Greek Texts' }];
  const expected = [{ id: 'greek', name: 'Greek' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /rendered as 'Greek Texts', expected 'Greek'/);
});

// Codex Sol re-verification of 8131f40, item 2: expected [a, a] (the catalog
// names the same collection twice for a work) against rendered [a] used to
// find neither a missing nor an extra id in the unequal-length branch and
// dereference undefined. The duplicate is now caught up front and named as
// the catalog's own defect, not the page's.
test('collectionMismatchReason names a duplicated expected id instead of crashing', () => {
  const rendered = [{ id: 'greek', name: 'Greek' }];
  const expected = [{ id: 'greek', name: 'Greek' }, { id: 'greek', name: 'Greek' }];
  const reason = collectionMismatchReason(rendered, expected);
  assert.match(reason, /catalog names collection 'greek' more than once/);
});


// ── fetchManifestIndex ────────────────────────────────────────────────────
// Grok review finding E(16a): the returned indexUrl must be the response's
// own `res.url` (the address actually served, following any redirect), not
// the candidate URL requested -- exercised here with a fake fetch whose
// Response.url differs from the request.

test('fetchManifestIndex returns res.url, not the requested candidate URL', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url) => {
    assert.equal(url, 'http://x/manifests/index.json');
    return {
      ok: true,
      url: 'http://x/releases/v3/manifests/index.json',
      json: async () => ({ manifests: [] }),
    };
  };
  try {
    const { json, indexUrl } = await fetchManifestIndex('http://x');
    assert.deepEqual(json, { manifests: [] });
    assert.equal(indexUrl, 'http://x/releases/v3/manifests/index.json');
  } finally {
    globalThis.fetch = original;
  }
});

test('fetchManifestIndex falls back to /data/manifests/index.json when the first candidate 404s', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url === 'http://x/manifests/index.json') return { ok: false, status: 404 };
    return { ok: true, url: 'http://x/data/manifests/index.json', json: async () => ({ manifests: [] }) };
  };
  try {
    const { indexUrl } = await fetchManifestIndex('http://x');
    assert.equal(indexUrl, 'http://x/data/manifests/index.json');
  } finally {
    globalThis.fetch = original;
  }
});

// ── result-line formatting / summarize ───────────────────────────────────

test('passLine/failLine/skipLine format as specified', () => {
  assert.equal(passLine('EN'), 'PASS EN');
  assert.equal(passLine('EN', 'fixture unreviewed'), 'PASS EN (fixture unreviewed)');
  assert.equal(failLine('EN', 'manifest-hash', 'expected a, got b'), 'FAIL EN: manifest-hash (expected a, got b)');
  assert.equal(skipLine('lyceum:caesar.civil-war', 'not built in this release'), 'SKIP lyceum:caesar.civil-war: not built in this release');
});

test('summarize counts each kind and sets exitCode 1 iff any FAIL', () => {
  const lines = [passLine('a'), failLine('b', 'x', 'y'), skipLine('c', 'z'), passLine('d')];
  assert.deepEqual(summarize(lines), { pass: 2, fail: 1, skip: 1, exitCode: 1 });
});

test('summarize with no failures exits 0', () => {
  const lines = [passLine('a'), skipLine('b', 'z')];
  assert.deepEqual(summarize(lines), { pass: 1, fail: 0, skip: 1, exitCode: 0 });
});
