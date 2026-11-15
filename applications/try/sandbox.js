/* OpenLine Genie sandbox. Local only. No receiver, no signed receipts.
 *
 * Engine math: deterministic ports of the real Python engine, verified
 * against it in evidence/phase3/crosscheck. Bakery ports core/bakery.py
 * (compute_bakery), garden ports core/community_garden.py
 * (compute_garden), neural ports core/model_optimizer.py
 * (compute_neural_model). The frozen living_world/graph_core.mjs does
 * the min-of-constraints projection (computeConstraintResonance), the
 * option comparison (evaluateInterventionCounterfactual), and the
 * synergy search (discoverSynergisticCombos) on top of those numbers.
 * The sandbox never calls the network: no fetch, no /api calls, no
 * external resources. A Content-Security-Policy of connect-src 'none'
 * is set in index.html, and the guard below makes any fetch, XHR, or
 * WebSocket attempt throw instead of sending.
 */
import {
  sha256Hex, canonicalJson, clone,
  computeConstraintResonance, computeCounterfactualIntelligence
} from '../living_world/graph_core.mjs';

/* Fail closed on any network attempt. */
if (typeof window !== 'undefined') {
  const blocked = () => { throw new Error('Sandbox blocked a network call. This page makes no network calls.'); };
  window.fetch = blocked;
  if (window.XMLHttpRequest) {
    window.XMLHttpRequest.prototype.open = blocked;
    window.XMLHttpRequest.prototype.send = blocked;
  }
  if (window.WebSocket) window.WebSocket = class { constructor() { throw new Error('Sandbox blocked a network call.'); } };
  if (navigator && navigator.sendBeacon) navigator.sendBeacon = () => false;
}

export const SANDBOX_VERSION = 'Local sandbox v1 (Genie v0.7.1 engine math)';

/* ------------------------------------------------------------------ */
/* Deterministic domain math. Exact ports of the Python engine.        */
/* ------------------------------------------------------------------ */

export const BAKERY_BASELINE = {
  ovens: 1, decks_per_oven: 1, batch_size_loaves: 29, cycle_minutes: 50,
  bake_window_minutes: 300, bakers: 1, loaves_per_baker_per_shift: 240,
  extra_baker_loaves: 160, staggered_shift_bonus_loaves: 60,
  shift_pattern: '05:00-13:00', staggered_shift: false,
  proofing_rack_loaves: 280, extra_retarder_racks: 0, retarder_rack_loaves: 60,
  demand_loaves_per_day: 320, shop_capacity_loaves: 300,
  schedule_capacity_loaves: 360, wish_capacity_loaves: 500,
  scenario_capacity_loaves: 400, margin_per_loaf_usd: 4.5,
  fixed_cost_usd_per_day: 140, uncertainty_pct: 7
};
const BAKERY_PRICES = {
  oven2: { capex_usd: 18500, fixed_cost_delta_usd: 15 },
  hours: { capex_usd: 0, fixed_cost_delta_usd: 35 },
  add_baker: { capex_usd: 600, fixed_cost_delta_usd: 165 },
  retarder_rack: { capex_usd: 3200, fixed_cost_delta_usd: 12 }
};

export function computeBakery(a0) {
  const a = { ...BAKERY_BASELINE, ...a0 };
  for (const k of ['ovens', 'decks_per_oven', 'batch_size_loaves', 'cycle_minutes',
    'bake_window_minutes', 'bakers', 'loaves_per_baker_per_shift',
    'proofing_rack_loaves', 'demand_loaves_per_day', 'shop_capacity_loaves',
    'schedule_capacity_loaves']) {
    const v = a[k];
    if (typeof v === 'boolean' || typeof v !== 'number' || !Number.isFinite(v) || v <= 0) {
      throw new Error('invalid_bakery_assumption:' + k);
    }
  }
  if (a.extra_retarder_racks < 0) throw new Error('invalid_bakery_assumption:extra_retarder_racks');
  const oven = Math.round(a.ovens * a.decks_per_oven * a.batch_size_loaves * (a.bake_window_minutes / a.cycle_minutes));
  const staff = a.loaves_per_baker_per_shift + (a.bakers - 1) * a.extra_baker_loaves
    + (a.staggered_shift ? a.staggered_shift_bonus_loaves : 0);
  const ingredients = a.proofing_rack_loaves + a.extra_retarder_racks * a.retarder_rack_loaves;
  const capacities = {
    wish: a.wish_capacity_loaves, demand: a.demand_loaves_per_day,
    ingredients, staff, oven, schedule: a.schedule_capacity_loaves,
    shop: a.shop_capacity_loaves, scenario: a.scenario_capacity_loaves
  };
  const bottleneckId = Object.keys(capacities).reduce((m, k) => capacities[k] < capacities[m] ? k : m, 'wish');
  const throughput = capacities[bottleneckId];
  const fixed = a.fixed_cost_usd_per_day + (a.ovens - 1) * 15
    + (a.staggered_shift ? 35 : 0) + (a.bakers - 1) * 165 + a.extra_retarder_racks * 12;
  const capex = (a.ovens - 1) * 18500 + (a.bakers - 1) * 600 + a.extra_retarder_racks * 3200;
  const net = Math.round(throughput * a.margin_per_loaf_usd - fixed);
  return {
    capacities, throughput, bottleneckId, bottleneckLabel: bottleneckId,
    unit: 'loaves/day', uncertaintyPct: a.uncertainty_pct,
    band: [Math.round(throughput * 0.93), Math.round(throughput * 1.07)],
    netLabel: 'Planning net', netValue: net, netUnit: '$/day',
    fixedCost: fixed, capex
  };
}

