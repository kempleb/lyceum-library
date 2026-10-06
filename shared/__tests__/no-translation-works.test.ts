import { describe, expect, it } from 'vitest';
import { WORKS } from '../lib/works';
import { schemeFor } from '../lib/citation';

// Review item 128. Landing.astro words a no-translation work two ways, keyed on
// the citation scheme: the Diels-Kranz testimonia works (all show English under
// some source passages) versus the six Latin works (no English anywhere).
// This pins that the DK key splits the registry exactly that way.
const noTranslation = WORKS.filter((w) => w.language !== 'en' && w.translations.length === 0);
const isDk = (id: string) => schemeFor(id).id === 'dk';

describe('no-translation works (item 128)', () => {
  it('the Diels-Kranz ones are the Greek testimonia works', () => {
    const dk = noTranslation.filter((w) => isDk(w.id));
    expect(dk.every((w) => w.language === 'grc' && w.id.endsWith('-testimonia'))).toBe(true);
    expect(dk.length).toBe(20);
  });

  it('none of the Latin ones is Diels-Kranz', () => {
    const latin = noTranslation.filter((w) => w.language === 'lat');
    expect(latin).toHaveLength(6);
    expect(latin.every((w) => !isDk(w.id))).toBe(true);
  });
});
