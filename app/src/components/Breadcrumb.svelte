<script lang="ts">
  import { authorPath, workLanding, workPath } from '@shared/lib/works';
  import { resumeFor } from '@shared/lib/resume';

  // HOME > AUTHOR (> WORK) — the site's one navigation breadcrumb, shared by
  // the author landing, work landing, and reader pages. Every crumb is a REAL
  // link (Home -> /, author name -> authorPath, work title -> workLanding), so
  // the hierarchy navigates with no JS at all; beside the author and work
  // crumbs sits a compact native <select> switcher (placeholder face "Switch
  // author…"/"Switch work…") as progressive enhancement. Native selects keep
  // Escape/focus-return/arrow-key handling as browser behaviour — no custom
  // listbox JS.
  //
  // Both option lists are computed by the calling page at build time (via
  // app/src/lib/built-works.ts's builtAuthors()/builtWorksOf()) and passed in
  // as plain data — this component never touches the filesystem.
  export let authorId: string;
  export let authors: { id: string; name: string }[];
  // Omitted on the author landing page: HOME > AUTHOR only, no WORK crumb.
  export let workId: string | undefined = undefined;
  export let works: { id: string; title: string }[] = [];
  // Reader pages: the work switcher resumes the target work at its last-read
  // book + citation (shared/lib/resume.ts) instead of its landing page, and
  // no crumb is aria-current (the current URL is a book page, not a crumb).
  export let readerNav = false;

  const base = import.meta.env.BASE_URL.replace(/\/$/, '');

  $: authorName = authors.find((a) => a.id === authorId)?.name ?? authorId;
  $: workTitle = works.find((w) => w.id === workId)?.title ?? workId;

  // Reset a no-op pick (empty placeholder or the current entry) back to the
  // placeholder so the select face keeps reading "Switch …".
  function goAuthor(e: Event) {
    const sel = e.target as HTMLSelectElement;
    const id = sel.value;
    if (!id || id === authorId) { sel.value = ''; return; }
    window.location.href = `${base}${authorPath(id)}`;
  }

  function goWork(e: Event) {
    const sel = e.target as HTMLSelectElement;
    const id = sel.value;
    if (!id || id === workId) { sel.value = ''; return; }
    if (readerNav) {
      // Same behaviour the reader's old work switcher had: reopen the target
      // work at its remembered book (+ citation anchor) if one is saved.
      const pos = resumeFor(id);
      const book = pos?.book ?? 1;
      window.location.href = `${base}${workPath(id, book)}${pos?.cite ? `#${pos.cite}` : ''}`;
      return;
    }
    window.location.href = `${base}${workLanding(id)}`;
  }
</script>

<nav class="header-title" aria-label="Breadcrumb">
  <ol class="breadcrumb-list" role="list">
    <li>
      <a class="home-link" href={`${base}/`} aria-label={workId ? 'All works' : 'All authors'}>Home</a>
    </li>
    <li>
      <span class="title-sep" aria-hidden="true">›</span>
      <a class="bc-crumb" href={`${base}${authorPath(authorId)}`}
         aria-current={workId ? undefined : 'page'}>{authorName}</a>
      <select class="work-switcher" on:change={goAuthor} aria-label="Switch author">
        <option value="" selected disabled>Switch author…</option>
        {#each authors as a}
          <option value={a.id}>{a.name}</option>
        {/each}
      </select>
    </li>
    {#if workId}
      <li>
        <span class="title-sep" aria-hidden="true">›</span>
        <a class="bc-crumb" href={`${base}${workLanding(workId)}`}
           aria-current={readerNav ? undefined : 'page'}>{workTitle}</a>
        <select class="work-switcher" on:change={goWork} aria-label="Switch work">
          <option value="" selected disabled>Switch work…</option>
          {#each works as w}
            <option value={w.id}>{w.title}</option>
          {/each}
        </select>
      </li>
    {/if}
  </ol>
</nav>

<style>
  /* Real ol/li structure styled as the flex row directly (no display:contents
     — Safari/VoiceOver drops list semantics from the AT tree for it). The ol
     is the single flex child of the nav (.header-title, global.css), so the
     row reads exactly like the markup it replaced. */
  .breadcrumb-list {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.4rem;
    list-style: none;
    margin: 0;
    padding: 0;
    min-width: 0;
    max-width: 100%;
  }
  .breadcrumb-list li {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    min-width: 0;
  }
  /* The crumb text itself; sized/weighted like the header-static title it
     replaced (global.css), ellipsizing rather than pushing actions off. */
  .bc-crumb {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }
  .bc-crumb:hover { color: var(--accent); }
</style>