export const GARDEN_BASELINE = {
  cistern_gallons_per_week: 420, municipal_supp_gallons_per_week: 0,
  gallons_per_lb_produce: 4.0, drip_mulch_enabled: false,
  volunteer_hours_per_week: 18, lbs_per_volunteer_hour: 7.5,
  plot_beds_count: 12, lbs_per_bed_per_week: 12.5,
  legume_rotation_coverage_pct: 25, wash_station_capacity_lbs: 180,
  member_demand_lbs_per_week: 200, produce_value_usd_per_lb: 3.5,
  weekly_operating_cost_usd: 45.0, uncertainty_pct: 8
};

export function computeGarden(a0) {
  const a = { ...GARDEN_BASELINE, ...a0 };
  for (const k of ['cistern_gallons_per_week', 'volunteer_hours_per_week',
    'lbs_per_volunteer_hour', 'plot_beds_count', 'lbs_per_bed_per_week',
    'wash_station_capacity_lbs', 'member_demand_lbs_per_week']) {
    const v = a[k];
    if (typeof v === 'boolean' || typeof v !== 'number' || !Number.isFinite(v) || v <= 0) {
      throw new Error('invalid_garden_assumption:' + k);
    }
  }
  if (a.municipal_supp_gallons_per_week < 0) throw new Error('invalid_garden_assumption:municipal_supp_gallons_per_week');
  const totalWater = a.cistern_gallons_per_week + a.municipal_supp_gallons_per_week;
  const galPerLb = a.drip_mulch_enabled ? 2.625 : a.gallons_per_lb_produce;
  if (galPerLb <= 0) throw new Error('invalid_gallons_per_lb_produce');
  const water = Math.round(totalWater / galPerLb);
  const volunteers = Math.round(a.volunteer_hours_per_week * a.lbs_per_volunteer_hour);
  const plots = Math.round(a.plot_beds_count * a.lbs_per_bed_per_week);
  const capacities = {
    water, volunteers, plots,
    wash_station: a.wash_station_capacity_lbs, demand: a.member_demand_lbs_per_week
  };
  const bottleneckId = Object.keys(capacities).reduce((m, k) => capacities[k] < capacities[m] ? k : m, 'water');
  const throughput = capacities[bottleneckId];
  const muniUnits = Math.max(0, Math.round(a.municipal_supp_gallons_per_week / 120));
  const volUnits = Math.max(0, Math.round((a.volunteer_hours_per_week - 18) / 4));
  const bedUnits = Math.max(0, Math.round((a.plot_beds_count - 12) / 4));
  const weeklyCost = a.weekly_operating_cost_usd + muniUnits * 18 + volUnits * 8 + bedUnits * 10;
  const capex = (a.drip_mulch_enabled ? 280 : 0) + volUnits * 60 + bedUnits * 640;
  const net = Math.round((throughput * a.produce_value_usd_per_lb - weeklyCost) * 100) / 100;
  return {
    capacities, throughput, bottleneckId, bottleneckLabel: bottleneckId,
    unit: 'lbs/week', uncertaintyPct: a.uncertainty_pct,
    band: [Math.round(throughput * 0.92), Math.round(throughput * 1.08)],
    netLabel: 'Planning net value', netValue: net, netUnit: '$/week',
    fixedCost: weeklyCost, capex
  };
}

export const NEURAL_BASELINE = {
  spectral_repaired: false, curriculum_filtered: false,
  temperature_calibrated: false, int8_quantized: false,
  naive_pruned: false, blind_sgd_steps: 0,
  compute_budget_units: 12, uncertainty_pct: 5
};

export function computeNeural(a0) {
  const a = { ...NEURAL_BASELINE, ...a0 };
  const specOk = Boolean(a.spectral_repaired);
  const currOk = Boolean(a.curriculum_filtered);
  const calOk = Boolean(a.temperature_calibrated && a.int8_quantized);
  const blind = a.blind_sgd_steps | 0;
  const spectralCap = specOk ? 92 : (blind > 0 ? 56 : 52);
  const dataCap = currOk ? (specOk ? 90 : 55) : (blind > 0 ? 60 : 64);
  const calCap = calOk ? 94 : 74;
  const capacities = {
    spectral_flow: spectralCap, data_subspace: dataCap,
    calibration_efficiency: calCap, architecture_ceiling: 95
  };
  const bottleneckId = Object.keys(capacities).reduce((m, k) => capacities[k] < capacities[m] ? k : m, 'spectral_flow');
  const throughput = capacities[bottleneckId];
  const capex = (specOk ? 2 : 0) + (currOk ? 3 : 0) + (calOk ? 2 : 0) + 3 * Math.max(0, Math.floor(blind / 28));
  return {
    capacities, throughput, bottleneckId, bottleneckLabel: bottleneckId,
    unit: 'frontier_pts', uncertaintyPct: a.uncertainty_pct,
    band: [Math.round(throughput * 0.95), Math.round(throughput * 1.05)],
    netLabel: 'Net utility', netValue: Math.round((throughput - capex * 0.5) * 100) / 100,
    netUnit: 'pts', fixedCost: capex, capex,
    memBytes: calOk ? 1856 : 6916, ece: calOk ? 0.042 : (currOk ? 0.148 : 0.215)
  };
}

