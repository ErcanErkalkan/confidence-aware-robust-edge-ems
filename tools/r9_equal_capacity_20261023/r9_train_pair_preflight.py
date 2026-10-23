#!/usr/bin/env python3
"""Fail-closed historical TRAIN pair integrity preflight for CRMT R9.

Reads only local historical TRAIN artifacts. NEVER performs EMS evaluations,
VALIDATION evaluation, independent TEST or prospective preregistration.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

STAGE = 'GATE3_FACTORIAL_TRAIN_ONLY'
PROTOCOL = 'CRMT-EAAI-E3-FACTORIAL-8CELL-EXPLORATORY-v1'
SOURCE_COMMIT = 'be5756321617087ca421a639d60a99513f29d889'
DATA_COMMIT = '5884d253a5267fb240b7a8df6fa9e4d49a905167'
MANIFEST_SHA = '3226013d8c8f0672162f10f3d1c6da5e064d1dcb28e973f5d054de2fe296b9b1'
REQUIRED = ('candidate_metrics.csv', 'ledger.csv', 'optimizer_front.csv')
OBJECTIVES = ('cap_violation_pct_total', 'lfp_cycle_loss_pct', 'ramp95_kw_per_min', 'flip_per_day')
TIMING = ('mean_cpu_ms', 'max_cpu_ms')
BUDGET = 12_600
CANDIDATES = 256


class PreflightBlocked(ValueError):
    """Any wrong provenance, mismatched science data or incomplete evidence."""


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise PreflightBlocked(msg)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        require(r.fieldnames is not None and len(r.fieldnames) == len(set(r.fieldnames)), f'{path.name}: invalid headers')
        require(required <= set(r.fieldnames), f'{path.name}: missing {sorted(required - set(r.fieldnames))}')
        rows = list(r)
        require(bool(rows) and all(None not in row and None not in row.values() for row in rows), f'{path.name}: empty/malformed CSV')
        return rows


def number(x: str, *, what: str) -> Decimal:
    try:
        n = Decimal(x)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PreflightBlocked(f'{what}: invalid number') from exc
    require(n.is_finite(), f'{what}: nonfinite number')
    return n


def check_run(folder: Path, *, seed: int, c: int, f: int, a: int) -> dict:
    path = folder / 'run_summary.json'
    require(path.is_file(), f'{path}: missing summary')
    try:
        summary = json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PreflightBlocked(f'{path}: invalid JSON') from exc
    cond = f'C{c}_F{f}_A{a}'
    check = {
        'stage': STAGE, 'protocol_id': PROTOCOL, 'status': 'EXPLORATORY',
        'condition_id': cond, 'seed': seed, 'original_git_sha': SOURCE_COMMIT,
        'source_data_commit': DATA_COMMIT, 'canonical_manifest_sha256': MANIFEST_SHA,
        'candidate_count': CANDIDATES, 'train_budget_used': BUDGET,
        'archive_mode': 'confidence' if f else 'risk_pareto',
        'allocation_mode': 'adaptive' if a else 'round_robin',
    }
    for key, expected in check.items():
        require(type(summary.get(key)) is type(expected) and summary[key] == expected, f'{cond}: invalid {key}: {summary.get(key)!r}')
    require(number(str(summary.get('risk_tail_weight')), what='risk_tail_weight') == Decimal('0.5' if c else '0'), f'{cond}: incorrect risk C mapping')
    ctx = summary.get('source_context') or {}
    require(ctx.get('split') == 'train' and ctx.get('split_block_count') == 210 and ctx.get('manifest_sha256') == MANIFEST_SHA, f'{cond}: invalid TRAIN context')
    expected_hashes = summary.get('files_sha256') or {}
    for fname in REQUIRED:
        file_path = folder / fname
        require(file_path.is_file() and fname in expected_hashes, f'{cond}: missing {fname} or SHA manifest')
        require(sha256(file_path) == expected_hashes[fname], f'{cond}: SHA-256 mismatch for {fname}')

    events = read_csv(folder / 'ledger.csv', {'ordinal', 'method_id', 'candidate_id', 'block_id', 'unit'})
    require(len(events) == BUDGET, f'{cond}: incorrect ledger budget')
    signature = []
    for i, row in enumerate(events, 1):
        require(row['ordinal'] == str(i) and row['method_id'] == 'CRMT' and row['unit'] == 'controller_block_evaluation', f'{cond}: ledger row {i} malformed')
        require(row['candidate_id'] and row['block_id'].startswith('opencem:'), f'{cond}: ledger identity invalid')
        signature.append((row['candidate_id'], row['block_id']))
    require(len(signature) == len(set(signature)), f'{cond}: duplicate controller-block evaluation')

    required_metrics = {'candidate_id', 'block_id', 'split', 'source', *OBJECTIVES, *TIMING}
    metrics = read_csv(folder / 'candidate_metrics.csv', required_metrics)
    require(len(metrics) == BUDGET, f'{cond}: metrics row count differs from ledger')
    measurements = {}
    for row in metrics:
        pair = (row['candidate_id'], row['block_id'])
        require(pair not in measurements and row['split'] == 'train' and row['source'] == 'OpenCEM', f'{cond}: invalid TRAIN metrics row')
        for col in (*OBJECTIVES, *TIMING):
            number(row[col], what=f'{cond}: {col}')
        measurements[pair] = row
    require(set(measurements) == set(signature), f'{cond}: metrics/ledger candidate-block identities mismatch')
    ids = {cid for cid, _ in signature}
    require(len(ids) == CANDIDATES, f'{cond}: expected 256 distinct candidates')

    front = read_csv(folder / 'optimizer_front.csv', {'candidate_id', *OBJECTIVES})
    front_ids = [row['candidate_id'] for row in front]
    require(len(front_ids) == len(set(front_ids)) == summary.get('archive_count'), f'{cond}: invalid archive front membership count')
    require(set(front_ids) <= ids, f'{cond}: archive contains unknown candidate')
    for row in front:
        for objective in OBJECTIVES:
            number(row[objective], what=f'{cond}: front {objective}')
    return {
        'summary': summary, 'signatures': signature, 'measurements': measurements,
        'file_sha256': {fname: expected_hashes[fname] for fname in REQUIRED},
        'front_count': len(front_ids),
    }


def audit_pair(f0_dir: Path, f1_dir: Path, *, seed: int, c: int, a: int) -> dict:
    require(seed in range(1001, 1006) and c in (0, 1) and a in (0, 1), 'unknown historical seed or factors')
    require(f0_dir.resolve() != f1_dir.resolve(), 'F0/F1 must be distinct run directories')
    f0 = check_run(f0_dir, seed=seed, c=c, f=0, a=a)
    f1 = check_run(f1_dir, seed=seed, c=c, f=1, a=a)
    require(f0['signatures'] == f1['signatures'], 'F0/F1 recorded evaluation ledger diverges')
    changed = {k: 0 for k in TIMING}
    for pair, arow in f0['measurements'].items():
        brow = f1['measurements'][pair]
        for key in arow:
            if key in TIMING:
                if number(arow[key], what=key) != number(brow[key], what=key):
                    changed[key] += 1
            elif key in OBJECTIVES:
                require(number(arow[key], what=key) == number(brow[key], what=key), f'F0/F1 science objective differs: {pair} {key}')
            else:
                require(arow[key] == brow[key], f'F0/F1 non-timing field differs: {pair} {key}')
    return {
        'status': 'HISTORICAL_TRAIN_PAIRED_PREFLIGHT_ONLY_NOT_NEW_TEST',
        'seed': seed, 'C': c, 'A': a, 'F0': f'C{c}_F0_A{a}', 'F1': f'C{c}_F1_A{a}',
        'budget_per_condition': BUDGET, 'identical_candidate_block_evaluation_pairs': True,
        'objective_fields_identical': list(OBJECTIVES), 'science_and_non_timing_metrics_equal': True,
        'timing_differences_in_rows': changed,
        'archive_size_F0': f0['front_count'], 'archive_size_F1': f1['front_count'],
        'candidate_metrics_raw_sha_equal': f0['file_sha256']['candidate_metrics.csv'] == f1['file_sha256']['candidate_metrics.csv'],
        'ledger_raw_sha_equal': f0['file_sha256']['ledger.csv'] == f1['file_sha256']['ledger.csv'],
        'input_sha256': {f'F{idx}': data['file_sha256'] for idx, data in [(0, f0), (1, f1)]},
        'limitation': 'Historical TRAIN; no new equal-capacity R9 execution, no VALIDATION, no prospective independent TEST or preregistration.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--f0-dir', type=Path, required=True)
    parser.add_argument('--f1-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--c', type=int, required=True)
    parser.add_argument('--a', type=int, required=True)
    parser.add_argument('--output-json', type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.output_json.exists(), 'output already exists: overwrite is forbidden')
        out = audit_pair(args.f0_dir, args.f1_dir, seed=args.seed, c=args.c, a=args.a)
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    except (PreflightBlocked, OSError, ValueError, TypeError) as exc:
        parser.exit(2, f'R9_PREFLIGHT_BLOCKED: {exc}\n')
    print('HISTORICAL TRAIN PAIRED PREFLIGHT VERIFIED - NO INDEPENDENT TEST')


if __name__ == '__main__':
    main()
