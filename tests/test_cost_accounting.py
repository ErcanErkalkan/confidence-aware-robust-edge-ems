import pytest
from crmt_edge_ems.contracts import ContractError
from crmt_edge_ems.profiling import CostTracker,peak_rss_bytes

def test_budget_failures_charged_and_phases_measured():
    t=CostTracker(2); k=t.reserve('TRAIN','c1','b1'); t.finish(k,success=False)
    with t.measure('bootstrap'): sum(range(100))
    with pytest.raises(ContractError,match='duplicate'): t.reserve('TRAIN','c1','b1')
    t.reserve('AUDIT','c1','b1')
    with pytest.raises(ContractError,match='BUDGET'): t.reserve('TEST','c2','b2')
    r=t.report()
    assert r['total_controller_block_events']==2 and r['failed_charged_events']==1 and r['incomplete_events']==1
    assert r['bootstrap_calls']==1 and r['bootstrap_cpu_time']>=0 and r['peak_process_rss']>0
    assert r['energy_consumption_estimate'] is None

@pytest.mark.parametrize('n',[True,0,-1,2.5,'2'])
def test_cost_budget_rejects_coercion(n):
    with pytest.raises(ContractError): CostTracker(n)

def test_measure_exception_still_records_and_forbids_nested():
    t=CostTracker(1)
    with pytest.raises(RuntimeError):
        with t.measure('simulation'): raise RuntimeError('failed simulator')
    assert t.report()['phases']['simulation']['calls']==1
    with t.measure('optimizer'):
        with pytest.raises(ContractError):
            with t.measure('bootstrap'): pass

def test_real_os_memory_measurement(): assert peak_rss_bytes()>0

def test_batch_reservation_is_atomic():
    t=CostTracker(2)
    with pytest.raises(ContractError,match='BUDGET'): t.reserve_many('TRAIN','c1',['a','b','c'])
    assert len(t.events)==0
    with pytest.raises(ContractError): t.reserve_many('TRAIN','c1',['a','a'])
    assert len(t.events)==0
