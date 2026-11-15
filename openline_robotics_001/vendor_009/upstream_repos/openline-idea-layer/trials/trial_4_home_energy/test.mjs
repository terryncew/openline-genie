import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compareEnergyOptions, exportComparisonMarkdown, ESTIMATE_BANNER} from './logic.mjs';

test('IL-1-0 acceptance test: changing a mock tariff updates the displayed comparison and every output is marked an estimate', () => {
 const lowTariff = compareEnergyOptions({mockTariffPerKwh: 0.25});
 const highTariff = compareEnergyOptions({mockTariffPerKwh: 0.50});
 assert.equal(lowTariff.is_estimate, true);
 assert.equal(highTariff.is_estimate, true);
 assert.equal(lowTariff.banner, ESTIMATE_BANNER);

 const lowSolar = lowTariff.comparisons.find(c => c.option_id === 'OPT-SOLAR-1200');
 const highSolar = highTariff.comparisons.find(c => c.option_id === 'OPT-SOLAR-1200');
 assert.notEqual(lowSolar.est_annual_avoided_usd, highSolar.est_annual_avoided_usd);
 assert.equal(highSolar.est_annual_avoided_usd, lowSolar.est_annual_avoided_usd * 2);

 for (const c of [...lowTariff.comparisons, ...highTariff.comparisons]) {
  assert.equal(c.is_estimate, true);
  assert.equal(c.estimate_label, ESTIMATE_BANNER);
  assert.equal(c.verified_installer_endorsed, false);
 }

 const md = exportComparisonMarkdown(highTariff);
 assert.ok(md.includes(ESTIMATE_BANNER));
 assert.ok(md.includes('[ESTIMATE ONLY]'));
 assert.throws(() => compareEnergyOptions({mockTariffPerKwh: -0.10}), /Invalid mockTariffPerKwh/);
});