/* ------------------------------------------------------------------ */
/* Domain definitions: stations, editable fields, option paths.        */
/* ------------------------------------------------------------------ */

const STATION_LABELS = {
  bakery: { oven: 'Oven', staff: 'Staff', ingredients: 'Ingredients', demand: 'Demand', shop: 'Shop experience', schedule: 'Production plan', scenario: 'What-if scenario' },
  garden: { water: 'Cistern and Irrigation', volunteers: 'Volunteer Crew', plots: 'Raised Crop Beds', wash_station: 'Wash and Pack Shed', demand: 'Neighborhood Share' },
  neural: { spectral_flow: 'Spectral SVD and GELU', data_subspace: 'Curriculum Filter', calibration_efficiency: 'INT8 and Temp Calibration', architecture_ceiling: 'Evaluator Holdout' }
};

export const DOMAINS = {
  bakery: {
    title: 'Hearth and Crumb Bakery', unit: 'loaves/day', baseline: BAKERY_BASELINE,
    compute: computeBakery, margin: 4.5,
    wishLabel: 'Your wish', wishDetail: 'Design a small neighborhood bakery.',
    stationDetail(a, c, id) {
      if (id === 'oven') return `${a.ovens} steam-injected deck oven${a.ovens > 1 ? 's' : ''}: ${a.batch_size_loaves} loaves/batch, ${a.cycle_minutes}-min cycle, ${a.bake_window_minutes / a.cycle_minutes} batches/day = ${c.capacities.oven} loaves/day of oven capacity.`;
      if (id === 'staff') return `${a.bakers} baker${a.bakers > 1 ? 's' : ''} shaping and loading${a.staggered_shift ? ', staggered 04:30-14:30 shift' : ', 05:00-13:00 shift'}: ${c.capacities.staff} loaves/day.`;
      if (id === 'ingredients') return `Stone-milled flour silo and ${a.proofing_rack_loaves}-loaf cold retarder rack${a.extra_retarder_racks ? ` plus ${a.extra_retarder_racks} extra rack(s)` : ''}: ${c.capacities.ingredients} loaves/day.`;
      if (id === 'demand') return `Neighborhood morning and cafe wholesale demand: ${c.capacities.demand} loaves/day (stated assumption).`;
      if (id === 'shop') return `Espresso and warm loaf counter service: ${c.capacities.shop} loaves/day.`;
      if (id === 'schedule') return `Batch sequencer and bottleneck solver: ${c.capacities.schedule} loaves/day.`;
      return `What-if comparison of accepted and proposed plans: ${c.capacities.scenario} loaves/day.`;
    },
    fields(a, id) {
      if (id === 'staff') return [
        { key: 'bakers', label: 'Bakers on shift', type: 'number', min: 1, max: 10, step: 1, val: a.bakers },
        { key: 'loaves_per_baker_per_shift', label: 'Loaves / baker / shift', type: 'number', min: 40, max: 600, step: 10, val: a.loaves_per_baker_per_shift },
        { key: 'staggered_shift', label: 'Staggered shift (+60/day)', type: 'boolean', val: Boolean(a.staggered_shift) }];
      if (id === 'ingredients') return [
        { key: 'proofing_rack_loaves', label: 'Base proofing rack (loaves)', type: 'number', min: 60, max: 1000, step: 10, val: a.proofing_rack_loaves },
        { key: 'extra_retarder_racks', label: 'Extra retarder racks (+60 each)', type: 'number', min: 0, max: 10, step: 1, val: a.extra_retarder_racks }];
      if (id === 'demand' || id === 'shop') return [
        { key: 'shop_capacity_loaves', label: 'Shop counter limit (loaves/day)', type: 'number', min: 60, max: 1000, step: 10, val: a.shop_capacity_loaves },
        { key: 'demand_loaves_per_day', label: 'Stated daily demand (loaves/day)', type: 'number', min: 60, max: 1000, step: 10, val: a.demand_loaves_per_day }];
      return [
        { key: 'ovens', label: 'Steam deck ovens', type: 'number', min: 1, max: 8, step: 1, val: a.ovens },
        { key: 'batch_size_loaves', label: 'Loaves per batch', type: 'number', min: 6, max: 120, step: 1, val: a.batch_size_loaves },
        { key: 'cycle_minutes', label: 'Bake cycle (minutes)', type: 'number', min: 15, max: 180, step: 5, val: a.cycle_minutes },
        { key: 'bake_window_minutes', label: 'Bake window (minutes)', type: 'number', min: 60, max: 720, step: 30, val: a.bake_window_minutes }];
    },
    formula(a, vals, id) {
      if (id === 'staff') return `${vals.bakers} baker(s) (${vals.loaves_per_baker_per_shift}/shift)${vals.staggered_shift ? ' + staggered (+60)' : ''} = ${Number(vals.loaves_per_baker_per_shift) + (Number(vals.bakers) - 1) * 160 + (vals.staggered_shift ? 60 : 0)} loaves/day staff capacity`;
      if (id === 'ingredients') return `${vals.proofing_rack_loaves} base + ${vals.extra_retarder_racks} x 60 retarder = ${Number(vals.proofing_rack_loaves) + Number(vals.extra_retarder_racks) * 60} loaves/day proofing capacity`;
      if (id === 'demand' || id === 'shop') return `Shop counter: ${vals.shop_capacity_loaves} loaves/day. Stated demand: ${vals.demand_loaves_per_day} loaves/day.`;
      const cyc = Math.max(1, Number(vals.cycle_minutes) || 50);
      const cap = Math.round(Number(vals.ovens) * Number(vals.batch_size_loaves) * (Number(vals.bake_window_minutes) / cyc));
      return `${vals.ovens} oven(s) x ${vals.batch_size_loaves} loaves/batch x (${vals.bake_window_minutes}/${cyc}m) = ${cap} loaves/day oven capacity`;
    },
    paths: [
      { id: 'oven2', label: 'Another oven?', target: 'oven', detail: 'Add Deck Oven #2. Oven capacity rises; Staff becomes the limit.', patch: a => ({ ovens: a.ovens + 1 }), prices: BAKERY_PRICES.oven2 },
      { id: 'hours', label: 'Adjust shift schedule', target: 'staff', detail: 'Staggered 04:30-14:30 bake shift lifts Staff 240 to 300 loaves/day (+$35/day).', patch: () => ({ staggered_shift: true, shift_pattern: '04:30-14:30 staggered' }), prices: BAKERY_PRICES.hours },
      { id: 'add_baker', label: 'Add a second baker', target: 'staff', detail: 'Lift Staff limit by 160 loaves/day (+$165/day wage) to unlock a 2nd oven.', patch: a => ({ bakers: a.bakers + 1 }), prices: BAKERY_PRICES.add_baker },
      { id: 'retarder_rack', label: 'Add cold retarder rack', target: 'ingredients', detail: 'Expand cold fermentation and proofing rack by 60 loaves/day (+$12/day power).', patch: a => ({ extra_retarder_racks: a.extra_retarder_racks + 1 }), prices: BAKERY_PRICES.retarder_rack }
    ]
  },
  garden: {
    title: 'Sunnyvale Community Garden', unit: 'lbs/week', baseline: GARDEN_BASELINE,
    compute: computeGarden, margin: 3.5,
    wishLabel: 'Your wish', wishDetail: 'Plan a neighborhood community garden with 4-family crop rotation, cistern drip irrigation, and volunteer harvest.',
    stationDetail(a, c, id) {
      if (id === 'water') return `${a.cistern_gallons_per_week} gal/wk rainwater cistern${a.municipal_supp_gallons_per_week ? ` + ${a.municipal_supp_gallons_per_week} gal/wk municipal tap` : ''} at ${a.drip_mulch_enabled ? '2.625' : '4.0'} gal/lb = ${c.capacities.water} lbs/week water capacity.`;
      if (id === 'volunteers') return `${a.volunteer_hours_per_week} volunteer hrs/week x ${a.lbs_per_volunteer_hour} lbs/hr = ${c.capacities.volunteers} lbs/week harvest capacity.`;
      if (id === 'plots') return `${a.plot_beds_count} raised beds x ${a.lbs_per_bed_per_week} lbs/bed/week across 4 rotation families = ${c.capacities.plots} lbs/week soil capacity.`;
      if (id === 'wash_station') return `Cold-rinse tables, harvest scale, and crate packing station (${c.capacities.wash_station} lbs/week capacity).`;
      return `Weekly member harvest boxes and community food-pantry share demand (${c.capacities.demand} lbs/week).`;
    },
    fields(a, id) {
      if (id === 'volunteers') return [
        { key: 'volunteer_hours_per_week', label: 'Volunteer hours / week', type: 'number', min: 2, max: 120, step: 2, val: a.volunteer_hours_per_week },
        { key: 'lbs_per_volunteer_hour', label: 'Harvest rate (lbs/hr)', type: 'number', min: 1, max: 30, step: 0.5, val: a.lbs_per_volunteer_hour }];
      if (id === 'plots') return [
        { key: 'plot_beds_count', label: 'Raised crop beds', type: 'number', min: 2, max: 60, step: 2, val: a.plot_beds_count },
        { key: 'lbs_per_bed_per_week', label: 'Yield per bed (lbs/wk)', type: 'number', min: 2, max: 40, step: 0.5, val: a.lbs_per_bed_per_week }];
      return [
        { key: 'cistern_gallons_per_week', label: 'Cistern supply (gal/wk)', type: 'number', min: 60, max: 2000, step: 20, val: a.cistern_gallons_per_week },
        { key: 'municipal_supp_gallons_per_week', label: 'Municipal tap supply (gal/wk)', type: 'number', min: 0, max: 1000, step: 30, val: a.municipal_supp_gallons_per_week },
        { key: 'drip_mulch_enabled', label: 'Drip headers + straw mulch', type: 'boolean', val: Boolean(a.drip_mulch_enabled) }];
    },
    formula(a, vals, id) {
      if (id === 'volunteers') return `${vals.volunteer_hours_per_week} hrs/wk x ${vals.lbs_per_volunteer_hour} lbs/hr = ${Math.round(Number(vals.volunteer_hours_per_week) * Number(vals.lbs_per_volunteer_hour))} lbs/week volunteer capacity`;
      if (id === 'plots') return `${vals.plot_beds_count} beds x ${vals.lbs_per_bed_per_week} lbs/bed = ${Math.round(Number(vals.plot_beds_count) * Number(vals.lbs_per_bed_per_week))} lbs/week bed capacity`;
      const gpl = vals.drip_mulch_enabled ? 2.625 : 4.0;
      const tot = Number(vals.cistern_gallons_per_week) + Number(vals.municipal_supp_gallons_per_week || 0);
      return `${tot} gal/wk divided by ${gpl} gal/lb = ${Math.round(tot / gpl)} lbs/week water capacity`;
    },
    paths: [
      { id: 'drip_mulch', label: 'Install drip headers + mulch', target: 'water', detail: 'Cuts water needed per lb from 4.0 to 2.625 gal/lb. Water capacity 105 to 160 lbs/week; limit moves to Volunteer Crew at 135 lbs/week.', patch: () => ({ drip_mulch_enabled: true, gallons_per_lb_produce: 2.625, legume_rotation_coverage_pct: 50 }), prices: { capex_usd: 280, fixed_cost_delta_usd: 0 } },
      { id: 'municipal_tap', label: 'Add metered municipal hose timer', target: 'water', detail: 'Adds +120 gal/week municipal tap water (+30 lbs/week water capacity, $0 CapEx, +$18/week utility bill).', patch: a => ({ municipal_supp_gallons_per_week: a.municipal_supp_gallons_per_week + 120 }), prices: { capex_usd: 0, fixed_cost_delta_usd: 18 } },
      { id: 'weekend_workday', label: 'Add Saturday 4-hr volunteer shift', target: 'volunteers', detail: 'Expands volunteer crew +4 hrs/week (+30 lbs/week labor capacity). Alone it gains +0 while water caps output at 105 lbs/week.', patch: a => ({ volunteer_hours_per_week: a.volunteer_hours_per_week + 4 }), prices: { capex_usd: 60, fixed_cost_delta_usd: 8 } },
      { id: 'extra_beds', label: 'Build 4 additional raised beds', target: 'plots', detail: 'Adds 4 compost-amended raised beds (+50 lbs/week plot capacity, $640 lumber/soil CapEx, +$10/week upkeep).', patch: a => ({ plot_beds_count: a.plot_beds_count + 4 }), prices: { capex_usd: 640, fixed_cost_delta_usd: 10 } }
    ]
  },
  neural: {
    title: 'ResidualMLP Checkpoint Optimizer', unit: 'frontier_pts', baseline: NEURAL_BASELINE,
    compute: computeNeural, margin: 2.0,
    wishLabel: 'Your wish', wishDetail: 'Optimize a local ResidualMLP checkpoint: accuracy, calibration, and size, under a lab-internal evaluator holdout (research-scoped; not independent verification).',
    stationDetail(a, c, id) {
      if (id === 'spectral_flow') return `Layer W2 singular spectrum and GELU activation flow (${a.spectral_repaired ? 'Repaired: rank restored, dead units reactivated' : 'Collapsed: 34% dead units'}; ${c.capacities.spectral_flow} frontier_pts).`;
      if (id === 'data_subspace') return `Training sample subspace and outlier gate (${a.curriculum_filtered ? '18% corrupted outliers filtered + cosine schedule' : 'Unfiltered 18% noisy outliers active'}; ${c.capacities.data_subspace} frontier_pts).`;
      if (id === 'calibration_efficiency') return `Post-logit temperature scaling and weight quantization (${a.temperature_calibrated && a.int8_quantized ? 'INT8 1,623B, ECE 0.042' : 'FP32 7,444B, ECE 0.215'}; ${c.capacities.calibration_efficiency} frontier_pts).`;
      return `Lab-internal evaluator holdout benchmark (${c.memBytes}B checkpoint, ECE ${c.ece}, ceiling ${c.capacities.architecture_ceiling} frontier_pts). Research-scoped receipt, not independent verification.`;
    },
    fields(a) {
      return [
        { key: 'spectral_repaired', label: 'Spectral SVD and GELU repair', type: 'boolean', val: Boolean(a.spectral_repaired) },
        { key: 'curriculum_filtered', label: 'Curriculum 18% outlier filter', type: 'boolean', val: Boolean(a.curriculum_filtered) },
        { key: 'temperature_calibrated', label: 'Logit temperature calibration', type: 'boolean', val: Boolean(a.temperature_calibrated) },
        { key: 'int8_quantized', label: 'Symmetric INT8 quantization', type: 'boolean', val: Boolean(a.int8_quantized) }];
    },
    formula(a, vals) {
      const s = vals.spectral_repaired ? 92 : (a.blind_sgd_steps > 0 ? 56 : 52);
      const d = vals.curriculum_filtered ? (vals.spectral_repaired ? 90 : 55) : (a.blind_sgd_steps > 0 ? 60 : 64);
      const c = (vals.temperature_calibrated && vals.int8_quantized) ? 94 : 74;
      return `Stage ceilings: Spectral ${s}. Curriculum ${d}. Calibration ${c}. Frontier ${Math.min(s, d, c, 95)} frontier_pts`;
    },
    paths: [
      { id: 'spectral_repair', label: 'Repair collapsed singular spectrum', target: 'spectral_flow', detail: 'Restores W2 singular value spectrum and reactivates dead GELU units (Spectral 52 to 92 frontier_pts; limit moves to Curriculum Filter at 64).', patch: () => ({ spectral_repaired: true }), prices: { capex_usd: 2, fixed_cost_delta_usd: 0 } },
      { id: 'curriculum_finetune', label: 'Filter 18% outliers + cosine fine-tune', target: 'data_subspace', detail: 'Downweights 18% noisy training outliers and runs cosine fine-tuning. Clamped at 52 until Spectral SVD is repaired.', patch: () => ({ curriculum_filtered: true }), prices: { capex_usd: 3, fixed_cost_delta_usd: 0 } },
      { id: 'calibrated_int8', label: 'Calibrate temperature + INT8 quantize', target: 'calibration_efficiency', detail: 'Calibrates temperature (ECE 0.215 to 0.042) and compresses weights about 4.6x (Calibration 74 to 94 frontier_pts).', patch: () => ({ temperature_calibrated: true, int8_quantized: true }), prices: { capex_usd: 2, fixed_cost_delta_usd: -1 } },
      { id: 'blind_sgd', label: 'Run conventional unfiltered SGD', target: 'spectral_flow', detail: 'Conventional comparator: 28 steps of unfiltered SGD (+4 Spectral frontier_pts; leaves dead units and outliers unresolved).', patch: a => ({ blind_sgd_steps: a.blind_sgd_steps + 28 }), prices: { capex_usd: 3, fixed_cost_delta_usd: 1 } }
    ]
  }
};

