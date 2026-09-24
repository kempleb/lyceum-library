# Rules for coding assistants
> DRAFT — awaiting approval by John Boyer and Brian Kemple.

Read these rules before working in this repository.

- Work on a branch whose name carries the author: `john/`, `brian/`, `claude/`, or `gpt/`.
- Open a pull request. Get the file owner's review and keep tests green. Never merge your own pull request.
- Never deploy the site or publish a data release. John runs the upload and deploy.
- Never commit licensed Greek source text from the TLG or Latin source text from the PHI.
- Never commit secrets or tokens. Names of secrets may appear; values never.
- Use English translations only when they are public domain in the US or John has approved them.
- Run the test commands in `README.md` before opening a pull request.
- Fetch data only through the data-root setting in `shared/lib/data.ts`.

These rules come from the plan John and Brian agreed for the shared
repository and from the project's hard rules.
