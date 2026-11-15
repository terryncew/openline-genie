#!/usr/bin/env node
/**
 * Zero-dependency CLI inspector & brief exporter for first-time visitors and coding agents.
 * Usage:
 *   node export_brief.mjs --list
 *   node export_brief.mjs --sector 0 --audience individuals --format service --budget 0 --seed 0
 */
import {sectors, audiences, formats, generate, brief} from './engine.mjs';

const USAGE = 'Usage: node export_brief.mjs --list | node export_brief.mjs --sector <0-11> --audience "<audience>" --format <service|toolkit|subscription> --budget <0-1000000> [--seed <n>] [--json]';
const VALUE_FLAGS = new Set(['--sector', '--audience', '--format', '--budget', '--seed']);
const BOOL_FLAGS = new Set(['--list', '-l', '--json']);

const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
 const a = args[i];
 if (BOOL_FLAGS.has(a)) continue;
 if (VALUE_FLAGS.has(a)) {
  if (i + 1 >= args.length) {
   console.error(`Error: Unknown option: missing value for ${a}`);
   console.error(USAGE);
   process.exit(1);
  }
  i += 1;
  continue;
 }
 console.error(`Error: Unknown option: ${a}`);
 console.error(USAGE);
 process.exit(1);
}

if (args.includes('--list') || args.includes('-l')) {
 console.log('OpenLine Idea Layer — 12 Curated Starting Problems (Hypotheses Only, No Verified Demand):');
 sectors.forEach(([category, problem, title, repo, guard, firstTest], idx) => {
  console.log(`  [${idx}] ${category}: ${title} (repo: ${repo})`);
  console.log(`      Problem: ${problem}`);
  console.log(`      Hard boundary: ${guard}`);
  console.log(`      Cheapest falsifier: ${firstTest}`);
 });
 process.exit(0);
}

function getArg(flag, fallback) {
 const idx = args.indexOf(flag);
 return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : fallback;
}

const opts = {
 sector: getArg('--sector', 0),
 audience: getArg('--audience', audiences[0]),
 format: getArg('--format', formats[0]),
 budget: getArg('--budget', 0),
 seed: getArg('--seed', 0)
};

let idea;
try {
 idea = generate(opts);
} catch (err) {
 console.error(`Error: ${err.message}`);
 console.error(USAGE);
 process.exit(1);
}
if (args.includes('--json')) {
 console.log(JSON.stringify(idea, null, 2));
} else {
 process.stdout.write(brief(idea));
}
