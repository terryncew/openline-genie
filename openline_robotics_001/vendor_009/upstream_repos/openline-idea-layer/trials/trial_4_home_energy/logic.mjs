/**
 * Trial 4 (IL-1-0): Local energy assessment and comparison reports (Regulated Home Energy Sector).
 * Enforces hard boundary: "Estimates require verified local tariffs, roof data, and qualified installers"
 * Acceptance test: "Changing a mock tariff updates the displayed comparison and every output is marked an estimate."
 */

export const ESTIMATE_BANNER = 'ESTIMATE ONLY — REQUIRES VERIFIED LOCAL TARIFFS, ROOF DATA, AND QUALIFIED INSTALLERS (FICTIONAL TARIFF DATA)';

export const DEFAULT_ASSUMPTIONS = {
 monthlyKwh: 650,
 mockTariffPerKwh: 0.34,
 fixedMonthlyChargeUsd: 24.15,
 daytimeLoadShare: 0.45,
 neighborhoodScope: 'Oak Ridge Feeder Neighborhood (Fictional)'
};

export const UPGRADE_OPTIONS = [
 {option_id: 'OPT-BASELINE', name: '0 W Baseline (Keep Current Utility Tariff)', system_watts: 0, est_annual_generation_kwh: 0, upfront_cost_usd: 0},
 {option_id: 'OPT-SOLAR-400', name: '400 W Plug-In Balcony Solar (Scenario Estimate)', system_watts: 400, est_annual_generation_kwh: 580, upfront_cost_usd: 450},
 {option_id: 'OPT-SOLAR-1200', name: '1,200 W Plug-In Canopy Solar (Scenario Estimate)', system_watts: 1200, est_annual_generation_kwh: 1740, upfront_cost_usd: 1350}
];

export function compareEnergyOptions(customAssumptions = {}) {
 const a = {...DEFAULT_ASSUMPTIONS, ...customAssumptions};
 const monthlyKwh = Number(a.monthlyKwh);
 const tariff = Number(a.mockTariffPerKwh);
 const fixedCharge = Number(a.fixedMonthlyChargeUsd);
 const daytimeShare = Number(a.daytimeLoadShare);
 if (!Number.isFinite(monthlyKwh) || monthlyKwh <= 0) throw new Error('Invalid monthlyKwh');
 if (!Number.isFinite(tariff) || tariff <= 0 || tariff > 5) throw new Error('Invalid mockTariffPerKwh');
 if (!Number.isFinite(fixedCharge) || fixedCharge < 0) throw new Error('Invalid fixedMonthlyChargeUsd');
 if (!Number.isFinite(daytimeShare) || daytimeShare <= 0 || daytimeShare > 1) throw new Error('Invalid daytimeLoadShare');

 const annualLoadKwh = monthlyKwh * 12;
 const maxDaytimeUsableKwh = Math.round(annualLoadKwh * daytimeShare);
 const baselineAnnualVariableUsd = annualLoadKwh * tariff;
 const nonAvoidableFixedAnnualUsd = fixedCharge * 12;

 const comparisons = UPGRADE_OPTIONS.map(opt => {
  const usableOnsiteKwh = Math.min(opt.est_annual_generation_kwh, maxDaytimeUsableKwh);
  const estAnnualAvoidedUsd = Number((usableOnsiteKwh * tariff).toFixed(2));
  const estAnnualBillAfterUsd = Number((baselineAnnualVariableUsd - estAnnualAvoidedUsd + nonAvoidableFixedAnnualUsd).toFixed(2));
  const estSimplePaybackYears = estAnnualAvoidedUsd > 0 ? Number((opt.upfront_cost_usd / estAnnualAvoidedUsd).toFixed(1)) : null;
  return {
   option_id: opt.option_id,
   name: opt.name,
   is_estimate: true,
   estimate_label: ESTIMATE_BANNER,
   verified_installer_endorsed: false,
   usable_onsite_kwh_estimate: usableOnsiteKwh,
   est_annual_avoided_usd: estAnnualAvoidedUsd,
   est_annual_bill_usd: estAnnualBillAfterUsd,
   non_avoidable_fixed_annual_usd: Number(nonAvoidableFixedAnnualUsd.toFixed(2)),
   est_simple_payback_years: estSimplePaybackYears
  };
 });

 return {
  is_estimate: true,
  banner: ESTIMATE_BANNER,
  buyer: 'homeowners',
  format: 'service',
  scope: a.neighborhoodScope,
  assumptions: {monthlyKwh, mockTariffPerKwh: tariff, fixedMonthlyChargeUsd: fixedCharge, daytimeLoadShare: daytimeShare},
  comparisons
 };
}

export function exportComparisonMarkdown(report) {
 const lines = [
  `# ${report.banner}`,
  `Scope: ${report.scope} | Buyer: ${report.buyer} (${report.format})`,
  `Mock Tariff: $${report.assumptions.mockTariffPerKwh}/kWh | Monthly Usage: ${report.assumptions.monthlyKwh} kWh | Non-Avoidable Fixed Charge: $${report.assumptions.fixedMonthlyChargeUsd}/mo`,
  ''
 ];
 for (const c of report.comparisons) {
  lines.push(`- [ESTIMATE ONLY] ${c.name}: Usable=${c.usable_onsite_kwh_estimate} kWh/yr | Est. Avoided=$${c.est_annual_avoided_usd}/yr | Est. Total Bill=$${c.est_annual_bill_usd}/yr | Simple Payback=${c.est_simple_payback_years ?? 'N/A'} yrs`);
 }
 return lines.join('\n');
}
