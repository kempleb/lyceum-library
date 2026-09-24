// The authors registry — the single source of truth for which philosophers
// the site carries. Complements works.ts: an Author owns an ordered list of
// Work ids (works.ts's `Work.author` is the reverse reference, a slug into
// this registry). Phase 0 ships this registry empty (+ a flag-gated fixture,
// see FIXTURES_ON below) — the pilot author (Marcus Aurelius) and the
// migrated Plato/Aristotle corpora land in later waves.

import { CORPUS_AUTHORS, FIXTURE_AUTHORS, AUTHOR_PERIOD_ORDER_DATA, PERIOD_LABEL_DATA, SCHOOL_LABEL_DATA, SCHOOL_GROUP_ORDER_DATA, WORK_CORPUS_DATA } from './registry.generated';

export type AuthorPeriod = 'presocratic' | 'sophists' | 'classical' | 'hellenistic' | 'roman' | 'imperial' | 'late-antique';

export interface Author {
  id: string;            // URL slug, kebab-case, e.g. 'marcus-aurelius'
  name: string;           // 'Marcus Aurelius'
  nativeName: string;     // 'Μᾶρκος Αὐρήλιος'
  languages: ('grc' | 'lat')[];
  period: AuthorPeriod;
  schools: string[];      // e.g. ['stoic']
  floruit: string;        // display string, e.g. 'AD 121–180'
  blurb: string;
  works: string[];        // ordered Work ids
  // Editorial completeness of the served corpus against the complete
  // surviving/standard collection for this author (e.g. the DK A+B pair for
  // a Presocratic, or the full Lives for Diogenes Laertius) — independent of
  // whether every work is *built* in a given checkout (see built-works.ts).
  // 'complete': the home page's author card reads "Complete works",
  // "Complete fragments & testimonia", or "Complete surviving works"
  // (see holdingsLabel). 'partial': the card lists the work titles held.
  holdings: 'complete' | 'partial';
}

// Fixture author+work enter the registries only when this env flag is
// truthy, mirroring works.ts's SHOW_PRIVATE / PUBLIC_SHOW_PRIVATE pattern
// (same import.meta.env.PUBLIC_* read, which Vite/Astro statically replace at
// build time — so an unset flag dead-code-eliminates the fixture out of any
// client bundle, and vitest picks up a shell-exported PUBLIC_READER_FIXTURES
// the same way it already does PUBLIC_SHOW_PRIVATE).
const FIXTURES_ON = import.meta.env.PUBLIC_READER_FIXTURES === '1';

// P6 wing-standalone build mode (docs/p6-plan.md, Settled decision 4): when
// set, scopes AUTHORS to the authors owning at least one work in that corpus
// (e.g. PUBLIC_WING=aristotle keeps 'aristotle' + 'porphyry'), via the
// work-id -> corpus map generated alongside the registry — an author-of-work
// mapping, since Author carries no corpus field of its own. No author today
// mixes works across corpora, so "owns any work in the corpus" and "owns
// only works in the corpus" agree. Same module-scope import.meta.env read as
// works.ts's mirroring filter; see that file's doc comment for the fixture
// ruling (fixtures ride along unfiltered — mirrored here for the same
// reason: WORK_CORPUS_DATA has no entry for the fixture author's works).
const WING = import.meta.env.PUBLIC_WING;
const WORK_CORPUS = WORK_CORPUS_DATA as Record<string, string>;

const WING_CORPUS_AUTHORS: Author[] = WING
  ? (CORPUS_AUTHORS as Author[]).filter((a) => a.works.some((id) => WORK_CORPUS[id] === WING))
  : (CORPUS_AUTHORS as Author[]);

export const AUTHORS: Author[] = [
  ...WING_CORPUS_AUTHORS,
  ...(FIXTURES_ON ? (FIXTURE_AUTHORS as Author[]) : []),
];

const BY_ID = new Map(AUTHORS.map((a) => [a.id, a]));

export function getAuthor(id: string): Author | undefined {
  return BY_ID.get(id);
}

// The five periods in canonical (chronological) order — drives shelf order
// on the home page and any period-grouped listing.
export const AUTHOR_PERIOD_ORDER: AuthorPeriod[] = AUTHOR_PERIOD_ORDER_DATA as AuthorPeriod[];

// Display names for each period.
// 'roman' label is provisional — John, 2026-08-03: "Latin or Roman. We fix
// later." Picked "Roman" (reads as a period, pairs with the eyebrow's
// "<label> · <floruit>" rendering); the string is the only thing to change
// if he later prefers "Latin".
export const PERIOD_LABEL: Record<AuthorPeriod, string> = PERIOD_LABEL_DATA as Record<AuthorPeriod, string>;

