import {test} from 'node:test';
import assert from 'node:assert/strict';
import {FICTIONAL_DOCUMENT_ISSUES, reviewAndTrackIssues, exportRemediationSummary, NON_COMPLIANCE_NOTICE} from './logic.mjs';

test('IL-4-0 acceptance test: issues can be reviewed, marked resolved, and exported without compliance guarantees', () => {
 const initial = reviewAndTrackIssues(FICTIONAL_DOCUMENT_ISSUES);
 assert.equal(initial.legal_compliance_guaranteed, false);
 assert.equal(initial.resolved_count, 1);
 assert.equal(initial.open_count, 2);

 const updated = reviewAndTrackIssues(FICTIONAL_DOCUMENT_ISSUES, {
  'A11Y-01': {status: 'RESOLVED', human_reviewer: 'Alex Rivera (Mock Staff)', remediation_note: 'Added descriptive alt text for hero diagram.'}
 });
 assert.equal(updated.resolved_count, 2);
 assert.equal(updated.open_count, 1);
 assert.equal(updated.legal_compliance_guaranteed, false);

 const md = exportRemediationSummary(updated);
 assert.ok(md.includes(NON_COMPLIANCE_NOTICE));
 assert.ok(md.includes('Legal Compliance Guaranteed: false'));
 assert.ok(!/ADA certified|guaranteed compliant/i.test(md));

 // Refuses marking RESOLVED without human reviewer
 assert.throws(
  () => reviewAndTrackIssues(FICTIONAL_DOCUMENT_ISSUES, {'A11Y-03': {status: 'RESOLVED', human_reviewer: '', remediation_note: 'auto-fixed'}}),
  /Human review and remediation note required/
 );
});
