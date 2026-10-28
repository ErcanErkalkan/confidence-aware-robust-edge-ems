"""Predeclared deterministic synthetic fixtures; never physical observations."""
from dataclasses import asdict
from pathlib import Path
import platform
import subprocess
import sys
import numpy as np
import pandas as pd
from jer_microgrid.config import SiteConfig
from .contracts import canonical, file_hash, ContractError

def execution_context():
    try:
        sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        raise ContractError("actual execution source SHA unavailable")
    return {"git_commit":sha,"python":sys.version,"platform":platform.platform(),
            "cpu_count":__import__("os").cpu_count(),"processor":platform.processor(),
            "environment_scope":"Captured execution environment; optimizer seeds are not independent sites."}

def make_engineering_plan(root, *, ticks=720, discovery_blocks=2, audit_blocks=2,
                          candidates=4, budget=None, seed=20261028):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    config={"schema_version":1,"source_kind":"SYNTHETIC_ENGINEERING","ticks":ticks,
        "discovery_blocks":discovery_blocks,"audit_blocks":audit_blocks,"candidates":candidates,
        "seed":seed,"cadence_minutes":2,"formula":"base_kw=15+4*sin(2*pi*t/720+block_index/3)",
        "physical_observations":False}
    # Refuse to regenerate a different fixture in an existing execution directory.
    config_path=root/"fixture_design.json"
    if config_path.exists() and config_path.read_bytes()!=canonical(config):
        raise ContractError("fixture design already frozen with different parameters")
    config_path.write_bytes(canonical(config))
    entries=[]
    for split,count,month in (("DISCOVERY",discovery_blocks,1),("AUDIT",audit_blocks,3)):
        for i in range(count):
            stamps=pd.date_range(f"2026-{month:02d}-{i+1:02d}",periods=ticks,freq="2min",tz="UTC")
            t=np.arange(ticks)
            frame=pd.DataFrame({"timestamp":stamps,"base_kw":15+4*np.sin(2*np.pi*t/720+i/3),
                                "peak_flag":((t>=480)&(t<660)).astype(int)})
            path=root/f"{split}_{i:02d}.csv"
            encoded=frame.to_csv(index=False).encode("utf-8")
            if path.exists() and path.read_bytes()!=encoded:raise ContractError("existing fixture bytes changed")
            path.write_bytes(encoded)
            entries.append({"block_id":f"{split}-{i:02d}","source_id":"SYNTHETIC-SINE-v1",
                "site_id":"SYNTHETIC-SITE","physical_unit_id":"SIMULATED-INVERTER",
                "day_id":stamps[0].date().isoformat(),"start_timestamp":stamps[0].isoformat(),
                "end_timestamp":stamps[-1].isoformat(),"split":split,"historical_exposure":"EXPOSED",
                "license_status":"SELF_GENERATED_SYNTHETIC","physical_evidence_status":"MODEL_ASSUMPTIONS_ONLY",
                "raw_path":path.name,"profile_path":path.name,"source_sha256":file_hash(path),
                "profile_sha256":file_hash(path),"cadence_minutes":2,"expected_ticks":ticks,
                "transformation_parameters":{"operation":"identity","full_day":ticks==720,"imputation":"NONE",
                    "unit":"kW","timezone":"UTC","origin":"DETERMINISTIC_SYNTHETIC_FORMULA"},
                "data_version":"SYNTHETIC-SINE-v1","exposure_record_id":"DECLARED-ENGINEERING-EXPOSED"})
    plan={"scope":"ENGINEERING_EXPOSED_OR_SYNTHETIC","source_kind":"SYNTHETIC_ENGINEERING",
        "candidate_count":candidates,"discovery_budget":budget or candidates*discovery_blocks,
        "initial_blocks":2,"output_capacity":1,"optimizer_seed":seed,"simulation_seed":seed,
        "allocation_mode":"adaptive","allocation_batch":2,"risk_weight":.5,"n_boot":200,
        "site":asdict(SiteConfig(ts_hours=2/60)),"blocks":entries,"embargo_days":7,
        "supervisor":{},"execution_context":execution_context()}
    (root/"plan.json").write_bytes(canonical(plan))
    return plan
