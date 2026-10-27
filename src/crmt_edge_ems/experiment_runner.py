"""Content-bound checkpoints for engineering dry runs. Real execution is gated."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime,timezone
import importlib.metadata
import numpy as np
from .contracts import ContractError,canonical,digest,integer,IMPLEMENTATION_ID,strict_risk,pareto_mask
from .r19_primary import select_shortlists,audit_fidelity
from .profiling import CostTracker

class Checkpoints:
    def __init__(self,directory,binding):
        self.root=Path(directory);self.root.mkdir(parents=True,exist_ok=True)
        self.binding=digest(binding);self.path=self.root/'checkpoint.json'
        self.state={'schema_version':1,'binding_sha256':self.binding,'stages':{},'status':'INCOMPLETE'}
        if self.path.exists():
            self.state=json.loads(self.path.read_text(encoding='utf-8'))
            if self.state.get('schema_version')!=1 or self.state.get('binding_sha256')!=self.binding: raise ContractError('resume binding mismatch')

    @contextmanager
    def locked(self):
        path=self.root/'.run.lock'
        try: handle=path.open('x',encoding='utf-8')
        except FileExistsError as exc: raise ContractError('run already locked; investigate stale owner before manual recovery') from exc
        try:
            handle.write(str(os.getpid()));handle.close();yield
        finally:
            handle.close();path.unlink()

    def _save(self):
        temporary=self.root/'checkpoint.json.pending'
        temporary.write_bytes(canonical(self.state));os.replace(temporary,self.path)

    def stage(self,name,input_payload,operation):
        if name not in {'synthetic_inputs','selection','fidelity'}: raise ContractError('unknown dry-run stage')
        inp=digest(input_payload);output=self.root/(name+'.json')
        if name in self.state['stages']:
            receipt=self.state['stages'][name]
            if receipt['input_sha256']!=inp or not output.exists(): raise ContractError('checkpoint input/output mismatch')
            payload=json.loads(output.read_text(encoding='utf-8'))
            if digest(payload)!=receipt['output_sha256']: raise ContractError('checkpoint artifact hash mismatch')
            return payload
        try: payload=operation()
        except Exception as exc:
            self.state['status']='FAILED_NOT_SCIENTIFIC_EVIDENCE';self.state['error']={'stage':name,'type':type(exc).__name__,'message':str(exc)};self._save();raise
        # Pure deterministic transformations only: a crash may leave an orphan,
        # which is accepted only after full recomputation and byte equality.
        content=canonical(payload)
        if output.exists() and output.read_bytes()!=content: raise ContractError('orphan artifact differs from deterministic recomputation')
        if not output.exists():
            pending=self.root/(name+'.pending');pending.write_bytes(content);os.replace(pending,output)
        self.state['stages'][name]={'input_sha256':inp,'output_sha256':digest(payload),'status':'COMPLETE'}
        self.state['status']='INCOMPLETE';self.state.pop('error',None);self._save()
        return payload

    def complete(self):
        if set(self.state['stages'])!={'synthetic_inputs','selection','fidelity'}: raise ContractError('missing stages')
        self.state['status']='SYNTHETIC_ENGINEERING_COMPLETE_NOT_EXPERIMENT';self._save()

def synthetic_inputs(optimizer_seed,simulation_seed):
    """Artificial loss observations, not EMS simulation or measured controller evaluations."""
    integer(optimizer_seed,'optimizer_seed');integer(simulation_seed,'simulation_seed')
    rng=np.random.default_rng(simulation_seed); ids=[f'synthetic-c{i:03d}' for i in range(256)]
    # Noise affects every objective equally and is common across candidates.
    # Opposing first/second coordinates make a known complete tradeoff front.
    noise=rng.normal(scale=1e-5,size=50);audit_noise=rng.normal(scale=1e-5,size=8)
    # Optimizer seed controls ID ordering only, in a separate RNG stream.
    order=np.random.default_rng(optimizer_seed).permutation(256).tolist()
    discovery={};audit={}
    for i,c in enumerate(ids):
        mean=np.asarray([i/255,1-i/255,i/255,1-i/255])+1
        discovery[c]={f'SYNTHETIC_DISCOVERY:{b}':(mean+noise[b]).tolist() for b in range(50 if i<56 else 49)}
        audit[c]={f'SYNTHETIC_AUDIT:{b}':(mean+audit_noise[b]).tolist() for b in range(8)}
    scores=np.stack([strict_risk(list(discovery[c].values())) for c in ids])
    natural=[c for c,keep in zip(ids,pareto_mask(scores)) if keep]
    return {'label':'SYNTHETIC_ARTIFICIAL_LOSS_FIXTURE_NOT_EMS_RUN','candidate_ids':[ids[i] for i in order],
        'discovery':discovery,'audit':audit,'ledger':[[c,b] for c,rows in discovery.items() for b in rows],
        'archives':{'F0':natural,'F1':natural},
        'archive_basis':'Constructed common tradeoff fixture; F1 archive supplied identically for pipeline testing, NOT legacy F1 execution or validation'}

def dry_run(output,*,optimizer_seed=2001,simulation_seed=3001,source_binding='UNMANIFESTED_ENGINEERING_ONLY'):
    binding={'implementation':IMPLEMENTATION_ID,'optimizer_seed':optimizer_seed,'simulation_seed':simulation_seed,
        'source_binding':source_binding,'scope':'SYNTHETIC_ARTIFICIAL_LOSSES_ONLY'}
    store=Checkpoints(output,binding); tracker=CostTracker(1)
    with store.locked():
        inputs=store.stage('synthetic_inputs',binding,lambda:synthetic_inputs(optimizer_seed,simulation_seed))
        selection_input={k:inputs[k] for k in ('candidate_ids','discovery','ledger','archives')}
        with tracker.measure('candidate_selection'):
            selection=store.stage('selection',selection_input,lambda:select_shortlists(inputs['candidate_ids'],inputs['discovery'],inputs['ledger'],inputs['ledger'],inputs['archives']))
        result=store.stage('fidelity',{'selection':selection,'audit':inputs['audit']},lambda:audit_fidelity(selection,inputs['audit']))
        store.complete()
    return {'schema_version':1,'status':'SYNTHETIC_ENGINEERING_COMPLETE_NOT_EXPERIMENT','binding':binding,'outcome':result,
        'cost':tracker.report(),'simulator_evaluations_executed':0,'synthetic_loss_rows':12600+256*8,
        'reused_checkpoints':True,'CONFIRMATORY_STATUS':'NO_GO'}

def environment(work):
    def git(*args):
        p=subprocess.run(['git',*args],cwd=work,capture_output=True,text=True)
        return p.stdout.strip() if p.returncode==0 else None
    return {'checked_utc':datetime.now(timezone.utc).isoformat(),'git_head':git('rev-parse','HEAD'),
        'git_status':git('status','--porcelain=v1'),'python':sys.version,
        'dependencies':{n:importlib.metadata.version(n) for n in ('numpy','pandas','scipy','pytest')}}