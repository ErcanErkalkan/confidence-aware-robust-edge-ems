from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from .utils import ensure_dir


plt.rcParams.update({
    'figure.dpi': 140,
    'savefig.dpi': 300,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
})


CONTROLLER_STYLES: dict[str, dict[str, object]] = {
    'Proposed': {'color': '#0f6b3f', 'label': 'Proposed', 'linewidth': 2.2, 'linestyle': '-'},
    'GR': {'color': '#4f6d7a', 'label': 'GR', 'linewidth': 2.0, 'linestyle': '--'},
    'RS': {'color': '#d48a00', 'label': 'RS', 'linewidth': 1.9, 'linestyle': '-'},
    'FBRL': {'color': '#7a3ea1', 'label': 'FBRL', 'linewidth': 1.9, 'linestyle': '-'},
    'NC': {'color': '#8c3d3d', 'label': 'NC', 'linewidth': 1.8, 'linestyle': ':'},
    'MPC_best_balanced': {'color': '#005f99', 'label': 'MPC_best_balanced', 'linewidth': 1.9, 'linestyle': '-.'},
    'MPC_best_ramp': {'color': '#5b7fff', 'label': 'MPC_best_ramp', 'linewidth': 1.9, 'linestyle': '-.'},
}


def _controller_style(name: str) -> dict[str, object]:
    style = CONTROLLER_STYLES.get(name, {})
    return {
        'color': style.get('color', '#334155'),
        'label': style.get('label', name),
        'linewidth': float(style.get('linewidth', 1.8)),
        'linestyle': style.get('linestyle', '-'),
    }


def _iter_contiguous_profile_blocks(df: pd.DataFrame) -> Iterable[pd.DataFrame]:
    group_cols = [col for col in ('scenario_seed', 'day_id') if col in df.columns]
    ordered = df.sort_values('timestamp').copy() if 'timestamp' in df.columns else df.copy()
    if not group_cols:
        yield ordered
        return
    for _, block in ordered.groupby(group_cols, sort=False):
        yield block.sort_values('timestamp')


