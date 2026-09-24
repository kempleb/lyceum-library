#!/usr/bin/env node

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

const FAILURE_LIMIT = 20;
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const greekLetter = /^\p{Script=Greek}$/u;
const latinLetter = /^\p{Script=Latin}$/u;
const lowerCaseLetter = /^\p{Lowercase_Letter}$/u;

const scriptPath = path.resolve(process.argv[1]);
const repoRoot = path.resolve(path.dirname(scriptPath), "..");
// Pre-change snapshots + 4.5 export backups live in the wave-2 archive
// (moved out of the session scratchpad 2026-08-30; sha256 manifest inside).
// Override with LINED_SNAPSHOT_ROOT if the archive moves.
const DEFAULT_SNAPSHOT_ROOT =
  process.env.LINED_SNAPSHOT_ROOT ??
  "/Users/johnboyer/Documents/CLAUDE CODE ARISTOTLE PROJECT/" +
    "reader-archives/wave2-2026-08-30";

const WORKS = Object.freeze({
  discourses: {
    id: "discourses",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0557001.xml",
    distDir: "build/dist/discourses",
    distGlob: "book-*.json",
    topology: { bookDivType: "Book", columnDivType: "chapter", sectionDivType: "section" },
    expected: {
      // wave-2 R4c amendment: 2 closing-siglum joins (cols 1.4, 3.10)
      columns: 95, bodyLines: 9285, wraps: 2393, sectionStraddling: 619,
      crossColumn: 0, columnFinal: 0, unjoinable: 2,
      indents: { 1: 390, 2: 53, 3: 4 }, siglumLoci: 2,
    },
    alphabet: "greek",
    snapshotDir: "discourses-prechange",
  },
  enchiridion: {
    id: "enchiridion",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0557002.xml",
    distDir: "build/dist/enchiridion",
    distGlob: "book-*.json",
    topology: { columnDivType: "Chapter", sectionDivType: "section" },
    expected: {
      columns: 53, bodyLines: 598, wraps: 132, sectionStraddling: 8,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 52, 2: 7 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "enchiridion-prechange",
  },
  "epicurus-letter-to-herodotus": {
    id: "epicurus-letter-to-herodotus",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0537010.xml",
    distDir: "build/dist/epicurus-letter-to-herodotus",
    distGlob: "book-*.json",
    topology: { columnDivType: "Section" },
    expected: {
      columns: 49, bodyLines: 522, wraps: 130, sectionStraddling: 0,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 28 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "epicurus-letter-to-herodotus-prechange",
  },
  "epicurus-letter-to-pythocles": {
    id: "epicurus-letter-to-pythocles",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0537011.xml",
    distDir: "build/dist/epicurus-letter-to-pythocles",
    distGlob: "book-*.json",
    topology: { columnDivType: "Section" },
    expected: {
      columns: 33, bodyLines: 372, wraps: 89, sectionStraddling: 0,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 29 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "epicurus-letter-to-pythocles-prechange",
  },
  "epicurus-letter-to-menoeceus": {
    id: "epicurus-letter-to-menoeceus",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0537012.xml",
    distDir: "build/dist/epicurus-letter-to-menoeceus",
    distGlob: "book-*.json",
    topology: { columnDivType: "Section" },
    expected: {
      columns: 14, bodyLines: 152, wraps: 38, sectionStraddling: 0,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 11, 2: 1 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "epicurus-letter-to-menoeceus-prechange",
  },
  "epicurus-kuriai-doxai": {
    id: "epicurus-kuriai-doxai",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0537013.xml",
    distDir: "build/dist/epicurus-kuriai-doxai",
    distGlob: "book-*.json",
    topology: { columnDivType: "Section" },
    expected: {
      columns: 40, bodyLines: 168, wraps: 39, sectionStraddling: 0,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 40 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "epicurus-kuriai-doxai-prechange",
  },
  "epicurus-vatican-sayings": {
    id: "epicurus-vatican-sayings",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0537014.xml",
    distDir: "build/dist/epicurus-vatican-sayings",
    distGlob: "book-*.json",
    topology: { columnDivType: "Fragment" },
    expected: {
      columns: 62, bodyLines: 149, wraps: 23, sectionStraddling: 0,
      crossColumn: 0, columnFinal: 0, unjoinable: 0,
      indents: { 1: 62 }, siglumLoci: 0,
    },
    alphabet: "greek",
    snapshotDir: "epicurus-vatican-sayings-prechange",
  },
  lives: {
    id: "lives",
    xmlPath: "build/export/Diogenes-Resources/xml/tlg/tlg0004001.xml",
    distDir: "build/dist/lives",
    distGlob: "book-*.json",
    topology: {
      bookDivType: "Book",
      columnDivType: "section",
      skipColumnPattern: /^t\d+(?:-\d+)?$/u,
      // Sections split across leaf divs merge into one citable column:
      // five sections interrupted by philosopher-heading stubs (2.125,
      // 7.160, 7.166, 8.83, 8.84) and the declared lettered_fragments
      // remap (10.120 = 120a+121b+120b, 10.121 = 121a). 1211 leaf divs
      // therefore emit 1204 columns.
      mergeRepeatedColumns: true,
      letteredN: { "120a": "120", "121b": "120", "120b": "120", "121a": "121" },
    },
    expected: {
      // wraps 1139 = 1138 + 1 cross-script join (1.67 "Her-" / "cher 637)."
      // -- a Latin editor's name wrapped inside this Greek work, 2026-08-30
      // cross-script wrap fix.
      columns: 1204, bodyLines: 13853, wraps: 1139, crossColumn: 61,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 0, siglumLoci: 0,
      indents: { 1: 1323, 2: 1538, 3: 378, 4: 230, 5: 59, 6: 14,
        7: 25, 8: 1, 9: 3, 10: 4, 11: 2, 12: 1, 13: 2, 14: 1, 16: 1 },
    },
    alphabet: "greek",
    roundTrip: "source",
  },
  "de-finibus": {
    id: "de-finibus",
    xmlPath: "build/export/Diogenes-Resources/xml/phi/phi0474048.xml",
    distDir: "build/dist/de-finibus", distGlob: "book-*.json",
    topology: { bookDivType: "book", columnDivType: "section" },
    // wraps 1529 = 1526 + 3 cross-script joins (1.15 "σκοτει-" / "νός",
    // 3.35 "πά-" / "θη", 3.52 "προηγ-" / "μένον") -- Greek terms wrapped
    // inside this Latin work, 2026-08-30 cross-script wrap fix.
    expected: { columns: 443, bodyLines: 6209, wraps: 1529, crossColumn: 68,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 0, siglumLoci: 0,
      indents: { 2: 337, 4: 28, 7: 3 } },
    alphabet: "latin", roundTrip: "source",
  },
  "de-divinatione": {
    id: "de-divinatione",
    xmlPath: "build/export/Diogenes-Resources/xml/phi/phi0474053.xml",
    distDir: "build/dist/de-divinatione", distGlob: "book-*.json",
    topology: { bookDivType: "book", columnDivType: "section" },
    expected: { columns: 282, bodyLines: 3780, wraps: 962, crossColumn: 69,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 0, siglumLoci: 0,
      indents: { 2: 89, 4: 277 } },
    alphabet: "latin", roundTrip: "source",
  },
  "de-legibus": {
    id: "de-legibus",
    xmlPath: "build/export/Diogenes-Resources/xml/phi/phi0474044.xml",
    distDir: "build/dist/de-legibus", distGlob: "book-*.json",
    topology: { bookDivType: "book", columnDivType: "section" },
    // wraps 478 = the census's 476 + the 2 R4c closing-siglum joins
    // (con<ten>-, <c>o<m>-), which the pre-R4c probe did not count.
    expected: { columns: 181, bodyLines: 2676, wraps: 478, crossColumn: 0,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 1, siglumLoci: 2,
      indents: { 2: 136, 4: 2 } },
    alphabet: "latin", roundTrip: "source",
  },
  "de-officiis": {
    id: "de-officiis",
    xmlPath: "build/export/Diogenes-Resources/xml/phi/phi0474055.xml",
    distDir: "build/dist/de-officiis", distGlob: "book-*.json",
    topology: { bookDivType: "book", columnDivType: "section" },
    // wraps 1471 = 1470 + 1 cross-script join (1.8 "κατ-" / "όρθωμα") --
    // a Greek term wrapped inside this Latin work, 2026-08-30 cross-script
    // wrap fix.
    expected: { columns: 372, bodyLines: 4595, wraps: 1471, crossColumn: 95,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 0, siglumLoci: 0,
      indents: { 2: 109, 4: 29, 7: 6 } },
    alphabet: "latin", roundTrip: "source",
  },
  "tusculan-disputations": {
    id: "tusculan-disputations",
    xmlPath: "build/export/Diogenes-Resources/xml/phi/phi0474049.xml",
    distDir: "build/dist/tusculan-disputations", distGlob: "book-*.json",
    topology: { bookDivType: "book", columnDivType: "section" },
    // wraps 1835 = 1833 + 2 cross-script joins (1.37 "νεκυο-" / "μαντεῖα",
    // 4.21 "κατηγο-" / "ρήματα") -- Greek terms wrapped inside this Latin
    // work, 2026-08-30 cross-script wrap fix.
    expected: { columns: 474, bodyLines: 6477, wraps: 1835, crossColumn: 108,
      sectionStraddling: 0, columnFinal: 0, unjoinable: 0, siglumLoci: 0,
      indents: { 2: 324, 4: 285, 5: 3, 7: 38 } },
    alphabet: "latin", roundTrip: "source",
  },
});

// The pre-change snapshot keeps these two words split. Check 5 and check 6
// repair only these declared wave-2 R4c differences before comparing.
const DECLARED_CLOSING_SIGLUM_JOINS = Object.freeze({
  "1.4": { left: "προ<ς>", right: "θέσει" },
  "3.10": { left: "πυρέ<ς>", right: "σοντα" },
});

function die(message) {
  console.error(`[ERROR] ${message}`);
  process.exit(2);
}

function readRequired(file) {
  try {
    return readFileSync(file, "utf8");
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    die(`required input file cannot be read: ${file}\n${detail}`);
  }
}

function parseJson(file) {
  const raw = readRequired(file);
  try {
    return JSON.parse(raw);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    die(`invalid JSON in required input file: ${file}\n${detail}`);
  }
}

function decodeXml(value, file) {
  return value.replace(/&(#x[0-9a-f]+|#\d+|lt|gt|amp|quot|apos);/giu, (_, entity) => {
    if (entity === "lt") return "<";
    if (entity === "gt") return ">";
    if (entity === "amp") return "&";
    if (entity === "quot") return '"';
    if (entity === "apos") return "'";
    const code = entity.toLowerCase().startsWith("#x")
      ? Number.parseInt(entity.slice(2), 16)
      : Number.parseInt(entity.slice(1), 10);
    if (!Number.isSafeInteger(code) || code < 0 || code > 0x10ffff) {
      die(`invalid XML character reference &${entity}; in ${file}`);
    }
    return String.fromCodePoint(code);
  });
}

function localName(name) {
  return name.includes(":") ? name.slice(name.lastIndexOf(":") + 1) : name;
}

function parseAttributes(source, file) {
  const attrs = {};
  const pattern = /([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/gu;
  for (const match of source.matchAll(pattern)) {
    attrs[localName(match[1])] = decodeXml(match[2] ?? match[3] ?? "", file);
  }
  return attrs;
}

function findTagEnd(xml, start, file) {
  let quote = null;
  for (let index = start + 1; index < xml.length; index += 1) {
    const char = xml[index];
    if (quote !== null) {
      if (char === quote) quote = null;
    } else if (char === '"' || char === "'") {
      quote = char;
    } else if (char === ">") {
      return index;
    }
  }
  die(`unterminated XML tag in ${file} at character ${start}`);
}

function parsePositiveInteger(value, what, file) {
  if (!/^\d+$/u.test(value ?? "") || Number(value) < 1) {
    die(`invalid ${what} ${JSON.stringify(value)} in ${file}`);
  }
  return Number(value);
}

function parseSectionNumber(value, file) {
  const match = /^(\d+)(?:,\d+)?$/u.exec(value ?? "");
  if (!match || Number(match[1]) < 1) {
    die(`invalid body section @n ${JSON.stringify(value)} in ${file}`);
  }
  return Number(match[1]);
}

function parseSourceXml(file, topology) {
  const xml = readRequired(file);
  const books = topology.bookDivType
    ? []
    : [{ number: 1, chapters: [], chapterMap: new Map() }];
  const bookMap = new Map();
  const stack = [];
  let activeLine = null;

  if (!topology.bookDivType) bookMap.set(1, books[0]);

  const matchesDivType = (actual, expected) =>
    typeof expected === "string" && actual.toLowerCase() === expected.toLowerCase();

  const nearest = (kind) => {
    for (let index = stack.length - 1; index >= 0; index -= 1) {
      if (stack[index].kind === kind) return stack[index];
    }
    return null;
  };

  const addText = (text, encoded = true) => {
    if (activeLine !== null) {
      activeLine.parts.push(encoded ? decodeXml(text, file) : text);
    }
  };

  const openElement = (rawTag) => {
    const selfClosing = /\/\s*$/u.test(rawTag);
    const content = rawTag.replace(/\/\s*$/u, "").trim();
    const nameMatch = /^([^\s]+)/u.exec(content);
    if (!nameMatch) die(`empty XML tag in ${file}`);
    const name = localName(nameMatch[1]);
    const attrs = parseAttributes(content.slice(nameMatch[0].length), file);
    const frame = { name, kind: null, attrs };

    if (name === "div") {
      const type = attrs.type ?? "";
      if (matchesDivType(type, topology.bookDivType)) {
        frame.kind = "book";
        if (attrs.n === "t") {
          frame.value = null;
          frame.title = true;
        } else {
          const number = parsePositiveInteger(attrs.n, "Book @n", file);
          if (bookMap.has(number)) die(`duplicate Book ${number} in ${file}`);
          const book = { number, chapters: [], chapterMap: new Map() };
          bookMap.set(number, book);
          books.push(book);
          frame.value = book;
          frame.title = false;
        }
      } else if (matchesDivType(type, topology.columnDivType)) {
        const bookFrame = topology.bookDivType ? nearest("book") : null;
        const book = topology.bookDivType ? bookFrame?.value : books[0];
        // A section inside a title book (<div type="book" n="t"> — the
        // PHI work-level title, dropped by stage1's _check_title_drop)
        // inherits the skip: its lines are title text, not body.
        const insideTitleBook = Boolean(bookFrame?.title);
        if (attrs.n === "t" || insideTitleBook || topology.skipColumnPattern?.test(attrs.n ?? "")) {
          frame.kind = "chapter";
          frame.value = null;
          frame.title = true;
        } else {
          if (!book) die(`${topology.columnDivType} column outside a ${topology.bookDivType} in ${file}`);
          if (!attrs.n) die(`missing ${topology.columnDivType} @n in ${file}`);
          // Lettered-fragment remap (Lives 10.120a/121b/120b/121a — the
          // manifest's declared lettered_fragments, mirrored here).
          const resolvedN = topology.letteredN?.[attrs.n] ?? attrs.n;
          const number = topology.bookDivType
            ? parsePositiveInteger(resolvedN, `${topology.columnDivType} @n`, file)
            : resolvedN;
          const column = topology.bookDivType ? `${book.number}.${number}` : resolvedN;
          if (book.chapterMap.has(column) && topology.mergeRepeatedColumns) {
            // A citable column split across leaf divs (a section
            // interrupted by a heading stub, or a lettered remap):
            // keep appending lines to the existing chapter, exactly as
            // stage1's lined_pending merge does — ordinals continue.
            frame.kind = "chapter";
            frame.value = book.chapterMap.get(column);
            frame.title = false;
            if (!selfClosing) stack.push(frame);
            return;
          }
          if (book.chapterMap.has(column)) {
            die(`duplicate ${topology.columnDivType} column ${column} in ${file}`);
          }
          const chapter = {
            book: book.number,
            number,
            column,
            sections: [],
            lines: [],
            implicitSections: topology.sectionDivType ? 0 : 1,
            nestedDivs: [],
          };
          book.chapterMap.set(column, chapter);
          book.chapters.push(chapter);
          frame.kind = "chapter";
          frame.value = chapter;
          frame.title = false;
        }
      } else if (matchesDivType(type, topology.sectionDivType)) {
        const chapterFrame = nearest("chapter");
        if (!chapterFrame) die(`${topology.sectionDivType} outside a column in ${file}`);
        const title = attrs.n === "t";
        const section = title
          ? null
          : {
              raw: attrs.n,
              number: parseSectionNumber(attrs.n, file),
              startIndex: chapterFrame.value.lines.length,
              lines: [],
            };
        if (section !== null) chapterFrame.value.sections.push(section);
        frame.kind = "section";
        frame.value = section;
        frame.title = title;
      } else {
        const chapterFrame = nearest("chapter");
        if (chapterFrame?.value && !nearest("section")) {
          chapterFrame.value.nestedDivs.push({ type, n: attrs.n ?? null });
        }
      }
    } else if (name === "l") {
      if (activeLine !== null) die(`nested <l> in ${file}`);
      const chapterFrame = nearest("chapter");
      const sectionFrame = nearest("section");
      if (!chapterFrame) die(`<l> outside a ${topology.columnDivType} column in ${file}`);
      if (topology.sectionDivType && !sectionFrame) {
        die(`<l> outside a ${topology.sectionDivType} in ${file}`);
      }
      activeLine = {
        attrs,
        parts: [],
        sectionFrame,
        chapter: chapterFrame.value,
        skip: chapterFrame.title || Boolean(sectionFrame?.title),
      };
    }

    if (!selfClosing) {
      stack.push(frame);
    } else if (name === "l") {
      closeLine(frame);
    }
  };

  const closeLine = () => {
    if (activeLine === null) die(`closing <l> without an open line in ${file}`);
    if (!activeLine.skip) {
      const section = activeLine.sectionFrame?.value ?? null;
      const chapter = activeLine.chapter;
      const text = activeLine.parts.join("").replace(/\s+/gu, " ").trim();
      if (text.length === 0) {
        activeLine = null;
        return;
      }
      const line = {
        book: chapter.book,
        chapter: chapter.number,
        sec: section?.number ?? null,
        sectionRaw: section?.raw ?? null,
        line: activeLine.attrs.n ?? String(chapter.lines.length + 1),
        ordinal: chapter.lines.length + 1,
        rend: activeLine.attrs.rend ?? null,
        text,
      };
      if (section) section.lines.push(line);
      chapter.lines.push(line);
    }
    activeLine = null;
  };

  const closeElement = (name) => {
    if (name === "l") closeLine();
    const frame = stack.pop();
    if (!frame || frame.name !== name) {
      die(`mismatched XML close tag </${name}> in ${file}; expected </${frame?.name ?? "none"}>`);
    }
  };

  let cursor = 0;
  while (cursor < xml.length) {
    if (xml[cursor] !== "<") {
      const next = xml.indexOf("<", cursor);
      const end = next === -1 ? xml.length : next;
      addText(xml.slice(cursor, end));
      cursor = end;
      continue;
    }
    if (xml.startsWith("<!--", cursor)) {
      const end = xml.indexOf("-->", cursor + 4);
      if (end === -1) die(`unterminated XML comment in ${file}`);
      cursor = end + 3;
      continue;
    }
    if (xml.startsWith("<![CDATA[", cursor)) {
      const end = xml.indexOf("]]>", cursor + 9);
      if (end === -1) die(`unterminated CDATA section in ${file}`);
      addText(xml.slice(cursor + 9, end), false);
      cursor = end + 3;
      continue;
    }
    if (xml.startsWith("<?", cursor)) {
      const end = xml.indexOf("?>", cursor + 2);
      if (end === -1) die(`unterminated XML processing instruction in ${file}`);
      cursor = end + 2;
      continue;
    }
    if (xml.startsWith("<!", cursor)) {
      const end = findTagEnd(xml, cursor, file);
      cursor = end + 1;
      continue;
    }
    const end = findTagEnd(xml, cursor, file);
    const raw = xml.slice(cursor + 1, end).trim();
    if (raw.startsWith("/")) closeElement(localName(raw.slice(1).trim()));
    else openElement(raw);
    cursor = end + 1;
  }

  if (activeLine !== null || stack.length !== 0) die(`unclosed XML element in ${file}`);
  return books;
}

function firstToken(text) {
  return text.split(/\s+/u, 1)[0] ?? "";
}

function isGreekLetter(char) {
  return greekLetter.test(char) && /^\p{Letter}$/u.test(char);
}

function isLatinLetter(char) {
  return latinLetter.test(char) && /^\p{Letter}$/u.test(char);
}

// --- Cross-script wrap letter test (2026-08-30, mirrors lined.py's
// `_is_wrap_letter`) ------------------------------------------------------
// A print-line wrap's letters do not always belong to the WORK's own
// language: an editor's citation glued into a Greek work sets the editor's
// name in Latin (Lives 1.67, "(Her-" / "cher 637)."), and a Latin work
// quotes a Greek technical term whole (de-finibus "σκοτει-" / "νός" etc.,
// 7 loci corpus-wide -- see lined.py's own cross-script comment for the
// full list). The wrap machinery's letter test is therefore a fixed
// script-UNION, never `alphabet.isLetter` alone.
function isWrapLetter(char) {
  return isGreekLetter(char) || isLatinLetter(char);
}

function isWrapLowercaseLetter(char) {
  return isWrapLetter(char) && lowerCaseLetter.test(char);
}

function alphabetPolicy(name) {
  if (name === "greek") {
    return {
      name,
      isLetter: isGreekLetter,
      isLowercaseLetter: (char) => isGreekLetter(char) && lowerCaseLetter.test(char),
      foldWrapFinal: foldHyphenFinalSigma,
      foldForDisplay: foldTrailingSigmaForDisplay,
      foldForComparison: (value) => typeof value === "string" ? value.replaceAll("ς", "σ") : value,
      // Greek glued quotes are EXCLUDED from token surfaces (the 17
      // Discourses ‘-loci), so the fragment-start walk skips them.
      gluedChars: "",
    };
  }
  if (name === "latin") {
    return {
      name,
      isLetter: isLatinLetter,
      isLowercaseLetter: (char) => isLatinLetter(char) && lowerCaseLetter.test(char),
      // Same universal sigma-fold the greek policy uses (2026-08-30
      // cross-script wrap fix, mirrors LATIN_LINED.fold_wrap_final in
      // stage1_latin.py) -- identity on ordinary Latin text (no final ς
      // to fold), so this changes no existing Latin behavior; it matters
      // only for a Greek fragment wrapped inside a Latin work.
      foldWrapFinal: foldHyphenFinalSigma,
      foldForDisplay: foldTrailingSigmaForDisplay,
      foldForComparison: (value) => typeof value === "string" ? value.replaceAll("ς", "σ") : value,
      // stage3 keeps a LEADING apostrophe in Latin token surfaces
      // ('moriatur), so the fragment start lands on it — mirroring
      // LATIN_LINED.frag_start_glued_chars in stage1_latin.py.
      gluedChars: "'’᾽ʼ",
    };
  }
  die(`unknown alphabet ${JSON.stringify(name)}`);
}

// Sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29), mirrored
// from stage1_greek.py's `_fold_hyphen_final_sigma`: Greek print sets the
// LINE-FINAL form of sigma (ς) immediately before a wrap hyphen even when it
// sits in MEDIAL position once rejoined ("προς-" / "ήκει" for προσήκει, no
// Greek word ever containing a medial ς). Every rejoin PREDICTION this
// verifier computes must apply the same fold the pipeline itself applies, or
// it would predict the wrong (buggy) surface and fail against the fixed
// pipeline output. It takes the full pre-hyphen fragment and looks back
// through trailing closing sigla; the substitution keeps the same length.
function foldHyphenFinalSigma(fragment) {
  return fragment.replace(/ς(?=[>\]]*$)/u, "σ");
}

function foldTrailingSigmaForDisplay(fragment) {
  return fragment.replace(/σ(?=[>\]]*$)/u, "ς");
}

// `alphabet` is kept as a parameter for call-site uniformity, but the
// letter test is the script-union `isWrapLetter`, not `alphabet.isLetter`
// -- a wrapped word's own script does not always match the work's nominal
// alphabet (see `isWrapLetter`'s own cross-script comment above).
function isWrapCandidateAt(text, hyphenIndex, _alphabet) {
  if (text[hyphenIndex] !== "-" || hyphenIndex < 1) return false;
  const previous = text[hyphenIndex - 1];
  if (isWrapLetter(previous)) return true;
  if (previous !== ">" && previous !== "]") return false;
  let start = hyphenIndex;
  while (
    start > 0
    && !/\s/u.test(text[start - 1])
    && text[start - 1] !== "—"
  ) {
    start -= 1;
  }
  return Array.from(text.slice(start, hyphenIndex)).some(isWrapLetter);
}

// Sigma-fold COMPARISON amendment (docs/lined-source-plan.md §3, 2026-08-29):
// check 5 (round-trip) and check 6 (token conservation) both compare the
// pipeline's current output against a PRE-CHANGE snapshot captured before
// this fix -- so the snapshot still carries the medial-ς bug at every locus
// this fix corrects. A byte-exact comparison would fail there, demanding the
// bug be reproduced to "pass." Folding every ς to σ on BOTH sides before
// comparing is sigma-SHAPE-blind, not content-blind: it changes no other
// character and preserves string length, so any other divergence between
// old and new is still caught. `sigmaFoldedComparisons` counts how many
// comparisons this actually changed the outcome of (would have failed
// without the fold) — printed in the final summary.
let sigmaFoldedComparisons = 0;
function equalWithAlphabet(check, actual, expected, locus, alphabet) {
  const foldedActual = alphabet.foldForComparison(actual);
  const foldedExpected = alphabet.foldForComparison(expected);
  if (alphabet.name === "greek" && actual !== expected && foldedActual === foldedExpected) {
    sigmaFoldedComparisons += 1;
  }
  check.equal(foldedActual, foldedExpected, locus);
}

// Paragraph-opening print-line indent (John's ruling 2026-08-29): the
// source <l>'s own @rend, when it names an indent level. Any OTHER @rend
// value is unrecognized and fails loudly, mirroring stage1_greek.py's
// _lined_chapter_lines guard.
const INDENT_RE = /^indent\((\d+)\)$/u;

function indentLevel(rend, locus) {
  if (rend === null || rend === undefined) return null;
  const match = INDENT_RE.exec(rend);
  if (!match) die(`unrecognized <l> @rend=${JSON.stringify(rend)} at ${locus}`);
  return Number(match[1]);
}

function sourceWraps(chapter, alphabet) {
  return chapter.lines.map((line, index) => {
    const terminalCandidate = isWrapCandidateAt(line.text, line.text.length - 1, alphabet);
    const next = chapter.lines[index + 1] ?? null;
    const head = next === null ? "" : firstToken(next.text);
    const first = Array.from(head)[0] ?? "";
    // Continuation-side letter test is the script-union (see
    // `isWrapLetter`'s cross-script comment above) -- a Latin continuation
    // wrapped inside a Greek work, or a Greek one inside a Latin work,
    // must still be accepted here.
    const joinable = terminalCandidate && next !== null && isWrapLowercaseLetter(first);
    // The wrap counts characters of the TOKEN's surface printed on this
    // line, and tokenization strips glued quotes but keeps editorial
    // sigla ("<ἀναισχυντία>" is one token) — so the token start is the
    // first character after the last space that is a Greek letter or an
    // opening siglum, not merely whatever follows the space (5 quote-glued
    // loci, e.g. "λέγειν ‘Συμβήσε-"; documented at plan §3 I3 as amended
    // 2026-08-29, mirrored from stage1's _apply_lined_wraps).
    // "—" is a hard token separator for both alphabets (stage3's [^\s—]+),
    // so a glued line-end like "appello—com-" wraps only "com", not the
    // whole glob (de-finibus 3.69 et al.).
    let lastTokenStart = Math.max(line.text.lastIndexOf(" "), line.text.lastIndexOf("—")) + 1;
    while (
      lastTokenStart < line.text.length - 1
      && !isWrapLetter(line.text[lastTokenStart])
      && line.text[lastTokenStart] !== "<"
      && line.text[lastTokenStart] !== "["
      && !alphabet.gluedChars.includes(line.text[lastTokenStart])
    ) {
      lastTokenStart += 1;
    }
    return {
      terminalCandidate,
      joinable,
      head,
      wrap: joinable ? line.text.length - 1 - lastTokenStart : null,
      // No `wrapO` prediction here (deliberately -- see check 3's own
      // comment below): unlike `wrap`, a SUFFIX-relative count, `wrapO`
      // is an ABSOLUTE offset that shifts whenever the PREVIOUS line
      // absorbed THIS line's own leading word, which this SOURCE
      // (pre-absorb) walk does not account for. Check 4 validates `wrapO`
      // against the ACTUAL emitted `text` self-consistently instead.
    };
  });
}

function sourceCrossColumnWraps(books, alphabet) {
  const chapters = sourceChapters(books);
  const outgoing = new Map();
  const incoming = new Map();
  for (let index = 0; index + 1 < chapters.length; index += 1) {
    const chapter = chapters[index];
    const nextChapter = chapters[index + 1];
    const line = chapter.lines.at(-1);
    const nextLine = nextChapter.lines[0];
    if (!line || !nextLine) continue;
    const candidate = isWrapCandidateAt(line.text, line.text.length - 1, alphabet);
    const head = firstToken(nextLine.text);
    const first = Array.from(head)[0] ?? "";
    // Script-union, same as `sourceWraps` above (cross-script wrap fix).
    if (!candidate || !isWrapLowercaseLetter(first)) continue;
    const key = `${chapter.column}:${chapter.lines.length}`;
    const prediction = { head, chapter, nextChapter, line };
    outgoing.set(key, prediction);
    incoming.set(nextChapter.column, prediction);
  }
  return { outgoing, incoming };
}

function isClosingSiglumCandidate(line, alphabet) {
  return /[>\]]-$/u.test(line.text)
    && isWrapCandidateAt(line.text, line.text.length - 1, alphabet);
}

function census(books, alphabet) {
  let columns = 0;
  let bodyLines = 0;
  let wraps = 0;
  let sectionStraddling = 0;
  let columnFinal = 0;
  let unjoinable = 0;
  const cross = sourceCrossColumnWraps(books, alphabet);
  for (const book of books) {
    for (const chapter of book.chapters) {
      columns += 1;
      bodyLines += chapter.lines.length;
      const predictions = sourceWraps(chapter, alphabet);
      predictions.forEach((prediction, index) => {
        if (prediction.joinable) {
          wraps += 1;
          if (chapter.lines[index].sec !== chapter.lines[index + 1].sec) {
            sectionStraddling += 1;
          }
        } else if (prediction.terminalCandidate) {
          if (
            index === chapter.lines.length - 1
            && cross.outgoing.has(`${chapter.column}:${index + 1}`)
          ) {
            // Counted separately as a declared cross-column join.
          } else if (index === chapter.lines.length - 1) columnFinal += 1;
          else unjoinable += 1;
        }
      });
    }
  }
  return {
    bodyLines, columns, wraps, crossColumn: cross.outgoing.size,
    sectionStraddling, columnFinal, unjoinable,
  };
}

function runCensus(books, expected, alphabet) {
  const actual = census(books, alphabet);
  const fields = [
    ["body lines", "bodyLines"],
    ["columns", "columns"],
    ["wraps", "wraps"],
    ["cross-column", "crossColumn"],
    ["section-straddling", "sectionStraddling"],
    ["column-final", "columnFinal"],
    ["unjoinable", "unjoinable"],
  ];
  let failed = false;
  for (const [label, key] of fields) {
    const ok = actual[key] === expected[key];
    console.log(`${ok ? "PASS" : "FAIL"} census ${label}: actual ${actual[key]}, plan ${expected[key]}`);
    failed ||= !ok;
  }
  return failed;
}

function requireObject(value, description, file) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    die(`${file}: ${description} must be an object`);
  }
}

function matchingFiles(dir, glob) {
  let names;
  try {
    names = readdirSync(dir);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    die(`required data directory cannot be read: ${dir}\n${detail}`);
  }
  const escaped = glob.replace(/[.+^${}()|[\]\\]/gu, "\\$&").replaceAll("*", ".*");
  const pattern = new RegExp(`^${escaped}$`, "u");
  const files = names.filter((name) => pattern.test(name)).sort().map((name) => path.join(dir, name));
  if (files.length === 0) die(`no files matching ${glob} in required data directory: ${dir}`);
  return files;
}

function loadLinedBooks(sourceBooks, work) {
  const byColumn = new Map();
  const leftDir = path.join(repoRoot, work.distDir);
  for (const file of matchingFiles(leftDir, work.distGlob)) {
    const data = parseJson(file);
    requireObject(data, "root", file);
    if (!Number.isInteger(data.book) || !Array.isArray(data.segments)) {
      die(`${file}: expected {book:<integer>, segments:[...]}`);
    }
    for (const segment of data.segments) {
      requireObject(segment, "segment", file);
      if (typeof segment.column !== "string" || !Array.isArray(segment.greek)) {
        die(`${file}: each segment must have string column and greek array`);
      }
      if (byColumn.has(segment.column)) die(`${file}: duplicate segment column ${segment.column}`);
      segment.greek.forEach((line, index) => {
        requireObject(line, `${segment.column} greek[${index}]`, file);
        if (!Number.isInteger(line.n) || typeof line.text !== "string" || !Array.isArray(line.tokens)) {
          die(`${file}: ${segment.column} greek[${index}] lacks required n/text/tokens fields`);
        }
        if (
          work.topology.sectionDivType
          && (!Number.isInteger(line.sec) || line.sec < 1)
        ) {
          const legacy = own(line, "sections") ? "; found legacy sections field" : "";
          die(
            `${file}: ${segment.column} greek[${index}] is not the NEW lined shape: ` +
              `required integer sec is missing or invalid${legacy}`,
          );
        }
        if (own(line, "sections")) {
          die(`${file}: ${segment.column} greek[${index}] has forbidden legacy sections field`);
        }
        if (own(line, "joined") && line.joined !== true) {
          die(`${file}: ${segment.column} greek[${index}].joined must be true when present`);
        }
        if (own(line, "wrap") && !Number.isInteger(line.wrap)) {
          die(`${file}: ${segment.column} greek[${index}].wrap must be an integer when present`);
        }
        // wrapO deviation (2026-08-29, docs/lined-source-plan.md §3): names
        // the wrapped token's own offset explicitly, since whole-
        // whitespace-token absorption can glue more than the wrapped word
        // onto a joined line (an em-dash glob), making "wrapped token =
        // last token" false. Present iff `wrap`/`joined` are.
        if (own(line, "wrap") !== own(line, "wrapO")) {
          die(`${file}: ${segment.column} greek[${index}] wrap and wrapO must be present together`);
        }
        if (own(line, "wrapO") && (!Number.isInteger(line.wrapO) || line.wrapO < 0)) {
          die(`${file}: ${segment.column} greek[${index}].wrapO must be a non-negative integer when present`);
        }
        if (own(line, "indent") && (!Number.isInteger(line.indent) || line.indent < 1 || line.indent > 20)) {
          die(`${file}: ${segment.column} greek[${index}].indent must be an integer 1..20 when present`);
        }
        line.tokens.forEach((token, tokenIndex) => {
          requireObject(token, `${segment.column} token ${tokenIndex}`, file);
          if (
            typeof token.t !== "string" ||
            (own(token, "k") && typeof token.k !== "string") ||
            !Number.isInteger(token.o)
          ) {
            die(`${file}: ${segment.column} token ${tokenIndex} lacks required t/o/k fields`);
          }
        });
      });
      byColumn.set(segment.column, { file, segment });
    }
  }

  const sourceColumns = new Set();
  for (const book of sourceBooks) {
    for (const chapter of book.chapters) {
      sourceColumns.add(chapter.column);
      if (!byColumn.has(chapter.column)) {
        die(`missing lined left-side segment for source column ${chapter.column} in ${leftDir}`);
      }
    }
  }
  for (const [column, entry] of byColumn) {
    if (!sourceColumns.has(column)) die(`${entry.file}: unexpected segment column ${column}`);
  }
  if (
    work.expected.bodyLines > work.expected.columns
    && [...byColumn.values()].every(({ segment }) => segment.greek.length === 1)
  ) {
    die(
      `${work.id}: lined data is missing or stale in ${leftDir}; ` +
        "every source column still has one flattened Greek row",
    );
  }
  return byColumn;
}

function loadSnapshots(sourceBooks, snapshotDir, distGlob) {
  const byColumn = new Map();
  for (const file of matchingFiles(snapshotDir, distGlob)) {
    const data = parseJson(file);
    requireObject(data, "snapshot root", file);
    if (!Number.isInteger(data.book) || !Array.isArray(data.segments)) {
      die(`${file}: expected old snapshot {book:<integer>, segments:[...]}`);
    }
    for (const segment of data.segments) {
      if (typeof segment?.column !== "string" || !Array.isArray(segment.greek)) {
        die(`${file}: malformed old snapshot segment`);
      }
      if (segment.greek.length !== 1) {
        die(`${file}: ${segment.column} must have exactly one pre-change Greek line`);
      }
      const line = segment.greek[0];
      if (typeof line?.text !== "string" || !Array.isArray(line.tokens)) {
        die(`${file}: ${segment.column} pre-change line lacks text/tokens`);
      }
      if (byColumn.has(segment.column)) die(`${file}: duplicate snapshot column ${segment.column}`);
      byColumn.set(segment.column, { file, line });
    }
  }
  for (const book of sourceBooks) {
    for (const chapter of book.chapters) {
      if (!byColumn.has(chapter.column)) {
        die(`missing pre-change snapshot segment for ${chapter.column} in ${snapshotDir}`);
      }
    }
  }
  return byColumn;
}

function shown(value) {
  const json = JSON.stringify(value);
  return json === undefined ? String(value) : json;
}

class Check {
  constructor(number, name) {
    this.number = number;
    this.name = name;
    this.passed = 0;
    this.failed = 0;
    this.failures = [];
  }

  equal(actual, expected, locus) {
    if (actual === expected) {
      this.passed += 1;
      return;
    }
    this.failed += 1;
    if (this.failures.length < FAILURE_LIMIT) {
      this.failures.push(`${locus} expected=${shown(expected)} actual=${shown(actual)}`);
    }
  }

  truth(actual, expected, locus) {
    this.equal(Boolean(actual), Boolean(expected), locus);
  }
}

function sourceChapters(books) {
  return books.flatMap((book) => book.chapters);
}

function lineLocus(line) {
  return line.sec === null
    ? `${line.book}.${line.chapter}.${line.line}`
    : `${line.book}.${line.chapter}.${line.sec}.${line.line}`;
}

function chapterLocus(chapter) {
  const first = chapter.lines[0];
  return first ? lineLocus(first) : `${chapter.book}.${chapter.number}.0.0`;
}

function orderedRuns(values) {
  const result = [];
  for (const value of values) {
    if (result.length === 0 || result.at(-1) !== value) result.push(value);
  }
  return result;
}

function expectedLineText(chapter, predictions, index, cross, alphabet) {
  // `consumed` is `head` from `sourceWraps`, itself `firstToken(next.text)`
  // -- the WHOLE whitespace-delimited word (an em-dash glob like
  // "σθαι—πολλὴν" included, since there is no internal space to split it
  // on). Removing exactly `consumed.length` characters here already matches
  // the pipeline's own whole-whitespace-token absorption (`_apply_lined_
  // wraps`' `head, _, rest = nxt["text"].partition(" ")`) -- no wrapO-
  // specific change needed on this side of the check; stated here so the
  // 2026-08-29 wrapO deviation (docs/lined-source-plan.md §3) doesn't get
  // mistaken for a hole in this check.
  let text = chapter.lines[index].text;
  const incoming = index === 0 ? cross.incoming.get(chapter.column) : null;
  if ((index > 0 && predictions[index - 1].joinable) || incoming) {
    const consumed = incoming?.head ?? predictions[index - 1].head;
    text = text.slice(consumed.length);
    if (text.startsWith(" ")) text = text.slice(1);
  }
  const outgoing = cross.outgoing.get(`${chapter.column}:${index + 1}`);
  if (predictions[index].joinable || outgoing) {
    // Mirrors `_apply_lined_wraps`' fragment fold, including closing sigla.
    const fragment = text.slice(0, -1);
    const folded = alphabet.foldWrapFinal(fragment);
    text = folded + (outgoing?.head ?? predictions[index].head);
  }
  return text;
}

function rejoinWrappedHyphens(text, alphabet) {
  let output = "";
  let index = 0;
  while (index < text.length) {
    if (isWrapCandidateAt(text, index, alphabet)) {
      let next = index + 1;
      while (next < text.length && text[next] === " ") next += 1;
      if (
        next > index + 1 &&
        next < text.length &&
        alphabet.isLowercaseLetter(text[next])
      ) {
        // Mirrors `_rejoin_wrapped_hyphens_mapped`'s fragment fold.
        if (output.length > 0) {
          output = alphabet.foldWrapFinal(output);
        }
        index = next;
        continue;
      }
    }
    output += text[index];
    index += 1;
  }
  return output;
}

const TOKEN_PUNCT = new Set(Array.from(".,·;—()|\"‘«»„“-:?!·;"));
const TOKEN_SIGLA = new Set(Array.from("†*<>()[]⎪⟦⟧⌜⌞⌝⌟⸏⸓Ͻ⌊⌋→←"));
const TOKEN_APOSTROPHES = new Set(Array.from("'’᾽ʼ"));

function sourceSurfaceTokens(text, alphabet) {
  const result = [];
  for (const match of text.matchAll(/[^\s—]+/gu)) {
    const raw = match[0];
    let start = 0;
    let end = raw.length;
    while (start < end && TOKEN_PUNCT.has(raw[start])) start += 1;
    while (end > start && TOKEN_PUNCT.has(raw[end - 1])) end -= 1;
    while (end > start && TOKEN_APOSTROPHES.has(raw[end - 1])) {
      let previous = end - 2;
      while (previous >= start && TOKEN_SIGLA.has(raw[previous])) previous -= 1;
      // stage3's peel is GREEK-letter-gated for BOTH languages
      // (_preceded_by_greek_letter): an apostrophe after a Greek letter is
      // elision (kept); after a Latin letter it closes a quotation and is
      // peeled (scriptorem' -> scriptorem), exactly as _surface does.
      if (previous >= start && isGreekLetter(raw[previous])) break;
      end -= 1;
      while (end > start && TOKEN_PUNCT.has(raw[end - 1])) end -= 1;
    }
    if (end > start) {
      const surface = raw.slice(start, end);
      // stage3's drop rule: a token whose fully-CLEANED form (all
      // punctuation, sigla, and apostrophes removed throughout) is empty
      // never reaches the emitted token list — standalone lacuna marks
      // "<...>", lone obeli "†", and unpaired brackets "[" (first
      // attested standalone in Lives, wave 2) clean to nothing and are
      // dropped by `if not token: continue` in stage3_tokenize.
      const cleaned = Array.from(surface).filter(
        (ch) => !TOKEN_PUNCT.has(ch) && !TOKEN_SIGLA.has(ch) && !TOKEN_APOSTROPHES.has(ch),
      );
      if (cleaned.length > 0) result.push(surface);
    }
  }
  return result;
}

function runChecks(books, lined, snapshots, work) {
  const { expected, topology } = work;
  const alphabet = alphabetPolicy(work.alphabet);
  const cross = sourceCrossColumnWraps(books, alphabet);
  const checks = [
    new Check(1, "Line count"),
    new Check(2, "Section boundaries"),
    new Check(3, "Line text modulo rejoin"),
    new Check(4, "Hyphen positions"),
    new Check(5, "Round-trip to pre-change text"),
    new Check(6, "Token conservation"),
    new Check(7, "Indent levels"),
  ];
  const chapters = sourceChapters(books);
  const allPredictedJoined = new Map();
  const allActualJoined = new Map();
  const allActualCrossColumn = new Map();
  let actualGlobalLines = 0;
  const indentCounts = {
    predicted: {},
    actual: {},
  };

  checks[0].equal(chapters.length, expected.columns, "0.0.0.0");
  checks[0].equal(
    chapters.reduce((count, chapter) => count + chapter.lines.length, 0),
    expected.bodyLines,
    "0.0.0.0",
  );

  for (const chapter of chapters) {
    const ours = lined.get(chapter.column).segment.greek;
    const predictions = sourceWraps(chapter, alphabet);
    actualGlobalLines += ours.length;

    checks[0].equal(ours.length, chapter.lines.length, chapterLocus(chapter));
    if (topology.sectionDivType) {
      for (const section of chapter.sections) {
        const actualCount = ours.filter((line) => line.sec === section.number).length;
        const locus = section.lines[0] ? lineLocus(section.lines[0]) : `${chapter.column}.${section.number}.0`;
        checks[0].equal(actualCount, section.lines.length, locus);
      }
    }
    ours.forEach((line, index) => {
      const source = chapter.lines[index];
      const locus = source ? lineLocus(source) : `${chapter.column}.${line.sec}.0`;
      checks[0].equal(line.n, index + 1, locus);
    });

    if (topology.sectionDivType) {
      const expectedSections = chapter.sections.map((section) => section.number);
      const actualSections = orderedRuns(ours.map((line) => line.sec));
      checks[1].equal(shown(actualSections), shown(expectedSections), chapterLocus(chapter));
      for (const section of chapter.sections) {
        const actualIndex = ours.findIndex((line) => line.sec === section.number);
        const locus = section.lines[0] ? lineLocus(section.lines[0]) : `${chapter.column}.${section.number}.0`;
        checks[1].equal(actualIndex, section.startIndex, locus);
      }
    } else {
      checks[1].equal(chapter.implicitSections, 1, chapterLocus(chapter));
      checks[1].equal(chapter.nestedDivs.length, 0, chapterLocus(chapter));
      ours.forEach((line, index) => {
        const source = chapter.lines[index];
        const locus = source ? lineLocus(source) : `${chapter.column}.0`;
        checks[1].equal(own(line, "sec"), false, locus);
      });
    }

    const maximum = Math.max(ours.length, chapter.lines.length);
    for (let index = 0; index < maximum; index += 1) {
      const source = chapter.lines[index];
      const line = ours[index];
      const locus = source ? lineLocus(source) : `${chapter.column}.${line?.sec ?? 0}.0`;
      const expectedText = source
        ? expectedLineText(chapter, predictions, index, cross, alphabet)
        : "<no source line>";
      checks[2].equal(line?.text ?? "<missing emitted line>", expectedText, locus);
      if (source && predictions[index].joinable) {
        checks[2].equal(line?.joined, true, locus);
        checks[2].equal(line?.wrap, predictions[index].wrap, locus);
        // No `wrapO` prediction check here (deliberately): `wrap` is a
        // SUFFIX-relative character count, invariant under the previous
        // line's own head-trim (see `expectedLineText`'s `consumed` slice
        // above), but `wrapO` is an ABSOLUTE offset from the start of the
        // text -- it shifts whenever the PREVIOUS line absorbed this
        // line's own leading word, which `sourceWraps`' independent walk
        // (computed against the untrimmed SOURCE text) does not account
        // for. Check 4 below validates `wrapO` against the ACTUAL emitted
        // `text` self-consistently instead, which is the correct and
        // sufficient check (docs/lined-source-plan.md §3's 2026-08-29
        // wrapO deviation note).
      }
      const crossPrediction = cross.outgoing.get(`${chapter.column}:${index + 1}`);
      if (source && crossPrediction) {
        checks[2].equal(line?.joined, true, locus);
        checks[2].equal(own(line ?? {}, "wrap"), false, locus);
        checks[2].equal(own(line ?? {}, "wrapO"), false, locus);
      }
    }

    predictions.forEach((prediction, index) => {
      if (prediction.joinable) {
        const source = chapter.lines[index];
        allPredictedJoined.set(`${chapter.column}:${index + 1}`, source);
      }
    });
    ours.forEach((line, index) => {
      const source = chapter.lines[index];
      const locus = source ? lineLocus(source) : `${chapter.column}.${line.sec}.0`;
      const hasJoined = own(line, "joined");
      const hasWrap = own(line, "wrap");
      const hasWrapO = own(line, "wrapO");
      checks[3].equal(hasWrap, hasWrapO, locus);
      checks[3].truth(!hasWrap || hasJoined, true, locus);
      if (hasJoined && !hasWrap) {
        checks[3].equal(index, ours.length - 1, locus);
        allActualCrossColumn.set(`${chapter.column}:${line.n}`, { chapter, index, line, source });
      }
      if (hasJoined) {
        checks[3].equal(line.joined, true, locus);
        if (!hasWrap) {
          // Cross-column join (R2a): `joined` alone, print split NOT
          // repainted — there is no wrap metadata to reconstruct from,
          // by design. The crossPrediction branch above already validated
          // this shape; the repaint comparison below is for in-column
          // (repainted) wraps only.
          return;
        }
        allActualJoined.set(`${chapter.column}:${line.n}`, { chapter, index, line, source });
        // wrapO deviation (2026-08-29, docs/lined-source-plan.md §3):
        // repaint by slicing THIS line's own `text` at `wrapO + wrap`
        // instead of locating "the last token" — whole-whitespace-token
        // absorption can glue more than the wrapped word onto a joined line
        // (an em-dash glob with no space before the next word), so the
        // wrapped token is not always last. `wrapO` is the offset where the
        // wrapped word starts in `text`, so `text.slice(0, wrapO + wrap)`
        // reproduces exactly what Schenkl printed on THIS line before the
        // hyphen.
        //
        // Repaint amendment (plan §5 check 4 deviation, 2026-08-29): a line
        // can BOTH receive the previous line's carried block AND end in a
        // wrap of its own (1.1 §1 l.2), so the full repaint prepends the
        // PREVIOUS emitted line's carried term before slicing this line's
        // own trailing wrap. That carried term is `text.slice(wrapO + wrap)`
        // on the PREVIOUS line — the wrapped word's own remainder plus
        // EVERYTHING printed after it (an absorbed punctuation tail like
        // "κιμαστικήν.", or in the em-dash glob case the glued "—" and the
        // whole following word "πολλὴν") — plus a space-normalized boundary.
        const prev = ours[index - 1];
        let carried = "";
        if (prev && own(prev, "wrap") && own(prev, "wrapO") && Number.isInteger(prev.wrap) && Number.isInteger(prev.wrapO)) {
          carried = prev.text.slice(prev.wrapO + prev.wrap) + " ";
        } else if (index === 0 && cross.incoming.has(chapter.column)) {
          // This segment's first line RECEIVED a cross-column join (R2a):
          // stage1 stripped the previous column's word-tail (the source
          // line's own first token) off this line's head. The source print
          // line still shows it, so the repaint puts it back.
          carried = `${cross.incoming.get(chapter.column).head} `;
        }
        // Sigma-fold correction (docs/lined-source-plan.md §3, 2026-08-29),
        // mirroring speakers.ts' `splitWrapLine`: the stored `text` carries
        // the correct medial σ (stage1 already folded ς->σ on rejoin), but
        // Schenkl's page prints the line-final ς before the hyphen -- repaint
        // for comparison against the raw source must undo the fold for
        // display, same as the reader does.
        const headSlice = Number.isInteger(line.wrapO) && Number.isInteger(line.wrap)
          ? line.text.slice(0, line.wrapO + line.wrap)
          : null;
        const foldedHead = headSlice === null
          ? null
          : alphabet.foldForDisplay(headSlice);
        const repainted =
          foldedHead !== null
            ? carried + foldedHead + "-"
            : "<cannot repaint: missing wrapO or wrap>";
        checks[3].equal(repainted, source?.text ?? "<no source line>", locus);
      }
    });

    // Check 7 (John's ruling 2026-08-29): the set of (chapter, line-ordinal,
    // level) triples carrying `indent` in our data equals the set of body
    // <l rend="indent(N)"> in the source -- compared per line (set equality
    // by construction: any mismatch, in either direction, fails at that
    // line's own locus) plus a global per-level total against expected.
    ours.forEach((line, index) => {
      const source = chapter.lines[index];
      const locus = source ? lineLocus(source) : `${chapter.column}.${line.sec}.0`;
      const predictedLevel = source ? indentLevel(source.rend, locus) : null;
      const actualLevel = own(line, "indent") ? line.indent : null;
      checks[6].equal(actualLevel, predictedLevel, locus);
      if (predictedLevel !== null) {
        indentCounts.predicted[predictedLevel] = (indentCounts.predicted[predictedLevel] ?? 0) + 1;
      }
      if (actualLevel !== null) {
        indentCounts.actual[actualLevel] = (indentCounts.actual[actualLevel] ?? 0) + 1;
      }
    });

    // I4 round-trip (mirrors pipeline/tests/test_stage1_lined_source.py's
    // own real_spine check): a fully-absorbed line's `text` is `""` -- its
    // ENTIRE physical print line was the previous line's carried word, so
    // it contributes no separating space of its own. Joining it in still
    // (18 such lines in the real corpus, docs/lined-source-plan.md §3)
    // would insert a stray double space the rejoin step can't collapse
    // (there is no hyphen there to trigger it), so empty-text lines are
    // skipped from the join entirely, same as the pipeline's own test.
    const newText = rejoinWrappedHyphens(
      ours
        .map((line) => line.text)
        .filter((text) => text.length > 0)
        .join(" "),
      alphabet,
    );
    if (snapshots !== null) {
      const oldLine = snapshots.get(chapter.column).line;
      const declaredJoin = work.id === "discourses"
        ? DECLARED_CLOSING_SIGLUM_JOINS[chapter.column]
        : undefined;
      const expectedOldText = declaredJoin
        ? rejoinWrappedHyphens(oldLine.text, alphabet)
        : oldLine.text;
      equalWithAlphabet(checks[4], newText, expectedOldText, chapterLocus(chapter), alphabet);

      // Token conservation compares surface `t` too (Beta Code `k` already
      // normalizes both sigmas to 's', so it needs no fold) -- same
      // pre-change-snapshot fold amendment as check 5. Folding the shown
      // (stringified) form is equivalent to folding each token's `t` and
      // simpler: the fold is a plain character substitution that never
      // touches JSON structure or the `k` field's content.
      const newTokens = ours.flatMap((line) => line.tokens).map(({ t, k }) => ({ t, k }));
      const oldTokens = oldLine.tokens.map(({ t, k }) => ({ t, k }));
      if (declaredJoin) {
        const leftIndex = oldTokens.findIndex(
          (token, index) => token.t === declaredJoin.left && oldTokens[index + 1]?.t === declaredJoin.right,
        );
        if (leftIndex < 0) {
          die(`${chapter.column}: declared closing-siglum snapshot token pair is absent`);
        }
        const left = oldTokens[leftIndex];
        const right = oldTokens[leftIndex + 1];
        oldTokens.splice(leftIndex, 2, {
          t: alphabet.foldWrapFinal(left.t) + right.t,
          k: left.k + right.k,
        });
      }
      equalWithAlphabet(
        checks[5], shown(newTokens), shown(oldTokens), chapterLocus(chapter), alphabet,
      );
    } else if (work.roundTrip === "source") {
      const sourceText = rejoinWrappedHyphens(
        chapter.lines
          .map((_line, index) => expectedLineText(chapter, predictions, index, cross, alphabet))
          .filter((text) => text.length > 0)
          .join(" "),
        alphabet,
      );
      equalWithAlphabet(checks[4], newText, sourceText, chapterLocus(chapter), alphabet);
      checks[5].equal(
        shown(ours.flatMap((line) => line.tokens).map((token) => token.t)),
        shown(sourceSurfaceTokens(sourceText, alphabet)),
        chapterLocus(chapter),
      );
      for (const [lineIndex, line] of ours.entries()) {
        for (const [tokenIndex, token] of line.tokens.entries()) {
          checks[5].equal(
            line.text.slice(token.o, token.o + token.t.length),
            token.t,
            `${chapter.column}:${lineIndex + 1}:token-${tokenIndex + 1}`,
          );
        }
      }
    }
  }

  checks[0].equal(actualGlobalLines, expected.bodyLines, "0.0.0.0");

  checks[3].truth(expected.wraps > 0, true, "Rule 0 expected.wraps");
  checks[3].equal(allPredictedJoined.size, expected.wraps, "0.0.0.0");
  checks[3].equal(allActualJoined.size, expected.wraps, "0.0.0.0");
  const sourceCensus = census(books, alphabet);
  checks[3].equal(sourceCensus.sectionStraddling, expected.sectionStraddling, "0.0.0.0");
  checks[3].equal(sourceCensus.columnFinal, expected.columnFinal, "0.0.0.0");
  checks[3].equal(sourceCensus.unjoinable, expected.unjoinable, "0.0.0.0");
  checks[3].equal(cross.outgoing.size, expected.crossColumn, "cross-column source set size");
  checks[3].equal(allActualCrossColumn.size, expected.crossColumn, "cross-column emitted set size");
  for (const [key, prediction] of cross.outgoing) {
    checks[3].truth(allActualCrossColumn.has(key), true, lineLocus(prediction.line));
  }
  for (const [key, value] of allActualCrossColumn) {
    checks[3].truth(cross.outgoing.has(key), true, value.source ? lineLocus(value.source) : key);
  }

  const siglumLoci = chapters
    .flatMap((chapter) => chapter.lines)
    .filter((line) => isClosingSiglumCandidate(line, alphabet)).length;
  checks[3].equal(siglumLoci, expected.siglumLoci, "R4c closing-siglum locus count");

  const normalizedHistogram = (histogram) => Object.fromEntries(
    Object.entries(histogram)
      .filter(([, count]) => count !== 0)
      .sort(([left], [right]) => Number(left) - Number(right)),
  );
  checks[6].equal(
    shown(normalizedHistogram(indentCounts.predicted)),
    shown(normalizedHistogram(expected.indents)),
    "source indent histogram",
  );
  checks[6].equal(
    shown(normalizedHistogram(indentCounts.actual)),
    shown(normalizedHistogram(expected.indents)),
    "emitted indent histogram",
  );
  for (const [key, source] of allPredictedJoined) {
    checks[3].truth(allActualJoined.has(key), true, lineLocus(source));
  }
  for (const [key, value] of allActualJoined) {
    checks[3].truth(allPredictedJoined.has(key), true, value.source ? lineLocus(value.source) : `${key}.0.0`);
  }

  const unjoinableCases = work.id === "discourses"
    ? [
        { book: 1, chapter: 2, sec: 3, line: "1", ending: "ἀπάγξα-" },
        { book: 2, chapter: 5, sec: 17, line: "1", ending: "βάλ-" },
      ]
    : [];
  for (const expected of unjoinableCases) {
    const chapter = chapters.find(
      (item) => item.book === expected.book && item.number === expected.chapter,
    );
    const source = chapter?.lines.find(
      (line) => line.sec === expected.sec && line.line === expected.line,
    );
    const locus = `${expected.book}.${expected.chapter}.${expected.sec}.${expected.line}`;
    checks[3].truth(source !== undefined, true, locus);
    checks[3].truth(source?.text.endsWith(expected.ending), true, locus);
    const line = source ? lined.get(chapter.column).segment.greek[source.ordinal - 1] : undefined;
    checks[3].equal(own(line ?? {}, "joined"), false, locus);
    checks[3].truth(line?.text.endsWith("-"), true, locus);
  }

  return checks;
}

function printResults(checks) {
  let failed = false;
  for (const check of checks) {
    const status = check.failed === 0 ? "PASS" : "FAIL";
    console.log(`${status} check ${check.number} ${check.name}: ${check.passed} passed, ${check.failed} failed`);
    for (const failure of check.failures) console.log(`  ${failure}`);
    if (check.failed > check.failures.length) {
      console.log(`  ... ${check.failed - check.failures.length} more failures suppressed (cap ${FAILURE_LIMIT})`);
    }
    failed ||= check.failed !== 0;
  }
  return failed;
}

function parseArgs(argv) {
  const workIds = [];
  let snapshotRoot = process.env.LINED_SNAPSHOT_DIR || DEFAULT_SNAPSHOT_ROOT;
  let noSnapshot = false;
  let censusOnly = false;

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--no-snapshot") {
      noSnapshot = true;
    } else if (arg === "--census") {
      censusOnly = true;
    } else if (arg === "--snapshot") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) die("--snapshot requires a root directory");
      snapshotRoot = value;
      index += 1;
    } else if (arg.startsWith("--snapshot=")) {
      snapshotRoot = arg.slice("--snapshot=".length);
      if (!snapshotRoot) die("--snapshot requires a root directory");
    } else if (arg.startsWith("--")) {
      die(`unknown option ${arg}`);
    } else {
      workIds.push(arg);
    }
  }

  const selected = workIds.length === 0 ? Object.keys(WORKS) : [...new Set(workIds)];
  for (const id of selected) {
    if (!own(WORKS, id)) {
      die(`unknown work ${JSON.stringify(id)}; choose one of: ${Object.keys(WORKS).join(", ")}`);
    }
  }
  return { selected, snapshotRoot: path.resolve(snapshotRoot), noSnapshot, censusOnly };
}

