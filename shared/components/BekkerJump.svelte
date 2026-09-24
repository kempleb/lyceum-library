<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { fetchColumns, resolveBekker, type ColumnRef } from '../lib/data';
  import { schemeFor, formatLocValue, parseDkFullCitation } from '../lib/citation';
  import { getWork, workPath } from '../lib/works';

  export let work: string = 'EN';
  // Navigation strategy: the site leaves this unset and navigates the tab;
  // the desktop shell passes a callback (a Tauri window has no URL routing).
  // `line` is null for a scheme with no user-facing lines (stephanus) or for
  // a bare-column jump on any scheme.
  export let onJump: ((book: number, column: string, line: number | null) => void) | null = null;
  // Hosts that mount more than one instance per page must pass distinct ids
  // (the site's ReaderShell mounts two) or the label/input pairing collides.
  // Deterministic prop rather than a generated id: this component is
  // server-rendered, so a random/counter id would break hydration.
  export let inputId = 'bekker-input';

  $: workMeta = getWork(work);
  // Scheme-aware citation grammar/copy: bekker/busse take a line ("1097a15"),
  // stephanus is page+letter only ("34b") — see shared/lib/citation.ts. This
  // makes the jump box work for any work's citation scheme, not just Bekker's.
  $: citeScheme = schemeFor(work);

  let open = false;
  let value = '';
  let error = '';
  let columns: Record<string, ColumnRef[]> | null = null;
  let inputEl: HTMLInputElement | undefined;

  // Preload the column index so the first lookup is instant; re-preload when
  // the shell switches works under us (desktop).
  onMount(() => { preload(); });
  $: if (work) preload();
  function preload() {
    columns = null;
    fetchColumns(work).then(c => (columns = c)).catch(() => {});
  }

  async function openBox() {
    open = true;
    error = '';
    await tick();
    inputEl?.focus();
  }

  function closeBox() {
    open = false;
    error = '';
    value = '';
  }

  async function jumpWithin(ref: { column: string; line: number | null; isRange?: boolean }) {
    // A dotted-scheme column (book-section: "4.23") carries its book as a
    // literal prefix, so it never needs the columns.json/resolveBekker
    // lookup below — see citation.ts's bookFromColumn doc comment.
    const direct = citeScheme.bookFromColumn(ref.column);
    let book: number | null;
    if (direct != null && !ref.isRange) {
      book = direct;
    } else {
      const cols = columns ?? (await fetchColumns(work).catch(() => null));
      if (!cols) { error = 'Could not load the index — try again'; return; }
      // A verse-line range ("1.1094-1101") is valid jump input only when
      // it exactly matches a declared lacuna — a real column in the
      // corpus — never merely well-formed range syntax (design memo
      // §3.4: parseLocation can PARSE any range shape, but the reader
      // must reject one that isn't a real, declared gap). Reuses the same
      // columns.json channel every other scheme's citation-membership
      // check reads below, rather than trusting bookFromColumn's
      // syntax-only book derivation.
      book = ref.isRange ? (cols[ref.column] ? direct : null) : resolveBekker(cols, ref.column, ref.line);
    }
    // bookFromColumn/resolveBekker validate the column's own grammar but not
    // corpus membership — a dotted column like "99.99" derives book 99 from
    // syntax alone. Reject an out-of-range book with the same not-found
    // message rather than jumping, which workPath would otherwise silently
    // clamp to the work's last book with an unresolvable ?loc (see
    // citation.ts's bookFromColumn doc comment).
    if (book == null || !workMeta || book < 1 || book > workMeta.books) {
      error = `${ref.column} is not in the ${workMeta?.title ?? 'text'}`;
      return;
    }
    if (onJump) {
      closeBox();
      onJump(book, ref.column, ref.line);
      return;
    }
    // Same-tab navigation; the reader snaps to the nearest line if exact is absent.
    window.location.href = `${import.meta.env.BASE_URL.replace(/\/$/, '')}${workPath(work, book)}?loc=${formatLocValue(work, ref.column, ref.line)}`;
  }

  async function go() {
    error = '';
    // Scheme-aware: accepts a bare column ("34b") for any scheme, and a
    // column+line citation ("1097a15"/"1097a:15") only for a scheme with
    // user-facing lines — a stephanus work rejects "34b12" rather than
    // silently truncating it (see shared/lib/citation.ts).
    const ref = citeScheme.parseLocation(value);
    if (ref) {
      await jumpWithin(ref);
      return;
    }
    // For a dk work only, a bare parseLocation miss might still be the
    // full scholarly citation form ("DK 22 B30" / "22 B30") — previously
    // this in-page box only ever fed the ⌘K palette's `parseDkFullCitation`
    // (CommandPalette.svelte), even though the site's own REVIEW-CHECKLIST
    // advertises "DK 22 B30" as valid input HERE too. `parseDkFullCitation`
    // resolves which work the cited chapter+series belongs to on its own
    // (see citation.ts's doc comment), so a citation naming a DIFFERENT
    // presocratic than the one currently open is not an error — it is a
    // real citation for a real, registered work, so we jump there. This
    // mirrors the palette's own href-based handling of the same grammar
    // (CommandPalette.svelte step 1.5); `onJump` is not called for a
    // cross-work jump because its signature (book, column, line) has no
    // way to name a different work.
    if (citeScheme.id === 'dk') {
      const full = parseDkFullCitation(value);
      if (full) {
        if (full.workId === work) {
          await jumpWithin({ column: full.column, line: full.line });
          return;
        }
        closeBox();
        window.location.href = `${import.meta.env.BASE_URL.replace(/\/$/, '')}${workPath(full.workId)}?loc=${formatLocValue(full.workId, full.column, full.line)}`;
        return;
      }
    }
    error = `Enter a ${citeScheme.label}, ${citeScheme.jumpPlaceholder}`;
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') { e.preventDefault(); closeBox(); }
  }
</script>

{#if !open}
  <button class="bekker-toggle" on:click={openBox} title="Look up a {citeScheme.label}">
    Go to a {citeScheme.label}
  </button>
{:else}
  <form class="bekker-jump" on:submit|preventDefault={go} role="search">
    <label class="bekker-label" for={inputId}>{citeScheme.label}</label>
    <input
      id={inputId}
      type="text"
      bind:this={inputEl}
      bind:value
      on:keydown={onKey}
      on:input={() => (error = '')}
      placeholder={citeScheme.jumpPlaceholder}
      aria-label="Jump to a {citeScheme.label}"
      spellcheck="false"
      autocapitalize="off"
      autocomplete="off"
    />
    <button type="submit">Go</button>
    <button type="button" class="bekker-close" on:click={closeBox} aria-label="Close">✕</button>
    {#if error}<span class="bekker-err" role="alert">{error}</span>{/if}
  </form>
{/if}
