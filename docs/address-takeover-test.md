# Address takeover test: results sheet

## What is being tested

Brian's live Library is a Cloudflare Pages project, and its web address points
at Pages through DNS held at WordPress.com. The question is whether that Pages
project can keep the address while everything it serves comes from the new
site instead. To find out, a throwaway Pages project (`lyceum-proxy-test`)
forwards every request to a running copy of the new site. The checks below
show whether pages, the catalog password check, large files, redirects and
offline reading all survive the forwarding. Files and setup steps are in
`tools/address-proxy/`.

## Which copy it forwards to (John decides before deploying)

A Pages project can only forward this way to a Worker in the same Cloudflare
account, so the choice of copy is also a choice of account.

| | A. John's demo, John's account | B. The test copy, Lyceum account |
| --- | --- | --- |
| Forwards to | `lyceum-reader-demo` | `lyceum-library-staging` |
| Touches Brian's account | No | Yes: one extra throwaway project, deleted after. Brian should be told first. |
| Texts | The demo reads its texts from John's storage, from another address. That storage only answers sites on its allowed list, so `https://lyceum-proxy-test.pages.dev` must be added to the list first (and removed after), or reading pages will load with no text. | The test copy serves its own texts, so nothing else changes. |
| Tests the site serving its own text files (check 3) | No: the demo has no `/data/` route. | Yes. |
| Same arrangement as the real takeover | Partly | Yes: same account as Brian's Pages project, texts served by the site itself. |

John chose B on 30 September, and `tools/address-proxy/wrangler.jsonc` is
written for B. For A, change `account_id` to
`6ff75c6d6c06d1092df2c7efd42077ba` and the service to `lyceum-reader-demo`.

Below, `FRONT` is `https://lyceum-proxy-test.pages.dev` and `ORIGIN` is the
copy's own address (`https://lyceum-reader-demo.johnhboyer.workers.dev` for A,
`https://lyceum-library-staging.lyceum-institute.workers.dev` for B). Set them
once in the terminal, then paste the commands as written:

    FRONT=https://lyceum-proxy-test.pages.dev
    ORIGIN=https://lyceum-library-staging.lyceum-institute.workers.dev

## Checks

Every check asks the same thing: does `FRONT` answer exactly as `ORIGIN` does?

| Check | Command | Expected | Result |
| --- | --- | --- | --- |
| 1. Acceptance script through the front | `node scripts/acceptance.mjs --origin "$FRONT" --data-origin "$FRONT/data/2026.09.30-1d87227"` (needs Playwright; add `--works a,b,c` to shorten) | The same PASS lines as the same script run with `"$ORIGIN"`; exit 0 | **Same as ORIGIN.** Both: 0 passed, 1 failed, 54 skipped, line for line. The skips are works with no reviewed passages yet; the one failure (`inactive-no-landing`, a draft work that has a landing page) is the test copy showing drafts on purpose. Neither comes from the front. |
| 2. A wrong password is refused by the site, not the front | `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$FRONT/api/catalog/publish" -H 'Authorization: Bearer wrong' -H 'Content-Type: application/json' -d '{}'` | `401`, as `"$ORIGIN"` gives (checked 30 September: the test copy answers 401) | **Pass.** `401` through the front, as from ORIGIN; also `401` with no password at all. |
| 3. A text file served by the site itself | `curl -s -o /dev/null -w '%{http_code} %{size_download}\n' -H 'Range: bytes=0-99' "$FRONT/data/2026.09.26-165d80c/RELEASE.json"` (use the release named on the board if it has changed) | The same two numbers as the same request to `"$ORIGIN"` gives. On 30 September the test copy answered `200 233282`: it sends the whole file and ignores the range, so the front should too. | **Pass.** `200 301275` from both. The same etag, `Cache-Control: public, max-age=31536000, immutable`, and `304` on a repeat with `If-None-Match`, from both. |
| 4. Reading page and offline copy | Open a reading page at `FRONT` in a browser. DevTools, Application, Service Workers. | The address bar stays on `lyceum-proxy-test.pages.dev`; `sw.js` is registered for that address; the text shows | **Pass.** `/read/plato/republic/book-1/` in a browser: the address stayed on `lyceum-proxy-test.pages.dev`; the Greek and its 136 sections loaded; `sw.js` registered for that address and controls the page. The site's own redirect (`/read/epictetus/enchiridion/text` → `…/text/`) points at the front's address, not at `workers.dev`. |
| 5. Requests per page view | Open a reading page, DevTools, Network, hard reload. Record the total request count, and how many went to `FRONT`. | Two numbers, recorded here | **22** on a first visit to Republic Book 1 (the page and 21 files), **all 22 to FRONT**. Later visits ask for fewer, since the offline copy answers from the browser. |

## What the count means

Every request the front receives is one Pages Function invocation, because the
front handles all paths (Cloudflare's Pages Functions pricing page: Function
requests bill as Workers requests; the Free plan allows 100,000 a day, shared
with Workers requests in the same account, reset at midnight UTC).

    invocations per day = requests to FRONT per view (check 5) × views per day

Compare that number with 100,000. The forwarded-to Worker's own requests may
count against the same limit (unverified on the Free plan), in which case use
twice the requests per view. Static files would be free on a Pages project
with no Function, but that does not apply here. The daily figure for views is
Brian's to supply; this sheet does not guess it.

Measured 30 September: 22 requests for a first visit to a reading page. On
the Free plan that is about 4,500 first visits a day, or about 2,250 if the
test copy's own requests count as well. On Cloudflare's paid Workers plan the
monthly allowance is 10 million requests, about 450,000 first visits (half
that on the same caveat). Which plan the Lyceum account is on, and the
Library's real traffic, are Brian's to confirm.

Also checked, 30 September: eleven addresses (home, author, landing and
reading pages, a redirect, `sw.js`, the catalog, the library page, search,
a missing page, a release file) came back byte for byte the same through the
front as from ORIGIN, with the same status codes. The front added no
measurable time: 177 ms average to the first byte through the front, 192 ms
direct, over six requests each.

## Recommendation

The route works. Keeping `library.lyceum.institute` at WordPress.com and having
Brian's existing Pages project hand every request to the new site passed every
check: the same pages, the same files, the same password refusals, the
offline copy working, and the address bar never leaving the front's address.

For the real takeover, the same small front would be deployed to Brian's live
`lyceum-library` Pages project, with a service binding to the production
Worker. That step belongs to Brian, and a redeploy of his current site undoes
it. Nothing changes at WordPress.com, and no domain has to be added to
Cloudflare, which the other route needs.

Two things to settle first: the request allowance (above: fine on the paid
plan, tight on the free one at real traffic), and a first test of the front
on a preview address of Brian's live project rather than its production
address.

The throwaway project can now be deleted (README.md, "Delete afterwards").
