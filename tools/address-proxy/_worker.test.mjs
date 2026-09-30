// Tests for the throwaway address-test front (public/_worker.js). Each test
// hands the front a fake LIBRARY binding that records what it receives and
// returns a canned response. Run: node --test _worker.test.mjs (Node 22).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import front from './public/_worker.js';

function fakeLibrary(response) {
  const seen = [];
  return {
    seen,
    fetch: async (request) => {
      seen.push({
        url: request.url,
        method: request.method,
        headers: request.headers,
        redirect: request.redirect,
        body: request.method === 'GET' || request.method === 'HEAD' ? null : await request.text(),
      });
      return response;
    },
  };
}

test('GET path and query string arrive unchanged', async () => {
  const lib = fakeLibrary(new Response('ok'));
  const res = await front.fetch(new Request('https://front.example/texts/plato/republic/?loc=327a&x=1'), { LIBRARY: lib });
  assert.equal(res.status, 200);
  assert.equal(await res.text(), 'ok');
  const url = new URL(lib.seen[0].url);
  assert.equal(url.pathname, '/texts/plato/republic/');
  assert.equal(url.search, '?loc=327a&x=1');
  assert.equal(lib.seen[0].method, 'GET');
});

test('Range header is forwarded and a 206 with Content-Range comes back unchanged', async () => {
  const canned = new Response('0123456789', {
    status: 206,
    headers: { 'Content-Range': 'bytes 0-9/500', 'Content-Type': 'application/json' },
  });
  const lib = fakeLibrary(canned);
  const res = await front.fetch(
    new Request('https://front.example/data/v1/RELEASE.json', { headers: { Range: 'bytes=0-9' } }),
    { LIBRARY: lib },
  );
  assert.equal(new URL(lib.seen[0].url).pathname, '/data/v1/RELEASE.json');
  assert.equal(lib.seen[0].headers.get('range'), 'bytes=0-9');
  assert.equal(res.status, 206);
  assert.equal(res.headers.get('content-range'), 'bytes 0-9/500');
  assert.equal(res.headers.get('content-type'), 'application/json');
  assert.equal(await res.text(), '0123456789');
});

test('POST body and Authorization header are forwarded; a 401 comes back as 401', async () => {
  const lib = fakeLibrary(new Response('{"error":"unauthorized"}', { status: 401 }));
  const body = JSON.stringify({ hello: 'world' });
  const res = await front.fetch(
    new Request('https://front.example/api/catalog/publish', {
      method: 'POST',
      headers: { Authorization: 'Bearer wrong', 'Content-Type': 'application/json' },
      body,
    }),
    { LIBRARY: lib },
  );
  assert.equal(new URL(lib.seen[0].url).pathname, '/api/catalog/publish');
  assert.equal(lib.seen[0].method, 'POST');
  assert.equal(lib.seen[0].body, body);
  assert.equal(lib.seen[0].headers.get('authorization'), 'Bearer wrong');
  assert.equal(lib.seen[0].headers.get('content-type'), 'application/json');
  assert.equal(res.status, 401);
  assert.equal(await res.text(), '{"error":"unauthorized"}');
});

test('a 301 from the origin is returned as 301, not followed', async () => {
  const lib = fakeLibrary(new Response(null, { status: 301, headers: { Location: '/texts/plato/' } }));
  const res = await front.fetch(new Request('https://front.example/texts/plato'), { LIBRARY: lib });
  assert.equal(lib.seen[0].redirect, 'manual');
  assert.equal(lib.seen.length, 1);
  assert.equal(res.status, 301);
  assert.equal(res.headers.get('location'), '/texts/plato/');
});

test('a missing LIBRARY binding gives 503 naming the binding', async () => {
  const res = await front.fetch(new Request('https://front.example/'), {});
  assert.equal(res.status, 503);
  assert.match(await res.text(), /LIBRARY/);
});
