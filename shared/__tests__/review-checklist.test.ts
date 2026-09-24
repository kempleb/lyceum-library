import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
// @ts-expect-error untyped .mjs module
import { parseChecklist, slugify } from '../../scripts/lib/review-checklist.mjs';
// @ts-expect-error untyped .mjs module
import { migrate } from '../../scripts/migrate-checklist-ids.mjs';

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

// parseChecklist/migrate come from an untyped .mjs module (see the
// ts-expect-error-annotated imports above), so their return value is `any`;
// give the parsed items an explicit shape here so downstream
// .filter/.find/.map callbacks don't each need their own parameter
// annotation.
type ChecklistItem = {
  section: string;
  num: number | null;
  title: string;
  marker: string | null;
  body: string;
  done: boolean;
  id: string | null;
};

// A small self-contained fixture exercising the messy real-world shapes
// (nested bold, inline code, links, checked/unchecked, Completed/Retired)
// without depending on the live REVIEW-CHECKLIST.md's exact wording.
const FIXTURE = `# Fixture checklist

## Active review queue (1-3)

1. [ ] **⚖ Decision title** — body text with a \`period\` field and a [link](https://example.com/x) to follow up. More prose in the same item.

2. [x] **Simple checked item** — this one is already checked, with **a second bold run** inside the body for good measure.

3. [ ] Item with no bold lead at all, just plain prose that keeps going for a while so the fallback title logic has something to chew on.

## Completed

- [x] **✅ Completed item one** — done and dusted, see \`some/code/path.mjs\`.
- [ ] **Completed item two** — technically unchecked but living in Completed.

## Retired — superseded and cut from the queue

- **Retired item one** — superseded by commit \`abc123\`.
`;

describe('parseChecklist', () => {
  const items = parseChecklist(FIXTURE) as ChecklistItem[];

  it('finds all items in each section', () => {
    expect(items.filter((i) => i.section === 'active')).toHaveLength(3);
    expect(items.filter((i) => i.section === 'completed')).toHaveLength(2);
    expect(items.filter((i) => i.section === 'retired')).toHaveLength(1);
  });

  it('extracts a markdown-formatted title as plain text, plus its marker', () => {
    const item = items.find((i) => i.num === 1)!;
    expect(item.title).toBe('Decision title');
    expect(item.marker).toBe('⚖');
  });

  it('renders inline code and links in the body as HTML', () => {
    const item = items.find((i) => i.num === 1)!;
    expect(item.body).toContain('<code>period</code>');
    expect(item.body).toContain('<a href="https://example.com/x">link</a>');
  });

  it('captures checkbox state for both checked and unchecked items', () => {
    const unchecked = items.find((i) => i.num === 1)!;
    const checked = items.find((i) => i.num === 2)!;
    expect(unchecked.done).toBe(false);
    expect(checked.done).toBe(true);
    // a second bold run in the body renders too, not just the title's
    expect(checked.body).toContain('<strong>a second bold run</strong>');
  });

  it('falls back to a plain-text lead when an item has no bold run', () => {
    const item = items.find((i) => i.num === 3)!;
    expect(item.title.startsWith('Item with no bold lead at all')).toBe(true);
    expect(item.marker).toBeNull();
  });

  it('parses Completed items with num=null and the right done state', () => {
    const completed = items.filter((i) => i.section === 'completed');
    expect(completed.every((i) => i.num === null)).toBe(true);
    expect(completed[0].done).toBe(true);
    expect(completed[0].title).toBe('Completed item one');
    expect(completed[1].done).toBe(false);
  });

  it('parses Retired items with no checkbox state and num=null', () => {
    const retired = items.find((i) => i.section === 'retired')!;
    expect(retired.num).toBeNull();
    expect(retired.done).toBe(false);
    expect(retired.title).toBe('Retired item one');
  });

  it('picks up any pinned <!--id:...--> comment already present', () => {
    const withId = parseChecklist(
      '## Active review queue (1-1)\n\n1. [ ] <!--id:my-pinned-id--> **Title** — body.\n\n## Completed\n\n## Retired\n',
    );
    expect(withId[0].id).toBe('my-pinned-id');
  });

  it('leaves id null when no pin comment is present', () => {
    const item = items.find((i) => i.num === 1)!;
    expect(item.id).toBeNull();
  });
});

