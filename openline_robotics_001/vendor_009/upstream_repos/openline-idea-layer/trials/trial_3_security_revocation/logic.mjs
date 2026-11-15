/**
 * Trial 3 (IL-11-0): Local authorization test-pack service — Mock revocation race demonstrator.
 * Enforces hard boundary: "Prototype coverage is bounded; never claim production containment"
 * Acceptance test: "STOP-first mock traces show no protected commit; the demo makes no live enforcement claims."
 */

export const BOUNDARY_NOTICE = 'MOCK FIXTURE TRACE ONLY — PROTOTYPE COVERAGE IS BOUNDED; NO LIVE ENFORCEMENT OR PRODUCTION CONTAINMENT CLAIMS';

export const FIXTURE_TRACES = {
 stop_first: {
  trace_id: 'TRACE-STOP-FIRST-01',
  mode: 'STOP-first',
  events: [
   {seq: 1, actor: 'owner', kind: 'ASSIGN_REPAIR', assignment_id: 'rep-101', epoch: 1},
   {seq: 2, actor: 'worker', kind: 'PRELIMINARY_CHECK_OK', assignment_id: 'rep-101', epoch: 1},
   {seq: 3, actor: 'owner', kind: 'ISSUE_STOP', reason: 'revoke stale authority before final gate', epoch: 2},
   {seq: 4, actor: 'worker', kind: 'FINAL_GATE_ATTEMPT', assignment_id: 'rep-101', issued_seq: 1, stop_seq: 3}
  ]
 },
 commit_first: {
  trace_id: 'TRACE-COMMIT-FIRST-01',
  mode: 'commit-first',
  events: [
   {seq: 1, actor: 'owner', kind: 'ASSIGN_REPAIR', assignment_id: 'rep-102', epoch: 1},
   {seq: 2, actor: 'worker', kind: 'PRELIMINARY_CHECK_OK', assignment_id: 'rep-102', epoch: 1},
   {seq: 3, actor: 'receiver', kind: 'FINAL_GATE_COMMIT', assignment_id: 'rep-102', issued_seq: 1, stop_seq: 0},
   {seq: 4, actor: 'owner', kind: 'ISSUE_STOP', reason: 'stop issued after pre-stop commit settled', epoch: 2}
  ]
 },
 stale_buggy_no_final_recheck: {
  trace_id: 'TRACE-BUGGY-STALE-01',
  mode: 'buggy-no-recheck-detector',
  events: [
   {seq: 1, actor: 'owner', kind: 'ASSIGN_REPAIR', assignment_id: 'rep-103', epoch: 1},
   {seq: 2, actor: 'worker', kind: 'PRELIMINARY_CHECK_OK', assignment_id: 'rep-103', epoch: 1},
   {seq: 3, actor: 'owner', kind: 'ISSUE_STOP', reason: 'mid-flight stop', epoch: 2},
   {seq: 4, actor: 'buggy_worker', kind: 'SKIP_FINAL_GATE_RECHECK', assignment_id: 'rep-103', issued_seq: 1, stop_seq: 3}
  ]
 }
};

export function evaluateTrace(trace) {
 if (!trace || !Array.isArray(trace.events)) throw new Error('Invalid fixture trace');
 let stopSeq = null;
 let commitSeq = null;
 let preliminaryCheckSeq = null;
 let stalePermissionBugReproduced = false;

 for (const ev of trace.events) {
  if (ev.kind === 'PRELIMINARY_CHECK_OK') preliminaryCheckSeq = ev.seq;
  if (ev.kind === 'ISSUE_STOP' && stopSeq === null) stopSeq = ev.seq;
  if (ev.kind === 'FINAL_GATE_ATTEMPT') {
   if (stopSeq !== null && stopSeq < ev.seq) {
    commitSeq = null; // Refused at final gate
   } else {
    commitSeq = ev.seq;
   }
  }
  if (ev.kind === 'FINAL_GATE_COMMIT') {
   if (stopSeq !== null && stopSeq < ev.seq) {
    throw new Error('Invariant violation: protected commit cannot succeed after STOP');
   }
   commitSeq = ev.seq;
  }
  if (ev.kind === 'SKIP_FINAL_GATE_RECHECK') {
   stalePermissionBugReproduced = (preliminaryCheckSeq !== null && stopSeq !== null && preliminaryCheckSeq < stopSeq && stopSeq < ev.seq);
   commitSeq = null; // Blocked by test-pack detector
  }
 }

 const protectedCommitOccurred = commitSeq !== null;
 return {
  trace_id: trace.trace_id,
  mode: trace.mode,
  protected_commit: protectedCommitOccurred,
  commit_seq: commitSeq,
  stop_seq: stopSeq,
  stale_permission_failure_reproduced: stalePermissionBugReproduced,
  verdict: protectedCommitOccurred ? 'PRE_STOP_COMMIT_ALLOWED' : 'STOPPED_NO_PROTECTED_COMMIT',
  live_enforcement_claimed: false,
  boundary_notice: BOUNDARY_NOTICE
 };
}
