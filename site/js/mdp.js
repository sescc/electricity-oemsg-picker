// Finite-horizon Markov Decision Process over contract choices, solved by backward induction.
//
// Time step: one month, so contract ends, contract lengths and move-out dates are exact.
// The regulated tariff only changes at calendar quarter starts (Jan/Apr/Jul/Oct) and is announced
// before the quarter begins, so it is known when each decision is made.
// State  (a, r, s, k): a = plan held, r = months left on its contract, s = tariff level when it
//        was signed (sets a re-contracted plan's price; s = K means "today's published offer"),
//        k = current tariff level (K-state Markov chain fitted in CI, one transition per quarter).
// Action: keep the plan (at expiry: renew it at an offer scaled to the current tariff), or switch
//        to plan q. Switching mid-contract pays the early-termination charge.
// Cost:  the month's bill (+ switching fees - sign-up rebate on today's offers).
// Terminal: moving out with r > 0 pays the early-termination charge (if the user says so).
// Objective: minimise expected discounted cost. Short-term savings (a cheaper plan now) are traded
// against long-term lock-in costs (termination fees, missing a later tariff drop).

import { monthlyBill, scalePlan } from './billing.js';

// Months of contract remaining at the *start* of a month -> early-termination charge.
export function etfFor(plan, rMonths, ctx) {
  if (rMonths <= 0) return 0;
  const t = plan.terms || {};
  if (plan.contract_months > 0 && t.etf_schedule?.length) {
    const elapsed = plan.contract_months - rMonths + 1; // 1-based contract month we'd leave in
    const row = t.etf_schedule.find((x) => elapsed >= x.from_month && elapsed <= x.to_month);
    return row ? row.fee_sgd : t.etf_schedule[t.etf_schedule.length - 1].fee_sgd;
  }
  if (t.etf_by_dwelling && ctx.dwelling in t.etf_by_dwelling) return t.etf_by_dwelling[ctx.dwelling];
  if (typeof t.early_termination_fee_sgd === 'number') return t.early_termination_fee_sgd;
  return ctx.defaultEtf;
}

// Cost of signing plan `to` now or later, excluding the exit fee of the plan being left.
function entryCost(to, ctx, isNow) {
  let c = ctx.hassle;
  if (to.smart_meter_required && !ctx.hasSmartMeter) c += ctx.meterFee;
  if (isNow && ctx.includeRebates) c -= to.rebate_sgd || 0;
  return c;
}

export function switchCost(from, rFrom, to, ctx, isNow) {
  return etfFor(from, rFrom, ctx) + entryCost(to, ctx, isNow);
}

const quarterStarts = (ym) => (Number(ym.slice(5, 7)) - 1) % 3 === 0;

/**
 * @param plans   candidate plans; plans[0] is the household's current plan (may be the SP tariff)
 * @param chain   {levels:[K], P:[K][K], initial:[K]} tariff levels in cents incl. GST;
 *                `initial` is the distribution for the first month of the horizon
 * @param months  [{month:'YYYY-MM', kwh, days}] consumption for each month of the horizon
 * @param ctx     {profile, dwelling, hassle, meterFee, hasSmartMeter, includeRebates, defaultEtf,
 *                 currentTariff, currentR (months left on plans[0]), payEtfOnMove, discount (per year),
 *                 frozenOffers}
 */
