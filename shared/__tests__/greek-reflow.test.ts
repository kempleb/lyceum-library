import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// The Both-view Greek reflow dissolves a turn's source lines into continuous
// prose. That is only safe where the line is NOT the citation unit, and this
// sheet is shared machinery (plato-reader, aristotle-reader and this repo all
// carry it). This repo is MIXED: de-rerum-natura is verse-line and four DK
// collections set `lines: true`, so an unscoped rule would dissolve a real
// citation. These tests pin the scope in the stylesheet itself.
const HERE = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(HERE, '../styles/global.css'), 'utf8');
const code = css.replace(/\/\*[\s\S]*?\*\//g, ''); // strip comments

describe('Both-view Greek reflow', () => {
  it('is scoped to lineless works, so a line-cited work cannot inherit it', () => {
    expect(code).toContain(
      '.reader-body.stephanus.view-both .turn-flow .greek-col .greek-line { display: inline;',
    );
    expect(code).toContain(
      '.reader-body.stephanus.view-both .turn-flow .greek-col .greek-line::after { content: " "; }',
    );
  });

  it('carries no unscoped copy of the rule', () => {
    // An unscoped selector would out-reach the guard above.
    expect(code).not.toMatch(
      /(?<!\.stephanus)\.view-both \.turn-flow \.greek-col \.greek-line\s*\{\s*display:\s*inline/,
    );
  });

  it('positions the Greek column, so the section ticks keep a containing block', () => {
    expect(code).toContain('.reader-body.view-both .turn-flow .greek-col { position: relative; }');
  });
});