// Authors grouped by period, period-ordered (AUTHOR_PERIOD_ORDER); within a
// period, authors keep their AUTHORS registry order. Every period key is
// present even when empty, so a caller can iterate the map without a
// separate existence check.
export function authorsByPeriod(): Map<AuthorPeriod, Author[]> {
  const map = new Map<AuthorPeriod, Author[]>(AUTHOR_PERIOD_ORDER.map((p) => [p, []]));
  for (const a of AUTHORS) map.get(a.period)!.push(a);
  return map;
}

// ── School clusters (home page sub-headings within a period shelf) ─────────
//
// A slot is either a school ({ school }) — every author in the input list
// whose `schools` includes that key, in registry order unless `order`
// overrides it — or a single standalone author ({ author }), rendered as its
// own unheaded group at that position in the sequence. `order` is only
// needed where AUTHORS registry order doesn't already match the wanted
// teaching sequence (Xenophanes predates Parmenides but is registered after
// him; Anaxagoras predates Empedocles but is registered before him — both
// pre-date the sophists batches added later).
interface SchoolGroupSlot {
  school?: string;
  author?: string;
  order?: string[];
}

// Only periods with an established teaching sequence get an entry. A period
// absent here (Sophists — six authors and nothing else, so a "Sophists"
// heading would label the whole shelf, i.e. label nothing; Classical —
// empty until Plato/Aristotle land; Imperial — 3 authors, too few to bother
// grouping) renders as one unheaded group, same as before this table existed.
export const SCHOOL_GROUP_ORDER: Partial<Record<AuthorPeriod, SchoolGroupSlot[]>> =
  SCHOOL_GROUP_ORDER_DATA as Partial<Record<AuthorPeriod, SchoolGroupSlot[]>>;

// Author-card holdings line on the home page. Partial holdings list the
// held work titles; complete holdings pick a collection kind from the works'
// workType values (three cases so a future mixed continuous+fragments author
// is not mislabeled as fragments-only).
export function holdingsLabel(
  holdings: Author['holdings'],
  works: { title: string; workType: string }[],
): string {
  if (holdings === 'partial') return works.map((w) => w.title).join(', ');
  const allContinuous = works.length > 0 && works.every((w) => w.workType === 'continuous');
  const allFragments = works.length > 0 && works.every((w) => w.workType === 'fragments');
  if (allContinuous) return 'Complete works';
  if (allFragments) return 'Complete fragments & testimonia';
  return 'Complete surviving works';
}

// Display heading for each school key used in SCHOOL_GROUP_ORDER above.
export const SCHOOL_LABEL: Record<string, string> = SCHOOL_LABEL_DATA;

export interface AuthorGroup {
  heading: string | null; // null = render unheaded
  authors: Author[];
}

// Clusters `authors` (already period-filtered, e.g. from authorsByPeriod())
// into the school groups the home page renders as sub-headings within a
// shelf, per SCHOOL_GROUP_ORDER[period]. Membership is driven entirely by
// each Author's `schools` field; this table only fixes the curated *sequence*
// the groups render in. Any author not claimed by a slot (a data gap, or a
// period outside the curated sequence) still comes back, unheaded, in a
// trailing group — grouping can never silently drop an author card.
export function authorGroups(period: AuthorPeriod, authors: Author[]): AuthorGroup[] {
  const order = SCHOOL_GROUP_ORDER[period];
  if (!order) return authors.length ? [{ heading: null, authors }] : [];

  const used = new Set<string>();
  const groups: AuthorGroup[] = [];
  for (const slot of order) {
    if (slot.author) {
      const a = authors.find((x) => x.id === slot.author && !used.has(x.id));
      if (a) {
        groups.push({ heading: null, authors: [a] });
        used.add(a.id);
      }
    } else if (slot.school) {
      let members = authors.filter((a) => !used.has(a.id) && a.schools.includes(slot.school!));
      if (slot.order) {
        const rank = new Map(slot.order.map((id, i) => [id, i]));
        members = [...members].sort((a, b) => (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity));
      }
      if (members.length) {
        groups.push({ heading: SCHOOL_LABEL[slot.school] ?? slot.school, authors: members });
        for (const a of members) used.add(a.id);
      }
    }
  }
  const leftover = authors.filter((a) => !used.has(a.id));
  if (leftover.length) groups.push({ heading: null, authors: leftover });
  return groups;
}
