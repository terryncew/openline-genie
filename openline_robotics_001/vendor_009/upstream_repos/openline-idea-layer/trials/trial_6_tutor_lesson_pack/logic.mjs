/**
 * Trial 6 (IL-6-0): Tutor lesson-plan starter packs (Regulated Minor Data Privacy Boundary).
 * Enforces hard boundary: "Protect minors’ data and verify instructional accuracy"
 * Acceptance test: "The user can edit and export a week-long plan without storing information about real minors."
 */

export const PRIVACY_AND_ACCURACY_BANNER = 'FICTIONAL CURRICULUM ONLY — ZERO STUDENT PII PERMITTED; VERIFY INSTRUCTIONAL ACCURACY BEFORE USE';

const FORBIDDEN_MINOR_PII_KEYS = new Set(['student_name', 'student_email', 'student_phone', 'student_dob', 'student_ssn', 'minor_id', 'home_address', 'parent_phone']);
const PII_TEXT_PATTERNS = [
 /\b\d{3}-\d{2}-\d{4}\b/, // SSN pattern
 /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i, // Email address
 /\b(student name|minor dob|home address|ieps?|504 plan)\s*:/i
];

export const DEFAULT_WEEK_PLAN = [
 {day: 'Monday', topic: 'Fractions: Common Denominators (Fictional Module)', activity: 'Visual fraction bar comparison worksheet', accuracy_verified_by_tutor: true},
 {day: 'Tuesday', topic: 'Fractions: Addition with Unlike Denominators', activity: 'Guided 5-problem practice set', accuracy_verified_by_tutor: true},
 {day: 'Wednesday', topic: 'Fractions: Subtraction & Mixed Numbers', activity: 'Peer explanation rubric (anonymous)', accuracy_verified_by_tutor: true},
 {day: 'Thursday', topic: 'Word Problems: Recipe Scaling', activity: 'Fictional bakery recipe doubling exercise', accuracy_verified_by_tutor: true},
 {day: 'Friday', topic: 'Weekly Concept Check & Reflection', activity: 'Self-graded 4-question concept check', accuracy_verified_by_tutor: true}
];

function assertNoMinorPII(objOrText) {
 const str = String(objOrText ?? '');
 for (const pat of PII_TEXT_PATTERNS) {
  if (pat.test(str)) {
   throw new Error('Minor privacy boundary violation: student PII (email, SSN, DOB, or student record) is forbidden.');
  }
 }
}

export function buildWeekLessonPack(days = DEFAULT_WEEK_PLAN, edits = {}) {
 if (!Array.isArray(days) || days.length !== 5) throw new Error('A 5-day week-long plan is required');
 const plan = days.map(entry => {
  const merged = edits[entry.day] ? {...entry, ...edits[entry.day]} : {...entry};
  for (const k of Object.keys(merged)) {
   if (FORBIDDEN_MINOR_PII_KEYS.has(k.toLowerCase())) {
    throw new Error(`Minor privacy boundary violation: forbidden student identifier field "${k}"`);
   }
  }
  assertNoMinorPII(merged.topic);
  assertNoMinorPII(merged.activity);
  return {
   day: String(merged.day),
   topic: String(merged.topic),
   activity: String(merged.activity),
   accuracy_verified_by_tutor: Boolean(merged.accuracy_verified_by_tutor)
  };
 });

 return {
  banner: PRIVACY_AND_ACCURACY_BANNER,
  contains_minor_pii: false,
  all_instructional_accuracy_verified: plan.every(d => d.accuracy_verified_by_tutor),
  days: plan
 };
}

export function exportLessonPackMarkdown(pack) {
 const lines = [
  `# ${pack.banner}`,
  `Contains Minor PII: ${pack.contains_minor_pii} | Instructional Accuracy Verified: ${pack.all_instructional_accuracy_verified}`,
  ''
 ];
 for (const d of pack.days) {
  lines.push(`- **${d.day}**: ${d.topic} — ${d.activity} [${d.accuracy_verified_by_tutor ? 'TUTOR-VERIFIED' : 'NEEDS ACCURACY CHECK'}]`);
 }
 return lines.join('\n');
}
