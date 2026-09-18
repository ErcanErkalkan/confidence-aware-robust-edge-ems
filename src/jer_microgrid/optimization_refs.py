from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, NonlinearConstraint, minimize
from scipy.sparse import csc_matrix

from .config import OptimConfig, SiteConfig
from .controllers import ControllerBase, compute_caps, forecast_base
from .utils import clip


@dataclass(frozen=True)
class WeightTuple:
    lam: float
    mu: float
    nu: float


class LinearMPCQPController(ControllerBase):
    def __init__(self, site: SiteConfig, optim: OptimConfig, weights: WeightTuple, *, perfect_preview: bool = False):
        self.optim = optim
        self.weights = weights
        self.perfect_preview = perfect_preview
        super().__init__(site)

    @property
    def name(self) -> str:
        return f"MPC_l{self.weights.lam:g}_m{self.weights.mu:g}_n{self.weights.nu:g}" + ("_oracle_preview" if self.perfect_preview else "")

    def step(self, t: int, history_base: np.ndarray, soc: float, peak_flag: int, future_base: np.ndarray | None = None,
             future_peak_flags: np.ndarray | None = None) -> tuple[float, dict[str, Any]]:
        s = self.site
        prev_mode = self.state.mode
        if self.perfect_preview and future_base is not None:
            horizon_base = np.asarray(future_base[: s.horizon_k], dtype=float)
            if horizon_base.size == 0:
                horizon_base = np.full(s.horizon_k, history_base[-1], dtype=float)
            elif horizon_base.size < s.horizon_k:
                horizon_base = np.pad(horizon_base, (0, s.horizon_k - horizon_base.size), mode='edge')
        else:
            horizon_base = forecast_base(history_base, s)
        if future_peak_flags is not None:
            horizon_peak = np.asarray(future_peak_flags[: s.horizon_k], dtype=int)
            if horizon_peak.size == 0:
                horizon_peak = np.full(s.horizon_k, peak_flag, dtype=int)
            elif horizon_peak.size < s.horizon_k:
                horizon_peak = np.pad(horizon_peak, (0, s.horizon_k - horizon_peak.size), mode='edge')
        else:
            horizon_peak = np.full(s.horizon_k, peak_flag, dtype=int)
        imp_caps = np.zeros(s.horizon_k)
        exp_caps = np.zeros(s.horizon_k)
        for k in range(s.horizon_k):
            imp_caps[k], exp_caps[k] = compute_caps(int(horizon_peak[k]), s)
        u_opt, meta = solve_convex_dispatch(
            base_hat=horizon_base,
            imp_caps=imp_caps,
            exp_caps=exp_caps,
            soc0=soc,
            prev_cmd=self.state.prev_cmd,
            site=s,
            weights=self.weights,
            rho_imp=self.optim.rho_imp,
            rho_exp=self.optim.rho_exp,
            maxiter=self.optim.maxiter_qp,
        )
        cmd_vec = decision_to_command(u_opt)
        cmd = float(cmd_vec[0])
        self.state.prev_cmd = cmd
        self.state.mode = 'PS' if cmd > 1e-9 else ('VF' if cmd < -1e-9 else 'RG')
        self.state.rg_state = 'MID'
        self.state.dwell = self.state.dwell + 1 if self.state.mode == prev_mode else 1
        return cmd, {
            'mode': self.state.mode,
            'rg_state': 'MID',
            'desired_kw': cmd,
            'solver_success': bool(meta['success']),
            'solver_status': meta['status'],
            'solver_nit': int(meta['nit']),
            'p_imp_cap': float(imp_caps[0]),
            'p_exp_cap': float(exp_caps[0]),
        }


def decision_to_command(decision: np.ndarray) -> np.ndarray:
    return np.asarray(decision, dtype=float).copy()


def _build_linear_constraints(n: int, prev_cmd: float, site: SiteConfig) -> LinearConstraint:
    rows = []
    lo = []
    hi = []

    # Step constraints on the net command: |cmd0 - prev| <= rmax
    row = np.zeros(n)
    row[0] = 1.0
    rows.append(row.copy()); lo.append(-np.inf); hi.append(prev_cmd + site.r_max_kw_per_tick)
    rows.append(row.copy()); lo.append(prev_cmd - site.r_max_kw_per_tick); hi.append(np.inf)

    # Difference constraints on the net command: |cmd_k - cmd_{k-1}| <= rmax
    for k in range(1, n):
        row = np.zeros(n)
        row[k] = 1.0
        row[k - 1] = -1.0
        rows.append(row.copy()); lo.append(-np.inf); hi.append(site.r_max_kw_per_tick)
        rows.append(row.copy()); lo.append(-site.r_max_kw_per_tick); hi.append(np.inf)

    A = csc_matrix(np.vstack(rows))
    return LinearConstraint(A, np.asarray(lo, dtype=float), np.asarray(hi, dtype=float))


def _soc_trajectory(cmd: np.ndarray, soc0: float, site: SiteConfig) -> np.ndarray:
    cmd = np.asarray(cmd, dtype=float)
    coef_dis = site.ts_hours / (site.e_nom_kwh * site.eta_dis)
    coef_ch = site.ts_hours * site.eta_ch / site.e_nom_kwh
    dis = np.maximum(cmd, 0.0)
    ch = np.maximum(-cmd, 0.0)
    return soc0 - coef_dis * np.cumsum(dis) + coef_ch * np.cumsum(ch)


def _soc_jacobian(cmd: np.ndarray, site: SiteConfig) -> csc_matrix:
    cmd = np.asarray(cmd, dtype=float)
    n = cmd.size
    slopes = _soc_slopes(cmd, site)
    jac = np.zeros((n, n), dtype=float)
    for k in range(n):
        jac[k, : k + 1] = slopes[: k + 1]
    return csc_matrix(jac)


