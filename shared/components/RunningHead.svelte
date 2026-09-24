<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import LibrarySheet from './LibrarySheet.svelte';
  import ContentsSheet from './ContentsSheet.svelte';
  import { citeDisplay, headingAt, type ContentsModel, type LibraryModel } from '../lib/contents';
  import { fetchColumns, resolveBekker } from '../lib/data';
  import { schemeFor, formatLocValue, parseDkFullCitation } from '../lib/citation';
  import { getWork, workPath } from '../lib/works';

  // The running head IS the navigation (PUBLIC_LYCEUM_CHROME). One typeset
  // line: AUTHOR · WORK · BOOK N · §n heading at the left, the reading view and
  // the translation at the right. Every part is pressable.
  //
  // View and translation are NOT state of their own here: Reader.svelte owns
  // them, and this line reads and drives Reader's existing controls strip
  // through the DOM (the strip is still rendered, just not shown, when this
  // chrome is on) — the same way Reader.svelte itself reaches out to the
  // Astro-rendered contents nav. One state, two faces.
  export let author: string;
  export let workTitle: string;
  export let workId: string;
  export let bookHeading: string | null = null;   // 'Book I' — null when bookless
  export let sourceLabel = 'Greek';               // 'Greek' | 'Latin'
  export let startColumn = '';
  // Unit noun for a scheme whose divisions are not sections ('Chapter',
  // 'Line'); null where the section mark is right.
  export let sectionNoun: string | null = null;
  export let library: LibraryModel;
  export let contents: ContentsModel;
  export let translations: { id: string; short: string; name: string }[] = [];

  const base = import.meta.env.BASE_URL.replace(/\/$/, '');

  // ── Live position, from Reader.svelte's scroll-spy ────────────────────────
  let column = startColumn;
  let fading = false;
  let fadeTimer: ReturnType<typeof setTimeout> | undefined;
  $: section = citeDisplay(column, sectionNoun);
  $: heading = headingAt(contents.books.find((b) => b.current), column);

  function onPosition(e: Event) {
    const next = (e as CustomEvent<{ column?: string }>).detail?.column ?? '';
    if (!next || next === column) return;
    if (reduceMotion) { column = next; return; }
    fading = true;
    clearTimeout(fadeTimer);
    fadeTimer = setTimeout(() => { column = next; fading = false; }, 120);
  }

  let reduceMotion = false;

  // ── Sheets ────────────────────────────────────────────────────────────────
  let sheet: 'library' | 'contents' | null = null;
  let returnFocus: HTMLElement | null = null;
  function openSheet(which: 'library' | 'contents') {
    returnFocus = document.activeElement as HTMLElement | null;
    sheet = which;
  }
  function closeSheet() {
    sheet = null;
    returnFocus?.focus();
    returnFocus = null;
  }

  // ── The citation field (press §n) ─────────────────────────────────────────
  let citing = false;
  let citeValue = '';
  let citeError = '';
  let citeEl: HTMLInputElement | undefined;
  async function startCiting() {
    citing = true;
    citeValue = '';
    citeError = '';
    await tick();
    citeEl?.focus();
  }
  function stopCiting() {
    citing = false;
    citeError = '';
  }
  function onCiteKey(e: KeyboardEvent) {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); stopCiting(); return; }
    if (e.key === 'Enter') { e.preventDefault(); goToCitation(citeValue); }
  }

  /**
   * Resolve a typed citation and go. Same resolver the ⌘K palette and the
   * "Go to a …" box use: the work's own citation scheme parses it
   * (parseLocation), columns.json settles which book it lands in
   * (resolveBekker), and a full Diels–Kranz citation resolves its own work.
   */
  async function goToCitation(raw: string) {
    const value = raw.trim();
    if (!value) return;
    citeError = '';
    const s = schemeFor(workId);
    const meta = getWork(workId);
    const ref = s.parseLocation(value);
    if (ref) {
      const direct = s.bookFromColumn(ref.column);
      let book: number | null;
      if (direct != null && !ref.isRange) {
        book = direct;
      } else {
        const cols = await fetchColumns(workId).catch(() => null);
        if (!cols) { citeError = 'Could not load the index — try again'; return; }
        book = ref.isRange ? (cols[ref.column] ? direct : null) : resolveBekker(cols, ref.column, ref.line);
      }
      if (book != null && meta && book >= 1 && book <= meta.books) {
        window.location.href =
          `${base}${workPath(workId, book)}?loc=${formatLocValue(workId, ref.column, ref.line)}`;
        return;
      }
      citeError = `${ref.column} is not in the ${meta?.title ?? 'text'}`;
      return;
    }
    const full = parseDkFullCitation(value);
    if (full) {
      window.location.href =
        `${base}${workPath(full.workId)}?loc=${formatLocValue(full.workId, full.column, full.line)}`;
      return;
    }
    citeError = `Enter a ${s.label}, ${s.jumpPlaceholder}`;
  }

  // ── Reader state bridge (view + translation) ──────────────────────────────
  let view: 'greek' | 'both' | 'english' = 'both';
  // Seeded from the translations prop (never true for a zero-translation work
  // such as Heraclitus' Testimonia or the Tusculans) so a work with no English
  // doesn't server-render Both/English buttons that flash away once
  // readReaderState() below corrects it post-hydration.
  let hasEnglish = translations.length > 0;
  let transId = '';
  let transOpen = false;
  let observer: MutationObserver | undefined;

  const viewButtons = (): HTMLButtonElement[] =>
    Array.from(document.querySelectorAll<HTMLButtonElement>('.rc-desktop-controls .view-toggle button'));
  const transSelect = (): HTMLSelectElement | null =>
    document.querySelector<HTMLSelectElement>('.rc-trans-select');

  function readReaderState() {
    const body = document.querySelector('.reader-body');
    if (body) {
      view = body.classList.contains('view-greek')
        ? 'greek'
        : body.classList.contains('view-english') ? 'english' : 'both';
    }
    const buttons = viewButtons();
    if (buttons.length) hasEnglish = buttons.length > 1;
    const sel = transSelect();
    if (sel && sel.value) transId = sel.value;
    else if (!transId) transId = translations[0]?.id ?? '';
  }

  function setView(v: 'greek' | 'both' | 'english') {
    const buttons = viewButtons();
    const i = v === 'greek' ? 0 : v === 'both' ? 1 : 2;
    buttons[i]?.click();
    view = v;
  }

  function setTrans(id: string) {
    transOpen = false;
    const sel = transSelect();
    if (sel) {
      sel.value = id;
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
    transId = id;
  }

  $: transShort = translations.find((t) => t.id === transId)?.short ?? translations[0]?.short ?? '';

  // ── Phone settings (the sitewide band) ─────────────────────────────────────
  // At phone widths the band's CSS (global.css, body.lyceum-chrome's ≤680px
  // block) hides Text size/Theme/Print, keeping only Search — a phone reader
  // had no way to change either (review finding). Rather than duplicate those
  // controls, move the three existing elements (ReaderShell.astro's #lyc-
  // textsize/#lyc-print, ThemeToggle.astro's .theme-toggle — same nodes, same
  // listeners, nothing re-wired) into one small disclosure behind a compact
  // "Settings" trigger inserted once, right after Search. `display: contents`
  // on the wrapper at ≥681px is a no-op there: the three controls still sit
  // in the row exactly where they always did — "no new buttons on desktop".
  let phoneSettingsOpen = false;
  let phoneSettingsList: HTMLElement | null = null;
  let phoneSettingsTrigger: HTMLButtonElement | null = null;

  function setupPhoneSettings() {
    const tools = document.querySelector<HTMLElement>('.lyc-chrome .tools');
    if (!tools || tools.querySelector('.tool-settings')) return;
    const search = tools.querySelector('.tool-search');
    const textSize = tools.querySelector('#lyc-textsize');
    const theme = tools.querySelector('.theme-toggle');
    const print = tools.querySelector('#lyc-print');
    if (!textSize || !theme || !print) return;

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'tool tool-settings';
    trigger.id = 'lyc-phone-settings-trigger';
    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', 'lyc-phone-settings');
    trigger.textContent = 'Settings';
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      setPhoneSettings(!phoneSettingsOpen);
    });

    const list = document.createElement('div');
    list.className = 'tool-settings-list';
    list.id = 'lyc-phone-settings';
    list.setAttribute('role', 'group');
    list.setAttribute('aria-label', 'Settings');
    list.append(textSize, theme, print);

    tools.insertBefore(trigger, search?.nextSibling ?? null);
    tools.insertBefore(list, trigger.nextSibling);

    phoneSettingsTrigger = trigger;
    phoneSettingsList = list;
  }

  function setPhoneSettings(open: boolean) {
    phoneSettingsOpen = open;
    phoneSettingsList?.classList.toggle('open', open);
    phoneSettingsTrigger?.setAttribute('aria-expanded', String(open));
  }

  // ── Keys ──────────────────────────────────────────────────────────────────
  function onDocKey(e: KeyboardEvent) {
    if (e.key !== 'Escape') return;
    if (transOpen) { transOpen = false; return; }
    if (phoneSettingsOpen) { setPhoneSettings(false); return; }
    if (citing) { stopCiting(); return; }
  }
  function onDocClick() {
    if (transOpen) transOpen = false;
    if (phoneSettingsOpen) setPhoneSettings(false);
  }

  onMount(() => {
    reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.addEventListener('reader-position', onPosition);
    document.addEventListener('keydown', onDocKey);
    document.addEventListener('click', onDocClick);
    // Reader.svelte hydrates independently; read its state once it is up, then
    // follow it. One observer covers the view classes and the strip's controls.
    readReaderState();
    requestAnimationFrame(readReaderState);
    setupPhoneSettings();
    observer = new MutationObserver(() => readReaderState());
    const body = document.querySelector('.reader-body');
    if (body) observer.observe(body, { attributes: true, attributeFilter: ['class'], subtree: true, childList: true });
    return () => {
      document.removeEventListener('reader-position', onPosition);
      document.removeEventListener('keydown', onDocKey);
      document.removeEventListener('click', onDocClick);
      observer?.disconnect();
    };
  });

  onDestroy(() => clearTimeout(fadeTimer));