/* ------------------------------------------------------------------ */
/* graph_core projection: build a graph from computed capacities and   */
/* let the frozen engine do resonance, counterfactuals, and synergy.   */
/* ------------------------------------------------------------------ */

export function buildGraph(domainKey, assumptions) {
  const def = DOMAINS[domainKey];
  const c = def.compute(assumptions);
  const nodes = [{ id: 'wish', label: def.wishLabel, category: 'intent', detail: def.wishDetail, state: 'accepted', capacity: 500, unit: def.unit }];
  for (const id of Object.keys(c.capacities)) {
    if (id === 'wish') continue;
    nodes.push({
      id, label: STATION_LABELS[domainKey][id] || id, category: 'resource',
      detail: def.stationDetail(assumptions, c, id), state: 'accepted',
      capacity: c.capacities[id], unit: def.unit
    });
  }
  const paths = def.paths.map(p => {
    const cand = { ...assumptions, ...p.patch(assumptions) };
    const candC = def.compute(cand);
    return {
      id: p.id, label: p.label, detail: p.detail, after: p.target,
      delta: {
        node: p.target,
        capacity_delta: candC.capacities[p.target] - c.capacities[p.target],
        capex_usd: p.prices.capex_usd,
        fixed_cost_delta_usd: p.prices.fixed_cost_delta_usd,
        summary: p.label
      }
    };
  });
  paths.push({ id: 'portable', label: 'Keep what I have', detail: 'Preserve accepted project state.', after: nodes[nodes.length - 1].id, export: true });
  const graph = {
    schema: 'openline.graph-communication.v0.5',
    id: 'sandbox-' + domainKey, title: def.title, domain_unit: def.unit,
    baseline_metrics: {
      daily_capacity: c.throughput, unit: def.unit,
      margin_per_loaf_usd: def.margin, fixed_cost_usd: c.fixedCost,
      net_daily_usd: typeof c.netValue === 'number' ? c.netValue : 0,
      uncertainty_pct: c.uncertaintyPct
    },
    source: 'LOCAL_SIMULATION_NOT_MODEL_EXECUTION',
    nodes, edges: [], paths
  };
  const res = computeConstraintResonance(graph, {});
  if (res.system_throughput !== c.throughput) {
    throw new Error(`sandbox_resonance_mismatch:${domainKey}:${res.system_throughput}!=${c.throughput}`);
  }
  graph.constraint_resonance = res;
  graph.counterfactual_intelligence = computeCounterfactualIntelligence(graph, {});
  return { graph, computed: c, resonance: res, intel: graph.counterfactual_intelligence };
}