def _soc_slopes(cmd: np.ndarray, site: SiteConfig) -> np.ndarray:
    cmd = np.asarray(cmd, dtype=float)
    coef_dis = site.ts_hours / (site.e_nom_kwh * site.eta_dis)
    coef_ch = site.ts_hours * site.eta_ch / site.e_nom_kwh
    return np.where(cmd > 0.0, -coef_dis, np.where(cmd < 0.0, -coef_ch, -0.5 * (coef_dis + coef_ch)))


def _objective_and_grad(cmd: np.ndarray, *, base_hat: np.ndarray, imp_caps: np.ndarray, exp_caps: np.ndarray, soc0: float,
                        prev_cmd: float, site: SiteConfig, weights: WeightTuple, rho_imp: float, rho_exp: float) -> tuple[float, np.ndarray]:
    cmd = np.asarray(cmd, dtype=float)

    imp_violation = np.maximum(0.0, base_hat - cmd - imp_caps)
    exp_violation = np.maximum(0.0, -base_hat + cmd - exp_caps)
    obj = rho_imp * np.sum(imp_violation ** 2) + rho_exp * np.sum(exp_violation ** 2)
    obj += weights.lam * np.sum(cmd ** 2)

    d = np.empty_like(cmd)
    d[0] = cmd[0] - prev_cmd
    d[1:] = cmd[1:] - cmd[:-1]
    obj += weights.mu * np.sum(d ** 2)

    soc = _soc_trajectory(cmd, soc0, site)
    obj += weights.nu * np.sum((soc - 0.5 * (site.soc_min + site.soc_max)) ** 2)

    grad = np.zeros_like(cmd)
    grad += -2.0 * rho_imp * imp_violation
    grad += 2.0 * rho_exp * exp_violation
    grad += 2.0 * weights.lam * cmd

    grad[0] += 2.0 * weights.mu * d[0]
    if cmd.size > 1:
        grad[0] -= 2.0 * weights.mu * d[1]
        for k in range(1, cmd.size - 1):
            grad[k] += 2.0 * weights.mu * d[k] - 2.0 * weights.mu * d[k + 1]
        grad[-1] += 2.0 * weights.mu * d[-1]
    else:
        grad[0] += 0.0

    soc_res = soc - 0.5 * (site.soc_min + site.soc_max)
    rev_csum = np.cumsum(soc_res[::-1])[::-1]
    slopes = _soc_slopes(cmd, site)
    grad += 2.0 * weights.nu * rev_csum * slopes
    return float(obj), grad


def solve_convex_dispatch(*, base_hat: np.ndarray, imp_caps: np.ndarray, exp_caps: np.ndarray, soc0: float, prev_cmd: float,
                          site: SiteConfig, weights: WeightTuple, rho_imp: float, rho_exp: float, maxiter: int = 120) -> tuple[np.ndarray, dict[str, Any]]:
    n = len(base_hat)
    bounds = Bounds(-site.p_ch_max * np.ones(n), site.p_dis_max * np.ones(n))
    lincon = _build_linear_constraints(n, prev_cmd, site)
    soc_con = NonlinearConstraint(
        lambda x: _soc_trajectory(x, soc0, site),
        site.soc_min * np.ones(n),
        site.soc_max * np.ones(n),
        jac=lambda x: _soc_jacobian(x, site),
    )

    x0 = np.full(n, clip(prev_cmd, -site.p_ch_max, site.p_dis_max), dtype=float)

    def fun(x):
        return _objective_and_grad(
            x, base_hat=base_hat, imp_caps=imp_caps, exp_caps=exp_caps, soc0=soc0, prev_cmd=prev_cmd,
            site=site, weights=weights, rho_imp=rho_imp, rho_exp=rho_exp,
        )[0]

    def jac(x):
        return _objective_and_grad(
            x, base_hat=base_hat, imp_caps=imp_caps, exp_caps=exp_caps, soc0=soc0, prev_cmd=prev_cmd,
            site=site, weights=weights, rho_imp=rho_imp, rho_exp=rho_exp,
        )[1]

    res = minimize(fun, x0=x0, jac=jac, method='trust-constr', bounds=bounds, constraints=[lincon, soc_con],
                   options={'maxiter': maxiter, 'verbose': 0})
    x = np.asarray(res.x, dtype=float)
    return x, {'success': bool(res.success), 'status': str(res.message), 'nit': int(getattr(res, 'nit', -1))}


def solve_global_oracle(profile_base: np.ndarray, peak_flags: np.ndarray, site: SiteConfig, optim: OptimConfig,
                        weights: WeightTuple, soc0: float | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    soc0 = site.soc_init if soc0 is None else soc0
    n = profile_base.size
    imp_caps = np.zeros(n)
    exp_caps = np.zeros(n)
    for i in range(n):
        imp_caps[i], exp_caps[i] = compute_caps(int(peak_flags[i]), site)
    u, meta = solve_convex_dispatch(
        base_hat=profile_base,
        imp_caps=imp_caps,
        exp_caps=exp_caps,
        soc0=soc0,
        prev_cmd=0.0,
        site=site,
        weights=weights,
        rho_imp=optim.rho_imp,
        rho_exp=optim.rho_exp,
        maxiter=optim.oracle_global_maxiter,
    )
    return decision_to_command(u), meta


def enumerate_weight_grid(optim: OptimConfig) -> list[WeightTuple]:
    return [WeightTuple(lam, mu, nu) for lam, mu, nu in product(optim.lambda_grid, optim.mu_grid, optim.nu_grid)]
