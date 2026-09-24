// Parser for REVIEW-CHECKLIST.md (repo root) -- turns the markdown source of
// truth into structured items with stable ids, so a separate rendering step
// can build the dashboard's HTML shell without re-parsing markdown itself.
//
// Shape settled on (see docs/ and the review-dashboard-pipeline memory note
// for the live dashboard's itemsData shape -- {id, kind, num?, section,
// title, cat, body, done} -- this module produces the subset of that shape
// that is actually derivable from the checklist text):
//
//   {
//     id:      string | null   -- pinned id from a `<!--id:...-->` comment
//                                  right after the checkbox; null until the
//                                  migration script (migrate-checklist-ids.mjs)
//                                  has run.
//     num:     number | null    -- active-queue position (1..81 today);
//                                  null for Completed/Retired items, which
//                                  are unnumbered in the source file.
//     section: 'active' | 'completed' | 'retired'
//     done:    boolean          -- checkbox state ([x] vs [ ]); Retired
//                                  items have no checkbox and are not
//                                  "done" in that sense, so this is always
//                                  false there.
//     title:   string           -- plain text (markdown stripped) of the
//                                  item's leading bold run, e.g.
//                                  "**Foo bar**" -> "Foo bar". Falls back to
//                                  a short plain-text lead when an item has
//                                  no bold run at all.
//     body:    string           -- the full item text rendered as HTML
//                                  (paragraphs, <strong>, <em>, <code>,
//                                  <a href>).
//     marker:  string | null    -- a leading symbol/emoji found inside the
//                                  title's bold run (e.g. "⚖", "✅", "⚑",
//                                  "🌊"), when present. This is the only
//                                  category-like signal actually present in
//                                  the markdown today -- the dashboard's
//                                  richer taxonomy (cat: authors | features
//                                  | site | ticket) lives in browser/export
//                                  state, not in REVIEW-CHECKLIST.md, so it
//                                  is NOT invented here. See the header note
//                                  in migrate-checklist-ids.mjs for the same
//                                  caveat applied to id derivation.
//   }
//
// Sections are delimited by the file's own `## ` headings: "Active review
// queue" (numbered list, `N. [ ]`), "Completed" (bullet list, `- [ ]`), and
// "Retired" (plain bullet list, no checkboxes). Item boundaries within a
// section are found by locating every list-item start marker and taking
// each item's raw text as the span up to the next start marker (or the end
// of the section) -- this is deliberately tolerant of items that contain
// blank lines in their own body (several do) as long as no line inside them
// itself looks like a new list-item start.

export const ID_COMMENT_RE = /<!--\s*id:([a-zA-Z0-9-]+)\s*-->\s*/;

export const ACTIVE_ITEM_START_RE = /^(\d+)\.\s+\[([ xX])\]\s*/gm;
export const BULLET_ITEM_START_RE = /^-\s+\[([ xX])\]\s*/gm;
export const PLAIN_BULLET_START_RE = /^-\s+/gm;

/** Slugify a title the way the (reconstructed) live dashboard does: lowercase,
 * non-alphanumerics collapsed to single hyphens, trimmed. This is our best
 * reconstruction of the live derivation, not a read of it (see
 * migrate-checklist-ids.mjs header). */