</script>

<div class="rh">
  <div class="rhl">
    <span class="rha">
      <button type="button" class="rhp" on:click={() => openSheet('library')}>{author}</button>
      <span class="sep" aria-hidden="true">·</span>
      <button type="button" class="rhp" on:click={() => openSheet('library')}>{workTitle}</button>
    </span>
    <span class="rhb">
      {#if bookHeading}
        <span class="sep sep-d" aria-hidden="true">·</span>
        <button type="button" class="rhp" on:click={() => openSheet('contents')}>{bookHeading}</button>
      {/if}
      {#if citing}
        <span class="sep" aria-hidden="true">·</span>
        <span class="cite-live">
          <label class="vh" for="lyc-citefield">Go to a citation</label>
          <input
            id="lyc-citefield"
            class="citefield"
            bind:this={citeEl}
            bind:value={citeValue}
            on:keydown={onCiteKey}
            on:blur={stopCiting}
            size="12"
            autocomplete="off"
            spellcheck="false"
            aria-describedby="lyc-citehint"
          />
          <span class="citehint" id="lyc-citehint">{citeError || 'Enter to go · esc to cancel'}</span>
        </span>
      {:else if section}
        <span class="sep" aria-hidden="true">·</span>
        <button type="button" class="rhp rhsec" on:click={startCiting}>
          <span class="secnum" class:fade={fading}>{section}</span>
          {#if heading}<span class="sechd" class:fade={fading}>{heading}</span>{/if}
        </button>
      {/if}
    </span>
  </div>
  <div class="rhr">
    <span class="views">
      <button type="button" class="rhp v" class:on={view === 'greek'}
        aria-current={view === 'greek' ? 'true' : undefined}
        on:click={() => setView('greek')}>{sourceLabel}</button>
      {#if hasEnglish}
        <span class="sep" aria-hidden="true">·</span>
        <button type="button" class="rhp v" class:on={view === 'both'}
          aria-current={view === 'both' ? 'true' : undefined}
          on:click={() => setView('both')}>Both</button>
        <span class="sep" aria-hidden="true">·</span>
        <button type="button" class="rhp v" class:on={view === 'english'}
          aria-current={view === 'english' ? 'true' : undefined}
          on:click={() => setView('english')}>English</button>
      {/if}
    </span>
    {#if translations.length > 1}
      <span class="trwrap">
        <button type="button" class="rhp tr" aria-expanded={transOpen}
          on:click|stopPropagation={() => (transOpen = !transOpen)}>{transShort} <span aria-hidden="true">▾</span></button>
        {#if transOpen}
          <div class="trlist" role="group" aria-label="Translation">
            {#each translations as t (t.id)}
              <button type="button" class="t" class:on={t.id === transId} on:click={() => setTrans(t.id)}>
                {t.short}<span class="sub">{t.name}</span>
              </button>
            {/each}
          </div>
        {/if}
      </span>
    {:else if translations.length === 1}
      <span class="rhp tr tr-static">{translations[0].short}</span>
    {/if}
  </div>
</div>

<LibrarySheet model={library} open={sheet === 'library'} onCite={goToCitation} onClose={closeSheet} />
<ContentsSheet model={contents} open={sheet === 'contents'} onCite={goToCitation} onClose={closeSheet} />
