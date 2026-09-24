import test from 'node:test';
import assert from 'node:assert/strict';
import { consumptionForecast, daysIn, fitHousehold, past12Months } from '../../site/js/household.js';

const clim = Object.fromEntries(Array.from({ length: 12 }, (_, i) => [String(i + 1), 3 + Math.sin(i / 2)]));
const recent = [];
for (let y = 2025; y <= 2026; y++) for (let m = 1; m <= 12; m++) {
  recent.push({ month: `${y}-${String(m).padStart(2, '0')}`, cdd_per_day: 2 + ((m * 7 + y) % 5) * 0.6 });
}
const weather = { climatology_cdd_per_day: clim, recent, forecast: {} };

test('past 12 months are the complete months before today', () => {
  const m = past12Months(new Date(2026, 8, 22)); // 22 Sep 2026
  assert.equal(m[0], '2025-09');
  assert.equal(m[11], '2026-08');
  assert.equal(m.length, 12);
});

test('with many months, the fit recovers the household\'s own sensitivity', () => {
  const a = Math.log(12), b = 0.10; // far from the national 0.06
  const bills = recent.slice(12).map((r) => ({ month: r.month, kwh: Math.exp(a + b * r.cdd_per_day) * daysIn(r.month) }));
  const fit = fitHousehold(bills, weather, 0.06, { tau: 0.03, s: 0.01 });
  assert.ok(Math.abs(fit.b - b) < 0.01, String(fit.b));
  assert.ok(Math.abs(fit.a - a) < 0.03);
});

test('one month: sensitivity stays at the national prior, level matches the bill', () => {
  const fit = fitHousehold([{ month: '2026-08', kwh: 400 }], weather, 0.06);
  assert.ok(Math.abs(fit.b - 0.06) < 1e-12);
  assert.equal(fit.n, 1);
  const fc = consumptionForecast({ fit, weather: { ...weather, forecast: {} }, firstMonth: '2026-08', nMonths: 1 });
  // August 2026 is in `recent` but the forecast path uses climatology for future months,
  // so compare against the fitted level at August's CDD directly:
  const x = recent.find((r) => r.month === '2026-08').cdd_per_day;
  assert.ok(Math.abs(Math.exp(fit.a + fit.b * x) * 31 - 400) < 1e-6);
  assert.ok(fc[0].kwh > 0);
});

test('skipped months and blanks are ignored', () => {
  const fit = fitHousehold([{ month: '2026-01', kwh: 0 }, { month: '2026-02', kwh: 350 }], weather, 0.06);
  assert.equal(fit.n, 1);
  assert.equal(fitHousehold([], weather, 0.06), null);
});
