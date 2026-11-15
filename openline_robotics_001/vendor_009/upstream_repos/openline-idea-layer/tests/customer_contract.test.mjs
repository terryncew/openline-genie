import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generate,brief,sectors,audiences,formats,targetBuyers,starterMVPs} from '../engine.mjs';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';

const VALID_OPENLINE_REPOS = new Set([
 'openline-energy',
 'openline-energy-autopilot',
 'openline-living-energy',
 'mandate-ledger',
 'openline-weight-space-repair',
 'openline-connect',
 'openline-living-projects'
]);

test('each curated problem has a concrete independently testable first deliverable, valid repo slug, and full cost/license disclosures',()=>{
 assert.equal(sectors.length,12);
 assert.equal(targetBuyers.length,sectors.length);
 assert.equal(starterMVPs.length,sectors.length);
 for(let index=0;index<12;index++){
  assert.ok(VALID_OPENLINE_REPOS.has(sectors[index][3]), `Invalid repo slug for sector ${index}: ${sectors[index][3]}`);
  for(const audience of audiences)for(const format of formats){
   const x=generate({sector:index,audience,format,budget:0});
   assert.ok(x.buyer&&x.mvp&&x.acceptanceTest&&x.formatPackaging,`${index} ${audience} ${format}`);
   assert.match(x.offer,new RegExp(x.buyer.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')));
   const md=brief(x);
   for(const required of [
    '## Make this one useful thing first',
    'Acceptance test:',
    '## Demand experiment',
    'No paid APIs',
    'https://github.com/ollama/ollama',
    'https://github.com/Aider-AI/aider',
    '8–16 GB RAM/VRAM',
    'Optional paid services:',
    'Do not publish'
   ]) assert.ok(md.includes(required),required);
   const agentSection = md.split('## Instructions for the coding agent')[1];
   assert.ok(agentSection, 'missing agent instructions section');
   assert.ok(!agentSection.includes('Interview five potential users'), 'coding agent steps must not instruct the agent to run human interviews');
   assert.ok(agentSection.includes(x.acceptanceTest), 'coding agent instructions must include the acceptance test');
  }
 }
});

test('offline built page includes all data, a hash-based script policy, hardware/license disclosures, and accessible status regions',()=>{
 const html=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 assert.match(html,/Content-Security-Policy/);
 assert.match(html,/connect-src 'none'/);
 assert.ok(html.includes('id="copy-top"'));
 assert.ok(html.includes('id="download-top"'));
 assert.ok(html.includes('<details open>'));
 assert.ok(html.includes('8–16 GB RAM/VRAM'));
 assert.ok(!html.includes('openline-kill-switch'));
 assert.ok(!html.includes('aria-atomic="true"'));
 assert.ok(!html.includes('<script type="module"'));
 assert.ok(!html.includes('src="./app.mjs"'));
});

test('budget interpolation survives generation',()=>{
 assert.match(brief(generate({budget:125})),/\$125/);
 assert.doesNotMatch(brief(generate({budget:125})),/\$\$125/);
});

test('CLI export_brief.mjs lists sectors and exports deterministic brief matching engine',()=>{
 const listOut = execFileSync(process.execPath, [new URL('../export_brief.mjs', import.meta.url).pathname, '--list'], {encoding: 'utf8'});
 assert.match(listOut, /12 Curated Starting Problems/);
 assert.ok(!listOut.includes('openline-kill-switch'));
 const cliBrief = execFileSync(process.execPath, [
  new URL('../export_brief.mjs', import.meta.url).pathname,
  '--sector', '3', '--audience', 'small businesses', '--format', 'service', '--budget', '0', '--seed', '0'
 ], {encoding: 'utf8'});
 assert.equal(cliBrief, brief(generate({sector: 3, audience: 'small businesses', format: 'service', budget: 0, seed: 0})));
});

test('CLI errors are clean messages, not stack traces', () => {
 const cli = new URL('../export_brief.mjs', import.meta.url).pathname;
 for (const badArgs of [['--budget', '-50'], ['--sector', '2', '--audience', 'community-groups']]) {
  let caught = null;
  try { execFileSync(process.execPath, [cli, ...badArgs], {encoding: 'utf8'}); } catch (e) { caught = e; }
  assert.ok(caught, `CLI should exit non-zero for ${badArgs.join(' ')}`);
  assert.notEqual(caught.status, 0);
  assert.match(caught.stderr, /^Error: (Invalid budget|Unknown option)/m);
  assert.doesNotMatch(caught.stderr, /\.mjs:\d+/);
  assert.doesNotMatch(caught.stderr, /\n\s+at\s/);
 }

 // Verify README has no stale 19-test references
 const readmeText = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
 assert.ok(!readmeText.includes('19-test') && !readmeText.includes('19/19'), 'README must not contain stale 19-test count');
 assert.ok(readmeText.includes('20-test') && readmeText.includes('20/20'), 'README must state accurate 20-test count');
});
