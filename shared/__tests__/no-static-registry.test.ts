import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const staticWorkRegistry = /export\s+const\s+WORKS\s*:\s*Work\s*\[\s*\]\s*=\s*\[\s*\{/s;
const staticAuthorRegistry = /export\s+const\s+AUTHORS\s*:\s*Author\s*\[\s*\]\s*=\s*\[\s*\{/s;

describe('registry source files', () => {
  it('contain composition code rather than static array-literal registries', () => {
    const worksSource = readFileSync(join(process.cwd(), 'lib', 'works.ts'), 'utf8');
    const authorsSource = readFileSync(join(process.cwd(), 'lib', 'authors.ts'), 'utf8');

    expect(worksSource).not.toMatch(staticWorkRegistry);
    expect(authorsSource).not.toMatch(staticAuthorRegistry);
  });
});
