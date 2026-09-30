// A throwaway test, not production. This Cloudflare Pages "advanced mode"
// worker sends every request on to the Worker bound as LIBRARY (a running copy
// of the site) and returns its answer as is. It exists to show whether a Pages
// project can stand in front of the new site. See ../README.md.
export default {
  async fetch(request, env) {
    if (!env.LIBRARY) {
      return new Response('Service binding LIBRARY is missing.\n', {
        status: 503,
        headers: { 'content-type': 'text/plain; charset=utf-8' },
      });
    }
    // Same method, URL, headers (Range, Authorization) and body. A redirect
    // reaches the browser instead of being followed here.
    return env.LIBRARY.fetch(new Request(request, { redirect: 'manual' }));
  },
};
