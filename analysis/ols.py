"""Minimal OLS with classical standard errors (numpy only, so CI needs no statsmodels)."""
from __future__ import annotations

import math

import numpy as np


def _t_pvalue(t: float, df: int) -> float:
    # two-sided p-value; normal approximation is adequate for df > 30, else a Student-t series
    if df > 30:
        return math.erfc(abs(t) / math.sqrt(2))
    x = df / (df + t * t)
    return _betainc_reg(df / 2, 0.5, x)


def _betainc_reg(a: float, b: float, x: float) -> float:
    # regularised incomplete beta via continued fraction (Numerical Recipes)
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x)) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(200):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1 + num * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + num / (c if abs(c) > 1e-30 else 1e-30)
        f *= c * d
        if abs(1 - c * d) < 1e-10:
            break
    return front * (f - 1)


def ols(y: np.ndarray, X: np.ndarray, names: list[str]) -> dict:
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    df = n - k
    s2 = float(resid @ resid) / df
    cov = s2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(resid @ resid) / tss if tss > 0 else 0.0
    coefs = []
    for i, name in enumerate(names):
        t = beta[i] / se[i] if se[i] > 0 else float("nan")
        coefs.append({"name": name, "coef": float(beta[i]), "se": float(se[i]), "t": float(t),
                      "p": float(_t_pvalue(t, df)) if math.isfinite(t) else None})
    return {"beta": beta, "resid": resid, "sigma": math.sqrt(s2), "n": n, "k": k,
            "r2": r2, "adj_r2": 1 - (1 - r2) * (n - 1) / df, "coefs": coefs}
