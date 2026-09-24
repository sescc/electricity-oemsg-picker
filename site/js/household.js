// Household consumption forecast: user's average monthly kWh, shaped by cooling degree days.
//   kWh_m = base_per_day * exp(b * (CDD/day_m - mean CDD/day)) * days_m
// b is the dwelling-type coefficient fitted in CI (analysis/models.py::fit_consumption).

export const DWELLINGS = [
  ['hdb12', 'HDB 1-2 room'], ['hdb3', 'HDB 3-room'], ['hdb4', 'HDB 4-room'], ['hdb5', 'HDB 5-room / Executive'],
  ['condo', 'Condo / private apartment'], ['landed', 'Landed property'],
];

export function daysIn(ym) {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

export function addMonths(ym, k) {
  const [y, m] = ym.split('-').map(Number);
  const i = y * 12 + (m - 1) + k;
  return `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`;
}

export function quarterStartMonth(q) { // "2026Q4" -> "2026-10"
  const [y, n] = q.split('Q').map(Number);
  return `${y}-${String((n - 1) * 3 + 1).padStart(2, '0')}`;
}

// weather: model.weather; returns [{month, cddPerDay, source}]
export function cddPath(weather, firstMonth, nMonths) {
  const clim = weather.climatology_cdd_per_day;
  const out = [];
  for (let i = 0; i < nMonths; i++) {
    const m = addMonths(firstMonth, i);
    const fc = weather.forecast?.[m];
    out.push(fc ? { month: m, cddPerDay: fc.cdd_per_day, p10: fc.p10, p90: fc.p90, source: 'seasonal forecast' }
      : { month: m, cddPerDay: clim[String(Number(m.slice(5)))], source: '10-year climatology' });
  }
  return out;
}

// The 12 complete calendar months before `today` (oldest first).
export function past12Months(today = new Date()) {
  const cur = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
  return Array.from({ length: 12 }, (_, i) => addMonths(cur, i - 12));
}

// Observed CDD/day for a past month (ERA5), falling back to climatology if not yet available.
export function pastCdd(weather, month) {
  const rec = weather.recent?.find((r) => r.month === month);
  return rec ? { cddPerDay: rec.cdd_per_day, observed: true }
    : { cddPerDay: weather.climatology_cdd_per_day[String(Number(month.slice(5)))], observed: false };
}

/**
 * Fit this household's own model from its bills: ln(kWh/day) = a + b * CDD/day.
 * With few months (or little weather variation) b can't be pinned down, so it is shrunk towards
 * the national coefficient for the home type b0 (a Gaussian prior with sd tau):
 *   b = (Sxy/s^2 + b0/tau^2) / (Sxx/s^2 + 1/tau^2),  a = mean(y) - b * mean(x)
 * s is the typical month-to-month noise in a single household's usage.
 * bills: [{month:'YYYY-MM', kwh}] (any subset of months).
 */
export function fitHousehold(bills, weather, b0, { tau = 0.03, s = 0.1 } = {}) {
  const pts = bills.filter((b) => b.kwh > 0).map((b) => {
    const w = pastCdd(weather, b.month);
    return { month: b.month, kwh: b.kwh, x: w.cddPerDay, y: Math.log(b.kwh / daysIn(b.month)), observed: w.observed };
  });
  const n = pts.length;
  if (!n) return null;
  const xbar = pts.reduce((t, p) => t + p.x, 0) / n;
  const ybar = pts.reduce((t, p) => t + p.y, 0) / n;
  let sxx = 0, sxy = 0;
  for (const p of pts) { sxx += (p.x - xbar) ** 2; sxy += (p.x - xbar) * (p.y - ybar); }
  const b = (sxy / s ** 2 + b0 / tau ** 2) / (sxx / s ** 2 + 1 / tau ** 2);
  const a = ybar - b * xbar;
  const resid = pts.map((p) => p.y - a - b * p.x);
  const clim = weather.climatology_cdd_per_day;
  let typical = 0;
  for (let m = 1; m <= 12; m++) typical += Math.exp(a + b * clim[String(m)]) * daysIn(`2025-${String(m).padStart(2, '0')}`);
  return {
    a, b, b0, n, points: pts, typicalMonthlyKwh: typical / 12,
    // how much the data moved b away from the national prior (0 = not at all, 1 = fully data-driven)
    dataWeight: (sxx / s ** 2) / (sxx / s ** 2 + 1 / tau ** 2),
    residSd: n > 2 ? Math.sqrt(resid.reduce((t, r) => t + r * r, 0) / (n - 2)) : null,
  };
}

/**
 * Monthly kWh forecast. Either from an average month (avgMonthlyKwh + national coef) or, when the
 * household entered bills, from its own fit {a, b}.
 */
export function consumptionForecast({ avgMonthlyKwh, coef, fit, weather, firstMonth, nMonths }) {
  const path = cddPath(weather, firstMonth, nMonths);
  if (fit) {
    return path.map((w) => ({ ...w, days: daysIn(w.month), kwh: Math.exp(fit.a + fit.b * w.cddPerDay) * daysIn(w.month) }));
  }
  const clim = weather.climatology_cdd_per_day;
  const climVals = Object.values(clim);
  const meanClim = climVals.reduce((a, b) => a + b, 0) / climVals.length;
  // normalise so a climatologically typical year averages exactly avgMonthlyKwh
  let z = 0;
  for (let m = 1; m <= 12; m++) z += daysIn(`2025-${String(m).padStart(2, '0')}`) * Math.exp(coef * (clim[String(m)] - meanClim));
  const basePerDay = (avgMonthlyKwh * 12) / z;
  return path.map((w) => ({
    ...w, days: daysIn(w.month),
    kwh: basePerDay * Math.exp(coef * (w.cddPerDay - meanClim)) * daysIn(w.month),
  }));
}
