"""Preflight cannot be bypassed by mutating a live backend or CLI flags."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.engineering_fixtures import make_engineering_plan
from crmt_edge_ems.execution_backend import EMSExecutionBackend

@pytest.mark.parametrize("change",["plan","profile","file"])
def test_live_preflight_binding(tmp_path,change):
    root=tmp_path/"fixture";plan=make_engineering_plan(root,ticks=4,candidates=2)
    backend=EMSExecutionBackend(plan,data_root=root,output=tmp_path/"execution")
    if change=="plan":backend.plan["risk_weight"]=.25
    elif change=="profile":backend.blocks[0].profile.loc[0,"base_kw"]+=1
    else:(root/plan["blocks"][0]["profile_path"]).write_text("tamper")
    with pytest.raises(ContractError,match="changed after preflight"):backend.run("prepare")
    assert backend.store.state["stages"]=={}

def test_fixed_r19_cannot_mix_risk_functionals(tmp_path):
    plan=make_engineering_plan(tmp_path/"fixture",ticks=4,candidates=2)
    plan.update(candidate_count=256,discovery_budget=12600,output_capacity=10,risk_weight=.25)
    with pytest.raises(ContractError,match="tail_weight=0.5"):
        EMSExecutionBackend(plan,data_root=tmp_path/"fixture",output=tmp_path/"execution")

def test_cli_does_not_read_plan_without_explicit_engineering(tmp_path):
    cli=Path(__file__).resolve().parents[1]/"experiments"/"runner"/"run.py"
    r=subprocess.run([sys.executable,str(cli),"prepare","--ems-plan",str(tmp_path/"absent")],capture_output=True,text=True)
    assert r.returncode==2
    assert "NO_GO" in r.stdout and "FileNotFound" not in r.stdout

def test_cli_engineering_prepare_uses_real_backend(tmp_path):
    root=tmp_path/"fixture";plan=make_engineering_plan(root,ticks=4,candidates=2)
    cli=Path(__file__).resolve().parents[1]/"experiments"/"runner"/"run.py"
    r=subprocess.run([sys.executable,str(cli),"prepare","--engineering","--ems-plan",str(root/"plan.json"),
        "--data-root",str(root),"--out",str(tmp_path/"execution")],capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr
    result=json.loads(r.stdout)
    assert result["scope"]=="ENGINEERING_EXPOSED_OR_SYNTHETIC"
    assert result["CONFIRMATORY_STATUS"]=="NO_GO"
