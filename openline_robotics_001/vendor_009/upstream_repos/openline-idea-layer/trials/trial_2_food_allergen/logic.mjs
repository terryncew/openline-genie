/**
 * Trial 2 (IL-8-0): Menu and allergen disclosure worksheet service.
 * Enforces hard boundary: "Human verification mandatory; never assert food safety certification"
 * Acceptance test: "Unchecked entries never appear verified and no safety certification is implied."
 */

export const NON_CERTIFICATION_DISCLAIMER = 'DRAFT WORKSHEET ONLY — NOT A FOOD SAFETY CERTIFICATION OR LEGAL COMPLIANCE GUARANTEE';

export const INITIAL_FICTIONAL_MENU = [
 {item_id:'M-01',name:'Roasted Sesame Noodle Bowl (Fictional)',allergens:['Sesame','Soy','Wheat'],cross_contact_note:'Prepared on shared wok line',human_checked:false,reviewer_name:''},
 {item_id:'M-02',name:'Citrus Herb Chickpea Salad (Fictional)',allergens:[],cross_contact_note:'Dedicated cold prep table',human_checked:true,reviewer_name:'Chef Taylor (Mock Staff)'},
 {item_id:'M-03',name:'Almond Espresso Brownie (Fictional)',allergens:['Tree Nuts (Almond)','Eggs','Milk'],cross_contact_note:'Shared bakery oven',human_checked:false,reviewer_name:''}
];


// UI rule: a dish may only be marked human-checked by a real, named reviewer.
// The page must never invent a reviewer name — a tick without a name stays unverified.
export function canMarkHumanChecked(item) {
 return !!item && typeof item.reviewer_name === 'string' && item.reviewer_name.trim().length > 0;
}

export function evaluateWorksheet(items) {
 if (!Array.isArray(items) || items.length === 0) throw new Error('Menu items required');
 const evaluated = items.map(item => {
  const checked = item.human_checked === true && typeof item.reviewer_name === 'string' && item.reviewer_name.trim().length > 0;
  return {
   item_id: String(item.item_id),
   name: String(item.name),
   allergens: Array.isArray(item.allergens) ? item.allergens.map(String) : [],
   cross_contact_note: String(item.cross_contact_note ?? ''),
   human_checked: checked,
   reviewer_name: checked ? item.reviewer_name.trim() : '',
   verification_badge: checked ? `HUMAN-REVIEWED BY ${item.reviewer_name.trim()}` : 'UNVERIFIED — MANDATORY HUMAN CHECK REQUIRED',
   certified_safe: false
  };
 });
 return {
  disclaimer: NON_CERTIFICATION_DISCLAIMER,
  implies_safety_certification: false,
  ready_for_staff_signoff: evaluated.every(x => x.human_checked),
  unverified_count: evaluated.filter(x => !x.human_checked).length,
  items: evaluated
 };
}

export function exportPrintableWorksheet(items) {
 const state = evaluateWorksheet(items);
 const lines = [
  `# ${NON_CERTIFICATION_DISCLAIMER}`,
  `Unverified items requiring staff check: ${state.unverified_count}`,
  ''
 ];
 for (const it of state.items) {
  lines.push(`- [${it.verification_badge}] ${it.name} | Allergens: ${it.allergens.join(', ') || 'None listed (verify ingredients)'} | Note: ${it.cross_contact_note}`);
 }
 return lines.join('\n');
}
