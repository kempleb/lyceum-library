<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { lookupWord, fetchLemmata, lemmaEntryHref, type Analysis, type LsjEntry, type LemmaRef } from '../lib/data';
  import { betaToGreek } from '../lib/betacode';
  import { renderLsjEntry } from '../lib/html';
  import { getWork } from '../lib/works';

  export let work: string = 'EN';
  // Matches Reader.svelte's sourceLang / Landing.astro's sourceLangTag
  // convention ('la', not 'lat'). Wave 2 Batch 1b: De Officiis now ships a
  // real lexicon, so this popup opens for Latin tokens too — `isLat` gates
  // every language-dependent presentation choice below (dictionary label,
  // lemma-page path, and — critically — whether the lemma display runs
  // through betaToGreek at all: Latin lemmata are already plain display
  // text, not Beta Code, so betaToGreek must never touch them, or it would
  // mistransliterate ordinary Latin words into Greek letters).
  const isLat = getWork(work)?.language === 'lat';
  const sourceLang = isLat ? 'la' : 'grc';
  const langPath: 'grc' | 'lat' = isLat ? 'lat' : 'grc';
  const dictLabel = isLat ? 'L&S' : 'LSJ';
  // k is optional: a non-lexical token (no Greek letters — inline apparatus,
  // editor names, bare numerals) has none, and the caller only opens this
  // popup for clickable (keyed) tokens in the first place — see Reader's
  // greekToks snippet, which renders an unkeyed token as plain text, never
  // clickable. The guard on the lookup below is defense-in-depth.
  export let token: { t: string; k?: string };
  export const anchor: { x: number; y: number } = { x: 0, y: 0 };
  export let onClose: () => void;
  // Compare mode packs three columns into the reading measure; on a tablet the
  // right-margin reserve would crush them, so there the panel drops to a bottom
  // sheet (like the phone layout) and the text keeps full width. See the
  // .word-sidebar.as-sheet block in global.css.
  export let asSheet: boolean = false;
  // PUBLIC_LYCEUM_CHROME=1 only (John, 2026-09-01): render the Grammata T8
  // widget's LSJ/L&S entry instead of our own shard HTML. Threaded down from
  // ReaderShell.astro's `lyceumChrome` const via Reader.svelte; default false
  // so every other host is untouched.
  export let grammataLookup: boolean = false;

  let dialogEl: HTMLDivElement;
  let previousFocus: HTMLElement | null = null;
  let analyses: Analysis[] = [];
  let lsj: LsjEntry[] = [];
  let loading = true;
  let error = '';
  // Resolved synchronously at instantiation (this component only ever mounts
  // client-side, on a word click) so the intro transition picks the right
  // direction: mobile rises from the bottom, desktop slides in from the right.
  // Reading it in onMount would be too late — Svelte evaluates transition
  // params when the element mounts, before onMount runs.
  const isMobile = typeof window !== 'undefined'
    && window.matchMedia('(max-width: 680px)').matches;
  // Whether we render as a bottom sheet: always on phones, and on tablets when
  // the caller is in compare mode (asSheet) — matches the CSS in global.css.
  const asSheetHere = typeof window !== 'undefined'
    && (isMobile || (asSheet && window.matchMedia('(min-width: 681px) and (max-width: 1100px)').matches));
  // Honour the OS "reduce motion" setting: the fly-in is decorative, so collapse
  // it to an instant appearance. (The CSS @media query can't reach Svelte's JS
  // transitions, so it's gated here too.)
  const reduceMotion = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Reactive on token.k: clicking another word while the panel is open swaps
  // the analysis in place (Reader reuses this instance — no remount, no
  // reflow). The request id guards against out-of-order responses when the
  // reader clicks quickly.
  let reqId = 0;
  $: loadWord(work, token.k);
  function loadWord(w: string, k: string | undefined) {
    const id = ++reqId;
    if (!k) {
      // Defense-in-depth only (see the note on `token` above): should be
      // unreachable in practice, since the caller never opens this popup for
      // an unkeyed token.
      analyses = [];
      lsj = [];
      error = '';
      loading = false;
      return;
    }
    loading = true;
    error = '';
    lookupWord(w, k)
      .then(r => { if (id !== reqId) return; analyses = r.analyses; lsj = r.lsj; })
      .catch(e => { if (id !== reqId) return; error = String(e); })
      .finally(() => { if (id === reqId) loading = false; });
  }

  // The lemma-page manifest (loaded once, cached): lets each analysis card offer
  // a "see all N occurrences" link into /lemma/<langPath>/entry/?w=<slug>, but only for
  // lemmata that actually have a page. Absent manifest = no links, popup unchanged.
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  let lemmata: Record<string, LemmaRef> = {};
  fetchLemmata(langPath).then(m => { lemmata = m; }).catch(() => {});
  // This card's own dictionary entries, resolved from the pooled `lsj` list
  // by the keys THIS analysis carries (a.lsj) -- scopes each card to only
  // the entries that are actually candidates for ITS lemma, not every
  // entry fetched for every card in the popup.
  const entriesFor = (a: Analysis): LsjEntry[] =>
    a.lsj.map((k) => lsj.find((e) => e.key === k)).filter((e): e is LsjEntry => !!e);
  // A card's lemma page keys off its primary dictionary key (matching the
  // concordance) -- but ONLY when the card resolved to exactly one
  // candidate. Governing principle (Wave 2 Batch 1b homonym fan-out review):
  // THE READER MUST NEVER BE SHOWN A WRONG GLOSS AS IF CERTAIN -- a card
  // with >1 surviving dictionary candidate (see entriesFor above) hasn't
  // been resolved to one specific headword, so linking to "the" lemma page
  // for a)/(one of several) would assert a certainty the data doesn't have.
  const lemmaRef = (a: Analysis): LemmaRef | null =>
    (a.lsj.length === 1 && lemmata[a.lsj[0]]) || null;
  // Latin lemmata are already plain display text (no Beta Code); Greek's
  // lemma field IS Beta Code and must be converted. Prefer the dictionary
  // entry's pre-converted head when every surviving candidate AGREES on it
  // -- homographs share their headword spelling by definition (that shared
  // spelling is exactly why they collided), so an ambiguous card can still
  // display the common head without asserting WHICH entry is meant; only
  // when candidates genuinely differ in spelling (a fold-fallback match,
  // e.g. Greek adverb -> adjective heading) does this fall back to the raw
  // lemma -- with Diogenes' internal '#N' homonym marker stripped for
  // Latin, which is pipeline vocabulary a reader should never see.
  const displayLemma = (a: Analysis): string => {
    const heads = [...new Set(entriesFor(a).map((e) => e.head))];
    if (heads.length === 1) return heads[0];
    return isLat ? a.lemma.replace(/#\d+$/, '') : betaToGreek(a.lemma);
  };

  // Grammata T8 lookup widget (John, 2026-09-01) — LSJ/L&S rendered by
  // grammata.pages.dev instead of our own shard HTML, when grammataLookup is
  // true. Imported from grammata's OWN public URL, never vendored: the
  // grammar-site handoff (handoff-lsj-widget.md) is explicit that central
  // serving is the architecture — "one grammata deploy updates every reader
  // site" — and forbids copying/vendoring/reimplementing anything from it.
  // The import is dynamic and lazy (first popup open only), so a flag-off
  // page never fetches it and a flag-on page pays nothing until a word is
  // clicked.
  const GRAMMATA_LOOKUP_URL = 'https://grammata.pages.dev/t8/lookup.js';
  type GrammataLookupFn = (word: string, el: HTMLElement, opts?: { lang?: 'grc' | 'lat' }) => Promise<void>;
  let grammataModPromise: Promise<{ lookup: GrammataLookupFn }> | null = null;
  let grammataEl: HTMLDivElement | undefined;
  let grammataStatus: 'idle' | 'loading' | 'ready' | 'error' = 'idle';
  let greqId = 0;

  // The word handed to the widget: the best-resolved lemma (Unicode) from
  // OUR OWN analysis pass when it found one, else the clicked surface form.
  // Deliberately the WORD, never the internal LSJ/L&S dictionary KEY: the
  // widget accepts an exact `key` (its packs' own key space), but grammata's
  // packs are an independent build (grammar-site, not this repo's
  // reader_pipeline/stage5_lsj.py) and there is no verified guarantee its key
  // space agrees with ours byte-for-byte — a mismatch there fails silently
  // (wrong entry, or a false "not found") with no way to catch it short of
  // an exhaustive audit. Passing the Unicode word lets the widget resolve it
  // with its own Morpheus pass, which is the documented default path and the
  // one every "Minimal integration" example in the handoff actually uses.
  $: grammataWord = grammataLookup
    ? (analyses.length > 0 ? displayLemma(analyses[0]) : token.t)
    : '';

  $: if (grammataLookup && !loading && grammataEl && grammataWord) {
    runGrammataLookup(grammataWord);
  }

  async function runGrammataLookup(word: string) {
    const id = ++greqId;
    grammataStatus = 'loading';
    try {
      if (!grammataModPromise) grammataModPromise = import(/* @vite-ignore */ GRAMMATA_LOOKUP_URL);
      const mod = await grammataModPromise;
      if (id !== greqId || !grammataEl) return;
      await mod.lookup(word, grammataEl, { lang: langPath });
      if (id !== greqId) return;
      grammataStatus = 'ready';
    } catch {
      // Import failure (offline, blocked, CORS) or a lookup rejection: fall
      // back to our own entry rendering (gated on grammataStatus below) plus
      // one plain status line — never a blank panel.
      if (id !== greqId) return;
      grammataStatus = 'error';
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onClose();
  }

  // Close on any CLICK outside the panel — EXCEPT on a token, whose own
  // click handler swaps the popup to the new word. (A blocking backdrop here
  // would swallow that click and force close-then-reopen, with two page
  // reflows; see the plato-reader bug report of 2026-07-29.) Click, not
  // pointerdown: a click only fires after press+release on the same target,
  // so a touch pan, a text-selection drag, or a right-click never dismisses
  // the panel — the same tap-not-pan semantics the old backdrop had (Sol
  // adversarial-review catch, 2026-07-29). Capture phase, not bubble:
  // Reader's footnote-marker, Bekker-info, and print-menu handlers
  // stopPropagation(), which would keep the panel open behind the popup they
  // raise — John's ruling 2026-07-29: a footnote click closes the word panel.
  function onOutsideClick(e: MouseEvent) {
    const t = e.target as HTMLElement | null;
    if (!t || t.closest('.word-sidebar') || t.closest('.tok')) return;
    onClose();
  }

  onMount(() => {
    previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setTimeout(() => dialogEl?.focus({ preventScroll: true }), 0);
  });

  onDestroy(() => {
    // preventScroll: the reader pins its own scroll position across the close
    // reflow (see Reader's pinAcrossReflow); letting focus() scroll to the old
    // word snaps the page around.
    previousFocus?.focus({ preventScroll: true });
  });
</script>

<svelte:window on:keydown={onKey} on:click|capture={onOutsideClick} />

<!-- Desktop: slide-in sidebar. Mobile / tablet-compare: bottom sheet. Both via CSS.
     A non-modal dialog, honestly: the reader can click other words (swap),
     footnotes, and links while it is open, so aria-modal and a Tab trap would
     tell assistive tech the background is unavailable while pointer users
     interact with it freely (Sol adversarial-review catch, 2026-07-29).
     Escape still closes; focus returns to the opener. -->
<div
  class="word-sidebar"
  class:as-sheet={asSheet}
  bind:this={dialogEl}
  transition:fly={reduceMotion ? { duration: 0 } : asSheetHere ? { y: 600, duration: 260, opacity: 1 } : { x: 420, duration: 220, opacity: 1 }}
  role="dialog"
  aria-label="Word analysis"
  tabindex="-1"
>
  <div class="word-sidebar-head">
    <span class="popup-surface" lang={sourceLang}>{token.t}</span>
    <button class="settings-close" on:click={onClose} aria-label="Close">×</button>
  </div>
  <div class="word-sidebar-body">
    {#if loading}
      <div class="popup-loading">Looking up…</div>
    {:else if error}
      <div class="popup-loading">Error: {error}</div>
    {:else if analyses.length === 0}
      <div class="popup-loading">No analysis found for this form.</div>
    {:else}
      {#if analyses.some((a) => a.foldedAccent)}
        <div class="lsj-ambiguous-note">
          All-capitals form — accents supplied; readings listed are all matches.
        </div>
      {/if}
      {#each analyses as a}
        <div class="analysis-card">
          <div class="lemma" lang={sourceLang}>{displayLemma(a)}</div>
          <div class="gloss">{a.gloss}</div>
          <div class="parse">{a.parse}</div>
          {#if lemmaRef(a)}
            <a class="lemma-link" href={lemmaEntryHref(base, langPath, lemmaRef(a)!.slug)}>
              Appears {lemmaRef(a)!.count.toLocaleString()}× across the corpus
              <span class="lemma-link-arr" aria-hidden="true">→</span>
            </a>
          {/if}
          {#if entriesFor(a).length > 0 && (!grammataLookup || grammataStatus === 'error')}
            <div class="lsj-section">
              <div class="lsj-label">{dictLabel}</div>
              {#if entriesFor(a).length > 1}
                <!-- Homonym fan-out (Wave 2 Batch 1b review): more than one
                     dictionary headword survives for this lemma and nothing
                     left can tell them apart -- render as an EXPLICIT
                     ambiguous group rather than stacking them under one
                     dictionary label as if only one were the answer. -->
                <div class="lsj-ambiguous-note">
                  {entriesFor(a).length} dictionary entries match this headword
                </div>
              {/if}
              {#each entriesFor(a) as entry}
                <!-- eslint-disable-next-line svelte/no-at-html-tags — sanitized by the shared renderer -->
                {@html renderLsjEntry(entry.html, { base })}
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
    {#if grammataLookup && !loading}
      <!-- Grammata T8 widget mount -- one call per popup word, using the
           best-resolved lemma/surface form (see grammataWord above). The
           widget replaces this element's children itself; nothing here
           renders our own markup into it. -->
      <div class="grammata-mount" bind:this={grammataEl}></div>
      {#if grammataStatus === 'error'}
        <div class="popup-loading">Dictionary unavailable</div>
      {/if}
    {/if}
  </div>
</div>

<style>
  /* "See all occurrences" link into the lemma page — the popup's one bridge to
     the deeper reference view. Sits at the foot of each analysis card. */
  .lemma-link {
    display: inline-flex; align-items: center; gap: 0.35em;
    margin-top: 0.5rem; font-family: var(--font-ui); font-size: 0.8rem;
    font-weight: 600; color: var(--accent); text-decoration: none;
  }
  .lemma-link:hover { text-decoration: underline; }
  .lemma-link-arr { transition: transform .1s ease; }
  .lemma-link:hover .lemma-link-arr { transform: translateX(2px); }
</style>
