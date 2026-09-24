// GPT-6 Sol code review item 2 (docs/todo/plato-mount.md, MAJOR): the search
// page's "works to include" refine panel used to list every WORKS registry
// entry — including a held mounted corpus's works, which have no built data
// and so no search index to hit. The fix is a `works` prop (default: the
// full registry, unchanged for every existing call site that doesn't pass
// one) a host page can narrow to only what's actually built
// (app/src/lib/built-works.ts's builtWorks()); every registered work
// belongs to exactly one shelf/WORK_GROUPS entry (see works.ts's SHELVES
// doc comment), so this exercises the real registry rather than a fixture
// that could drift from it.
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Search from '../components/Search.svelte';
import { getWork } from '../lib/works';

// Both real, stable registry entries (Aristotle's Categories, Heraclitus'
// B-fragments) — neither belongs to a held corpus, so either can stand in
// for "built" or "held" as the test needs.
const INCLUDED = getWork('heraclitus-fragments')!;
const EXCLUDED_ID = 'Cat';
const EXCLUDED_CHIP_TEXT = 'Cat. · Categories';
const INCLUDED_CHIP_TEXT = 'Her. B · Fragments';

async function openWorksPanel() {
  await fireEvent.click(screen.getByRole('button', { name: /Refine/ }));
}

describe('Search — the works prop scopes the "works to include" refine panel', () => {
  it('lists a chip for a work present in the works prop', async () => {
    render(Search, { props: { works: [INCLUDED] } });
    await openWorksPanel();
    expect(screen.getByText(INCLUDED_CHIP_TEXT)).toBeInTheDocument();
  });

  it('never lists a chip for a work left out of the works prop, even though it is really registered', async () => {
    expect(getWork(EXCLUDED_ID)).toBeDefined(); // sanity: a real registry entry
    render(Search, { props: { works: [INCLUDED] } });
    await openWorksPanel();
    expect(screen.queryByText(EXCLUDED_CHIP_TEXT)).not.toBeInTheDocument();
  });

  it('defaults to every registered work when no works prop is passed (unchanged existing behavior)', async () => {
    render(Search);
    await openWorksPanel();
    expect(screen.getByText(INCLUDED_CHIP_TEXT)).toBeInTheDocument();
    expect(screen.getByText(EXCLUDED_CHIP_TEXT)).toBeInTheDocument();
  });
});
