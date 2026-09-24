import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { assertSafeRelativePath, buildFetchCommand, DEFAULT_BUCKET, downloadFileWithRetry, fetchReleaseFromUrl } from '../fetch-release.mjs';
import { buildReleaseIndex } from '../release-index.mjs';
import { verifyRelease } from '../verify-release.mjs';

test('builds an rclone copy command against the default bucket', () => {
  const { command, args, bucket, destDir } = buildFetchCommand('2026.09.13-abc1234', 'build/dist');
  assert.equal(command, 'rclone');
  assert.deepEqual(args, ['copy', `r2:${DEFAULT_BUCKET}/releases/2026.09.13-abc1234`, 'build/dist', '--checksum']);
  assert.equal(bucket, DEFAULT_BUCKET);
  assert.equal(destDir, 'build/dist');
});

test('defaults dest to build/dist when omitted', () => {
  const { destDir } = buildFetchCommand('v1', undefined);
  assert.equal(destDir, join('build', 'dist'));
});

test('an explicit bucket option overrides the default', () => {
  const { args, bucket } = buildFetchCommand('v1', 'out', { bucket: 'other-bucket' });
  assert.equal(bucket, 'other-bucket');
  assert.equal(args[1], 'r2:other-bucket/releases/v1');
});

test('throws without a version', () => {
  assert.throws(() => buildFetchCommand(undefined, 'out'), /version is required/);
});

// --from-url: fetches a release over plain HTTPS GETs from a static file
// server, in place of rclone. Exercised here against a local node:http
// server serving a tiny synthetic release (2-3 files + RELEASE.json).

async function withTmpDir(fn) {
  const dir = mkdtempSync(join(tmpdir(), 'fetch-release-test-'));
  try {
    return await fn(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const VERSION = '2026.09.22-testfixt';

// A tiny release: one work manifest plus two data files.
function writeSyntheticRelease(dir) {
  mkdirSync(join(dir, 'work1'), { recursive: true });
  writeFileSync(join(dir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: 'test-1' }), 'utf8');
  writeFileSync(join(dir, 'work1', 'text.json'), JSON.stringify({ hello: 'world' }), 'utf8');
  writeFileSync(join(dir, 'work1', 'more.json'), JSON.stringify({ another: 'file' }), 'utf8');
}

function writeIndex(dir) {
  const index = buildReleaseIndex(dir);
  writeFileSync(join(dir, 'RELEASE.json'), JSON.stringify(index, null, 2), 'utf8');
  return index;
}

// Serves <servedDir>/<version>/<relpath> verbatim, 404ing anything not on
// disk. Requests for a version other than the fixed VERSION are also 404s.
// `requests` collects every request URL seen, in order -- used to prove the
// download queue stopped early after a fatal failure.
function startReleaseServer(servedDir) {
  const requests = [];
  return new Promise((resolveServer) => {
    const server = createServer((req, res) => {
      requests.push(req.url);
      const prefix = `/${VERSION}/`;
      if (!req.url.startsWith(prefix)) {
        res.writeHead(404).end('not found');
        return;
      }
      const rel = decodeURIComponent(req.url.slice(prefix.length));
      const abs = join(servedDir, rel);
      let body;
      try {
        body = readFileSync(abs);
      } catch {
        res.writeHead(404).end('not found');
        return;
      }
      res.writeHead(200, { 'content-type': 'application/octet-stream' }).end(body);
    });
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolveServer({ server, baseUrl: `http://127.0.0.1:${port}`, requests });
    });
  });
}

function stopServer(server) {
  return new Promise((res) => server.close(() => res()));
}

test('--from-url: good fetch lands every file and passes verify', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    const index = writeIndex(sourceDir);
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        const result = await fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl });
        assert.equal(result.ok, true);
        assert.equal(result.fileCount, index.files.length);
        const verify = verifyRelease(destDir);
        assert.equal(verify.ok, true, verify.problems.join('; '));
      });
    } finally {
      await stopServer(server);
    }
  });
});

test('--from-url: a file whose bytes do not match its sha256 is refused', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    // Corrupt the file on disk *after* indexing, so the server hands out
    // bytes that no longer match the sha256 RELEASE.json already recorded --
    // simulating corruption in transit.
    writeFileSync(join(sourceDir, 'work1', 'text.json'), JSON.stringify({ hello: 'WORLD' }), 'utf8');
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /sha256 mismatch|failed verification/,
        );
      });
    } finally {
      await stopServer(server);
    }
  });
});

