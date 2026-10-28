"""Real EMS execution backend; scientific admission remains independently gated.

ENGINEERING permits only explicitly exposed/synthetic fixtures. No engineering
flag authorizes prospective observations, an independent TEST, or publication.
Historical replay, metrics, R19 drafts, and immutable result packages are untouched.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import time
import numpy as np
import pandas as pd

from .contracts import ContractError, OBJECTIVES, canonical, digest, file_hash, integer, strict_risk, pareto_mask
from .budget import EvaluationLedger
from .generator import sobol_candidates
from .parameter_space import validate_physical
from .risk import RiskConfig
from .study import CRMTStudy
from .archive import CandidateRecord, ConfidenceArchive
from .strict_replay_v2 import StrictReplayBlock, StrictReplayEvaluator
from .safety.process_supervisor import ProcessSupervisorConfig
from .r19_primary import select_shortlists, audit_fidelity
from .gates import gate_report, require_scientific_execution
from .engineering_fixtures import execution_context
from jer_microgrid.config import SiteConfig

STAGES = ("prepare", "verify", "gate-check", "discovery", "archive-build",
          "shortlist-select", "audit", "analyze", "report")

def plain(value):
    if isinstance(value, np.ndarray): return plain(value.tolist())
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {str(k): plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [plain(v) for v in value]
    if isinstance(value, pd.Timestamp): return value.isoformat()
    return value

class StageStore:
    """Bound outputs; failed or interrupted simulator stages are never auto-retried."""
    def __init__(self, root, binding):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.binding=digest(binding); self.path=self.root/"execution_checkpoint.json"
        self.state={"schema_version":1,"binding_sha256":self.binding,"stages":{}}
        if self.path.exists():
            self.state=json.loads(self.path.read_text(encoding="utf-8"))
            if self.state.get("binding_sha256")!=self.binding: raise ContractError("resume source/config/environment binding mismatch")

    def save(self):
        pending=self.root/"execution_checkpoint.pending"
        pending.write_bytes(canonical(self.state)); os.replace(pending,self.path)

    @contextmanager
    def locked(self):
        path=self.root/".execution.lock"
        try: handle=path.open("x",encoding="utf-8")
        except FileExistsError as exc: raise ContractError("execution already locked; stale ownership needs review") from exc
        try:
            handle.write(str(os.getpid())); handle.close(); yield
        finally:
            handle.close(); path.unlink()

    def load(self,name):
        receipt=self.state["stages"].get(name)
        if not receipt or receipt["status"]!="COMPLETE": raise ContractError("required stage incomplete: "+name)
        path=self.root/(name+".json")
        if not path.is_file() or file_hash(path)!=receipt["output_sha256"]: raise ContractError("checkpoint artifact mismatch: "+name)
        return json.loads(path.read_text(encoding="utf-8"))

    def stage(self,name,inputs,operation):
        if name not in STAGES: raise ContractError("unknown execution stage")
        current=self.state["stages"].get(name)
        if current:
            if current.get("input_sha256")!=digest(inputs): raise ContractError("stage input binding mismatch")
            if current["status"]!="COMPLETE": raise ContractError("interrupted/failed stage cannot be silently retried")
            return self.load(name)
        started=datetime.now(timezone.utc).isoformat()
        self.state["stages"][name]={"status":"STARTED","input_sha256":digest(inputs),"started_at":started}
        self.save(); wall=time.perf_counter(); cpu=time.process_time()
        try:
            result=plain(operation()); encoded=canonical(result)
            target=self.root/(name+".json")
            if target.exists(): raise ContractError("untracked stage artifact requires explicit investigation")
            pending=self.root/(name+".pending"); pending.write_bytes(encoded); os.replace(pending,target)
            self.state["stages"][name].update(status="COMPLETE",output_sha256=file_hash(target),
                ended_at=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-wall,
                parent_process_cpu_seconds=time.process_time()-cpu)
            self.save(); return result
        except BaseException as exc:
            failure={"stage":name,"error_type":type(exc).__name__,"message":str(exc),
                "binding_sha256":self.binding,"started_at":started,"ended_at":datetime.now(timezone.utc).isoformat(),
                "wall_seconds":time.perf_counter()-wall,"parent_process_cpu_seconds":time.process_time()-cpu,
                "status":"FAILED_CHARGES_PRESERVED_NO_AUTOMATIC_RETRY"}
            (self.root/(name+"_failure.json")).write_bytes(canonical(failure))
            self.state["stages"][name].update(status="FAILED",failure=failure); self.save(); raise

class EMSExecutionBackend:
    """Opt-in active backend, distinct from historical and artificial-loss dry runs."""
    def __init__(self, plan, *, data_root, output):
        self.scope=plan.get("scope") if isinstance(plan,dict) else None
        if self.scope not in {"ENGINEERING_EXPOSED_OR_SYNTHETIC","PROSPECTIVE"}: raise ContractError("explicit execution scope required")
        if self.scope=="PROSPECTIVE": require_scientific_execution("discovery")
        self.plan=json.loads(canonical(plan)); plan=self.plan
        self.data_root=Path(data_root).resolve()
        self.actual_execution_context=execution_context()
        declared_commit=plan.get("execution_context",{}).get("git_commit")
        if declared_commit!=self.actual_execution_context["git_commit"]:
            raise ContractError("declared source commit differs from actual execution checkout")
        if plan.get("source_kind") not in {"SYNTHETIC_ENGINEERING","HISTORICAL_TRAIN_ENGINEERING","AUTHORIZED_PROSPECTIVE"}:
            raise ContractError("explicit source kind required")
        if self.scope!="PROSPECTIVE" and plan["source_kind"]=="AUTHORIZED_PROSPECTIVE":
            raise ContractError("engineering scope cannot downgrade a prospective source")
        for field in ("candidate_count","discovery_budget","initial_blocks","output_capacity"):
            integer(plan.get(field),field,1)
        integer(plan.get("optimizer_seed"),"optimizer_seed");integer(plan.get("simulation_seed"),"simulation_seed")
        integer(plan.get("allocation_batch",2),"allocation_batch",1)
        integer(plan.get("n_boot",200),"n_boot",1)
        if plan.get("allocation_mode","adaptive") not in {"adaptive","round_robin"}:
            raise ContractError("invalid declared allocation mode")
        strict_risk(np.zeros((2,4)),tail_weight=plan.get("risk_weight",.5))
        if plan["initial_blocks"]<2: raise ContractError("at least two initial paired blocks required")
        if plan["discovery_budget"]<plan["candidate_count"]*plan["initial_blocks"]: raise ContractError("initial budget insufficient")
        if plan["output_capacity"]>plan["candidate_count"]: raise ContractError("capacity exceeds candidate pool")
        if self.scope=="PROSPECTIVE" and (plan["candidate_count"],plan["discovery_budget"],plan["output_capacity"])!=(256,12600,10):
            raise ContractError("prospective R19 fixed design mismatch")
        if (plan["candidate_count"],plan["discovery_budget"],plan["output_capacity"])==(256,12600,10) and plan.get("risk_weight",.5)!=.5:
            raise ContractError("fixed R19 archive/ranking must use identical tail_weight=0.5")
        self.site=SiteConfig(**plan["site"])
        self.blocks=[]; self.source_bindings=[]; self.physical_sites={}
        for entry in plan.get("blocks",[]): self.blocks.append(self._load_block(entry))
        if not self.blocks: raise ContractError("empty replay inventory")
        self.discovery=[b for b in self.blocks if b.split=="DISCOVERY"];self.audit=[b for b in self.blocks if b.split=="AUDIT"]
        if len(self.discovery)<plan["initial_blocks"] or len(self.audit)<2: raise ContractError("incomplete declared support")
        if plan["discovery_budget"]>plan["candidate_count"]*len(self.discovery):
            raise ContractError("DISCOVERY budget exceeds unique candidate/block support")
        if self.scope=="PROSPECTIVE" and len(self.audit)<60: raise ContractError("prospective panel below predeclared sixty blocks")
        # Validate every block together before candidate generation, reservation, or simulation.
        self.validation_evaluator=self._evaluator(None)
        self.validation_evaluator.validate_blocks(self.blocks)
        self._partition_check()
        self.binding={"implementation":"REAL-EMS-BACKEND-v2-DRAFT","plan_sha256":digest(plan),
            "source_bindings":self.source_bindings,"site":asdict(self.site),"scope":self.scope,
            "execution_context":self.actual_execution_context}
        self.block_snapshot_hashes={b.block_id:digest(plain(b.profile.to_dict(orient="records"))) for b in self.blocks}
        self.store=StageStore(output,self.binding)

    def _path(self,value):
        p=(self.data_root/value).resolve()
        if not p.is_relative_to(self.data_root) or not p.is_file(): raise ContractError("unsafe/missing input path")
        return p

    def _load_block(self,e):
        required={"block_id","source_id","site_id","physical_unit_id","day_id","start_timestamp","end_timestamp",
            "split","historical_exposure","license_status","physical_evidence_status","raw_path","source_sha256",
            "profile_path","profile_sha256","transformation_parameters","cadence_minutes","expected_ticks",
            "data_version","exposure_record_id"}
        if not isinstance(e,dict) or not required<=set(e): raise ContractError("block provenance schema incomplete")
        integer(e["expected_ticks"],"expected_ticks",2)
        integer(e["cadence_minutes"],"cadence_minutes",1)
        if not isinstance(e["transformation_parameters"],dict):
            raise ContractError("block transformation parameters must be a mapping")
        if not isinstance(e["physical_unit_id"],str) or not e["physical_unit_id"].strip():
            raise ContractError("block physical unit identity required")
        if e["split"] not in {"DISCOVERY","AUDIT"}: raise ContractError("backend permits only declared DISCOVERY/AUDIT")
        if self.scope!="PROSPECTIVE" and e["historical_exposure"]!="EXPOSED": raise ContractError("engineering inputs must be explicitly exposed fixtures/history")
        raw=self._path(e["raw_path"]); profile=self._path(e["profile_path"])
        raw_bytes=raw.read_bytes(); profile_bytes=raw_bytes if raw==profile else profile.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest()!=e["source_sha256"] or hashlib.sha256(profile_bytes).hexdigest()!=e["profile_sha256"]:
            raise ContractError("source/transformed byte hash mismatch")
        # Parse the exact verified bytes; a second path read would permit a
        # hash/parse race during cloud synchronization or concurrent writes.
        frame=pd.read_csv(io.BytesIO(profile_bytes)); frame["timestamp"]=pd.to_datetime(frame["timestamp"],errors="raise")
        if len(frame)!=e["expected_ticks"]: raise ContractError("declared support tick count mismatch")
        if frame["timestamp"].iloc[0].isoformat()!=pd.Timestamp(e["start_timestamp"]).isoformat() or frame["timestamp"].iloc[-1].isoformat()!=pd.Timestamp(e["end_timestamp"]).isoformat():
            raise ContractError("declared time bounds differ from profile")
        zone=e["transformation_parameters"].get("timezone")
        if not isinstance(zone,str) or not zone:
            raise ContractError("replay inventory requires declared local timezone")
        try:
            days=pd.DatetimeIndex(frame["timestamp"]).tz_convert(zone).strftime("%Y-%m-%d")
        except (TypeError,ValueError,KeyError) as exc:
            raise ContractError("invalid inventory timezone") from exc
        if any(day!=e["day_id"] for day in days):
            raise ContractError("declared day_id differs from observed local-day support")
        physical=e["physical_unit_id"]; site=str(e["site_id"])
        if physical in self.physical_sites and self.physical_sites[physical]!=site:
            raise ContractError("physical unit cannot change site identity across partitions")
        self.physical_sites[physical]=site
        self.source_bindings.append({"block_id":e["block_id"],"raw_sha256":e["source_sha256"],"profile_sha256":e["profile_sha256"],"data_version":e["data_version"]})
        return StrictReplayBlock(block_id=e["block_id"],profile=frame,source=e["source_id"],split=e["split"],site_id=e["site_id"],
            cadence_minutes=e["cadence_minutes"],expected_ticks=e["expected_ticks"],source_sha256=e["source_sha256"],
            transformation_parameters=e["transformation_parameters"],physical_unit_id=e["physical_unit_id"],data_version=e["data_version"],
            exposure_record_id=e["exposure_record_id"],historical_exposure=e["historical_exposure"])

    def _partition_check(self):
        from data_adapters.validation import validate_partitions
        entries=[]
        for e in self.plan["blocks"]:
            entries.append({"block_id":e["block_id"],"split":e["split"],"site_id":str(e["site_id"]),
                "local_day":e["day_id"],"group_id":e["day_id"],"exposure":e["historical_exposure"],"source_sha256":e["source_sha256"]})
        self.partition_receipt=validate_partitions(entries,embargo_days=self.plan.get("embargo_days",7))

    def _evaluator(self,ledger):
        supervisor=ProcessSupervisorConfig(**self.plan.get("supervisor",{}))
        return StrictReplayEvaluator(self.site,ledger=ledger,strict_metadata=True,supervisor=supervisor,
            seed=self.plan["simulation_seed"],execution_binding={"plan_sha256":digest(self.plan),"scope":self.scope})

    def _observe(self,metrics):
        return {cid:{str(r["block_id"]):[float(r[o]) for o in OBJECTIVES] for r in rows} for cid,rows in metrics.items()}

    def _records(self,discovery):
        records={}
        for cid,rows in discovery["metrics"].items():
            samples=np.asarray([[r[o] for o in OBJECTIVES] for r in rows],dtype=float)
            scores=strict_risk(samples,tail_weight=self.plan.get("risk_weight",.5))
            records[cid]=CandidateRecord(cid,discovery["candidates"][cid],samples,scores,tuple(r["block_id"] for r in rows))
        return records

    def _execute(self,name):
        p=self.plan
        if name=="prepare":return {"scope":self.scope,"binding":self.binding,"declared_blocks":[b.block_id for b in self.blocks],"CONFIRMATORY_STATUS":"NO_GO" if self.scope!="PROSPECTIVE" else "REQUIRES_AUTHORITY"}
        if name=="verify":return {"source_bindings":self.source_bindings,"partition_validation":self.partition_receipt,"strict_blocks":len(self.blocks),"status":"ENGINEERING_INPUTS_VERIFIED_NOT_AUTHORITY"}
        if name=="gate-check":return gate_report()
        if name=="discovery":
            pool=sobol_candidates(p["candidate_count"],seed=p["optimizer_seed"])
            candidates={f"CRMT-c{i:04d}":x for i,x in enumerate(pool)}
            if any(not validate_physical(x,self.site)[0] for x in pool): raise ContractError("candidate incompatible with declared physical model")
            ledger=EvaluationLedger(p["discovery_budget"]);evaluator=self._evaluator(ledger)
            study=CRMTStudy(evaluator,risk=RiskConfig(tail_weight=p.get("risk_weight",.5)),
                initial_blocks=p["initial_blocks"],allocation_batch=p.get("allocation_batch",2),
                n_boot=p.get("n_boot",200),allocation_mode=p.get("allocation_mode","adaptive"),archive_mode="risk_pareto")
            try: result=study.run(candidates,self.discovery,max_evaluations=p["discovery_budget"])
            except BaseException:
                (self.store.root/"discovery_event_failure.json").write_bytes(canonical(plain({"used":ledger.used,"receipts":evaluator.receipts})));raise
            if result.budget_used!=p["discovery_budget"] or ledger.used!=p["discovery_budget"]: raise ContractError("incomplete DISCOVERY budget")
            metrics={c:df.to_dict(orient="records") for c,df in result.candidate_metrics.items()}
            return {"status":"ENGINEERING_REAL_EMS_NOT_R19_CONFIRMATION","candidates":candidates,"metrics":metrics,
                "events":[[c,r["block_id"]] for c,rows in metrics.items() for r in rows],"charged_events":ledger.used,
                "receipts":evaluator.receipts,"allocation_counts":{c:len(rows) for c,rows in metrics.items()},
                "source_sha256":digest(self.source_bindings),"legacy_study_final_point_archive_included_in_discovery_cost":True}
        if name=="archive-build":
            d=self.store.load("discovery");records=self._records(d);ids=list(records)
            point=[cid for cid,keep in zip(ids,pareto_mask([records[c].risk_vector for c in ids])) if keep]
            import crmt_edge_ems.archive as module
            original=module.confidence_risk_dominance;calls=0
            def counted(*args,**kwargs):
                nonlocal calls
                calls+=1;return original(*args,**kwargs)
            archive=ConfidenceArchive(risk=RiskConfig(tail_weight=p.get("risk_weight",.5)),n_boot=p.get("n_boot",200))
            for record in records.values():archive.add(record)
            module.confidence_risk_dominance=counted
            try: confidence=archive.confidently_nondominated_ids()
            finally: module.confidence_risk_dominance=original
            return {"archives":{"F0":point,"F1":confidence},"native_counts":{"F0":len(point),"F1":len(confidence)},
                "B_is_output_only":True,"confidence_pair_calls":calls,"bootstrap_resamples":2*p.get("n_boot",200)*calls,
                "archive_wide_95pct_validated":False,"scope":self.scope}
        if name=="shortlist-select":
            d=self.store.load("discovery");a=self.store.load("archive-build")["archives"];obs=self._observe(d["metrics"])
            if p["candidate_count"]==256 and p["discovery_budget"]==12600 and p["output_capacity"]==10:
                result=select_shortlists(list(d["candidates"]),obs,d["events"],d["events"],a,
                    audit_block_ids=[b.block_id for b in self.audit],require_declared_audit=True)
                if result["status"]=="BLOCKED_CAPACITY":raise ContractError("BLOCKED_CAPACITY: natural archive below K10; no backfill")
                return result
            # Deliberately different schema: small engineering smoke is not a R19 seed.
            ids=list(d["candidates"]);x=np.stack([strict_risk(list(obs[c].values()),tail_weight=p.get("risk_weight",.5)) for c in ids])
            span=np.ptp(x,axis=0);z=np.divide(x-x.min(axis=0),span,out=np.zeros_like(x),where=span>0)
            order=sorted(range(len(ids)),key=lambda i:(float(z[i].max()),float(z[i].sum()),ids[i]))
            selected={}
            for arm in ("F0","F1"):
                selected[arm]=[ids[i] for i in order if ids[i] in a[arm]][:p["output_capacity"]]
                if len(selected[arm])!=p["output_capacity"]:raise ContractError("BLOCKED_CAPACITY engineering; no backfill")
            return {"schema_version":"SMALL_ENGINEERING_NOT_R19","candidate_ids":ids,"selected":selected,
                "discovery_block_ids":[b.block_id for b in self.discovery],"audit_block_ids":[b.block_id for b in self.audit],
                "scope":self.scope,"locked":False}
        if name=="audit":
            d=self.store.load("discovery");selection=self.store.load("shortlist-select")
            ledger=EvaluationLedger(len(d["candidates"])*len(self.audit));evaluator=self._evaluator(ledger);metrics={}
            try:
                for cid,params in d["candidates"].items():metrics[cid]=evaluator.evaluate(params,self.audit,candidate_id=cid).to_dict(orient="records")
            except BaseException:
                (self.store.root/"audit_event_failure.json").write_bytes(canonical(plain({"used":ledger.used,"receipts":evaluator.receipts})));raise
            ledger.assert_exact()
            return {"observations":self._observe(metrics),"events":ledger.used,"receipts":evaluator.receipts,
                "selection_sha256":digest(selection),"status":"ENGINEERING_REAL_EMS_EXPOSED_NOT_INDEPENDENT_TEST"}
        if name=="analyze":
            selection=self.store.load("shortlist-select");audit=self.store.load("audit")
            if selection.get("schema_version")!="SMALL_ENGINEERING_NOT_R19":
                return audit_fidelity(selection,audit["observations"],require_declared_audit=True)
            ids=selection["candidate_ids"];blocks=selection["audit_block_ids"];obs=audit["observations"]
            if set(obs)!=set(ids) or any(set(obs[c])!=set(blocks) for c in ids):raise ContractError("missing declared engineering audit support")
            truth={c for c,keep in zip(ids,pareto_mask([strict_risk([obs[c][b] for b in blocks],tail_weight=p.get("risk_weight",.5)) for c in ids])) if keep}
            miss={arm:len(truth-set(picks))/len(truth) for arm,picks in selection["selected"].items()}
            return {"status":"SMALL_ENGINEERING_NOT_R19","miss_rate":miss,"delta_miss":miss["F1"]-miss["F0"],
                "reference_size":len(truth),"independent_test":False}
        if name=="report":
            d=self.store.load("discovery");a=self.store.load("audit");result=self.store.load("analyze")
            return {"scope":self.scope,"scientific_confirmation":False,"independent_TEST_executed":False,"locked":False,
                "result":result,"actual_simulator_events":d["charged_events"]+a["events"],"source_binding_sha256":digest(self.binding),
                "phase_costs":{k:v for k,v in self.store.state["stages"].items() if k!="report"},"energy_joules":None,
                "cost_limit":"Parent process CPU, worker CPU/RSS in event receipts; killed worker totals may be unmeasured. No equal-compute assertion."}
        raise ContractError("unsupported stage")

    def run(self,through="report"):
        if digest(self.plan)!=self.binding["plan_sha256"]:
            raise ContractError("execution plan changed after preflight")
        for block in self.blocks:
            if digest(plain(block.profile.to_dict(orient="records")))!=self.block_snapshot_hashes[block.block_id]:
                raise ContractError("replay snapshot changed after preflight")
        for entry in self.plan["blocks"]:
            if file_hash(self._path(entry["raw_path"]))!=entry["source_sha256"] or file_hash(self._path(entry["profile_path"]))!=entry["profile_sha256"]:
                raise ContractError("source bytes changed after preflight")
        if through=="independent-test":require_scientific_execution("independent-test")
        if through not in STAGES:raise ContractError("unknown stage")
        result=None
        with self.store.locked():
            for name in STAGES[:STAGES.index(through)+1]:
                dependencies={k:v["output_sha256"] for k,v in self.store.state["stages"].items() if v["status"]=="COMPLETE"}
                # Bind only earlier dependencies, so an already-complete later stage
                # cannot perturb resume verification of an earlier one.
                dependencies={k:dependencies[k] for k in STAGES[:STAGES.index(name)] if k in dependencies}
                result=self.store.stage(name,{"binding":self.binding,"dependencies":dependencies},lambda n=name:self._execute(n))
        return result