export function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function htmlEscape(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/** Render one paragraph of markdown (bold/italic/inline-code/links) to HTML.
 * Order matters: code and bold are matched before italic so `**bold**`
 * doesn't get eaten by the single-`*` italic rule first. */
function renderInline(text) {
  let html = htmlEscape(text);
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  html = html.replace(/_([^_]+)_/g, '<em>$1</em>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  return html;
}

/** Render the full (possibly multi-paragraph) raw item text to HTML. */
function renderBody(rawText) {
  const paragraphs = rawText
    .split(/\n\s*\n/)
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  return paragraphs.map((p) => `<p>${renderInline(p)}</p>`).join('\n');
}

/** Strip markdown syntax down to plain text, for title extraction. */
function toPlainText(text) {
  return text
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
    .trim();
}

// Known leading markers seen in the checklist (decisions, flags, waves,
// content-drop announcements...). Not exhaustive by design -- new markers
// just fall through to "no marker found" (null) until this list catches up.
const KNOWN_MARKERS = [
  '⚖', '⚑', '✅', '🌊', '📖', '🏺', '🔍', '📝', '🧩', '📗', '✉️', '🏛️', '🔤',
  '🧭', '🏷️', '🇬🇧', '📜', '📚',
];

export function extractTitleAndMarker(rawText) {
  const boldMatch = rawText.match(/\*\*([^*]+)\*\*/);
  const lead = boldMatch ? boldMatch[1] : rawText.slice(0, 80);
  let marker = null;
  let title = lead;
  for (const m of KNOWN_MARKERS) {
    if (lead.startsWith(m)) {
      marker = m;
      title = lead.slice(m.length).trim();
      break;
    }
  }
  return { title: toPlainText(title), marker };
}

function stripLeadingIdComment(rawText) {
  const match = rawText.match(ID_COMMENT_RE);
  if (!match) return { id: null, rest: rawText };
  return { id: match[1], rest: rawText.slice(match[0].length) };
}

/** Split `sectionText` into raw item strings using `startRe`, a global regex
 * matching only the list-item start marker (checkbox etc.) -- everything
 * from the end of one match to the start of the next becomes one item's raw
 * text, tagged with any captured checkbox/number groups. */
export function splitItems(sectionText, startRe) {
  const items = [];
  const matches = [...sectionText.matchAll(startRe)];
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const start = match.index + match[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index : sectionText.length;
    items.push({ match, raw: sectionText.slice(start, end).trim() });
  }
  return items;
}

export function findSection(markdown, headingRe, nextHeadingRe) {
  const startMatch = markdown.match(headingRe);
  if (!startMatch) return '';
  const start = startMatch.index + startMatch[0].length;
  const rest = markdown.slice(start);
  const endMatch = nextHeadingRe ? rest.match(nextHeadingRe) : null;
  return endMatch ? rest.slice(0, endMatch.index) : rest;
}

/**
 * Parse REVIEW-CHECKLIST.md into structured items. See module header for the
 * item shape.
 */
export function parseChecklist(markdown) {
  const items = [];

  const activeText = findSection(
    markdown,
    /^##\s+Active review queue.*$/m,
    /^##\s+Completed\s*$/m,
  );
  for (const { match, raw } of splitItems(activeText, ACTIVE_ITEM_START_RE)) {
    const num = Number(match[1]);
    const done = match[2].toLowerCase() === 'x';
    const { id, rest } = stripLeadingIdComment(raw);
    const { title, marker } = extractTitleAndMarker(rest);
    items.push({
      id,
      num,
      section: 'active',
      done,
      title,
      body: renderBody(rest),
      marker,
    });
  }

  const completedText = findSection(
    markdown,
    /^##\s+Completed\s*$/m,
    /^##\s+Retired.*$/m,
  );
  for (const { match, raw } of splitItems(completedText, BULLET_ITEM_START_RE)) {
    const done = match[1].toLowerCase() === 'x';
    const { id, rest } = stripLeadingIdComment(raw);
    const { title, marker } = extractTitleAndMarker(rest);
    items.push({
      id,
      num: null,
      section: 'completed',
      done,
      title,
      body: renderBody(rest),
      marker,
    });
  }

  const retiredText = findSection(markdown, /^##\s+Retired.*$/m, null);
  for (const { raw } of splitItems(retiredText, PLAIN_BULLET_START_RE)) {
    const { id, rest } = stripLeadingIdComment(raw);
    const { title, marker } = extractTitleAndMarker(rest);
    items.push({
      id,
      num: null,
      section: 'retired',
      done: false,
      title,
      body: renderBody(rest),
      marker,
    });
  }

  return items;
}
