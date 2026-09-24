import test from 'node:test';
import assert from 'node:assert/strict';
import { SP_TARIFF_PLAN } from '../../site/js/billing.js';
import { etfFor, policyAt, simulate, solve } from '../../site/js/mdp.js';

const flat = { weekday: Array(24).fill(1 / 24), weekend: Array(24).fill(1 / 24) };
// n months starting at a quarter start (Oct 2026), 400 kWh each, 30 days each
const months = (n, kwh = 400) => Array.from({ length: n }, (_, i) => {
  const idx = 2026 * 12 + 9 + i;
  return { month: `${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, '0')}`, kwh, days: 30 };
});
const baseCtx = {
  profile: flat, dwelling: 'hdb4', hassle: 0, meterFee: 43.6, hasSmartMeter: false, includeRebates: true,
  defaultEtf: 200, currentTariff: 34, currentR: 0, payEtfOnMove: true, discount: 1,
};
const fixed = (rate, m, extra = {}) => ({
  id: `f${rate}-${m}`, price_type: 'fixed', rates: { rate }, contract_months: m, daily_charge_cents: 0,
  rebate_sgd: 0, terms: { early_termination_fee_sgd: 200 }, ...extra,
});
const argmin = (xs) => xs.indexOf(Math.min(...xs));
const flatChain = { levels: [34], P: [[1]], initial: [1] };

test('deterministic chain: cheapest plan wins and Q-values match hand calculation', () => {
  const plans = [SP_TARIFF_PLAN, fixed(30, 12), fixed(32, 12)];
  const sol = solve(plans, flatChain, months(12), baseCtx);
  assert.ok(Math.abs(sol.firstQ[0] - 4800 * 0.34) < 1e-6);
  assert.ok(Math.abs(sol.firstQ[1] - 4800 * 0.30) < 1e-6);
  assert.ok(sol.firstQ[1] < sol.firstQ[2]);
});

test('moving out before the contract ends: the termination fee can flip the choice', () => {
  // 6 months of stay; 24-month plan is 0.5c cheaper but costs $200 on moving out
  const plans = [SP_TARIFF_PLAN, fixed(33, 24), fixed(33.5, 6)];
  assert.equal(plans[argmin(solve(plans, flatChain, months(6), baseCtx).firstQ)].id, 'f33.5-6');
  const noFee = solve(plans, flatChain, months(6), { ...baseCtx, payEtfOnMove: false });
  assert.equal(plans[argmin(noFee.firstQ)].id, 'f33-24');
});

test('current contract with 1 month left ends after exactly 1 month', () => {
  // current plan: 36c, 1 month left, $500 exit fee; alternative 30c. Best: wait 1 month, then switch.
  const cur = { ...fixed(36, 12), id: 'current', terms: { early_termination_fee_sgd: 500 } };
  const plans = [cur, SP_TARIFF_PLAN, fixed(30, 12, { terms: { early_termination_fee_sgd: 0 } })];
  const ctx = { ...baseCtx, currentR: 1 };
  const sol = solve(plans, flatChain, months(12), ctx);
  // keep: 1 month at 36c, then 11 months at 30c (switch free at expiry)
  assert.ok(Math.abs(sol.firstQ[0] - (400 * 0.36 + 11 * 400 * 0.30)) < 1e-6, String(sol.firstQ[0]));
  assert.deepEqual(policyAt(sol, 1, 0, 0, 1), [2]); // at month 1, contract over: switch to the 30c plan
  const sim = simulate(sol, plans, flatChain, ctx, 0, 10);
  assert.ok(Math.abs(sim.mean - sol.firstQ[0]) < 1e-6);
});

test('months left shift when the contract can be left for free', () => {
  const cur = { ...fixed(36, 12), id: 'current', terms: { early_termination_fee_sgd: 500 } };
  const plans = [cur, fixed(30, 12, { terms: { early_termination_fee_sgd: 0 } })];
  const keep = (r) => solve(plans, flatChain, months(12), { ...baseCtx, currentR: r }).firstQ[0];
  assert.ok(Math.abs(keep(4) - keep(1) - 3 * 400 * 0.06) < 1e-6); // 3 extra months at the dearer rate
});

test('rebates are one-off and only on today\'s offers', () => {
  const plans = [SP_TARIFF_PLAN, fixed(34, 12, { rebate_sgd: 100 })];
  const sol = solve(plans, flatChain, months(12), { ...baseCtx, payEtfOnMove: false });
  assert.ok(Math.abs(sol.firstQ[0] - sol.firstQ[1] - 100) < 1e-6);
});

test('ETF schedule by month and by dwelling', () => {
  const senoko = { contract_months: 24, terms: { etf_schedule: [
    { from_month: 1, to_month: 12, fee_sgd: 545 }, { from_month: 13, to_month: 24, fee_sgd: 327 }] } };
  assert.equal(etfFor(senoko, 24, baseCtx), 545); // leaving in month 1
  assert.equal(etfFor(senoko, 12, baseCtx), 327); // month 13
  assert.equal(etfFor(senoko, 0, baseCtx), 0);
  const pl = { contract_months: 24, terms: { etf_by_dwelling: { hdb4: 320, condo: 480 } } };
  assert.equal(etfFor(pl, 4, { ...baseCtx, dwelling: 'condo' }), 480);
  assert.equal(etfFor({ contract_months: 12, terms: {} }, 2, baseCtx), 200); // default assumption
});

test('tariff only moves at quarter starts', () => {
  const chain = { levels: [30, 40], P: [[0, 1], [1, 0]], initial: [1, 0] };
  const sol = solve([SP_TARIFF_PLAN], chain, months(6), baseCtx);
  // Oct-Dec at 30c, Jan-Mar at 40c
  assert.ok(Math.abs(sol.firstQ[0] - (3 * 400 * 0.30 + 3 * 400 * 0.40)) < 1e-6);
});

test('uncertain tariff: a discount plan is preferred when a fall is likely, fixed when a rise is', () => {
  const dot = { id: 'dot10', price_type: 'dot_pct', rates: { discount_pct: 10 }, contract_months: 12,
    daily_charge_cents: 0, rebate_sgd: 0, terms: { early_termination_fee_sgd: 0 } };
  const fix = fixed(30, 12, { terms: { early_termination_fee_sgd: 0 } });
  const plans = [SP_TARIFF_PLAN, dot, fix];
  const falling = { levels: [25, 34], P: [[1, 0], [0.9, 0.1]], initial: [0.9, 0.1] };
  const rising = { levels: [34, 45], P: [[0.1, 0.9], [0, 1]], initial: [0.1, 0.9] };
  assert.equal(plans[argmin(solve(plans, falling, months(12), baseCtx).firstQ)].id, 'dot10');
  assert.equal(plans[argmin(solve(plans, rising, months(12), baseCtx).firstQ)].id, 'f30-12');
});

test('simulation mean agrees with the Bellman value (undiscounted)', () => {
  const chain = { levels: [30, 36], P: [[0.7, 0.3], [0.4, 0.6]], initial: [0.5, 0.5] };
  const plans = [SP_TARIFF_PLAN, fixed(31, 12, { terms: { early_termination_fee_sgd: 0 } })];
  const sol = solve(plans, chain, months(18), baseCtx);
  const sim = simulate(sol, plans, chain, baseCtx, 1, 20000);
  const rel = Math.abs(sim.mean - sol.firstQ[1]) / sol.firstQ[1];
  assert.ok(rel < 0.01, `sim ${sim.mean} vs bellman ${sol.firstQ[1]}`);
});
