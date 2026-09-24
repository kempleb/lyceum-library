<script lang="ts">
  import { tick } from 'svelte';
  import { filterContents, looksLikeCitation, type ContentsModel } from '../lib/contents';

  // This work's contents, opened from the book in the running head. The book
  // you are reading is open; the others are one line each with their range.
  // Inside a book the entries are the work's own headings where the built data
  // has them, and citation ranges where it does not.
  export let model: ContentsModel;
  export let open = false;
  export let onCite: (raw: string) => void = () => {};
  export let onClose: () => void = () => {};

  let dialogEl: HTMLDialogElement | undefined;
  let query = '';

  $: books = filterContents(model.books, query);
  $: citeOffer = looksLikeCitation(query) ? query.trim() : '';

  $: if (dialogEl) syncOpen(open);
  async function syncOpen(want: boolean) {
    await tick();
    if (!dialogEl) return;
    if (want && !dialogEl.open) {
      dialogEl.showModal();
      (dialogEl.querySelector('.filter') as HTMLInputElement | null)?.focus();
    } else if (!want && dialogEl.open) {
      dialogEl.close();
    }
  }

  function onFilterKey(e: KeyboardEvent) {
    if (e.key !== 'Enter' || !citeOffer) return;
    e.preventDefault();
    onCite(citeOffer);
  }
</script>

<dialog class="sheet" bind:this={dialogEl} on:close={onClose} aria-label={model.title}>
  <div class="sheetin">
    <div class="sheethead">
      <div class="sheettop">
        <h2 class="sheettitle">{model.title}</h2>
        <span class="sheetmeta">{model.meta}</span>
        <button type="button" class="closebtn" on:click={onClose}>Close <kbd aria-hidden="true">esc</kbd></button>
      </div>
      <label class="vh" for="lyc-toc-filter">{model.placeholder}</label>
      <input
        class="filter"
        id="lyc-toc-filter"
        type="text"
        bind:value={query}
        on:keydown={onFilterKey}
        placeholder={model.placeholder}
        autocomplete="off"
        spellcheck="false"
      />
      {#if citeOffer}
        <button type="button" class="citego" on:click={() => onCite(citeOffer)}>
          Go to {citeOffer}<span class="citego-hint">enter</span>
        </button>
      {/if}
    </div>
    <div class="sheetbody">
      {#each books as b (b.n)}
        {#if b.current}
          <div class="bk cur" aria-current="page">
            <span class="bknm">{b.heading}</span>
            <span class="ld" aria-hidden="true"></span>
            <span class="lc">{b.extent}</span>
          </div>
          {#each b.entries as e (e.hash)}
            <a class="ent ent-in" href={e.hash} on:click={onClose}>
              <span class="nm">{e.name}</span>
              <span class="ld" aria-hidden="true"></span>
              <span class="lc">{e.extent}</span>
            </a>
          {/each}
        {:else}
          <a class="ent bk-line" href={b.href}>
            <span class="nm">{b.heading}</span>
            <span class="ld" aria-hidden="true"></span>
            <span class="lc">{b.extent}</span>
          </a>
        {/if}
      {/each}
      {#if model.note && !query}<p class="hint">{model.note}</p>{/if}
      {#if books.length === 0}<p class="hint">Nothing here matches “{query}”.</p>{/if}
    </div>
  </div>
</dialog>