export function stateChecksum(assumptions) {
  return sha256Hex(canonicalJson(assumptions));
}

/* ------------------------------------------------------------------ */
/* Browser UI. Runs only when document exists (Node imports the        */
/* engine above for cross-checks without touching the DOM).            */
/* ------------------------------------------------------------------ */

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  let domain = 'bakery';
  let accepted = clone(DOMAINS.bakery.baseline);
  let preview = null; /* {label, detail, before, after, bottleneckAfter, apply()} */
  let stopped = false;
  let selectedStation = 'oven';
  let version = 1;

  function current() { return buildGraph(domain, accepted); }
  function def() { return DOMAINS[domain]; }

  function log(kind, text) {
    const li = document.createElement('li');
    li.textContent = `${new Date().toLocaleTimeString()} ${kind}: ${text} (Local sandbox note. Not a signed receipt.)`;
    $('logList').prepend(li);
  }

  function render() {
    const { computed, resonance, intel } = current();
    const d = def();
    $('acceptedLine').textContent = `${computed.throughput} ${computed.unit} (v${version}, local only)`;
    $('limitLine').textContent = `${STATION_LABELS[domain][computed.bottleneckId] || computed.bottleneckId} (${computed.throughput} ${computed.unit})`;
    $('stateChecksum').textContent = stateChecksum(accepted).slice(0, 16) + '...';
    $('versionLine').textContent = `${SANDBOX_VERSION} · ${d.title}`;

    for (const b of document.querySelectorAll('#domainTabs button')) {
      b.setAttribute('aria-pressed', String(b.dataset.domain === domain));
    }

    /* Stations */
    const list = $('stationList');
    list.replaceChildren();
    for (const id of Object.keys(computed.capacities)) {
      if (id === 'wish') continue;
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'station'; b.dataset.stationId = id;
      b.setAttribute('role', 'listitem');
      b.setAttribute('aria-pressed', String(selectedStation === id));
      const isLimit = id === computed.bottleneckId;
      b.innerHTML = '';
      const strong = document.createElement('strong');
      strong.textContent = (STATION_LABELS[domain][id] || id) + (isLimit ? ' (LIMIT)' : '');
      const cap = document.createElement('span');
      cap.className = 'cap';
      cap.textContent = `${computed.capacities[id]} ${computed.unit}`;
      b.append(strong, document.createElement('br'), cap);
      b.addEventListener('click', () => { selectedStation = id; renderInspector(); render(); });
      list.appendChild(b);
    }

    /* Preview banner */
    const pb = $('previewBanner');
    if (preview) {
      pb.hidden = false;
      pb.textContent = `PREVIEW, local only: ${preview.label}. ${preview.before} to ${preview.after} ${computed.unit}. Limit after: ${preview.bottleneckAfter}. Accepted work is still ${computed.throughput} ${computed.unit}. No receiver, no signed receipt.`;
    } else {
      pb.hidden = true;
    }
    $('stopBanner').hidden = !stopped;
    $('stopBtn').hidden = stopped;
    $('clearStopBtn').hidden = !stopped;

    /* Decisions */
    $('acceptBtn').disabled = !preview || stopped;
    $('rejectBtn').disabled = !preview;
    $('applyAssumptionBtn').disabled = stopped;

    /* Options */
    const opts = $('optionsList');
    opts.replaceChildren();
    const seen = new Set();
    for (const ev of intel.single_interventions || []) {
      if (ev.id === 'portable') continue;
      seen.add(ev.id);
      opts.appendChild(optionCard(ev.id, ev.label, ev.detail || ev.explanation, ev));
    }
    for (const combo of intel.synergistic_combos || []) {
      opts.appendChild(optionCard(combo.id, combo.label, combo.evaluation.explanation, combo.evaluation, combo.component_ids));
    }
    if (!opts.children.length) {
      const p = document.createElement('p');
      p.textContent = 'No further options in this sandbox state. Reset to start over.';
      opts.appendChild(p);
    }
    renderInspector();
  }

  function optionCard(id, label, detail, ev, componentIds) {
    const card = document.createElement('div');
    card.className = 'option';
    const kind = document.createElement('p');
    kind.className = 'kind';
    kind.textContent = ev.classification || 'Option';
    const h = document.createElement('h3');
    h.textContent = label;
    const nums = document.createElement('p');
    nums.textContent = `${ev.throughput_before} to ${ev.throughput_after} ${def().unit} (${ev.throughput_gain >= 0 ? '+' : ''}${ev.throughput_gain}). CapEx $${ev.capex_usd}. Limit after: ${ev.bottleneck_after_label || ev.bottleneck_after}.`;
    const det = document.createElement('p');
    det.className = 'fine';
    det.textContent = detail || '';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Preview this option (local only)';
    btn.disabled = stopped;
    btn.addEventListener('click', () => {
      const path = def().paths.find(p => p.id === id);
      const combo = componentIds;
      if (combo) {
        const cand = clone(accepted);
        for (const pid of combo) Object.assign(cand, def().paths.find(p => p.id === pid).patch(accepted));
        const candC = def().compute(cand);
        preview = {
          label, kind: 'combo', candidate: cand,
          before: ev.throughput_before, after: ev.throughput_after,
          bottleneckAfter: ev.bottleneck_after_label || ev.bottleneck_after
        };
      } else if (path) {
        const cand = { ...accepted, ...path.patch(accepted) };
        preview = {
          label, kind: 'path', candidate: cand,
          before: ev.throughput_before, after: ev.throughput_after,
          bottleneckAfter: ev.bottleneck_after_label || ev.bottleneck_after
        };
      }
      log('Preview', `${label}: ${ev.throughput_before} to ${ev.throughput_after} ${def().unit}. Local only.`);
      render();
    });
    card.append(kind, h, nums, det, btn);
    return card;
  }

  function renderInspector() {
    const { computed } = current();
    const d = def();
    const id = selectedStation in computed.capacities ? selectedStation : Object.keys(computed.capacities)[0];
    selectedStation = id;
    $('inspectTitle').textContent = `${STATION_LABELS[domain][id] || id} · ${computed.capacities[id]} ${computed.unit}${id === computed.bottleneckId ? ' (current limit)' : ''}`;
    $('inspectDetail').textContent = d.stationDetail(accepted, computed, id)
      + ` Planning net: ${computed.netLabel} ${computed.netValue} ${computed.netUnit} (projection from stated assumptions, ±${computed.uncertaintyPct}%, not real earnings).`;
    const editor = $('assumptionEditor');
    editor.hidden = false;
    const fields = d.fields(accepted, id);
    const host = $('assumptionFields');
    host.replaceChildren();
    const readVals = () => {
      const out = {};
      for (const f of fields) {
        const el = host.querySelector(`[data-assumption-key="${f.key}"]`);
        if (!el) continue;
        out[f.key] = f.type === 'boolean' ? (el.value === 'true') : Number(el.value);
      }
      return out;
    };
    const updateFormula = () => {
      try { $('assumptionFormula').textContent = d.formula(accepted, readVals(), id); } catch (e) { /* keep last text */ }
    };
    for (const f of fields) {
      const lbl = document.createElement('label');
      lbl.className = 'assumptionField';
      const span = document.createElement('span');
      span.textContent = f.label;
      lbl.appendChild(span);
      if (f.type === 'boolean') {
        const sel = document.createElement('select');
        sel.dataset.assumptionKey = f.key;
        sel.innerHTML = '<option value="false">Off (Baseline)</option><option value="true">Active / Enabled</option>';
        sel.value = String(Boolean(f.val));
        sel.addEventListener('change', updateFormula);
        lbl.appendChild(sel);
      } else {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.dataset.assumptionKey = f.key;
        if (f.min !== undefined) inp.min = String(f.min);
        if (f.max !== undefined) inp.max = String(f.max);
        if (f.step !== undefined) inp.step = String(f.step);
        inp.value = String(f.val);
        inp.addEventListener('input', updateFormula);
        lbl.appendChild(inp);
      }
      host.appendChild(lbl);
    }
    updateFormula();
    $('applyAssumptionBtn').onclick = () => {
      if (stopped) return;
      const vals = readVals();
      for (const [k, v] of Object.entries(vals)) {
        if (typeof v === 'number' && (!Number.isFinite(v) || v < 0 || (k !== 'extra_retarder_racks' && k !== 'municipal_supp_gallons_per_week' && v <= 0))) {
          $('assumptionFormula').textContent = `Invalid assumption for ${k}: must be a positive number. Preview refused. Accepted work unchanged.`;
          return;
        }
      }
      const cand = { ...accepted, ...vals };
      if (domain === 'garden' && vals.drip_mulch_enabled !== undefined) {
        cand.gallons_per_lb_produce = vals.drip_mulch_enabled ? 2.625 : 4.0;
        cand.legume_rotation_coverage_pct = vals.drip_mulch_enabled ? 50 : 25;
      }
      if (domain === 'bakery' && vals.staggered_shift !== undefined) {
        cand.shift_pattern = vals.staggered_shift ? '04:30-14:30 staggered' : '05:00-13:00';
      }
      let candC;
      try { candC = def().compute(cand); } catch (e) {
        $('assumptionFormula').textContent = `Preview refused: ${e.message}. Accepted work unchanged.`;
        return;
      }
      const before = computed.throughput;
      preview = {
        label: `Assumption edit on ${STATION_LABELS[domain][id] || id}`,
        kind: 'assumption', candidate: cand,
        before, after: candC.throughput,
        bottleneckAfter: STATION_LABELS[domain][candC.bottleneckId] || candC.bottleneckId
      };
      log('Preview', `Assumption edit on ${STATION_LABELS[domain][id] || id}: ${before} to ${candC.throughput} ${computed.unit}. Local only.`);
      render();
    };
  }

  function resetDomain(nextDomain) {
    domain = nextDomain;
    accepted = clone(DOMAINS[domain].baseline);
    preview = null;
    stopped = false;
    version = 1;
    selectedStation = domain === 'bakery' ? 'oven' : domain === 'garden' ? 'water' : 'spectral_flow';
    log('Reset', `Sandbox reset to ${DOMAINS[domain].title} baseline. Local only.`);
    render();
  }

  for (const b of document.querySelectorAll('#domainTabs button')) {
    b.addEventListener('click', () => resetDomain(b.dataset.domain));
  }

  $('acceptBtn').addEventListener('click', () => {
    if (!preview || stopped) return;
    const before = current().computed.throughput;
    const beforeSum = stateChecksum(accepted);
    accepted = clone(preview.candidate);
    version += 1;
    const after = current().computed.throughput;
    log('Accept (local only)', `${preview.label}: accepted ${before} to ${after} ${def().unit}, now v${version}. No signed receipt was issued. Checksum ${beforeSum.slice(0, 8)} to ${stateChecksum(accepted).slice(0, 8)}.`);
    preview = null;
    render();
  });

  $('rejectBtn').addEventListener('click', () => {
    if (!preview) return;
    const sumBefore = stateChecksum(accepted);
    const label = preview.label;
    preview = null;
    const sumAfter = stateChecksum(accepted);
    log('Reject (local only)', `${label} rejected. Accepted state unchanged: checksum ${sumBefore.slice(0, 16)} ${sumBefore === sumAfter ? '==' : '!='} ${sumAfter.slice(0, 16)}. No receipt involved.`);
    render();
  });

  $('stopBtn').addEventListener('click', () => {
    stopped = true;
    log('STOP (local only)', 'STOP on. Previews and accepts frozen in this sandbox. Reject still works. This is not a signed receiver STOP.');
    render();
  });
  $('clearStopBtn').addEventListener('click', () => {
    stopped = false;
    log('Clear STOP (local only)', 'STOP cleared. Previews and accepts work again in this sandbox.');
    render();
  });
  $('resetBtn').addEventListener('click', () => resetDomain(domain));
  $('downloadBtn').addEventListener('click', () => {
    const { computed } = current();
    const data = {
      sandbox: 'OpenLine Genie sandbox, local only. No receiver, no signed receipt.',
      domain, version, accepted_assumptions: accepted, computed,
      local_state_checksum: stateChecksum(accepted)
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `genie-sandbox-${domain}-local-only.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    log('Download', 'Local copy downloaded as JSON. Local only.');
  });

  render();
}
