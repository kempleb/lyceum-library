<script lang="ts">
  import { tick } from 'svelte';
  import { filterLibrary, looksLikeCitation, type LibraryModel } from '../lib/contents';

  // The library, opened from the author or the work in the running head. It is
  // the front matter of the library rather than a menu: shelves in small caps,
  // authors beneath them, works as dot-leadered entries. One field at the top
  // narrows the whole sheet; a citation-shaped entry offers a jump instead.
  export let model: LibraryModel;
  export let open = false;
  // Resolves a typed citation and navigates. Supplied by RunningHead.svelte so
  // the sheet and the running head's own citation field share one resolver.
  export let onCite: (raw: string) => void = () => {};
  export let onClose: () => void = () => {};

  let dialogEl: HTMLDialogElement | undefined;
  let query = '';

  $: filtered = filterLibrary(model, query);
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

<dialog class="sheet" bind:this={dialogEl} on:close={onClose} aria-label="The library">
  <div class="sheetin">
    <div class="sheethead">
      <div class="sheettop">
        <h2 class="sheettitle">The library</h2>
        <span class="sheetmeta">{filtered.meta}</span>
        <button type="button" class="closebtn" on:click={onClose}>Close <kbd aria-hidden="true">esc</kbd></button>
      </div>
      <label class="vh" for="lyc-lib-filter">Find an author, work, or citation</label>
      <input
        class="filter"
        id="lyc-lib-filter"
        type="text"
        bind:value={query}
        on:keydown={onFilterKey}
        placeholder="Find an author, work, or citation"
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
      {#each filtered.shelves as shelf (shelf.id)}
        <div class="coll">
          <h3 class="chead">{shelf.name}</h3>
          <span class="cmeta">{shelf.meta}</span>
        </div>
        {#each shelf.authors as author (author.id)}
          <div class="au">{author.name}<span class="ameta">{author.meta}</span></div>
          {#each author.groups as group, gi (group.label ?? gi)}
            {#if group.label}<div class="grp">{group.label}</div>{/if}
            {#each group.works as w (w.id)}
              <a
                class="ent"
                class:cur={w.current}
                href={w.href}
                aria-current={w.current ? 'page' : undefined}
              >
                <span class="nm">{w.title}</span>
                <span class="ld" aria-hidden="true"></span>
                <span class="lc">{w.extent}</span>
              </a>
            {/each}
          {/each}
        {/each}
      {/each}
      {#if filtered.shelves.length === 0}
        <p class="hint">Nothing here matches “{query}”.</p>
      {/if}
    </div>
  </div>
</dialog>
