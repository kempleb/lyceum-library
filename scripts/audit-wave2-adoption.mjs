#!/usr/bin/env node

// Classifies every remaining divergence between a wave-2 work's pre-change
// snapshot and its freshly-built lined-source text into a known, adjudicated
// class (see `classify` and `isClass7Pair` below) so a genuinely new
// regression cannot hide among expected differences. Restored-agreement
// note (2026-08-30 cross-script wrap fix, pipeline/reader_pipeline/lined.py):
// 7 loci where a wrapped word's letters belong to the OTHER script from the
// work's own alphabet -- lives 1.67 ("Her-"/"cher"), de-finibus 1.15/3.35/
// 3.52, de-officiis 1.8, tusculan-disputations 1.37/4.21 -- used to stay
// split and show up here as unclassified hunks. Once the pipeline fix
// rejoins them (matching the 4.5 exports' own whole-word text), they
// produce NO hunk at all and simply vanish from this audit's diff. No
// classifier exists for them, deliberately: agreement is the expected
// (and now restored) outcome, not a case to adjudicate.

import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";

const REPO_ROOT = path.resolve(path.dirname(process.argv[1]), "..");
const WORK_IDS = [
  "lives",
  "de-finibus",
  "de-divinatione",
  "de-legibus",
  "de-officiis",
  "tusculan-disputations",
];
const CICERO_IDS = WORK_IDS.filter((id) => id !== "lives");
const CLASS1_BY_WORK = Object.freeze({
  "de-finibus": 67,
  "de-divinatione": 50,
  "de-legibus": 17,
  "de-officiis": 6,
  "tusculan-disputations": 73,
});
const ADJUDICATED_PAREN_CLASS = "adjudicated-paren-2026-08-30";
const greekLetter = /\p{Script=Greek}/u;

function fail(message) {
  console.error(`audit-wave2-adoption: ${message}`);
  process.exitCode = 1;
}

function fatal(message) {
  console.error(`audit-wave2-adoption: ${message}`);
  process.exit(2);
}

function parseArgs(argv) {
  let snapshots = null;
  const selected = [];
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--snapshots") {
      snapshots = argv[index + 1] ?? null;
      index += 1;
    } else if (arg.startsWith("--snapshots=")) {
      snapshots = arg.slice("--snapshots=".length);
    } else if (arg.startsWith("--")) {
      fatal(`unknown option ${arg}`);
    } else {
      selected.push(arg);
    }
  }
  if (!snapshots) fatal("usage: audit-wave2-adoption.mjs --snapshots <root> [work ...]");
  const workIds = selected.length === 0 ? WORK_IDS : [...new Set(selected)];
  for (const id of workIds) {
    if (!WORK_IDS.includes(id)) fatal(`unknown wave-2 work ${JSON.stringify(id)}`);
  }
  return { snapshots: path.resolve(snapshots), workIds };
}