describe('slugify', () => {
  it('lowercases, hyphenates non-alphanumerics, and trims', () => {
    expect(slugify("Gummere's English")).toBe('gummere-s-english');
    expect(slugify('  Leading/trailing -- punctuation!! ')).toBe('leading-trailing-punctuation');
  });
});

// Evidence from a genuine export of the LIVE dashboard (five items with
// their real ids and titles) -- the single best evidence available for how
// the live page actually derives ids, since the page itself needs auth and
// can't be fetched from here. We test the slug rule directly against these
// title/id pairs (not against today's REVIEW-CHECKLIST.md wording, which has
// since been edited with RULED/RESOLVED prefixes -- exactly the drift this
// mechanism exists to stop, so current wording is not expected to match).
const REAL_EXPORT_ITEMS = [
  {
    title: 'Source-passage credit copy — approval before deploy',
    id: 'source-passage-credit-copy',
  },
  {
    title: 'Phase-3 English sourcing — per-work calls + PD queue',
    id: 'phase3-sourcing-census',
  },
  {
    title: "Cicero's shelf** — placed provisionally on 'Hellenistic' (the peri",
    id: 'cicero-s-shelf-placed-provisionally-on-hellenistic-the-peri',
  },
  {
    title: "⚖ Latin inside Gummere's English",
    id: 'latin-inside-gummere-s-english',
  },
  {
    title: "Sophists on the 'classical' shelf",
    id: 'sophists-on-the-classical-shelf',
  },
];

describe('slugify against the five real live-dashboard ids', () => {
  it.each(REAL_EXPORT_ITEMS)('$id', ({ title, id }) => {
    const got = slugify(title);
    // Documented outcome (see scripts/migrate-checklist-ids.mjs header):
    // items 3 (Cicero shelf), 4 (Gummere) and 5 (Sophists) reproduce
    // exactly; items 1 (source-passage-credit-copy) and 2
    // (phase3-sourcing-census) do not, because their real ids were
    // evidently pinned from earlier/shorter title text no longer present
    // in this export's own title field.
    if (id === 'cicero-s-shelf-placed-provisionally-on-hellenistic-the-peri'
      || id === 'latin-inside-gummere-s-english'
      || id === 'sophists-on-the-classical-shelf') {
      expect(got).toBe(id);
    } else {
      expect(got).not.toBe(id);
    }
  });
});

describe('migrate (id pinning)', () => {
  it('is idempotent: a second pass adds zero ids', () => {
    const first = migrate(FIXTURE);
    expect(first.added).toBeGreaterThan(0);
    const second = migrate(first.markdown);
    expect(second.added).toBe(0);
    expect(second.markdown).toBe(first.markdown);
  });

  it('never touches an item that already has a pinned id', () => {
    const alreadyPinned = '## Active review queue (1-1)\n\n1. [ ] <!--id:keep-me--> **Title** — body.\n\n## Completed\n\n## Retired\n';
    const { markdown, added } = migrate(alreadyPinned);
    expect(added).toBe(0);
    expect(markdown).toBe(alreadyPinned);
  });

  it('assigns distinct ids when two titles would slugify the same way', () => {
    const collision = '## Active review queue (1-2)\n\n1. [ ] **Same Title** — first.\n\n2. [ ] **Same Title** — second.\n\n## Completed\n\n## Retired\n';
    const { markdown } = migrate(collision);
    const items = parseChecklist(markdown) as ChecklistItem[];
    const ids = items.filter((i) => i.section === 'active').map((i) => i.id);
    expect(new Set(ids).size).toBe(2);
  });
});

describe('parseChecklist against the real REVIEW-CHECKLIST.md', () => {
  const real = readFileSync(join(REPO_ROOT, 'REVIEW-CHECKLIST.md'), 'utf8');
  const items = parseChecklist(real) as ChecklistItem[];

  it('finds 106 active items, 28 completed, 9 retired (current file shape)', () => {
    expect(items.filter((i) => i.section === 'active')).toHaveLength(106);
    expect(items.filter((i) => i.section === 'completed')).toHaveLength(28);
    expect(items.filter((i) => i.section === 'retired')).toHaveLength(9);
  });

  it('numbers active items 1..106 in order with no gaps', () => {
    const nums = items.filter((i) => i.section === 'active').map((i) => i.num);
    expect(nums).toEqual(Array.from({ length: 106 }, (_, i) => i + 1));
  });
});
