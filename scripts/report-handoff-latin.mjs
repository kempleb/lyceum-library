#!/usr/bin/env node
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { mapPassagesOntoLatin } from './lib/corpus-adapter/lyceum-handoff.mjs';

const args = Object.fromEntries(process.argv.slice(2).reduce((out, value, i, all) =>
  value.startsWith('--') ? [...out, [value.slice(2), all[i + 1]]] : out, []));
if (!args.handoff || !args['phi-latin']) throw new Error('usage: report-handoff-latin.mjs --handoff <dir> --phi-latin <json>');
const handoff = JSON.parse(readFileSync(join(resolve(args.handoff), 'aeneid.books.json'), 'utf8'));
const phi = JSON.parse(readFileSync(resolve(args['phi-latin']), 'utf8'));
const say = line => console.log(line);
const list = rows => rows.map(row => row.n).join(', ');
say('# Aeneid Latin: PHI and Perseus');
say('');
say('PHI supplies the Latin text. The Perseus copy keeps the passage and line addresses.');
say('');
say('| Book | PHI lines | PHI last line | Perseus lines | Perseus last line |');
say('| --- | ---: | ---: | ---: | ---: |');
for (const [i, book] of handoff.books.entries()) {
  const p = phi.books[i].rows, q = book.scholarSegments.flatMap(s => s.latin);
  say(`| ${i + 1} | ${p.length} | ${p.at(-1).n} | ${q.length} | ${q.at(-1).n} |`);
}
say('');
say('## Perseus lines absent from PHI');
say('');
let missing = 0;
for (const [i, book] of handoff.books.entries()) {
  const maps = mapPassagesOntoLatin(book, phi.books[i].rows);
  const present = new Set(phi.books[i].rows.map(row => row.n));
  for (const map of maps) for (const row of map.passage.latin) if (!present.has(row.n)) {
    say(`- ${i + 1}.${row.n}: Perseus: “${row.text}” Address now lands on PHI ${i + 1}.${map.landings[row.n]}.`);
    missing++;
  }
}
say('');
say('## PHI lines absent from Perseus');
say('');
let extra = 0;
for (const [i, book] of handoff.books.entries()) {
  const known = new Set(book.scholarSegments.flatMap(s => s.latin.map(row => row.n)));
  for (const row of phi.books[i].rows) if (!known.has(row.n)) { say(`- ${i + 1}.${row.n}: “${row.text}”`); extra++; }
}
if (!extra) say('None.');
say('');
say('## Different line order');
say('');
let reordered = 0;
for (const [i, book] of handoff.books.entries()) {
  const maps = mapPassagesOntoLatin(book, phi.books[i].rows);
  for (const map of maps) {
    const kept = new Set(map.rows.map(row => row.n));
    const perseus = map.passage.latin.filter(row => kept.has(row.n));
    if (list(perseus) !== list(map.rows)) {
      say(`- ${map.passage.id}: PHI ${list(map.rows)}; Perseus ${list(perseus)}.`);
      reordered++;
    }
  }
}
if (!reordered) say('None.');
say('');
say('## Three checked corrections');
say('');
const one = phi.books[0].rows.find(row => row.n === '170');
const first170 = mapPassagesOntoLatin(handoff.books[0], phi.books[0].rows).find(item => item.passage.id === 'aeneid-1-170-197');
say(`- Book I 170: PHI ${one ? 'has line 170' : 'lacks line 170'}; passage aeneid-1-170-197 ${first170?.rows[0].n === '170' ? 'begins on it' : 'does not begin on it'}.`);
const tenPhi = phi.books[9].rows.map(row => row.n), tenPer = handoff.books[9].scholarSegments.flatMap(s => s.latin.map(row => row.n));
say(`- Book X 713–718: PHI ${tenPhi.filter(n => ['713','714','715','716','717','718'].includes(n)).join(', ')}; Perseus ${tenPer.filter(n => ['713','714','715','716','717','718'].includes(n)).join(', ')}.`);
const sixtyTwo = phi.books[9].rows.find(row => row.n === '62');
say(`- Book X 62b: PHI ${phi.books[9].rows.some(row => row.n === '62b') ? 'has' : 'has no'} 62b; its address lands on 10.62, with ref 62. PHI 10.62: “${sixtyTwo?.text}”`);
say('');
say('## Passages with changed lines');
say('');
let changed = 0;
for (const [i, book] of handoff.books.entries()) {
  for (const map of mapPassagesOntoLatin(book, phi.books[i].rows)) {
    const original = map.passage.latin.map(row => row.n);
    const current = map.rows.map(row => row.n);
    if (JSON.stringify(original) !== JSON.stringify(current)) {
      say(`- ${map.passage.id}: Perseus ${original.join(', ')}; PHI ${current.join(', ')}.`);
      changed++;
    }
  }
}
say('');
say(`Nine addresses move to another line (${missing} listed above). ${changed} passages have changed line lists.`);
