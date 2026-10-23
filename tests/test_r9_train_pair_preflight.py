"""Synthetic fail-closed tests; NO OpenCEM TEST/VAL measurements."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from r9_equal_capacity_20261023 import r9_train_pair_preflight as gate


def _write(path: Path, names, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def sandbox_pair(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(gate, 'BUDGET', 4)
    monkeypatch.setattr(gate, 'CANDIDATES', 2)
    ids = [('a', 'opencem:b1'), ('a', 'opencem:b2'), ('b', 'opencem:b1'), ('b', 'opencem:b2')]
    for F in (0, 1):
        folder = tmp_path / f'f{F}'
        folder.mkdir()
        ledger = [dict(ordinal=str(i), method_id='CRMT', candidate_id=cid, block_id=bid, unit='controller_block_evaluation') for i, (cid, bid) in enumerate(ids, 1)]
        _write(folder / 'ledger.csv', ['ordinal', 'method_id', 'candidate_id', 'block_id', 'unit'], ledger)
        metrics = []
        for cid, bid in ids:
            base = 1 if cid == 'a' else 2
            metrics.append(dict(candidate_id=cid, block_id=bid, source='OpenCEM', split='train', cap_violation_pct_total=str(base), lfp_cycle_loss_pct=str(base / 10), ramp95_kw_per_min='0.22', flip_per_day='1.0', mean_cpu_ms=str(0.4 + 0.001 * F), max_cpu_ms=str(0.8 + 0.002 * F)))
        _write(folder / 'candidate_metrics.csv', list(metrics[0]), metrics)
        front = [{x: metrics[i][x] for x in ['candidate_id', *gate.OBJECTIVES]} for i in ([0] if F == 0 else [0, 2])]
        # Native front is an independent retained subset, not an enforced K20.
        _write(folder / 'optimizer_front.csv', list(front[0]), front)
        summary = {
            'stage': gate.STAGE, 'protocol_id': gate.PROTOCOL, 'status': 'EXPLORATORY',
            'condition_id': f'C0_F{F}_A0', 'seed': 1001,
            'original_git_sha': gate.SOURCE_COMMIT, 'source_data_commit': gate.DATA_COMMIT,
            'canonical_manifest_sha256': gate.MANIFEST_SHA,
            'candidate_count': 2, 'archive_count': 1 if F == 0 else 2,
            'train_budget_used': 4, 'archive_mode': 'risk_pareto' if F == 0 else 'confidence',
            'allocation_mode': 'round_robin', 'risk_tail_weight': 0.0,
            'source_context': {'split': 'train', 'split_block_count': 210, 'manifest_sha256': gate.MANIFEST_SHA},
            'files_sha256': {name: gate.sha256(folder / name) for name in gate.REQUIRED},
        }
        (folder / 'run_summary.json').write_text(json.dumps(summary))
    return tmp_path / 'f0', tmp_path / 'f1'


def _reseal(folder: Path, filename: str):
    path = folder / 'run_summary.json'
    summary = json.loads(path.read_text())
    summary['files_sha256'][filename] = gate.sha256(folder / filename)
    path.write_text(json.dumps(summary))


def _modify_csv(folder, name, key, value):
    path = folder / name
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    columns = list(rows[0])
    rows[0][key] = value
    _write(path, columns, rows)
    _reseal(folder, name)


def test_valid_pair_allows_timing_variation(sandbox_pair):
    out = gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)
    assert out['science_and_non_timing_metrics_equal']
    assert out['archive_size_F0'] == 1 and out['archive_size_F1'] == 2
    assert out['timing_differences_in_rows']['mean_cpu_ms'] == 4
    assert not out['candidate_metrics_raw_sha_equal']


def test_raw_corruption_rejected(sandbox_pair):
    p = sandbox_pair[0] / 'ledger.csv'
    p.write_text(p.read_text() + '\n')
    with pytest.raises(gate.PreflightBlocked, match='SHA-256 mismatch'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_scientific_objective_diff_rejected_even_if_resealed(sandbox_pair):
    _modify_csv(sandbox_pair[1], 'candidate_metrics.csv', 'flip_per_day', '17.0')
    with pytest.raises(gate.PreflightBlocked, match='science objective differs'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_ledger_pair_mismatch_rejected_even_if_resealed(sandbox_pair):
    _modify_csv(sandbox_pair[1], 'ledger.csv', 'block_id', 'opencem:b3')
    _modify_csv(sandbox_pair[1], 'candidate_metrics.csv', 'block_id', 'opencem:b3')
    with pytest.raises(gate.PreflightBlocked, match='evaluation ledger diverges'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_test_label_rejected(sandbox_pair):
    _modify_csv(sandbox_pair[1], 'candidate_metrics.csv', 'split', 'test')
    with pytest.raises(gate.PreflightBlocked, match='invalid TRAIN metrics'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_wrong_source_commit_rejected(sandbox_pair):
    path = sandbox_pair[0] / 'run_summary.json'
    s = json.loads(path.read_text());s['original_git_sha'] = 'wrong';path.write_text(json.dumps(s))
    with pytest.raises(gate.PreflightBlocked, match='original_git_sha'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)



def test_unrecorded_local_source_commit_rejected(sandbox_pair):
    """A historical condition with this marker cannot pass the provenance gate."""
    path = sandbox_pair[1] / 'run_summary.json'
    summary = json.loads(path.read_text())
    summary['original_git_sha'] = 'UNRECORDED_LOCAL_SHA'
    path.write_text(json.dumps(summary))
    with pytest.raises(gate.PreflightBlocked, match='original_git_sha'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_extra_front_candidate_rejected(sandbox_pair):
    _modify_csv(sandbox_pair[0], 'optimizer_front.csv', 'candidate_id', 'ghost')
    with pytest.raises(gate.PreflightBlocked, match='unknown candidate'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_metric_ledger_mismatch_rejected(sandbox_pair):
    _modify_csv(sandbox_pair[0], 'candidate_metrics.csv', 'block_id', 'opencem:unknown')
    with pytest.raises(gate.PreflightBlocked, match='metrics/ledger'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_invalid_seed_rejected(sandbox_pair):
    with pytest.raises(gate.PreflightBlocked, match='unknown historical seed'):
        gate.audit_pair(*sandbox_pair, seed=1009, c=0, a=0)


def test_nonfinite_rejected(sandbox_pair):
    _modify_csv(sandbox_pair[1], 'candidate_metrics.csv', 'cap_violation_pct_total', 'nan')
    with pytest.raises(gate.PreflightBlocked, match='nonfinite'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_cpu_nonnumeric_rejected(sandbox_pair):
    _modify_csv(sandbox_pair[0], 'candidate_metrics.csv', 'mean_cpu_ms', 'bad')
    with pytest.raises(gate.PreflightBlocked, match='invalid number'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)


def test_risk_factor_mapping_rejected(sandbox_pair):
    path = sandbox_pair[1] / 'run_summary.json'
    s = json.loads(path.read_text());s['risk_tail_weight'] = 0.5;path.write_text(json.dumps(s))
    with pytest.raises(gate.PreflightBlocked, match='incorrect risk C mapping'):
        gate.audit_pair(*sandbox_pair, seed=1001, c=0, a=0)