function parseJson(file) {
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch (error) {
    fatal(`${file}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function bookFiles(dir) {
  if (!existsSync(dir)) fatal(`required directory is missing: ${dir}`);
  const files = readdirSync(dir)
    .filter((name) => /^book-\d+\.json$/u.test(name))
    .sort()
    .map((name) => path.join(dir, name));
  if (files.length === 0) fatal(`no book-*.json files in ${dir}`);
  return files;
}

function loadSide(dir) {
  const columns = new Map();
  const segmentOrder = [];
  for (const file of bookFiles(dir)) {
    const data = parseJson(file);
    if (!Array.isArray(data?.segments)) fatal(`${file}: missing segments array`);
    for (const segment of data.segments) {
      if (typeof segment?.column !== "string" || !Array.isArray(segment.greek)) {
        fatal(`${file}: malformed segment`);
      }
      const lines = segment.greek;
      const text = lines.map((line) => line.text).filter(Boolean).join(" ");
      const tokens = lines.flatMap((line) => line.tokens ?? []);
      if (columns.has(segment.column)) fatal(`${file}: duplicate column ${segment.column}`);
      columns.set(segment.column, { text, tokens });
      segmentOrder.push(segment.column);
    }
  }
  return { dir, columns, segmentOrder };
}

function diffSequence(left, right, key = (value) => value) {
  const rows = Array.from({ length: left.length + 1 }, () => new Uint32Array(right.length + 1));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      rows[i][j] = key(left[i]) === key(right[j])
        ? rows[i + 1][j + 1] + 1
        : Math.max(rows[i + 1][j], rows[i][j + 1]);
    }
  }
  const operations = [];
  let i = 0;
  let j = 0;
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && key(left[i]) === key(right[j])) {
      operations.push({ type: "equal", left: left[i], right: right[j], leftIndex: i, rightIndex: j });
      i += 1;
      j += 1;
    } else if (j >= right.length || (i < left.length && rows[i + 1][j] >= rows[i][j + 1])) {
      operations.push({ type: "delete", left: left[i], leftIndex: i });
      i += 1;
    } else {
      operations.push({ type: "insert", right: right[j], rightIndex: j });
      j += 1;
    }
  }
  return operations;
}

function textTokens(text) {
  return [...text.matchAll(/\s+|[\p{L}\p{M}\p{N}<>\[\]'’]+|./gu)].map((match) => match[0]);
}

function diffHunks(oldText, newText) {
  const hunks = [];
  let current = null;
  for (const operation of diffSequence(textTokens(oldText), textTokens(newText))) {
    if (operation.type === "equal") {
      if (current) hunks.push({ ...current, followingWord: operation.right });
      current = null;
      continue;
    }
    current ??= { old: [], new: [] };
    if (operation.type === "delete") current.old.push(operation.left);
    else current.new.push(operation.right);
  }
  if (current) hunks.push(current);
  return hunks.map((hunk) => ({
    old: hunk.old.join(""),
    new: hunk.new.join(""),
    followingWord: hunk.followingWord,
  }));
}

const HOMOGLYPHS = new Map(Object.entries({
  Α: "A", Β: "B", Ε: "E", Ζ: "Z", Η: "H", Ι: "I", Κ: "K", Μ: "M",
  Ν: "N", Ο: "O", Ρ: "P", Τ: "T", Χ: "X", Θ: "Q", Ϲ: "C",
  α: "a", β: "b", ε: "e", ζ: "z", η: "h", ι: "i", κ: "k", μ: "m",
  ν: "n", ο: "o", ρ: "p", τ: "t", χ: "x", θ: "q", ϲ: "c",
  // Beta Code letter values, not visual lookalikes: 4.5's runaway Greek
  // handler read the intended Latin capital AS Beta Code, so P came out π
  // (πlatonis) and L came out λ (λatina, λatine).
  π: "p", Π: "P", λ: "l", Λ: "L",
}));

function repairHomoglyphs(value) {
  return Array.from(value, (char) => HOMOGLYPHS.get(char) ?? char).join("");
}

// Class 2 (homoglyph capitals) whole-word shape: a rekeying artifact typed
// a WORD-INITIAL capital as a lookalike lowercase Greek letter instead --
// 'τimaeo' -> 'Timaeo' (τ/T), 'θuamquam' -> 'Quamquam' (θ/Q, same table
// entry as lowercase θ->q, just compared case-insensitively here since the
// intended capital never appears lowercase in the homoglyph table). Only
// the leading Greek-letter run gets case-folded through the homoglyph
// table; everything after it must match byte-for-byte, same strictness as
// the old whole-string check.
function leadingGreekRunLength(value) {
  let length = 0;
  while (length < value.length && greekLetter.test(value[length])) length += 1;
  return length;
}

function compact(value) {
  return value.replace(/\s+/gu, "");
}

function dehyphenated(value) {
  return value.replace(/-\s+/gu, "");
}

function withoutSigla(value) {
  return value.replace(/[<>\[\]]/gu, "");
}

function quoteDashCanonical(value) {
  return value.replace(/[\s“”„"‘’'«»—]/gu, "");
}

function classify(workId, hunk) {
  const oldCompact = compact(hunk.old);
  const newCompact = compact(hunk.new);
  // docs/phi-punctuation-adjudication.md §6a rules this single PHI `(` faithful.
  if (
    workId === "de-divinatione"
    && hunk.old === ""
    && hunk.new === "("
    && hunk.followingWord === "quam"
  ) return ADJUDICATED_PAREN_CLASS;
  if (oldCompact === "." && newCompact === "!") return 1;
  // Class 2 is a Cicero-only declared class; without the work gate,
  // Lives' iota-numeral repairs (class 4) would match this predicate
  // first and be miscounted.
  if (CICERO_IDS.includes(workId) && greekLetter.test(oldCompact) && !greekLetter.test(newCompact)) {
    const leadLen = leadingGreekRunLength(oldCompact);
    if (
      leadLen > 0
      && oldCompact.length === newCompact.length
      && oldCompact.slice(leadLen) === newCompact.slice(leadLen)
      && repairHomoglyphs(oldCompact.slice(0, leadLen)).toLowerCase()
        === newCompact.slice(0, leadLen).toLowerCase()
    ) return 2;
  }
  if (oldCompact === ";" && newCompact === ";") return 3;
  // Class 4 (Lives Roman-numeral homoglyphs): a run of Greek iotas
  // rekeyed for the Latin capital 'I' it looks like -- 'ι' -> 'I',
  // 'ιιι' -> 'III', optionally multi-char, with an optional trailing
  // '.' (the numeral's own period) carried through unchanged.
  if (workId === "lives") {
    const iotaMatch = /^(ι+)(\.?)$/u.exec(oldCompact);
    if (iotaMatch && newCompact === "I".repeat(iotaMatch[1].length) + iotaMatch[2]) return 4;
  }
  // Class 7 (de-legibus R4d unjoined continuation) is NOT classified
  // per-hunk here -- it appears as a PAIRED hunk ('prae<tendebat>' -> 'prae-'
  // then '' -> '<tendebat> '), so it is matched by `isClass7Pair` below and
  // consumed two-at-a-time in the main per-book loop.
  // Class 10 (2026-08-30): de-finibus 3.35 "dicerẹ" -> "dicere?" -- PHI's
  // raw source carries a literal ASCII '?' (0x3F) at byte offset
  // 0x479b47 ("iracundiam morbum solet dicere? at illi"), but the 4.5
  // export rendered that question mark as a combining dot below (U+0323)
  // attached to the preceding letter instead. Predicate: old ends in
  // <letter> + U+0323, new ends in the same <letter> followed by a
  // literal '?' -- i.e. old with its trailing combining mark swapped for
  // '?'. Restricted to de-finibus, the only work where this artifact
  // occurs.
  if (
    workId === "de-finibus"
    && hunk.old.endsWith("̣")
    && hunk.new === `${hunk.old.slice(0, -1)}?`
  ) return 10;
  if (/-\s+/u.test(hunk.old) && dehyphenated(hunk.old) === hunk.new) return 6;
  if (
    hunk.old !== hunk.new
    && quoteDashCanonical(hunk.old) === quoteDashCanonical(hunk.new)
  ) return 5;
  return null;
}

// Class 7 (de-legibus R4d unjoined continuation) is a PAIRED hunk: the
// first hunk deletes the whole old word and re-inserts only its non-
// hyphenated head ("prae<tendebat>" -> "prae-"), and the very NEXT hunk
// has NO deletion at all -- it is a pure insert of the rest ("" ->
// "<tendebat> "). Concatenating the two hunks own new sides and stripping
// sigla/hyphens/whitespace must reassemble the first hunk own old side
// exactly, or this is not the R4d shape.
function isClass7Pair(workId, first, second) {
  if (workId !== "de-legibus") return false;
  if (second.old !== "" || second.new === "") return false;
  if (first.new === "") return false;
  const reassembled = compact(withoutSigla(first.new + second.new)).replace(/-/gu, "");
  return reassembled === compact(withoutSigla(first.old));
}

function changedTokenPositions(oldSide, newSide) {
  const oldAllowed = new Set();
  const newAllowed = new Set();
  for (const [segmentIndex, column] of oldSide.segmentOrder.entries()) {
    const oldEntry = oldSide.columns.get(column);
    const newEntry = newSide.columns.get(column);
    if (!newEntry) continue;
    const key = (token) => `${token.t}\u0000${token.k ?? ""}`;
    for (const operation of diffSequence(oldEntry.tokens, newEntry.tokens, key)) {
      if (operation.type === "delete") oldAllowed.add(`${segmentIndex}:${operation.leftIndex}`);
      if (operation.type === "insert") newAllowed.add(`${segmentIndex}:${operation.rightIndex}`);
    }
  }
  return { oldAllowed, newAllowed };
}

function assertSearchKeyChanges(workId, oldDir, newDir, oldAllowed, newAllowed) {
  for (const indexName of ["lemma", "form"]) {
    const oldIndex = parseJson(path.join(oldDir, "search", `${indexName}.json`));
    const newIndex = parseJson(path.join(newDir, "search", `${indexName}.json`));
    const removed = Object.keys(oldIndex).filter((key) => !(key in newIndex));
    const added = Object.keys(newIndex).filter((key) => !(key in oldIndex));
    for (const key of removed) {
      const outside = oldIndex[key].filter(([segment, token]) => !oldAllowed.has(`${segment}:${token}`));
      if (outside.length > 0) {
        fail(`${workId}: removed ${indexName} key ${JSON.stringify(key)} has undeclared positions ${JSON.stringify(outside)}`);
      }
    }
    for (const key of added) {
      const outside = newIndex[key].filter(([segment, token]) => !newAllowed.has(`${segment}:${token}`));
      if (outside.length > 0) {
        fail(`${workId}: added ${indexName} key ${JSON.stringify(key)} has undeclared positions ${JSON.stringify(outside)}`);
      }
    }
    console.log(`${workId}: ${indexName} key-set delta -${removed.length} +${added.length} (all at class-touched tokens)`);
  }
}

const options = parseArgs(process.argv.slice(2));
const counts = Object.fromEntries(options.workIds.map((id) => [id, Object.fromEntries(
  [...Array.from({ length: 7 }, (_unused, index) => [index + 1, 0]), [ADJUDICATED_PAREN_CLASS, 0], [10, 0]],
)]));
const unknown = [];

for (const workId of options.workIds) {
  const oldDir = path.join(options.snapshots, `${workId}-prechange`);
  const newDir = path.join(REPO_ROOT, "build", "dist", workId);
  const oldSide = loadSide(oldDir);
  const newSide = loadSide(newDir);
  if (oldSide.segmentOrder.join("\n") !== newSide.segmentOrder.join("\n")) {
    fail(`${workId}: snapshot and new column spines differ`);
    continue;
  }
  // Compare per BOOK, not per column: the 4.5 exports split text mid-line
  // at section markers while print-line fidelity assigns whole lines to
  // one section, so sentence-ends legitimately migrate between adjacent
  // columns (text-conserving — thousands of paired boundary hunks at
  // column granularity, zero at book granularity). The pre-adoption
  // classifier used book granularity for the same reason; column
  // assignment itself is verified separately by verify-lined-source's
  // check 5 round-trip against the fresh export.
  const oldBooks = new Map();
  const newBooks = new Map();
  for (const column of oldSide.segmentOrder) {
    const book = column.split(".")[0];
    oldBooks.set(book, `${oldBooks.get(book) ?? ""} ${oldSide.columns.get(column).text}`);
    newBooks.set(book, `${newBooks.get(book) ?? ""} ${newSide.columns.get(column).text}`);
  }
  for (const [book, oldText] of oldBooks) {
    const newText = newBooks.get(book);
    const hunks = diffHunks(oldText, newText);
    for (let index = 0; index < hunks.length; index += 1) {
      const hunk = hunks[index];
      const classNumber = classify(workId, hunk);
      if (classNumber !== null) {
        counts[workId][classNumber] += 1;
        continue;
      }
      // Class 7 is a PAIRED hunk (see isClass7Pair above) -- try the
      // adjacent hunk before giving up as unclassified.
      const next = hunks[index + 1];
      if (next && isClass7Pair(workId, hunk, next)) {
        counts[workId][7] += 1;
        index += 1;
        continue;
      }
      unknown.push({ workId, column: `book ${book}`, ...hunk });
    }
  }

  if (CICERO_IDS.includes(workId)) {
    for (const [column, entry] of newSide.columns) {
      for (const [index, token] of entry.tokens.entries()) {
        if (token.t.includes("!")) fail(`${workId} ${column} token ${index + 1} contains !: ${JSON.stringify(token.t)}`);
        // R7.4 as corrected (2026-08-30, amending the plan's phrasing):
        // Cicero quotes Greek terms deliberately (τέλος, ἡδονή, καθῆκον —
        // ~120 legitimate pure-Greek tokens), so the corruption assertion
        // is MIXED-script within one token (the πlatonis/θuamquam class),
        // not any Greek letter at all.
        if (greekLetter.test(token.t) && /[A-Za-z]/u.test(token.t)) {
          fail(`${workId} ${column} token ${index + 1} mixes Greek and Latin letters: ${JSON.stringify(token.t)}`);
        }
      }
    }
    const { oldAllowed, newAllowed } = changedTokenPositions(oldSide, newSide);
    assertSearchKeyChanges(workId, oldDir, newDir, oldAllowed, newAllowed);
  }
}

console.log("\nPer-class counts (classes 5 and 6 are measured outputs):");
for (const workId of options.workIds) {
  const class1to7 = Array.from({ length: 7 }, (_unused, index) => `${index + 1}=${counts[workId][index + 1]}`);
  console.log(`${workId}: ${[...class1to7, `10=${counts[workId][10]}`].join(" ")}`);
}
console.log(`MEASURED class 5 total: ${options.workIds.reduce((sum, id) => sum + counts[id][5], 0)}`);
console.log(`MEASURED class 6 total: ${options.workIds.reduce((sum, id) => sum + counts[id][6], 0)}`);
console.log(`${ADJUDICATED_PAREN_CLASS}: ${options.workIds.reduce((sum, id) => sum + counts[id][ADJUDICATED_PAREN_CLASS], 0)}`);

for (const [workId, expected] of Object.entries(CLASS1_BY_WORK)) {
  if (!options.workIds.includes(workId)) continue;
  if (counts[workId][1] !== expected) fail(`${workId}: class 1 expected ${expected}, got ${counts[workId][1]}`);
}
const total = (classNumber) => options.workIds.reduce((sum, id) => sum + counts[id][classNumber], 0);
if (
  options.workIds.includes("de-divinatione")
  && counts["de-divinatione"][ADJUDICATED_PAREN_CLASS] !== 1
) {
  fail(`${ADJUDICATED_PAREN_CLASS} expected 1 in de-divinatione, got ${counts["de-divinatione"][ADJUDICATED_PAREN_CLASS]}`);
}
if (options.workIds.length === WORK_IDS.length) {
  if (total(2) !== 15) fail(`class 2 expected 15 total, got ${total(2)}`);
  if (total(3) !== 5) fail(`class 3 expected 5 total, got ${total(3)}`);
  if (counts.lives[4] !== 2 || total(4) !== 2) fail(`class 4 expected 2 in lives only, got ${total(4)} total`);
  if (counts["de-legibus"][7] !== 1 || total(7) !== 1) fail(`class 7 expected 1 in de-legibus only, got ${total(7)} total`);
  if (counts["de-finibus"][10] !== 1 || total(10) !== 1) fail(`class 10 expected 1 in de-finibus only, got ${total(10)} total`);
}
if (unknown.length > 0) {
  fail(`${unknown.length} unclassified divergence(s):`);
  for (const item of unknown.slice(0, 100)) {
    console.error(`  ${item.workId} ${item.column}: ${JSON.stringify(item.old)} -> ${JSON.stringify(item.new)}`);
  }
  if (unknown.length > 100) console.error(`  ... ${unknown.length - 100} more`);
}
