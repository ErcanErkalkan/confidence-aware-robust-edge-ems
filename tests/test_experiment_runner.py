import json
from pathlib import Path
import subprocess
import sys
import pytest
from crmt_edge_ems.contracts import ContractError,digest
from crmt_edge_ems.experiment_runner import Checkpoints,dry_run

def test_synthetic_pipeline_and_exact_resume(tmp_path):
    a=dry_run(tmp_path,optimizer_seed=19,simulation_seed=29)
    artifacts={p.name:p.read_bytes() for p in tmp_path.glob('*.json')}
    b=dry_run(tmp_path,optimizer_seed=19,simulation_seed=29)
    assert a['outcome']==b['outcome']
    assert artifacts=={p.name:p.read_bytes() for p in tmp_path.glob('*.json')}
    assert a['simulator_evaluations_executed']==0 and a['cost']['total_controller_block_events']==0
    with pytest.raises(ContractError,match='binding'): dry_run(tmp_path,optimizer_seed=20,simulation_seed=29)

def test_failed_stage_and_tampered_checkpoint_never_complete(tmp_path):
    s=Checkpoints(tmp_path,{'config':'a'})
    with pytest.raises(RuntimeError): s.stage('synthetic_inputs',{},lambda:(_ for _ in ()).throw(RuntimeError('failed')))
    assert json.loads((tmp_path/'checkpoint.json').read_text())['status']=='FAILED_NOT_SCIENTIFIC_EVIDENCE'
    with pytest.raises(ContractError): s.complete()
    s.stage('synthetic_inputs',{},lambda:{'x':1})
    (tmp_path/'synthetic_inputs.json').write_text('{"x":2}')
    with pytest.raises(ContractError,match='hash'): s.stage('synthetic_inputs',{},lambda:{'x':1})

def test_concurrent_lock_blocked(tmp_path):
    a=Checkpoints(tmp_path,{});b=Checkpoints(tmp_path,{})
    with a.locked():
        with pytest.raises(ContractError):
            with b.locked(): pass

def test_independent_test_cli_no_go_before_input_access(tmp_path):
    runner=Path(__file__).resolve().parents[1]/'experiments/runner/run.py'
    p=subprocess.run([sys.executable,str(runner),'independent-test','--out',str(tmp_path/'forbidden')],capture_output=True,text=True)
    assert p.returncode==2 and 'NO_GO' in p.stdout and not (tmp_path/'forbidden').exists()
