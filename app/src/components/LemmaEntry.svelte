<script lang="ts">
  import { onMount } from 'svelte';
  import { dataRoot } from '@shared/lib/data';
  import { getWork, workLanding, bookLabel, isBookless } from '@shared/lib/works';
  import { groupUnitNoun } from '@shared/lib/citation';
  import { tocGroupNoun } from '../lib/citation-copy';
  import { renderLsjEntry } from '../lib/html';
  import { instHref, instLabel, type Instance } from '../lib/lemma-instance';

  export let lang: 'grc' | 'lat' = 'grc';

  interface ChapterInstances { chapter: string; bekker: string; instances: Instance[]; }
  interface BookInstances { book: number; chapters: ChapterInstances[]; }
  interface WorkInstances { work: string; title: string; count: number; shown: number; books: BookInstances[]; }
  interface LemmaData {
    slug: string; key: string; head: string; lemmaBeta: string; dictHtml: string;
    count: number; glosses: string[]; byWork: { work: string; title: string; count: number }[];
    instancesByWork: WorkInstances[]; truncated: boolean;
  }

  let data: LemmaData | null = null;
  let loading = true;
  let problem = '';
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  $: langPath = lang;
  $: langLabel = lang === 'lat' ? 'Latin' : 'Greek';
  $: dictLabel = lang === 'lat' ? 'L&S' : 'LSJ';
  $: htmlLang = lang === 'lat' ? 'la' : 'grc';
  $: headFont = lang === 'lat' ? 'var(--font-latin)' : 'var(--font-greek)';
  $: maxWork = data?.byWork[0]?.count ?? 1;

  onMount(async () => {
    const slug = new URLSearchParams(window.location.search).get('w')?.trim();
    if (!slug) {
      problem = 'This entry has no word selected.';
      loading = false;
      return;
    }
    const dir = lang === 'lat' ? 'lemmata-lat' : 'lemmata';
    try {
      const response = await fetch(`${dataRoot()}/${dir}/${encodeURIComponent(slug)}.json`);
      if (!response.ok) {
        problem = 'That lexicon entry was not found.';
      } else {
        data = await response.json();
      }
    } catch {
      problem = 'This lexicon entry could not be loaded.';
    }
    loading = false;
  });

  const workView = (w: WorkInstances) => {
    const work = getWork(w.work);
    return {
      ...w,
      bookless: work ? isBookless(work) : false,
      unit: groupUnitNoun(w.work),
      bookNoun: tocGroupNoun(w.work),
      flat: w.shown <= 30,
      capped: w.shown < w.count,
      barPct: Math.max(2, (w.count / maxWork) * 100),
      books: w.books.map((bk) => ({
        ...bk,
        label: work ? bookLabel(work, bk.book) : String(bk.book),
        bookCount: bk.chapters.reduce((n, ch) => n + ch.instances.length, 0),
      })),
    };
  };
</script>

