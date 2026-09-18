from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .config import PRIMARY_STRESS_METRICS
from .utils import ensure_dir, latex_escape, mean_std_str


TABLE_MAP = {
    'main_comparison': 'main_comparison_table.csv',
    'stress_proxy': 'stress_proxy_table.csv',
    'paired_stats': 'paired_stats_table.csv',
    'claims_summary': 'claims_summary_table.csv',
    'claims_by_scenario': 'claims_by_scenario.csv',
    'ablation': 'ablation_table.csv',
    'sensitivity': 'sensitivity_summary.csv',
    'runtime': 'runtime_summary.csv',
}



def aggregate_mean_std(df: pd.DataFrame, group_cols: Sequence[str], metric_cols: Sequence[str]) -> pd.DataFrame:
    agg = df.groupby(list(group_cols))[list(metric_cols)].agg(['mean', 'std'])
    agg.columns = ['_'.join(col).strip() for col in agg.columns.to_flat_index()]
    return agg.reset_index()



def build_main_comparison_table(metrics_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for controller, g in metrics_df.groupby('controller'):
        rows.append({
            'Controller': controller,
            'Ramp95': mean_std_str(g['ramp95_kw_per_min']),
            'CapViolPct': mean_std_str(g['cap_violation_pct_total']),
            'Throughput': mean_std_str(g['throughput_kwh']),
            'EFC': mean_std_str(g['efc']),
            'LFP_CycleLossPct': mean_std_str(g['lfp_cycle_loss_pct'], ndigits=4),
            'HighSOCDwell': mean_std_str(g['t_high_soc_h']),
            'HighCExposure': mean_std_str(g['t_high_c_h']),
            'IDOD': mean_std_str(g['idod'], ndigits=4),
        })
    return pd.DataFrame(rows)



def build_stress_proxy_table(metrics_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for controller, g in metrics_df.groupby('controller'):
        rows.append({
            'Controller': controller,
            'Throughput': mean_std_str(g['throughput_kwh']),
            'EFC': mean_std_str(g['efc']),
            'LFP_CycleLossPct': mean_std_str(g['lfp_cycle_loss_pct'], ndigits=4),
            'T_high_SOC': mean_std_str(g['t_high_soc_h']),
            'Q95_Ceq': mean_std_str(g['ceq_q95']),
            'T_high_C': mean_std_str(g['t_high_c_h']),
            'IDOD': mean_std_str(g['idod'], ndigits=4),
        })
    return pd.DataFrame(rows)



def build_ablation_table(metrics_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for controller, g in metrics_df.groupby('controller'):
        rows.append({
            'Variant': controller,
            'Ramp95': mean_std_str(g['ramp95_kw_per_min']),
            'Throughput': mean_std_str(g['throughput_kwh']),
            'LFP_CycleLossPct': mean_std_str(g['lfp_cycle_loss_pct'], ndigits=4),
            'T_high_SOC': mean_std_str(g['t_high_soc_h']),
            'IDOD': mean_std_str(g['idod'], ndigits=4),
            'MicroCycles': mean_std_str(g['n_micro']),
            'FlipDay': mean_std_str(g['flip_per_day']),
        })
    return pd.DataFrame(rows)


def build_claims_summary_table(metrics_df: pd.DataFrame, reference: str, baselines: Sequence[str],
                               unit_cols: Sequence[str] = ('scenario_seed', 'day_id')) -> pd.DataFrame:
    key_metrics = [
        'ramp95_kw_per_min', 'cap_violation_pct_total', 'throughput_kwh', 'lfp_cycle_loss_pct', 'idod', 'flip_per_day'
    ]
    ref_df = metrics_df[metrics_df['controller'] == reference].copy()
    rows = []
    for baseline in baselines:
        base_df = metrics_df[metrics_df['controller'] == baseline].copy()
        merged = ref_df.merge(base_df, on=list(unit_cols), suffixes=('_ref', '_base'))
        if merged.empty:
            continue
        row = {
            'Reference': reference,
            'Baseline': baseline,
            'Pairs': int(len(merged)),
        }
        for metric in key_metrics:
            delta = merged[f'{metric}_ref'] - merged[f'{metric}_base']
            row[f'{metric}_delta_mean'] = float(np.nanmean(delta))
            row[f'{metric}_wins'] = int(np.sum(delta < 0.0))
            row[f'{metric}_ties'] = int(np.sum(delta == 0.0))
            row[f'{metric}_losses'] = int(np.sum(delta > 0.0))
        all4 = (
            (merged['ramp95_kw_per_min_ref'] <= merged['ramp95_kw_per_min_base']) &
            (merged['cap_violation_pct_total_ref'] <= merged['cap_violation_pct_total_base']) &
            (merged['throughput_kwh_ref'] <= merged['throughput_kwh_base']) &
            (merged['idod_ref'] <= merged['idod_base'])
        )
        row['all4_nonworse_count'] = int(np.sum(all4))
        rows.append(row)
    return pd.DataFrame(rows)


def build_claims_by_scenario_table(metrics_df: pd.DataFrame, reference: str, baselines: Sequence[str],
                                   unit_cols: Sequence[str] = ('scenario_seed', 'day_id')) -> pd.DataFrame:
    rows = []
    for scenario, g in metrics_df.groupby('scenario'):
        claims = build_claims_summary_table(g, reference, baselines, unit_cols=unit_cols)
        if claims.empty:
            continue
        claims.insert(0, 'Scenario', scenario)
        rows.append(claims)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_runtime_table(tick_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for controller, g in tick_df.groupby('controller'):
        cpu = g['cpu_ms'].dropna().to_numpy(dtype=float)
        if cpu.size == 0:
            continue
        rows.append({
            'Controller': controller,
            'MeanCpuMs': float(np.mean(cpu)),
            'MedianCpuMs': float(np.median(cpu)),
            'P95CpuMs': float(np.quantile(cpu, 0.95)),
            'MaxCpuMs': float(np.max(cpu)),
        })
    return pd.DataFrame(rows)



def dataframe_to_latex_table(df: pd.DataFrame, caption: str, label: str) -> str:
    cols = list(df.columns)
    align = 'l' + 'c' * (len(cols) - 1)
    out = []
    out.append('\\begin{table}[t]')
    out.append('\\centering')
    out.append(f'\\caption{{{latex_escape(caption)}}}')
    out.append(f'\\label{{{label}}}')
    out.append(f'\\begin{{tabular}}{{{align}}}')
    out.append('\\toprule')
    out.append(' & '.join(latex_escape(c) for c in cols) + ' \\\\')
    out.append('\\midrule')
    for _, row in df.iterrows():
        out.append(' & '.join(latex_escape(str(row[c])) for c in cols) + ' \\\\')
    out.append('\\bottomrule')
    out.append('\\end{tabular}')
    out.append('\\end{table}')
    return '\n'.join(out)



def save_tables(output_dir: str | Path, *, main_df: pd.DataFrame | None = None, stress_df: pd.DataFrame | None = None,
                stats_df: pd.DataFrame | None = None, claims_df: pd.DataFrame | None = None,
                claims_by_scenario_df: pd.DataFrame | None = None,
                ablation_df: pd.DataFrame | None = None,
                sensitivity_df: pd.DataFrame | None = None,
                runtime_df: pd.DataFrame | None = None) -> None:
    out = ensure_dir(output_dir)
    if main_df is not None:
        main_df.to_csv(out / TABLE_MAP['main_comparison'], index=False)
        (out / 'main_comparison_table.tex').write_text(
            dataframe_to_latex_table(main_df, 'Final main comparison table.', 'tab:results_final_auto'), encoding='utf-8'
        )
    if stress_df is not None:
        stress_df.to_csv(out / TABLE_MAP['stress_proxy'], index=False)
        (out / 'stress_proxy_table.tex').write_text(
            dataframe_to_latex_table(stress_df, 'Battery stress proxy detail table.', 'tab:stress_proxy_auto'), encoding='utf-8'
        )
    if stats_df is not None:
        stats_df.to_csv(out / TABLE_MAP['paired_stats'], index=False)
        (out / 'paired_stats_table.tex').write_text(
            dataframe_to_latex_table(stats_df, 'Paired statistical comparison table.', 'tab:stats_auto'), encoding='utf-8'
        )
    if claims_df is not None:
        claims_df.to_csv(out / TABLE_MAP['claims_summary'], index=False)
        (out / 'claims_summary_table.tex').write_text(
            dataframe_to_latex_table(claims_df, 'Controller claim audit summary table.', 'tab:claims_auto'), encoding='utf-8'
        )
    if claims_by_scenario_df is not None:
        claims_by_scenario_df.to_csv(out / TABLE_MAP['claims_by_scenario'], index=False)
        (out / 'claims_by_scenario.tex').write_text(
            dataframe_to_latex_table(
                claims_by_scenario_df,
                'Scenario-wise controller claim audit summary table.',
                'tab:claims_scenario_auto',
            ),
            encoding='utf-8',
        )
    if ablation_df is not None:
        ablation_df.to_csv(out / TABLE_MAP['ablation'], index=False)
        (out / 'ablation_table.tex').write_text(
            dataframe_to_latex_table(ablation_df, 'Ablation results table.', 'tab:ablation_auto'), encoding='utf-8'
        )
    if sensitivity_df is not None:
        sensitivity_df.to_csv(out / TABLE_MAP['sensitivity'], index=False)
    if runtime_df is not None:
        runtime_df.to_csv(out / TABLE_MAP['runtime'], index=False)
        (out / 'runtime_summary.tex').write_text(
            dataframe_to_latex_table(runtime_df, 'Controller runtime summary table.', 'tab:runtime_auto'),
            encoding='utf-8',
        )
