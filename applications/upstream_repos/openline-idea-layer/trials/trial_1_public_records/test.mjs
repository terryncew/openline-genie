import {test} from 'node:test';
import assert from 'node:assert/strict';
import {SNAPSHOT_A, SNAPSHOT_B, diffSnapshots, FICTIONAL_BANNER} from './logic.mjs';

test('IL-3-0 acceptance test: identifies changed rows without attributing motives or calling fictional records real', () => {
 const digest = diffSnapshots(SNAPSHOT_A, SNAPSHOT_B);
 assert.equal(digest.fictional_only, true);
 assert.equal(digest.banner, FICTIONAL_BANNER);
 assert.equal(digest.changed_count, 3);
 const byId = Object.fromEntries(digest.rows.map(r => [r.record_id, r]));
 assert.equal(byId['ORD-2026-101'].status, 'MODIFIED');
 assert.deepEqual(byId['ORD-2026-101'].changed_fields, ['vote_tally', 'summary']);
 assert.equal(byId['ORD-2026-102'].status, 'UNCHANGED');
 assert.equal(byId['ORD-2026-103'].status, 'REMOVED');
 assert.equal(byId['ORD-2026-104'].status, 'ADDED');
 for (const row of digest.rows) {
  assert.ok(row.primary_sources.length >= 1, 'every row cites primary source');
  assert.equal(row.fictional_notice, FICTIONAL_BANNER);
 }
});

test('IL-3-0 hard boundary: refuses motive attribution or missing primary source reference', () => {
 assert.throws(() => diffSnapshots(SNAPSHOT_A, SNAPSHOT_B, 'Council secretly flip-flopped due to lobbyist payoff'), /Motive inference refused/);
 const missingSource = [{...SNAPSHOT_A[0], source_ref: ''}];
 assert.throws(() => diffSnapshots(missingSource, SNAPSHOT_B), /Missing source_ref/);
});
