/**
 * Trial 1 (IL-3-0): Local public-record revision digest — Two-snapshot diff engine.
 * Enforces hard boundary: "Do not infer motives from record changes; cite primary sources"
 * Acceptance test: "The viewer identifies changed rows without attributing motives or calling fictional records real."
 */

export const FICTIONAL_BANNER = 'FICTIONAL SAMPLE RECORD — NOT OFFICIAL PUBLIC DATA';

const SPECULATIVE_MOTIVE_PATTERNS = [
 /\b(corrupt|corruption|bribe|bribed|secretly|conspiracy|ulterior|payoff|kickback|agenda|dishonest|flip-flopped|betrayed|pandering)\b/i
];

export const SNAPSHOT_A = [
 {record_id:'ORD-2026-101',section:'Zoning §4.2',vote_tally:'4-1 Approve',summary:'Permits accessory solar canopies up to 14ft.',source_ref:'fictional://council-minutes/2026-10-01#item-4'},
 {record_id:'ORD-2026-102',section:'Budget §9.1',vote_tally:'5-0 Approve',summary:'Allocates $45,000 for crosswalk repainting.',source_ref:'fictional://council-minutes/2026-10-01#item-9'},
 {record_id:'ORD-2026-103',section:'Procurement §2.4',vote_tally:'3-2 Table',summary:'Defers municipal fleet battery lease review.',source_ref:'fictional://council-minutes/2026-10-01#item-12'}
];

export const SNAPSHOT_B = [
 {record_id:'ORD-2026-101',section:'Zoning §4.2',vote_tally:'5-0 Approve',summary:'Permits accessory solar canopies up to 16ft.',source_ref:'fictional://council-minutes/2026-10-15#item-4'},
 {record_id:'ORD-2026-102',section:'Budget §9.1',vote_tally:'5-0 Approve',summary:'Allocates $45,000 for crosswalk repainting.',source_ref:'fictional://council-minutes/2026-10-15#item-9'},
 {record_id:'ORD-2026-104',section:'Transit §6.0',vote_tally:'4-1 Approve',summary:'Adds weekend shuttle stop at community library.',source_ref:'fictional://council-minutes/2026-10-15#item-15'}
];

export function assertMotiveNeutral(text) {
 const str = String(text ?? '');
 for (const pat of SPECULATIVE_MOTIVE_PATTERNS) {
  if (pat.test(str)) {
   throw new Error('Motive inference refused: digest must state factual field changes and cite sources only.');
  }
 }
 return str;
}

export function diffSnapshots(snapA, snapB, note = '') {
 assertMotiveNeutral(note);
 const mapA = new Map(snapA.map(r => [r.record_id, r]));
 const mapB = new Map(snapB.map(r => [r.record_id, r]));
 const allIds = Array.from(new Set([...mapA.keys(), ...mapB.keys()])).sort();
 const rows = [];
 for (const id of allIds) {
  const a = mapA.get(id) || null;
  const b = mapB.get(id) || null;
  if (a) { assertMotiveNeutral(a.summary); if (!a.source_ref) throw new Error(`Missing source_ref on ${id}`); }
  if (b) { assertMotiveNeutral(b.summary); if (!b.source_ref) throw new Error(`Missing source_ref on ${id}`); }
  if (a && !b) {
   rows.push({record_id: id, status: 'REMOVED', changed_fields: ['record_removed'], before: a, after: null, primary_sources: [a.source_ref], fictional_notice: FICTIONAL_BANNER});
  } else if (!a && b) {
   rows.push({record_id: id, status: 'ADDED', changed_fields: ['record_added'], before: null, after: b, primary_sources: [b.source_ref], fictional_notice: FICTIONAL_BANNER});
  } else {
   const changed = ['section', 'vote_tally', 'summary'].filter(k => a[k] !== b[k]);
   rows.push({
    record_id: id,
    status: changed.length ? 'MODIFIED' : 'UNCHANGED',
    changed_fields: changed,
    before: a,
    after: b,
    primary_sources: Array.from(new Set([a.source_ref, b.source_ref])),
    fictional_notice: FICTIONAL_BANNER
   });
  }
 }
 return {
  fictional_only: true,
  banner: FICTIONAL_BANNER,
  motive_attribution_allowed: false,
  changed_count: rows.filter(r => r.status !== 'UNCHANGED').length,
  rows
 };
}
