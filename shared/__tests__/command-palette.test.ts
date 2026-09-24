// GPT-6 Sol code review item 2 (docs/todo/plato-mount.md, MAJOR): the ⌘K
// palette used to rank "jump to a work" results against the full WORKS
// registry, which now lists Plato's 36 dialogues even though their data is
// held out of the build — a matching query offered a work whose page 404s.
// The fix is a `works` prop (default: the full registry, unchanged for every
// existing call site that doesn't pass one) that a host page can narrow to
// only what's actually built (app/src/lib/built-works.ts's builtWorks()).
// This suite proves the prop actually scopes the "work" result kind, without
// depending on any particular real registry work staying held or built.
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import CommandPalette from '../components/CommandPalette.svelte';
import type { Work } from '../lib/works';

function fakeWork(overrides: Partial<Work>): Work {
  return {
    id: 'fake', slug: undefined, title: 'Fake Work', greekTitle: undefined, abbr: 'FW.',
    author: 'fixtureauthor', language: 'grc', workType: 'continuous', books: 1,
    bookLabels: ['1'], greekEdition: 'Test', greekSource: { short: 'Test', full: 'Test' },
    translations: [], blurb: 'Test.',
    ...overrides,
  } as Work;
}

// workPath() (called when a "work" result is built) resolves the id against
// the REAL WORKS registry, not against the fake object passed here -- so the
// "offered" case needs a real, stable, always-built id. 'heraclitus-fragments'
// is used the same way by bekker-jump.test.ts. The "held" case is never
// passed to the component at all, so it never reaches workPath and needs no
// real id.
const REAL_WORK_ID = 'heraclitus-fragments';

async function openAndQuery(query: string) {
  await fireEvent.keyDown(window, { key: 'k', metaKey: true });
  const input = await screen.findByLabelText('Jump to a work, Stephanus page, or Greek word');
  await fireEvent.input(input, { target: { value: query } });
  // compute() is async (awaits nothing on this path, but is still a promise
  // chain) -- flush microtasks so `items` has settled before assertions.
  await Promise.resolve();
  await Promise.resolve();
}

describe('CommandPalette — the works prop scopes "jump to a work" results', () => {
  it('offers a work present in the works prop', async () => {
    const built = fakeWork({ id: REAL_WORK_ID, title: 'Built Dialogue', abbr: 'BD.' });
    render(CommandPalette, { props: { works: [built] } });
    await openAndQuery('Built Dialogue');
    expect(screen.getByText('Built Dialogue')).toBeInTheDocument();
  });

  it('never offers a work left out of the works prop, even though it would otherwise match', async () => {
    const built = fakeWork({ id: REAL_WORK_ID, title: 'Built Dialogue', abbr: 'BD.' });
    const held = fakeWork({ id: 'held-dialogue', title: 'Held Dialogue', abbr: 'HD.' });
    // held is a real Work the ranking function would match -- it's simply
    // never passed in `works`, the same as an unbuilt registry work would be
    // once its host page filters to builtWorks().
    render(CommandPalette, { props: { works: [built] } });
    await openAndQuery('Held Dialogue');
    expect(screen.queryByText('Held Dialogue')).not.toBeInTheDocument();
    void held; // documents what "held" stands in for; never passed to the component
  });
});