def _select_step_window(series_df: pd.DataFrame, n_points: int) -> pd.DataFrame:
    if n_points <= 0:
        return series_df.copy()
    if 'timestamp' not in series_df.columns or 'base_kw' not in series_df.columns:
        return series_df.head(n_points).copy()
    first_controller = str(series_df['controller'].iloc[0]) if 'controller' in series_df.columns and not series_df.empty else None
    base_view = series_df[series_df['controller'] == first_controller].copy() if first_controller else series_df.copy()
    base_view = base_view.sort_values('timestamp').reset_index(drop=True)
    if len(base_view) <= n_points:
        return series_df.copy()
    step_score = base_view['base_kw'].diff().abs().fillna(0.0).to_numpy(dtype=float)
    center = int(np.argmax(step_score))
    start = max(0, min(center - n_points // 3, len(base_view) - n_points))
    end = start + n_points
    start_ts = base_view.iloc[start]['timestamp']
    end_ts = base_view.iloc[end - 1]['timestamp']
    return series_df[(series_df['timestamp'] >= start_ts) & (series_df['timestamp'] <= end_ts)].copy()


def save_ramp_cdf(series_df: pd.DataFrame, output_path: str | Path, controller_order: list[str]) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for name in controller_order:
        g = series_df[series_df['controller'] == name].copy()
        if g.empty:
            continue
        ramp_parts = []
        for block in _iter_contiguous_profile_blocks(g):
            vals = block['grid_kw'].to_numpy(dtype=float)
            if vals.size == 0:
                continue
            ramp_parts.append(np.abs(np.diff(vals, prepend=vals[0])))
        if not ramp_parts:
            continue
        ramp = np.concatenate(ramp_parts)
        xs = np.sort(ramp)
        ys = np.arange(1, len(xs) + 1) / len(xs)
        style = _controller_style(name)
        ax.plot(
            xs,
            ys,
            label=str(style['label']),
            color=str(style['color']),
            linewidth=float(style['linewidth']),
            linestyle=str(style['linestyle']),
        )
    ax.set_xlabel('Absolute PCC step (kW)')
    ax.set_ylabel('CDF')
    ax.set_title('Ramp-rate magnitude distribution')
    ax.grid(alpha=0.18, linewidth=0.6)
    ax.legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_representative_timeseries(series_df: pd.DataFrame, output_path: str | Path, controllers: list[str], n_points: int = 360) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    plot_df = series_df.copy()
    if 'timestamp' in plot_df.columns:
        plot_df['timestamp'] = pd.to_datetime(plot_df['timestamp'])
    if n_points and 'timestamp' in plot_df.columns:
        plot_df = _select_step_window(plot_df, n_points)
    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    base_plotted = False
    for name in controllers:
        g = plot_df[plot_df['controller'] == name].sort_values('timestamp').copy()
        if g.empty:
            continue
        style = _controller_style(name)
        if not base_plotted:
            ax.plot(g['timestamp'], g['base_kw'], label='Base net demand', color='#111827', linewidth=1.7, alpha=0.75)
            base_plotted = True
        ax.plot(
            g['timestamp'],
            g['grid_kw'],
            label=f"Grid ({style['label']})",
            color=str(style['color']),
            linewidth=float(style['linewidth']),
            linestyle=str(style['linestyle']),
        )
    ax.set_xlabel('Time')
    ax.set_ylabel('Power (kW)')
    ax.set_title('Representative base and grid power trajectories')
    ax.legend(fontsize=8)
    ax.grid(alpha=0.18, linewidth=0.6)
    if 'timestamp' in plot_df.columns and not plot_df.empty:
        locator = mdates.AutoDateLocator(minticks=4, maxticks=7)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_metric_boxplot(metrics_df: pd.DataFrame, output_path: str | Path, metric: str,
                        controller_order: list[str], ylabel: str, title: str | None = None) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    data = []
    labels = []
    for controller in controller_order:
        vals = metrics_df[metrics_df['controller'] == controller][metric].dropna().to_numpy(dtype=float)
        if vals.size == 0:
            continue
        data.append(vals)
        labels.append(controller)
    if not data:
        plt.close(fig)
        return
    bp = ax.boxplot(data, labels=[str(_controller_style(label)['label']) for label in labels], patch_artist=True, showfliers=False, widths=0.56)
    for patch, label in zip(bp['boxes'], labels):
        patch.set_facecolor(str(_controller_style(label)['color']))
        patch.set_alpha(0.62)
        patch.set_edgecolor('#334155')
        patch.set_linewidth(1.1)
    for key in ('whiskers', 'caps', 'medians'):
        for artist in bp[key]:
            artist.set_color('#334155')
            artist.set_linewidth(1.1)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(axis='y', alpha=0.18, linewidth=0.6)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_rainflow_hist(hist_df: pd.DataFrame, output_path: str | Path, controllers: list[str]) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    width = 0.12
    bins = sorted(hist_df['depth_bin'].unique())
    xs = np.arange(len(bins))
    for i, name in enumerate(controllers):
        g = hist_df[hist_df['controller'] == name]
        if g.empty:
            continue
        vals = [float(g[g['depth_bin'] == b]['count_weighted'].sum()) for b in bins]
        ax.bar(xs + i * width, vals, width=width, label=name)
    ax.set_xticks(xs + width * (len(controllers) - 1) / 2)
    ax.set_xticklabels(bins, rotation=20)
    ax.set_ylabel('Count-weighted cycles')
    ax.set_title('Rainflow cycle-depth histogram')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_stress_boxplots(metrics_df: pd.DataFrame, output_path: str | Path, metrics: list[str], controller_order: list[str]) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, axes = plt.subplots(len(metrics), 1, figsize=(8.0, 2.8 * len(metrics)), sharex=True)
    if len(metrics) == 1:
        axes = [axes]
    for ax, metric in zip(axes, metrics):
        data = [metrics_df[metrics_df['controller'] == c][metric].to_numpy(dtype=float) for c in controller_order if c in metrics_df['controller'].unique()]
        labels = [c for c in controller_order if c in metrics_df['controller'].unique()]
        ax.boxplot(data, labels=labels, showfliers=False)
        ax.set_ylabel(metric)
        ax.set_title(metric)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_pareto_frontier(frontier_df: pd.DataFrame, output_path: str | Path, x: str = 'ramp95_kw_per_min', y: str = 'throughput_kwh') -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    if not frontier_df.empty:
        ax.scatter(frontier_df[x], frontier_df[y], s=20)
        for _, row in frontier_df.iterrows():
            ax.annotate(row.get('label', ''), (row[x], row[y]), fontsize=7)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title('Optimization Pareto frontier')
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def save_sensitivity_heatmap(pivot_df: pd.DataFrame, output_path: str | Path, title: str) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    fig, ax = plt.subplots(figsize=(6.0, 4.5))
    mat = pivot_df.to_numpy(dtype=float)
    im = ax.imshow(mat, aspect='auto')
    ax.set_xticks(range(pivot_df.shape[1]))
    ax.set_xticklabels([str(c) for c in pivot_df.columns])
    ax.set_yticks(range(pivot_df.shape[0]))
    ax.set_yticklabels([str(i) for i in pivot_df.index])
    ax.set_title(title)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