const options = parseArgs(process.argv.slice(2));
let failed = false;
for (const id of options.selected) {
  const work = WORKS[id];
  console.log(`== ${id} ==`);
  if (!(work.expected.wraps > 0)) {
    die(`${id}: Rule 0 requires expected.wraps > 0 for every lined work`);
  }
  const books = parseSourceXml(path.join(repoRoot, work.xmlPath), work.topology);
  const alphabet = alphabetPolicy(work.alphabet);
  if (options.censusOnly) {
    failed = runCensus(books, work.expected, alphabet) || failed;
    continue;
  }
  const lined = loadLinedBooks(books, work);
  const snapshots = options.noSnapshot || work.roundTrip === "source"
    ? null
    : loadSnapshots(books, path.join(options.snapshotRoot, work.snapshotDir), work.distGlob);
  failed = printResults(runChecks(books, lined, snapshots, work)) || failed;
}
if (sigmaFoldedComparisons > 0) {
  console.log(
    `sigma-fold amendment (docs/lined-source-plan.md §3, 2026-08-29): ` +
      `${sigmaFoldedComparisons} pre-change-snapshot comparison(s) needed the ` +
      `ς/σ fold to pass (the snapshot still carries the medial-ς bug this fix corrects)`,
  );
}
process.exitCode = failed ? 1 : 0;
