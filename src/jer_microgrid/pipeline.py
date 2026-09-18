from __future__ import annotations

import argparse
from dataclasses import replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ABLATION_MAP, CONTROLLERS_MAIN, ExperimentConfig, OptimConfig, PRIMARY_STRESS_METRICS, SiteConfig, SyntheticConfig
from .controllers import build_controller, get_proposed_controller_params
from .metrics import compute_group_metrics
from .optimization_refs import LinearMPCQPController, WeightTuple, enumerate_weight_grid, solve_global_oracle
from .plotting import (
    save_metric_boxplot,
    save_pareto_frontier,
    save_rainflow_hist,
    save_ramp_cdf,
    save_representative_timeseries,
    save_sensitivity_heatmap,
    save_stress_boxplots,
)
from .reporting import (
    build_ablation_table,
    build_claims_by_scenario_table,
    build_claims_summary_table,
    build_main_comparison_table,
    build_runtime_table,
    build_stress_proxy_table,
    dataframe_to_latex_table,
    save_tables,
)
from .simulation import attach_profile_columns, replay_command_profile, simulate_controller
from .stats_utils import paired_stats_table
from .synth import generate_dataset, generate_profile
from .utils import ensure_dir, save_json



def _profile_iterator(dataset: pd.DataFrame):
    for _, g in dataset.groupby(['scenario', 'seed', 'scenario_seed'], sort=False):
        yield g.reset_index(drop=True)



