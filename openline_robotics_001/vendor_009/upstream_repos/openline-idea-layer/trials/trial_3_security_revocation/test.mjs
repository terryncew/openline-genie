import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FIXTURE_TRACES, evaluateTrace, BOUNDARY_NOTICE} from './logic.mjs';

test('IL-11-0 acceptance test: STOP-first mock traces show no protected commit; demo makes no live enforcement claims', () => {
 const stopFirst = evaluateTrace(FIXTURE_TRACES.stop_first);
 assert.equal(stopFirst.protected_commit, false);
 assert.equal(stopFirst.verdict, 'STOPPED_NO_PROTECTED_COMMIT');
 assert.equal(stopFirst.live_enforcement_claimed, false);
 assert.equal(stopFirst.boundary_notice, BOUNDARY_NOTICE);

 const commitFirst = evaluateTrace(FIXTURE_TRACES.commit_first);
 assert.equal(commitFirst.protected_commit, true);
 assert.equal(commitFirst.verdict, 'PRE_STOP_COMMIT_ALLOWED');
 assert.ok(commitFirst.commit_seq < commitFirst.stop_seq);
 assert.equal(commitFirst.live_enforcement_claimed, false);

 const staleRepro = evaluateTrace(FIXTURE_TRACES.stale_buggy_no_final_recheck);
 assert.equal(staleRepro.stale_permission_failure_reproduced, true);
 assert.equal(staleRepro.protected_commit, false);
});
