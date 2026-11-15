import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_WEEK_PLAN, buildWeekLessonPack, exportLessonPackMarkdown, PRIVACY_AND_ACCURACY_BANNER} from './logic.mjs';

test('IL-6-0 acceptance test: user can edit and export a week-long plan without storing information about real minors', () => {
 const edited = buildWeekLessonPack(DEFAULT_WEEK_PLAN, {
  Wednesday: {topic: 'Fractions: Equivalent Ratios (Fictional)', activity: 'Number-line matching cards'}
 });
 assert.equal(edited.contains_minor_pii, false);
 assert.equal(edited.days.length, 5);
 assert.equal(edited.days[2].topic, 'Fractions: Equivalent Ratios (Fictional)');

 const md = exportLessonPackMarkdown(edited);
 assert.ok(md.includes(PRIVACY_AND_ACCURACY_BANNER));
 assert.ok(md.includes('Contains Minor PII: false'));

 // Rejects forbidden minor PII fields or embedded student emails/SSNs
 assert.throws(
  () => buildWeekLessonPack(DEFAULT_WEEK_PLAN, {Monday: {student_name: 'Timmy Smith'}}),
  /forbidden student identifier field/
 );
 assert.throws(
  () => buildWeekLessonPack(DEFAULT_WEEK_PLAN, {Tuesday: {activity: 'Send score to child@example.org'}}),
  /Minor privacy boundary violation/
 );
});