test('--from-url: a listed file that 404s is refused', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    // Remove the file from disk after indexing, so the server 404s a path
    // RELEASE.json still lists.
    rmSync(join(sourceDir, 'work1', 'more.json'));
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /404|more\.json/,
        );
      });
    } finally {
      await stopServer(server);
    }
  });
});

// --- Sol blocker: unsafe RELEASE.json paths must never reach the filesystem ---

test('assertSafeRelativePath: rejects traversal, absolute, backslash, empty-segment, dot-segment, and NUL paths', () => {
  const bad = ['../escaped.json', '/etc/passwd', 'a\\b.json', 'a//b.json', 'a/./b.json', 'a/../b.json', '', 'a/\0b.json'];
  for (const p of bad) {
    assert.throws(() => assertSafeRelativePath(p), undefined, `expected ${JSON.stringify(p)} to be rejected`);
  }
  // Sanity: ordinary safe paths are accepted.
  assert.doesNotThrow(() => assertSafeRelativePath('work1/text.json'));
  assert.doesNotThrow(() => assertSafeRelativePath('a file #1?.json'));
});

test('--from-url: a RELEASE.json path that escapes destDir via ".." is refused before any file is downloaded', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    const index = writeIndex(sourceDir);
    index.files.push({ path: '../escaped.json', size: 5, sha256: '0'.repeat(64) });
    writeFileSync(join(sourceDir, 'RELEASE.json'), JSON.stringify(index), 'utf8');
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /unsafe path/,
        );
        // Validation ran before any download -- not even the legitimate
        // files should have landed.
        assert.equal(existsSync(join(destDir, 'work1')), false);
        assert.equal(existsSync(join(dirname(destDir), 'escaped.json')), false);
      });
    } finally {
      await stopServer(server);
    }
  });
});

test('--from-url: a symlinked destination directory is refused before any write', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (parentDir) => {
        const realTarget = join(parentDir, 'real-target');
        mkdirSync(realTarget);
        const destDir = join(parentDir, 'dest-symlink');
        symlinkSync(realTarget, destDir, 'dir');
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /symlink/,
        );
        assert.deepEqual(readdirSync(realTarget), []);
      });
    } finally {
      await stopServer(server);
    }
  });
});

test('--from-url: an existing symlinked subdirectory inside destDir is refused, nothing written through it', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await withTmpDir(async (outsideDir) => {
          // Plant a symlinked "work1" subdirectory inside destDir, pointing
          // outside it, before the fetch runs -- simulates a leftover or
          // planted symlink at an intermediate path component.
          symlinkSync(outsideDir, join(destDir, 'work1'), 'dir');
          await assert.rejects(
            () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
            /symlink/,
          );
          assert.deepEqual(readdirSync(outsideDir), []);
        });
      });
    } finally {
      await stopServer(server);
    }
  });
});

// --- Sol: URL-encode path segments; reuse the version rule; HTTPS only; no cross-origin redirects ---

test('--from-url: file names with spaces, #, ?, and non-ASCII characters are fetched and verified correctly', async () => {
  await withTmpDir(async (sourceDir) => {
    mkdirSync(join(sourceDir, 'work1'), { recursive: true });
    writeFileSync(join(sourceDir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: 'test-1' }), 'utf8');
    writeFileSync(join(sourceDir, 'work1', 'a file #1?.json'), JSON.stringify({ ok: true }), 'utf8');
    writeFileSync(join(sourceDir, 'work1', 'héllo.json'), JSON.stringify({ ok: true }), 'utf8');
    const index = writeIndex(sourceDir);
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        const result = await fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl });
        assert.equal(result.ok, true);
        assert.equal(result.fileCount, index.files.length);
        const verify = verifyRelease(destDir);
        assert.equal(verify.ok, true, verify.problems.join('; '));
      });
    } finally {
      await stopServer(server);
    }
  });
});

test('--from-url: a version that fails the release-version rule is refused before any request is made', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    const { server, baseUrl, requests } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: '../x', destDir, baseUrl }),
          /not a valid release version/,
        );
      });
    } finally {
      await stopServer(server);
    }
    assert.equal(requests.length, 0);
  });
});

test('--from-url: a non-HTTPS base URL to a non-local host is refused before any request is made', async () => {
  await withTmpDir(async (destDir) => {
    await assert.rejects(
      () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl: 'http://example.test' }),
      /https:/,
    );
  });
});

