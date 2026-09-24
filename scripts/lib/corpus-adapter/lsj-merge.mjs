// Lyceum P3 stage 2 (docs/p3-plan.md, Settled decisions 2, 4).
//
// mergeShards() unions a source corpus's own pre-built LSJ shard directory
// (e.g. the sibling aristotle-reader's build/dist/lsj/) into this repo's
// shared build/dist/lsj/ shards. Classical always wins a key collision
// (probe finding: of 1,468 overlapping keys, 874 carry differing HTML --
// classical's is the newer sense-hierarchy renderer); a key present only in
// the incoming shards is added as-is.
//
// This gives immediate, non-empty dictionary coverage for aristotle-only
// lemmata right after mount, using whatever the sibling repo's own (older)
// renderer produced. It is deliberately NOT the final word on content
// quality for aristotle-only keys -- pipeline/reader_pipeline/lsj_topup.py
// runs later in build:public and re-renders every genuinely aristotle-only
// key (one not referenced by any classical work) from grc.lsj.xml with
// THIS repo's current renderer, superseding whatever this merge added for
// those keys ("moots their flagged-inconsistent shards", Settled decision
// 4). mergeShards() never overwrites a classical shard's existing key
// either way -- "conflicts" here means: present in both, so incoming is
// discarded (classical wins), not "corrupted" or "unresolved".

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/**
 * @param {string} classicalDir - this repo's build/dist/lsj (or /ls)
 *   directory. Modified in place; created if missing.
 * @param {string} incomingDir - the source corpus's own prebuilt shard
 *   directory (e.g. <ARISTOTLE_DATA_DIR>/lsj).
 * @returns {{added: number, conflicts: number}} added = keys that existed
 *   only in incomingDir and were copied in; conflicts = keys present in
 *   both (classical's entry was kept, incoming's was discarded).
 */
export function mergeShards(classicalDir, incomingDir) {
  if (!existsSync(incomingDir)) {
    return { added: 0, conflicts: 0 };
  }
  mkdirSync(classicalDir, { recursive: true });

  let added = 0;
  let conflicts = 0;

  const shardFiles = readdirSync(incomingDir).filter((f) => f.endsWith('.json'));
  for (const filename of shardFiles) {
    const incomingPath = join(incomingDir, filename);
    const classicalPath = join(classicalDir, filename);

    const incoming = JSON.parse(readFileSync(incomingPath, 'utf8'));
    const classical = existsSync(classicalPath)
      ? JSON.parse(readFileSync(classicalPath, 'utf8'))
      : {};

    let changed = false;
    for (const [key, entry] of Object.entries(incoming)) {
      if (Object.prototype.hasOwnProperty.call(classical, key)) {
        conflicts += 1;
        continue; // classical wins; incoming discarded, never overwrites.
      }
      classical[key] = entry;
      added += 1;
      changed = true;
    }

    if (changed) {
      // Canonical emission, matching the Python shard writers' sort_keys
      // (stage5_lsj, stage7's _merge_shared_lsj, lsj_topup): shard bytes are
      // a pure function of content, so byte-identity across builds holds as
      // a regression contract. Keys are Beta Code / L&S headwords — always
      // letter-bearing ASCII, so JS key sort ≡ Python's codepoint sort and
      // no key is an integer-like string V8 would reorder.
      const canonical = Object.fromEntries(
        Object.keys(classical).sort().map((key) => [
          key,
          Object.fromEntries(Object.entries(classical[key]).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))),
        ]),
      );
      writeFileSync(classicalPath, JSON.stringify(canonical), 'utf8');
    }
  }

  return { added, conflicts };
}
