// @vitest-environment node
// No build setting lives in wrangler.jsonc's vars.
//
// @astrojs/cloudflare reads the Wrangler config when the build starts and
// copies every var into process.env (utils/wrangler-config.js,
// loadWranglerEnv), overwriting what the build command set. A
// PUBLIC_DATA_ROOT there is baked into data.js and search.js, while
// postbuild-sw.mjs, a separate process, still sees the command's value; a
// PUBLIC_SITE_ORIGIN there turns on canonical URLs in a staging build. Both
// belong on the build command (docs/cloudflare-setup.md §3). Found
// 2026-09-16: the placeholder https://data.lyceum.institute/releases/<version>
// was in every build's bundles.
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { unstable_readConfig } from 'wrangler';
import { describe, expect, it } from 'vitest';

const CONFIG = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'wrangler.jsonc');

// Since 2026-09-21 the wrangler login sees two accounts: John's, and Brian's
// (Lyceum Institute), which holds a Worker named `lyceum-library` -- the
// top-level name here. Every environment therefore pins its own account and
// its own Worker name, and the top level pins no account, so a bare
// `wrangler deploy` stops and asks which account rather than landing on
// Brian's Worker.
const ACCOUNTS = {
  demo: '6ff75c6d6c06d1092df2c7efd42077ba', // John
  staging: '570b13129baea40d581ac89859a9c8aa', // Lyceum Institute (Brian)
} as const;

describe('wrangler.jsonc', () => {
  it('pins no account at the top level', () => {
    const config = unstable_readConfig({ config: CONFIG }, { hideWarnings: true });
    expect(config.account_id).toBeUndefined();
  });

  for (const [env, account] of Object.entries(ACCOUNTS)) {
    it(`pins its account and its own Worker name (${env})`, () => {
      const config = unstable_readConfig({ config: CONFIG, env }, { hideWarnings: true });
      expect(config.account_id).toBe(account);
      expect(config.name).not.toBe('lyceum-library');
    });
  }

  it('keeps the test copy off the live catalog store', () => {
    const config = unstable_readConfig({ config: CONFIG, env: 'staging' }, { hideWarnings: true });
    const ids = config.kv_namespaces.map((ns: { id?: string }) => ns.id);
    expect(ids).toEqual(['d3944cf97d744c12a904ab7db1558cea']);
    expect(ids).not.toContain('7f6985e4d5c34c7f8e938e421327bbb7'); // lyceum-library-catalog, live
  });

  for (const env of [undefined, 'demo', 'staging']) {
    it(`sets no PUBLIC_ var (${env ?? 'top level'})`, () => {
      const config = unstable_readConfig({ config: CONFIG, env }, { hideWarnings: true });
      expect(Object.keys(config.vars).filter((k) => k.startsWith('PUBLIC_'))).toEqual([]);
    });
  }

  it('binds the CORPUS r2 bucket for staging only', () => {
    const staging = unstable_readConfig({ config: CONFIG, env: 'staging' }, { hideWarnings: true });
    expect(staging.r2_buckets).toEqual([{ binding: 'CORPUS', bucket_name: 'lyceum-library-data' }]);

    for (const env of [undefined, 'demo']) {
      const config = unstable_readConfig({ config: CONFIG, env }, { hideWarnings: true });
      expect(config.r2_buckets).toEqual([]);
    }
  });
});