test('--from-url: a redirect to a different origin is refused', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    const { server: serverB, baseUrl: baseUrlB } = await startReleaseServer(sourceDir);
    let requestsToB = 0;
    serverB.on('request', () => { requestsToB += 1; });
    const serverA = createServer((req, res) => {
      res.writeHead(302, { location: `${baseUrlB}${req.url}` });
      res.end();
    });
    await new Promise((res) => serverA.listen(0, '127.0.0.1', res));
    const baseUrlA = `http://127.0.0.1:${serverA.address().port}`;
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl: baseUrlA }),
          /redirect|origin/,
        );
      });
      assert.equal(requestsToB, 0, 'the redirect target must never be contacted');
    } finally {
      await new Promise((res) => serverA.close(res));
      await stopServer(serverB);
    }
  });
});

test('--from-url: a same-origin redirect (RELEASE.json redirected to another path on the same origin) is refused', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    // A server that redirects RELEASE.json requests to a different path on
    // the SAME origin, rather than serving it directly -- release paths are
    // immutable and never legitimately redirect, so even this must be
    // refused, not just a cross-origin redirect.
    const server = createServer((req, res) => {
      if (req.url.endsWith('/RELEASE.json')) {
        res.writeHead(302, { location: req.url.replace('/RELEASE.json', '/RELEASE-moved.json') });
        res.end();
        return;
      }
      res.writeHead(404).end('not found');
    });
    await new Promise((res) => server.listen(0, '127.0.0.1', res));
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /redirect/,
        );
      });
    } finally {
      await new Promise((res) => server.close(res));
    }
  });
});

// --- Sol second pass: dest dir must be fresh; exclusive-create temp files; validate size/sha256; clean up a failed rename; body-stream stall times out ---

test('--from-url: a non-empty destination directory is refused before any request is made', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    writeIndex(sourceDir);
    const { server, baseUrl, requests } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        writeFileSync(join(destDir, 'leftover.txt'), 'stale', 'utf8');
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /not empty/,
        );
      });
    } finally {
      await stopServer(server);
    }
    assert.equal(requests.length, 0);
  });
});

test('--from-url: a RELEASE.json entry with a missing or non-numeric size is refused before any file is downloaded', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    const index = writeIndex(sourceDir);
    delete index.files[0].size;
    writeFileSync(join(sourceDir, 'RELEASE.json'), JSON.stringify(index), 'utf8');
    const { server, baseUrl, requests } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /invalid size/,
        );
      });
    } finally {
      await stopServer(server);
    }
    // Only RELEASE.json itself was fetched -- entry validation ran before
    // any file download request.
    assert.equal(requests.length, 1);
  });
});

test('--from-url: a RELEASE.json entry with a malformed sha256 is refused before any file is downloaded', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    const index = writeIndex(sourceDir);
    index.files[0].sha256 = 'not-hex';
    writeFileSync(join(sourceDir, 'RELEASE.json'), JSON.stringify(index), 'utf8');
    const { server, baseUrl, requests } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl }),
          /invalid sha256/,
        );
      });
    } finally {
      await stopServer(server);
    }
    assert.equal(requests.length, 1);
  });
});

test('downloadFileWithRetry: an existing .part symlink is refused rather than followed (test-only seam: calls the per-file downloader directly, bypassing fetchReleaseFromUrl\'s dest-dir-must-be-empty check, which would otherwise refuse first)', async () => {
  await withTmpDir(async (destDir) => {
    const content = Buffer.from('hello world');
    const server = createServer((req, res) => res.writeHead(200).end(content));
    await new Promise((res) => server.listen(0, '127.0.0.1', res));
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    try {
      const target = join(destDir, 'real-target.bin');
      writeFileSync(target, 'untouched');
      const destPath = join(destDir, 'file.bin');
      symlinkSync(target, `${destPath}.part`);
      await assert.rejects(
        () => downloadFileWithRetry(`${baseUrl}/file.bin`, destPath, content.length, { retries: 0 }),
        /existing file|symlink/,
      );
      // The pre-existing symlink's target must not have been written through.
      assert.equal(readFileSync(target, 'utf8'), 'untouched');
    } finally {
      await new Promise((res) => server.close(res));
    }
  });
});

test('downloadFileWithRetry: a failed rename removes the .part temp file', async () => {
  await withTmpDir(async (destDir) => {
    const content = Buffer.from('hello');
    const server = createServer((req, res) => res.writeHead(200).end(content));
    await new Promise((res) => server.listen(0, '127.0.0.1', res));
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    try {
      // destPath already exists as a non-empty directory, so the final
      // rename(partPath, destPath) fails (EISDIR/ENOTEMPTY) after a
      // successful download -- the .part temp file must still be cleaned up.
      const destPath = join(destDir, 'target');
      mkdirSync(destPath);
      writeFileSync(join(destPath, 'inner.txt'), 'x', 'utf8');
      await assert.rejects(() => downloadFileWithRetry(`${baseUrl}/file.bin`, destPath, content.length, { retries: 0 }));
      assert.equal(existsSync(`${destPath}.part`), false);
    } finally {
      await new Promise((res) => server.close(res));
    }
  });
});

