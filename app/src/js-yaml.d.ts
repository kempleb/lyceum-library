// js-yaml ships no types and @types/js-yaml isn't installed. Only `load` is
// used (citation-routes.ts, which casts the result), so declare just that
// rather than add a package.
declare module 'js-yaml' {
  export function load(str: string): unknown;
}