def _run_named_controller_on_dataset(dataset: pd.DataFrame, controller_name: str, site: SiteConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_tick = []
    for profile in _profile_iterator(dataset):
        ctrl = build_controller(controller_name if controller_name != 'Proposed' else 'Proposed', site)
        sim = simulate_controller(profile, ctrl, site)
        tick = attach_profile_columns(sim.series, profile)
        tick['controller'] = controller_name
        per_tick.append(tick)
    tick_df = pd.concat(per_tick, ignore_index=True)
    metrics_df = compute_group_metrics(tick_df, site, ['controller', 'scenario', 'seed', 'scenario_seed', 'day_id'])
    return tick_df, metrics_df



def _run_weighted_controller(dataset: pd.DataFrame, site: SiteConfig, optim: OptimConfig, weights: WeightTuple,
                             *, perfect_preview: bool, label_prefix: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_tick = []
    for profile in _profile_iterator(dataset):
        ctrl = LinearMPCQPController(site, optim, weights, perfect_preview=perfect_preview)
        sim = simulate_controller(profile, ctrl, site, future_preview=perfect_preview)
        tick = attach_profile_columns(sim.series, profile)
        tick['controller'] = f'{label_prefix}_{weights.lam:g}_{weights.mu:g}_{weights.nu:g}'
        tick['reference_type'] = label_prefix
        tick['weight_label'] = f'{weights.lam:g}|{weights.mu:g}|{weights.nu:g}'
        per_tick.append(tick)
    tick_df = pd.concat(per_tick, ignore_index=True)
    metrics_df = compute_group_metrics(tick_df, site, ['controller', 'reference_type', 'weight_label', 'scenario', 'seed', 'scenario_seed', 'day_id'])
    return tick_df, metrics_df



def _summarize_weight_metrics(metrics_df: pd.DataFrame, group_cols: tuple[str, ...] = ('weight_label',)) -> pd.DataFrame:
    rows = []
    for keys, g in metrics_df.groupby(list(group_cols), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_cols, keys))
        row.update({
            'ramp95_kw_per_min': g['ramp95_kw_per_min'].mean(),
            'throughput_kwh': g['throughput_kwh'].mean(),
            'efc': g['efc'].mean(),
            'lfp_cycle_loss_pct': g['lfp_cycle_loss_pct'].mean(),
            't_high_soc_h': g['t_high_soc_h'].mean(),
            'ceq_q95': g['ceq_q95'].mean(),
            't_high_c_h': g['t_high_c_h'].mean(),
            'idod': g['idod'].mean(),
        })
        rows.append(row)
    return pd.DataFrame(rows)



def _nondominated(df: pd.DataFrame, x: str = 'ramp95_kw_per_min', y: str = 'throughput_kwh') -> pd.DataFrame:
    pts = df.sort_values([x, y]).reset_index(drop=True)
    keep = []
    best_y = float('inf')
    for _, row in pts.iterrows():
        if row[y] < best_y:
            keep.append(True)
            best_y = row[y]
        else:
            keep.append(False)
    out = pts[np.array(keep, dtype=bool)].copy()
    if {'reference_type', 'weight_label'}.issubset(out.columns):
        out['label'] = out['reference_type'].astype(str) + ':' + out['weight_label'].astype(str)
    elif 'weight_label' in out.columns:
        out['label'] = out['weight_label']
    return out



def _select_best_balanced(frontier: pd.DataFrame, best_ramp: float, tol: float = 1.05) -> str:
    cand = frontier[frontier['ramp95_kw_per_min'] <= best_ramp * tol].sort_values(['throughput_kwh', 'ramp95_kw_per_min'])
    return str(cand.iloc[0]['weight_label']) if not cand.empty else str(frontier.iloc[0]['weight_label'])



def run_full_pipeline(site: SiteConfig, synth: SyntheticConfig, optim: OptimConfig, exp: ExperimentConfig,
                      *, smoke: bool = False, publication_package: bool = False) -> dict[str, Any]:
    outdir = ensure_dir(exp.output_dir)
    figures_dir = ensure_dir(outdir / 'figures')

    dataset = generate_dataset(exp.seeds, site, synth)
    dataset.to_csv(outdir / 'synthetic_dataset.csv', index=False)

    all_tick = []
    all_metrics = []

    # Core baselines and proposed controller.
    for ctrl_name in ['Proposed', 'NC', 'GR', 'RS', 'FBRL']:
        tick_df, metrics_df = _run_named_controller_on_dataset(dataset, ctrl_name, site)
        all_tick.append(tick_df)
        all_metrics.append(metrics_df)

    # Fair MPC sweep.
    mpc_weights = enumerate_weight_grid(optim)
    if smoke:
        mpc_weights = mpc_weights[:3]
    mpc_metric_blocks = []
    mpc_tick_blocks = []
    for weights in mpc_weights:
        tick_df, metrics_df = _run_weighted_controller(dataset, site, optim, weights, perfect_preview=False, label_prefix='MPC')
        mpc_tick_blocks.append(tick_df)
        mpc_metric_blocks.append(metrics_df)
    mpc_metrics = pd.concat(mpc_metric_blocks, ignore_index=True)
    mpc_summary = _summarize_weight_metrics(mpc_metrics)
    mpc_frontier = _nondominated(mpc_summary)
    best_ramp_label = str(mpc_summary.sort_values('ramp95_kw_per_min').iloc[0]['weight_label'])
    best_balanced_label = _select_best_balanced(mpc_frontier, mpc_summary['ramp95_kw_per_min'].min())

    # Oracle references: perfect-preview receding sweep always, global oracle optional.
    oracle_metric_blocks = []
    for weights in mpc_weights:
        _, metrics_df = _run_weighted_controller(dataset, site, optim, weights, perfect_preview=True, label_prefix='OraclePreview')
        oracle_metric_blocks.append(metrics_df)
    oracle_metrics = pd.concat(oracle_metric_blocks, ignore_index=True)
    oracle_summary = _summarize_weight_metrics(oracle_metrics, group_cols=('reference_type', 'weight_label'))
    oracle_frontier = _nondominated(oracle_summary)

    if optim.enable_global_oracle and not smoke:
        global_rows = []
        for weights in mpc_weights:
            per_weight_ticks = []
            for profile in _profile_iterator(dataset):
                u, _ = solve_global_oracle(profile['base_kw'].to_numpy(dtype=float), profile['peak_flag'].to_numpy(dtype=int), site, optim, weights)
                tick = replay_command_profile(profile, u, site)
                tick = attach_profile_columns(tick, profile)
                tick['controller'] = f'OracleGlobal_{weights.lam:g}_{weights.mu:g}_{weights.nu:g}'
                tick['reference_type'] = 'OracleGlobal'
                tick['weight_label'] = f'{weights.lam:g}|{weights.mu:g}|{weights.nu:g}'
                per_weight_ticks.append(tick)
            g_tick = pd.concat(per_weight_ticks, ignore_index=True)
            g_metrics = compute_group_metrics(g_tick, site, ['controller', 'reference_type', 'weight_label', 'scenario', 'seed', 'scenario_seed', 'day_id'])
            global_rows.append(g_metrics)
        if global_rows:
            oracle_metrics = pd.concat([oracle_metrics] + global_rows, ignore_index=True)
            oracle_summary = _summarize_weight_metrics(oracle_metrics, group_cols=('reference_type', 'weight_label'))
            oracle_frontier = _nondominated(oracle_summary)

    # Select best MPC variants for the main comparison set.

    mpc_tick = pd.concat(mpc_tick_blocks, ignore_index=True)
    best_ramp_metrics = mpc_metrics[mpc_metrics['weight_label'] == best_ramp_label].copy()
    best_ramp_metrics['controller'] = 'MPC_best_ramp'
    best_bal_metrics = mpc_metrics[mpc_metrics['weight_label'] == best_balanced_label].copy()
    best_bal_metrics['controller'] = 'MPC_best_balanced'
    all_metrics.extend([best_ramp_metrics, best_bal_metrics])

    best_ramp_tick = mpc_tick[mpc_tick['weight_label'] == best_ramp_label].copy()
    best_ramp_tick['controller'] = 'MPC_best_ramp'
    best_bal_tick = mpc_tick[mpc_tick['weight_label'] == best_balanced_label].copy()
    best_bal_tick['controller'] = 'MPC_best_balanced'
    all_tick.extend([best_ramp_tick, best_bal_tick])

    tick_df = pd.concat(all_tick, ignore_index=True)
    metrics_df = pd.concat(all_metrics, ignore_index=True)

    # Ablations.
    ab_tick_all = []
    ab_met_all = []
    for ab_id in ABLATION_MAP.keys():
        ctrl_name = 'Proposed' if ab_id == 'A0' else ab_id
        tick_ab, met_ab = _run_named_controller_on_dataset(dataset, ctrl_name, site)
        tick_ab['controller'] = ab_id if ab_id != 'A0' else 'A0'
        met_ab['controller'] = ab_id if ab_id != 'A0' else 'A0'
        ab_tick_all.append(tick_ab)
        ab_met_all.append(met_ab)
    ab_tick_df = pd.concat(ab_tick_all, ignore_index=True)
    ab_metrics_df = pd.concat(ab_met_all, ignore_index=True)

    # Paired stats on primary stress metrics.
    stats_df = paired_stats_table(
        pd.concat([
            metrics_df[metrics_df['controller'] == 'Proposed'].assign(controller='Proposed'),
            metrics_df[metrics_df['controller'] == 'FBRL'].assign(controller='FBRL'),
        ], ignore_index=True),
        'Proposed', 'FBRL',
    )
    paired_metric_set = ['ramp95_kw_per_min', 'cap_violation_pct_total'] + list(dict.fromkeys(PRIMARY_STRESS_METRICS + ['flip_per_day']))
    pairwise_stats_all = []
    for baseline in [c for c in CONTROLLERS_MAIN if c != 'Proposed']:
        pairwise_stats_all.append(
            paired_stats_table(
                metrics_df[metrics_df['controller'].isin(['Proposed', baseline])],
                'Proposed',
                baseline,
                metrics=paired_metric_set,
            )
        )
    pairwise_stats_all_df = pd.concat(pairwise_stats_all, ignore_index=True) if pairwise_stats_all else pd.DataFrame()

    # Sensitivity analyses.
    sens_rows = []
    for rmax, tmin in product(exp.sensitivity_rmax, exp.sensitivity_tmin):
        site_mod = replace(site, r_max_kw_per_tick=rmax, t_min_ticks=tmin)
        _, met = _run_named_controller_on_dataset(dataset, 'Proposed', site_mod)
        sens_rows.append({
            'rmax': rmax,
            'tmin': tmin,
            'ramp95_kw_per_min': met['ramp95_kw_per_min'].mean(),
            'throughput_kwh': met['throughput_kwh'].mean(),
            'lfp_cycle_loss_pct': met['lfp_cycle_loss_pct'].mean(),
            'idod': met['idod'].mean(),
        })
    sensitivity_df = pd.DataFrame(sens_rows)

    # Tables.
    main_table_df = build_main_comparison_table(metrics_df[metrics_df['controller'].isin(CONTROLLERS_MAIN)])
    stress_table_df = build_stress_proxy_table(metrics_df[metrics_df['controller'].isin(CONTROLLERS_MAIN)])
    claims_df = build_claims_summary_table(metrics_df[metrics_df['controller'].isin(CONTROLLERS_MAIN)], 'Proposed',
                                           [c for c in CONTROLLERS_MAIN if c != 'Proposed'])
    claims_by_scenario_df = build_claims_by_scenario_table(
        metrics_df[metrics_df['controller'].isin(CONTROLLERS_MAIN)],
        'Proposed',
        [c for c in CONTROLLERS_MAIN if c != 'Proposed'],
    )
    runtime_df = build_runtime_table(tick_df[tick_df['controller'].isin(CONTROLLERS_MAIN)])
    ablation_table_df = build_ablation_table(ab_metrics_df)
    save_tables(
        outdir,
        main_df=main_table_df,
        stress_df=stress_table_df,
        stats_df=stats_df,
        claims_df=claims_df,
        claims_by_scenario_df=claims_by_scenario_df,
        ablation_df=ablation_table_df,
        sensitivity_df=sensitivity_df,
        runtime_df=runtime_df,
    )

    # CSV data exports.
    tick_df.to_csv(outdir / 'main_tick_results.csv', index=False)
    metrics_df.to_csv(outdir / 'main_metrics_by_scenario_day.csv', index=False)
    ab_tick_df.to_csv(outdir / 'ablation_tick_results.csv', index=False)
    ab_metrics_df.to_csv(outdir / 'ablation_metrics_by_scenario_day.csv', index=False)
    mpc_summary.to_csv(outdir / 'mpc_weight_sweep_summary.csv', index=False)
    mpc_frontier.to_csv(outdir / 'mpc_pareto_frontier.csv', index=False)
    oracle_metrics.to_csv(outdir / 'oracle_metrics_by_scenario_day.csv', index=False)
    oracle_summary.to_csv(outdir / 'oracle_weight_sweep_summary.csv', index=False)
    oracle_frontier.to_csv(outdir / 'oracle_pareto_frontier.csv', index=False)
    if not pairwise_stats_all_df.empty:
        pairwise_stats_all_df.to_csv(outdir / 'paired_stats_all_baselines.csv', index=False)
        (outdir / 'paired_stats_all_baselines.tex').write_text(
            dataframe_to_latex_table(pairwise_stats_all_df, 'Paired statistics: Proposed versus every main baseline.', 'tab:stats_all_auto'),
            encoding='utf-8',
        )

    # Rainflow histogram payload.
    hist_rows = []
    for ctrl, g in tick_df.groupby('controller'):
        if ctrl not in {'Proposed', 'FBRL', 'RS', 'MPC_best_balanced'}:
            continue
        depths = []
        weights = []
        for _, gg in g.groupby(['scenario_seed', 'day_id']):
            from .metrics import rainflow_cycles
            cycles = rainflow_cycles(gg['soc'].to_numpy(dtype=float))
            for d, w in cycles:
                depths.append(d)
                weights.append(w)
        if depths:
            bins = np.array([0.0, 0.1, 0.2, 0.4, 0.6, 1.0 + 1e-9])
            hist, edges = np.histogram(np.asarray(depths), bins=bins, weights=np.asarray(weights))
            for i in range(len(hist)):
                hist_rows.append({'controller': ctrl, 'depth_bin': f'[{edges[i]:.1f},{edges[i+1]:.1f})', 'count_weighted': float(hist[i])})
    hist_df = pd.DataFrame(hist_rows)
    hist_df.to_csv(outdir / 'rainflow_histogram.csv', index=False)

    # Representative plotting dataset.
    rep_tick = []
    rep_plot_controllers = ['Proposed', 'GR', 'RS', 'FBRL']
    rep_profile = generate_profile(exp.representative_seed, exp.representative_scenario, site, synth)
    for ctrl_name in rep_plot_controllers:
        ctrl = build_controller('Proposed' if ctrl_name == 'Proposed' else ctrl_name, site)
        sim = simulate_controller(rep_profile, ctrl, site)
        tick = attach_profile_columns(sim.series, rep_profile)
        tick['controller'] = ctrl_name
        rep_tick.append(tick)
    rep_tick_df = pd.concat(rep_tick, ignore_index=True)
    rep_tick_df.to_csv(outdir / 'representative_timeseries.csv', index=False)

    # Figures.
    save_ramp_cdf(
        tick_df[tick_df['controller'].isin(rep_plot_controllers)],
        figures_dir / 'ramp_cdf_ccdf.pdf',
        ['GR', 'Proposed', 'RS', 'FBRL'],
    )
    save_representative_timeseries(
        rep_tick_df,
        figures_dir / 'representative_timeseries.pdf',
        ['GR', 'Proposed', 'RS', 'FBRL'],
        n_points=240,
    )
    save_metric_boxplot(
        metrics_df[metrics_df['controller'].isin(['Proposed', 'GR', 'FBRL'])],
        figures_dir / 'modeled_cycle_loss_boxplot.pdf',
        'lfp_cycle_loss_pct',
        ['Proposed', 'GR', 'FBRL'],
        ylabel='Modeled LFP cycle-life loss (%)',
        title='Primary 24-hour benchmark: chemistry-calibrated cycling indicator',
    )
    if not hist_df.empty:
        save_rainflow_hist(hist_df, figures_dir / 'rainflow_hist.pdf', ['Proposed', 'FBRL', 'RS', 'MPC_best_balanced'])
    save_stress_boxplots(
        metrics_df[metrics_df['controller'].isin(['Proposed', 'FBRL', 'MPC_best_balanced'])],
        figures_dir / 'stress_proxy_boxplots.pdf',
        ['throughput_kwh', 'lfp_cycle_loss_pct', 't_high_soc_h', 't_high_c_h', 'idod'],
        ['Proposed', 'FBRL', 'MPC_best_balanced'],
    )
    save_pareto_frontier(mpc_frontier, figures_dir / 'mpc_pareto_frontier.pdf')
    if not sensitivity_df.empty:
        pivot = sensitivity_df.pivot(index='tmin', columns='rmax', values='idod')
        save_sensitivity_heatmap(pivot, figures_dir / 'sensitivity_rmax_tmin_idod.pdf', 'Sensitivity: IDOD over Rmax and Tmin')

    save_json(outdir / 'run_manifest.json', {
        'site': site.__dict__,
        'synthetic': synth.__dict__,
        'optim': {
            'rho_imp': optim.rho_imp,
            'rho_exp': optim.rho_exp,
            'lambda_grid': list(optim.lambda_grid),
            'mu_grid': list(optim.mu_grid),
            'nu_grid': list(optim.nu_grid),
            'enable_global_oracle': optim.enable_global_oracle,
        },
        'proposed_controller': get_proposed_controller_params(site),
        'experiment': {
            'seeds': list(exp.seeds),
            'representative_scenario': exp.representative_scenario,
            'representative_seed': exp.representative_seed,
        },
        'best_ramp_label': best_ramp_label,
        'best_balanced_label': best_balanced_label,
    })

    return {
        'dataset': dataset,
        'tick_df': tick_df,
        'metrics_df': metrics_df,
        'ablation_metrics_df': ab_metrics_df,
        'stats_df': stats_df,
        'pairwise_stats_all_df': pairwise_stats_all_df,
        'claims_df': claims_df,
        'claims_by_scenario_df': claims_by_scenario_df,
        'main_table_df': main_table_df,
        'stress_table_df': stress_table_df,
        'runtime_df': runtime_df,
        'ablation_table_df': ablation_table_df,
        'sensitivity_df': sensitivity_df,
        'mpc_frontier': mpc_frontier,
        'oracle_metrics_df': oracle_metrics,
        'oracle_frontier': oracle_frontier,
        'output_dir': str(outdir),
    }



def build_default_configs(smoke: bool = False):
    site = SiteConfig()
    synth = SyntheticConfig()
    optim = OptimConfig()
    exp = ExperimentConfig(output_dir='outputs_smoke' if smoke else 'outputs_reference')
    if smoke:
        site = replace(site, w_f=3, w_ema=3, horizon_k=3)
        exp.seeds = [0]
        synth.hours = 1
        synth.scenario_names = ['mixed']
        optim.lambda_grid = [1e-2]
        optim.mu_grid = [1e-2]
        optim.nu_grid = [1e-3]
        optim.maxiter_qp = 30
        optim.enable_global_oracle = False
        exp.sensitivity_rmax = [20.0]
        exp.sensitivity_tmin = [3]
    return site, synth, optim, exp



def main():
    parser = argparse.ArgumentParser(description='Run the core benchmark pipeline for the microgrid supervisory-computing study.')
    parser.add_argument('--smoke', action='store_true', help='Run a reduced verification sweep.')
    parser.add_argument('--output-dir', type=str, default=None)
    parser.add_argument('--publication-package', action='store_true', help='Also build publication-audit artifacts after the run.')
    args = parser.parse_args()

    site, synth, optim, exp = build_default_configs(smoke=args.smoke)
    if args.output_dir:
        exp.output_dir = args.output_dir
    results = run_full_pipeline(site, synth, optim, exp, smoke=args.smoke, publication_package=args.publication_package)
    if args.publication_package:
        from .publication import run_publication_package
        run_publication_package(site, synth, exp, Path(results['output_dir']) / 'publication_package')
    print(f"Finished. Outputs written to: {results['output_dir']}")


if __name__ == '__main__':
    main()
