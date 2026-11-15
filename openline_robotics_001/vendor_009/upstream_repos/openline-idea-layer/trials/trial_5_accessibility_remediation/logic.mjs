/**
 * Trial 5 (IL-4-0): Accessible document remediation studio (Regulated Accessibility / ADA Sector).
 * Enforces hard boundary: "Human review required; do not promise legal compliance"
 * Acceptance test: "Issues can be reviewed, marked resolved, and exported without compliance guarantees."
 */

export const NON_COMPLIANCE_NOTICE = 'HUMAN REVIEW REQUIRED — THIS TRACKER DOES NOT GUARANTEE ADA, SECTION 508, OR WCAG LEGAL COMPLIANCE';

export const FICTIONAL_DOCUMENT_ISSUES = [
 {issue_id: 'A11Y-01', location: 'Page 1 Hero Image', criterion: 'Non-text Content (Alt Text)', status: 'OPEN', human_reviewer: '', remediation_note: ''},
 {issue_id: 'A11Y-02', location: 'Page 2 Fee Table', criterion: 'Table Header Association', status: 'RESOLVED', human_reviewer: 'Jordan Lee (Mock Accessibility Reviewer)', remediation_note: 'Added explicit scope="col" headers in fictional draft.'},
 {issue_id: 'A11Y-03', location: 'Page 4 Contact Form', criterion: 'Visible Focus & Label Binding', status: 'OPEN', human_reviewer: '', remediation_note: ''}
];

export function reviewAndTrackIssues(issues, updates = {}) {
 if (!Array.isArray(issues) || issues.length === 0) throw new Error('Issues list required');
 const tracked = issues.map(item => {
  const patch = updates[item.issue_id] ? {...item, ...updates[item.issue_id]} : {...item};
  const hasHumanReview = typeof patch.human_reviewer === 'string' && patch.human_reviewer.trim().length > 0 &&
                         typeof patch.remediation_note === 'string' && patch.remediation_note.trim().length > 0;
  const resolved = patch.status === 'RESOLVED' && hasHumanReview;
  if (patch.status === 'RESOLVED' && !hasHumanReview) {
   throw new Error(`Human review and remediation note required before marking ${item.issue_id} RESOLVED`);
  }
  return {
   issue_id: String(patch.issue_id),
   location: String(patch.location),
   criterion: String(patch.criterion),
   status: resolved ? 'RESOLVED' : 'OPEN',
   human_reviewer: resolved ? patch.human_reviewer.trim() : '',
   remediation_note: resolved ? patch.remediation_note.trim() : '',
   legal_compliance_guaranteed: false,
   notice: NON_COMPLIANCE_NOTICE
  };
 });

 return {
  disclaimer: NON_COMPLIANCE_NOTICE,
  legal_compliance_guaranteed: false,
  resolved_count: tracked.filter(x => x.status === 'RESOLVED').length,
  open_count: tracked.filter(x => x.status === 'OPEN').length,
  issues: tracked
 };
}

export function exportRemediationSummary(trackerState) {
 const lines = [
  `# ${trackerState.disclaimer}`,
  `Resolved: ${trackerState.resolved_count} | Open: ${trackerState.open_count} | Legal Compliance Guaranteed: false`,
  ''
 ];
 for (const it of trackerState.issues) {
  lines.push(`- [${it.status}] ${it.issue_id} (${it.location} — ${it.criterion}) | Reviewer: ${it.human_reviewer || 'Pending mandatory human review'} | Note: ${it.remediation_note || 'None'}`);
 }
 return lines.join('\n');
}