<main class="lx-body">
  {#if loading}
    <p class="lx-note">Loading lexicon entry…</p>
  {:else if problem}
    <p class="lx-note">{problem} <a href={`${base}/lemma/${langPath}/`}>Browse the {langLabel.toLowerCase()} lexicon.</a></p>
  {:else if data}
    <h1 class="lx-head-gk" lang={htmlLang} style={`font-family:${headFont}`}>{data.head}</h1>
    <p class="lx-translit">{data.slug}</p>
    {#if data.glosses[0]}<p class="lx-gloss">{data.glosses.join('; ')}</p>{/if}
    <p class="lx-freq">Appears <b>{data.count.toLocaleString()}</b> times across the corpus.</p>

    <h2 class="lx-h">Frequency by work</h2>
    <p class="lx-note">Click a work to list every occurrence by citation — each links into the reader.</p>
    <ul class="lx-freqbars">
      {#each data.instancesByWork as raw}
        {@const w = workView(raw)}
        <li>
          <details class="fb-item">
            <summary>
              <span class="fb-name">{w.title}</span><span class="fb-track"><span class="fb-fill" style={`width:${w.barPct}%`}></span></span>
              <span class="fb-n">{w.count.toLocaleString()}</span><span class="fb-caret" aria-hidden="true">▸</span>
            </summary>
            <div class="fb-cites">
              <a class="fb-open" href={`${base}${workLanding(w.work)}`}>Open {w.title} ›</a>
              {#each w.books as bk}
                {#if w.bookless}
                  <div class="fb-book-group">
                    {#each bk.chapters as ch}
                      <div class="fb-chapter">
                        {#if ch.chapter !== '?'}<div class="fb-ch-head"><span class="fb-ch-label">{w.unit ? `${w.unit} ${ch.chapter}` : ch.chapter}</span>{#if ch.bekker}<span class="fb-ch-bekker">{ch.bekker}</span>{/if}</div>{/if}
                        <ul class="fb-citelist">{#each ch.instances as inst}<li><a href={instHref(base, w.work, bk.book, inst)}>{instLabel(w.work, inst)}</a></li>{/each}</ul>
                      </div>
                    {/each}
                  </div>
                {:else}
                  <details class="fb-book-d" open={w.flat}>
                    <summary><span class="fb-book">{w.bookNoun} {bk.label}</span><span class="fb-book-n">{bk.bookCount}</span><span class="fb-caret fb-book-caret" aria-hidden="true">▸</span></summary>
                    <div class="fb-book-body">
                      {#each bk.chapters as ch}
                        <div class="fb-chapter">
                          {#if ch.chapter !== '?'}<div class="fb-ch-head"><span class="fb-ch-label">{w.unit ? `${w.unit} ${ch.chapter}` : ch.chapter}</span>{#if ch.bekker}<span class="fb-ch-bekker">{ch.bekker}</span>{/if}</div>{/if}
                          <ul class="fb-citelist">{#each ch.instances as inst}<li><a href={instHref(base, w.work, bk.book, inst)}>{instLabel(w.work, inst)}</a></li>{/each}</ul>
                        </div>
                      {/each}
                    </div>
                  </details>
                {/if}
              {/each}
              {#if w.capped}<p class="lx-note">Showing {w.shown.toLocaleString()} of {w.count.toLocaleString()} (list capped).</p>{/if}
            </div>
          </details>
        </li>
      {/each}
    </ul>

    {#if data.dictHtml}
      <h2 class="lx-h">Dictionary ({dictLabel})</h2>
      <!-- eslint-disable-next-line svelte/no-at-html-tags — sanitized by the shared renderer -->
      {@html renderLsjEntry(data.dictHtml, { base, scale: 'page', outline: true })}
    {/if}
  {/if}
  <a class="lx-back" href={`${base}/lemma/${langPath}/`}>‹ All lexicon entries</a>
</main>

<style>
  .lx-body { max-width: 820px; margin: 0 auto; padding: 2rem 1rem 5rem; font-family: var(--font-english); color: var(--text); }
  .lx-head-gk { font-size: 2.6rem; font-weight: 600; line-height: 1.1; margin: 0; }
  .lx-translit { font-family: var(--font-ui); font-size: .85rem; letter-spacing: .06em; text-transform: uppercase; color: var(--text-mid); margin: .3rem 0 0; }
  .lx-gloss { font-size: 1.15rem; margin: .7rem 0 0; }.lx-freq { font-family: var(--font-ui); font-size: .95rem; color: var(--text-mid); margin: 1rem 0 0; }.lx-freq b { color: var(--accent); font-size: 1.1rem; }
  h2.lx-h { font-family: var(--font-ui); font-size: .95rem; font-weight: 700; letter-spacing: .03em; color: var(--accent); margin: 2.4rem 0 .8rem; padding-bottom: .3rem; border-bottom: 1px solid var(--border); }
  .lx-freqbars,.fb-citelist { list-style: none; padding: 0; margin: 0; }.fb-item>summary { display:grid; grid-template-columns:minmax(6rem,12rem) 1fr 3.2rem 1rem; align-items:center; gap:.7rem; cursor:pointer; list-style:none; padding:.28rem .4rem; border-radius:5px; }.fb-item>summary::-webkit-details-marker,.fb-book-d>summary::-webkit-details-marker { display:none; }.fb-item>summary:hover { background:var(--surface-2,rgba(128,128,128,.08)); }.fb-name { font-size:.9rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }.fb-track { height:.7rem; background:var(--border); border-radius:4px; overflow:hidden; }.fb-fill { display:block; height:100%; background:var(--accent); border-radius:4px; }.fb-n,.fb-book-n { font-family:var(--font-ui); font-variant-numeric:tabular-nums; font-size:.82rem; color:var(--text-mid); text-align:right; }.fb-caret { font-size:.7rem; color:var(--text-mid); justify-self:center; }.fb-item[open]>summary .fb-caret,.fb-book-d[open]>summary .fb-book-caret { transform:rotate(90deg); }
  .fb-cites { padding:.5rem .4rem 1rem; }.fb-open,.lx-back { display:inline-block; font-family:var(--font-ui); color:var(--accent); text-decoration:none; }.fb-open { font-size:.8rem; font-weight:600; margin:0 0 .6rem; }.fb-citelist { display:flex; flex-wrap:wrap; gap:.35rem; }.fb-citelist a { display:inline-block; font-family:var(--font-ui); font-variant-numeric:tabular-nums; font-size:.78rem; color:var(--text); text-decoration:none; border:1px solid var(--border); border-radius:4px; padding:.15rem .45rem; }.fb-citelist a:hover,.fb-open:hover,.lx-back:hover { color:var(--accent); text-decoration:underline; }.fb-book-group { margin:0 0 .9rem; }.fb-book-d { border-top:1px solid var(--border); }.fb-book-d>summary { display:flex; align-items:center; gap:.5rem; cursor:pointer; list-style:none; padding:.4rem .2rem; }.fb-book { font-family:var(--font-ui); font-size:.88rem; font-weight:700; }.fb-book-n { margin-left:auto; }.fb-book-body { padding:.2rem 0 .6rem .5rem; }.fb-chapter { margin:0 0 .7rem .2rem; }.fb-ch-head { display:flex; align-items:baseline; gap:.5rem; margin:0 0 .35rem; }.fb-ch-label { font-family:var(--font-ui); font-size:.82rem; font-weight:600; color:var(--text-mid); }.fb-ch-bekker { font-family:var(--font-ui); font-size:.72rem; color:var(--text-mid); font-variant-numeric:tabular-nums; opacity:.8; }
  .lsj { font-size:.95rem; line-height:1.6; }.lsj :global(.lsj-head) { font-family:var(--font-greek); }.lx-note { font-size:.82rem; color:var(--text-mid); margin:.4rem 0 0; }.lx-note a { color:var(--accent); }.lx-back { margin:2.5rem 0 0; font-size:.9rem; }
</style>