test(
  '--from-url: a request whose headers arrive but whose body stalls times out and fails cleanly',
  { timeout: 5000 },
  async () => {
    await withTmpDir(async (sourceDir) => {
      writeSyntheticRelease(sourceDir);
      writeIndex(sourceDir);
      const server = createServer((req, res) => {
        // Send headers and part of the body, then never finish -- proves the
        // request timeout covers the body, not just the initial response.
        res.writeHead(200, { 'content-type': 'application/octet-stream' });
        res.write('partial-body-then-silence');
        // Deliberately never call res.end().
      });
      await new Promise((res) => server.listen(0, '127.0.0.1', res));
      const baseUrl = `http://127.0.0.1:${server.address().port}`;
      try {
        await withTmpDir(async (destDir) => {
          await assert.rejects(() =>
            fetchReleaseFromUrl({
              version: VERSION,
              destDir,
              baseUrl,
              retries: 0,
              timeoutMs: 150,
            }),
          );
        });
      } finally {
        await new Promise((res) => server.close(res));
      }
    });
  },
);

// --- Sol: stream with a size cap; request timeout with bounded backoff; stop the queue on the first failure ---

test('--from-url: a file whose actual bytes exceed RELEASE.json\'s declared size is refused', async () => {
  await withTmpDir(async (sourceDir) => {
    writeSyntheticRelease(sourceDir);
    const index = writeIndex(sourceDir);
    const entry = index.files.find((f) => f.path === 'work1/text.json');
    entry.size = 3; // understate it so the real bytes exceed the cap
    writeFileSync(join(sourceDir, 'RELEASE.json'), JSON.stringify(index), 'utf8');
    const { server, baseUrl } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl, retries: 0 }),
          /exceeded|size/,
        );
      });
    } finally {
      await stopServer(server);
    }
  });
});

test(
  '--from-url: a request that hangs times out and fails cleanly',
  { timeout: 5000 },
  async () => {
    await withTmpDir(async (sourceDir) => {
      writeSyntheticRelease(sourceDir);
      writeIndex(sourceDir);
      const server = createServer(() => {
        // Never respond -- simulates a hung connection.
      });
      await new Promise((res) => server.listen(0, '127.0.0.1', res));
      const baseUrl = `http://127.0.0.1:${server.address().port}`;
      try {
        await withTmpDir(async (destDir) => {
          await assert.rejects(() =>
            fetchReleaseFromUrl({
              version: VERSION,
              destDir,
              baseUrl,
              retries: 1,
              retryDelayMs: 10,
              timeoutMs: 150,
            }),
          );
        });
      } finally {
        await new Promise((res) => server.close(res));
      }
    });
  },
);

test('--from-url: one 404 stops the queue -- no new requests are started after the failure', async () => {
  await withTmpDir(async (sourceDir) => {
    mkdirSync(join(sourceDir, 'work1'), { recursive: true });
    writeFileSync(join(sourceDir, 'work1', 'manifest.json'), JSON.stringify({ corpus_version: 'test-1' }), 'utf8');
    // Sorts first alphabetically, so it lands in the first dispatch batch.
    writeFileSync(join(sourceDir, 'work1', '0-missing.json'), JSON.stringify({ x: 1 }), 'utf8');
    for (let i = 1; i <= 20; i += 1) {
      writeFileSync(join(sourceDir, 'work1', `file-${String(i).padStart(2, '0')}.json`), JSON.stringify({ i }), 'utf8');
    }
    const index = writeIndex(sourceDir);
    // Remove it after indexing so RELEASE.json still lists it but the server 404s it.
    rmSync(join(sourceDir, 'work1', '0-missing.json'));
    const { server, baseUrl, requests } = await startReleaseServer(sourceDir);
    try {
      await withTmpDir(async (destDir) => {
        await assert.rejects(
          () => fetchReleaseFromUrl({ version: VERSION, destDir, baseUrl, concurrency: 3, retries: 0 }),
          /404/,
        );
      });
    } finally {
      await stopServer(server);
    }
    assert.ok(
      requests.length < index.files.length,
      `expected an early stop, got ${requests.length} requests for ${index.files.length} files`,
    );
  });
});
