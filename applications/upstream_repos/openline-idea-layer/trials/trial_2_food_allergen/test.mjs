import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {INITIAL_FICTIONAL_MENU, evaluateWorksheet, exportPrintableWorksheet, NON_CERTIFICATION_DISCLAIMER, canMarkHumanChecked} from './logic.mjs';

test('IL-8-0 acceptance test: unchecked entries never appear verified and no safety certification is implied', () => {
 const res = evaluateWorksheet(INITIAL_FICTIONAL_MENU);
 assert.equal(res.implies_safety_certification, false);
 assert.equal(res.disclaimer, NON_CERTIFICATION_DISCLAIMER);
 assert.equal(res.unverified_count, 2);
 assert.equal(res.ready_for_staff_signoff, false);

 const m01 = res.items.find(x => x.item_id === 'M-01');
 assert.equal(m01.human_checked, false);
 assert.match(m01.verification_badge, /UNVERIFIED/);
 assert.doesNotMatch(m01.verification_badge, /^HUMAN-REVIEWED/);
 assert.equal(m01.certified_safe, false);

 // Even if human_checked=true, missing reviewer_name must remain UNVERIFIED
 const missingReviewer = evaluateWorksheet([{...INITIAL_FICTIONAL_MENU[0], human_checked: true, reviewer_name: '   '}]);
 assert.equal(missingReviewer.items[0].human_checked, false);
 assert.match(missingReviewer.items[0].verification_badge, /UNVERIFIED/);

 const md = exportPrintableWorksheet(INITIAL_FICTIONAL_MENU);
 assert.ok(md.includes(NON_CERTIFICATION_DISCLAIMER));
 assert.ok(!/FDA certified|certified safe/i.test(md));
});

test('IL-8-0 UI guard (regression): a tick without a named reviewer must not verify a dish', () => {
 const unnamed = {...INITIAL_FICTIONAL_MENU[0], human_checked: false, reviewer_name: ''};
 assert.equal(canMarkHumanChecked(unnamed), false);
 const whitespace = {...INITIAL_FICTIONAL_MENU[0], reviewer_name: '   '};
 assert.equal(canMarkHumanChecked(whitespace), false);
 const named = {...INITIAL_FICTIONAL_MENU[0], reviewer_name: 'Chef Taylor'};
 assert.equal(canMarkHumanChecked(named), true);
 // The shipped page must never invent a reviewer name to satisfy the guard.
 const page = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
 assert.doesNotMatch(page, /Staff Reviewer \(Mock\)/);
 assert.ok(page.includes('canMarkHumanChecked'));
});