export function solve(plans, chain, months, ctx) {
  const K = chain.levels.length, H = months.length, A = plans.length;
  const S = K + 1; // sign level; index K = today's offer
  const lenM = plans.map((p) => p.contract_months);
  const r0 = ctx.currentR || 0;
  const R = Math.max(...lenM, r0) + 1;
  const gamma = (ctx.discount ?? 0.97) ** (1 / 12);
  // future offers move with the tariff unless ctx.frozenOffers (sensitivity check)
  const factor = (s) => (s === K || ctx.frozenOffers ? 1 : chain.levels[s] / ctx.currentTariff);
  // tariff changes between month t and t+1 only if month t+1 starts a calendar quarter
  const changes = months.map((_, t) => t + 1 < H && quarterStarts(months[t + 1].month));

  const scaled = plans.map((p) => Array.from({ length: S }, (_, s) => scalePlan(p, factor(s))));
  // C[t][a][s][k]: bill for month t holding plan a (signed at level s) when the tariff is level k
  const C = months.map((m) => plans.map((_, a) => Array.from({ length: S }, (_, s) =>
    chain.levels.map((lvl) => monthlyBill(scaled[a][s], m.kwh, m.days, lvl, ctx.profile)))));
  const etf = plans.map((p, a) => Float64Array.from({ length: R }, (_, r) => etfFor(p, r, ctx)));

  const idx = (a, r, s, k) => ((a * R + r) * S + s) * K + k;
  const N = A * R * S * K;
  let V = new Float64Array(N);
  for (let a = 0; a < A; a++) for (let r = 0; r < R; r++) for (let s = 0; s < S; s++) for (let k = 0; k < K; k++)
    V[idx(a, r, s, k)] = ctx.payEtfOnMove ? etf[a][r] : 0;

  const policy = new Array(H);
  const EV = new Float64Array(N);
  let firstQ = null;
  for (let t = H - 1; t >= 0; t--) {
    for (let i = 0; i < N; i += K) {
      for (let k = 0; k < K; k++) {
        if (!changes[t]) { EV[i + k] = V[i + k]; continue; }
        let e = 0;
        const row = chain.P[k];
        for (let k2 = 0; k2 < K; k2++) e += row[k2] * V[i + k2];
        EV[i + k] = e;
      }
    }
    const isNow = t === 0;
    // Value of entering plan q this month (excluding the exit fee of the plan left), per tariff level.
    // It doesn't depend on the plan being left, so keep the best and second best per k.
    const enter = Array.from({ length: K }, (_, k) => {
      const s2 = isNow ? K : k;
      let b1 = Infinity, q1 = -1, b2 = Infinity, q2 = -1;
      const vals = new Float64Array(A);
      for (let q = 0; q < A; q++) {
        const v = entryCost(plans[q], ctx, isNow) + C[t][q][s2][k] + gamma * EV[idx(q, Math.max(lenM[q] - 1, 0), s2, k)];
        vals[q] = v;
        if (v < b1) { b2 = b1; q2 = q1; b1 = v; q1 = q; } else if (v < b2) { b2 = v; q2 = q; }
      }
      return { b1, q1, b2, q2, vals };
    });
    const keepValue = (a, r, s, k) => {
      if (r > 0 || lenM[a] === 0) return C[t][a][s][k] + gamma * EV[idx(a, Math.max(r - 1, 0), s, k)];
      const s2 = isNow ? K : k; // contract expired: renew at the current offer
      return C[t][a][s2][k] + gamma * EV[idx(a, Math.max(lenM[a] - 1, 0), s2, k)];
    };
    const Vt = new Float64Array(N);
    const pol = new Int16Array(N);
    for (let a = 0; a < A; a++) for (let r = 0; r < R; r++) for (let s = 0; s < S; s++) for (let k = 0; k < K; k++) {
      const e = enter[k];
      const [bv, bq] = e.q1 !== a ? [e.b1, e.q1] : [e.b2, e.q2];
      let best = keepValue(a, r, s, k), bestA = a;
      if (bq >= 0 && etf[a][r] + bv < best) { best = etf[a][r] + bv; bestA = bq; }
      const i = idx(a, r, s, k);
      Vt[i] = best;
      pol[i] = bestA;
    }
    policy[t] = pol;
    V = Vt;
    if (isNow) {
      // Q-value of each first move from the household's actual state, before the first month's
      // tariff level is known (it is announced at the end of the current quarter).
      firstQ = plans.map((_, q) => chain.initial.reduce((tot, pk, k) => tot + pk * (q === 0
        ? keepValue(0, r0, K, k)
        : etf[0][r0] + enter[k].vals[q]), 0));
    }
  }
  return { firstQ, policy, C, idx, etf, changes, dims: { A, R, S, K, H }, lenM };
}

function sampleIndex(probs, u) {
  let c = 0;
  for (let i = 0; i < probs.length; i++) { c += probs[i]; if (u < c) return i; }
  return probs.length - 1;
}

export function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Monte-Carlo: take first action q, then follow the optimal policy along simulated tariff paths.
 * Returns undiscounted total cost samples plus how often the policy switches later.
 */
export function simulate(sol, plans, chain, ctx, q, nPaths = 800, seed = 1) {
  const { C, idx, policy, etf, changes, dims: { K, H }, lenM } = sol;
  const rand = mulberry32(seed + q * 7919);
  const costs = new Float64Array(nPaths);
  let laterSwitches = 0;
  for (let n = 0; n < nPaths; n++) {
    let k = sampleIndex(chain.initial, rand());
    let a = 0, r = ctx.currentR || 0, s = K, total = 0, switchedLater = false;
    for (let t = 0; t < H; t++) {
      const choice = t === 0 ? q : policy[t][idx(a, r, s, k)];
      if (choice !== a) {
        total += switchCost(plans[a], r, plans[choice], ctx, t === 0);
        a = choice; s = t === 0 ? K : k; r = lenM[a];
        if (t > 0 && !switchedLater) { switchedLater = true; laterSwitches++; } // share of paths, not count
      } else if (r === 0 && lenM[a] > 0) { // renewal at expiry
        s = t === 0 ? K : k; r = lenM[a];
      }
      total += C[t][a][s][k];
      r = Math.max(r - 1, 0);
      if (changes[t]) k = sampleIndex(chain.P[k], rand());
    }
    if (ctx.payEtfOnMove) total += etf[a][r];
    costs[n] = total;
  }
  const sorted = Array.from(costs).sort((x, y) => x - y);
  const pct = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  const mean = sorted.reduce((x, y) => x + y, 0) / sorted.length;
  return { mean, p10: pct(0.1), p50: pct(0.5), p90: pct(0.9), laterSwitchRate: laterSwitches / nPaths };
}

// What the optimal policy does at month t in state (a, r, s), for each possible tariff level.
export function policyAt(sol, t, a, r, s) {
  const { idx, policy, dims: { K } } = sol;
  return Array.from({ length: K }, (_, k) => policy[t][idx(a, r, s, k)]);
}
