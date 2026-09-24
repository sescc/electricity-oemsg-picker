import test from 'node:test';
import assert from 'node:assert/strict';
import {
  PROFILES, blockCost, effectiveRate, inWindow, monthlyBill, nightShare, scalePlan, touAverageRate, withNightShare,
} from '../../site/js/billing.js';

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const flat = { weekday: Array(24).fill(1 / 24), weekend: Array(24).fill(1 / 24) };

test('profiles sum to one', () => {
  for (const p of Object.values(PROFILES)) {
    close(p.weekday.reduce((a, b) => a + b), 1);
    close(p.weekend.reduce((a, b) => a + b), 1);
  }
});

test('windows, including ones that wrap past midnight', () => {
  const night = { days: 'all', start: 23, end: 7 };
  assert.ok(inWindow(night, 'weekday', 23));
  assert.ok(inWindow(night, 'weekday', 3));
  assert.ok(!inWindow(night, 'weekday', 7));
  const wk = { days: 'weekday', start: 9, end: 21 };
  assert.ok(inWindow(wk, 'weekday', 9));
  assert.ok(!inWindow(wk, 'weekend', 12));
});

test('TOU average with a flat profile is the time-weighted average', () => {
  // Senoko LifeSavvy24: 7am-11pm 36.95, else 20.05 -> 16h peak, 8h off-peak
  const rates = { periods: [{ rate: 36.95, windows: [{ days: 'all', start: 7, end: 23 }] }], default_rate: 20.05 };
  close(touAverageRate(rates, flat), (16 * 36.95 + 8 * 20.05) / 24);
  // Keppel Weekend Saver: weekday 9am-9pm 39.90, rest 27.90
  const ks = { periods: [{ rate: 39.9, windows: [{ days: 'weekday', start: 9, end: 21 }] }], default_rate: 27.9 };
  close(touAverageRate(ks, flat), (5 / 7) * (12 * 39.9 + 12 * 27.9) / 24 + (2 / 7) * 27.9);
});

test('night share slider rescales the profile', () => {
  const p = withNightShare(PROFILES.out_daytime, 0.6);
  close(nightShare(p), 0.6);
  close(p.weekday.reduce((a, b) => a + b), 1);
});

test('block (stacked) tariff is marginal', () => {
  const blocks = [{ upto_kwh: 300, rate: 30 }, { upto_kwh: 600, rate: 29.4 }, { upto_kwh: null, rate: 28 }];
  close(blockCost(blocks, 200), 200 * 30);
  close(blockCost(blocks, 450), 300 * 30 + 150 * 29.4);
  close(blockCost(blocks, 700), 300 * 30 + 300 * 29.4 + 100 * 28);
});

test('discount-off-tariff and daily charges', () => {
  const easySave = { price_type: 'dot_pct', rates: { discount_pct: 18 }, daily_charge_cents: 55 };
  // 400 kWh, 30 days, tariff 34.78: 400*34.78*0.82/100 + 0.55*30
  close(monthlyBill(easySave, 400, 30, 34.78, flat), 400 * 34.78 * 0.82 / 100 + 16.5);
  const steady = { price_type: 'dot_cents', rates: { discount_cents: 1.64 } };
  close(monthlyBill(steady, 100, 30, 34.78, flat), 100 * (34.78 - 1.64) / 100);
  // the daily charge adds ~4.2 c/kWh at 400 kWh
  const eff = effectiveRate(easySave, 400, 34.78, flat);
  assert.ok(eff > 34.78 * 0.82 + 4 && eff < 34.78 * 0.82 + 4.4, String(eff));
});

test('scaling future offers leaves discount plans alone', () => {
  const fixed = { price_type: 'fixed', rates: { rate: 30 } };
  close(scalePlan(fixed, 1.1).rates.rate, 33);
  const dot = { price_type: 'dot_pct', rates: { discount_pct: 10 } };
  assert.equal(scalePlan(dot, 1.1), dot);
});
