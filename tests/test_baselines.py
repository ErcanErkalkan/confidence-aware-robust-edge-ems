import numpy as np

from baseline_optimizers import FunctionOracle, run_mode, run_mopso, run_nsga2, run_sobol
from baseline_optimizers.mo_utils import nondominated_indices


def zdt1(x):
    x=np.asarray(x,float)
    f1=x[0]
    g=1.0+9.0*np.mean(x[1:])
    f2=g*(1.0-np.sqrt(f1/g))
    return np.array([f1,f2])


def _run(method, seed=7, budget=60):
    o=FunctionOracle(zdt1, dim=9, n_obj=2, max_evaluations=budget)
    if method=='sobol': r=run_sobol(o,seed=seed,batch_size=11)
    elif method=='nsga2': r=run_nsga2(o,seed=seed,pop_size=10)
    elif method=='mopso': r=run_mopso(o,seed=seed,swarm_size=10,archive_size=30)
    elif method=='mode': r=run_mode(o,seed=seed,pop_size=10)
    return r


def test_all_baselines_respect_exact_candidate_budget_and_return_finite_fronts():
    for name in ['sobol','nsga2','mopso','mode']:
        r=_run(name)
        assert r.evaluations_used==60
        assert len(r.objectives)>0
        assert np.isfinite(r.objectives).all()
        assert np.all((r.positions>=0)&(r.positions<=1))
        assert len(nondominated_indices(r.objectives))==len(r.objectives) if name in ['sobol','mopso'] else len(nondominated_indices(r.objectives))>=1


def test_nsga2_seed_reproducibility():
    a=_run('nsga2',seed=13,budget=40)
    b=_run('nsga2',seed=13,budget=40)
    assert np.allclose(a.positions,b.positions)
    assert np.allclose(a.objectives,b.objectives)


def test_mopso_seed_reproducibility():
    a=_run('mopso',seed=23,budget=40)
    b=_run('mopso',seed=23,budget=40)
    assert np.allclose(a.positions,b.positions)
    assert np.allclose(a.objectives,b.objectives)


def test_sobol_and_mode_seed_reproducibility():
    for name in ['sobol', 'mode']:
        a = _run(name, seed=31, budget=40)
        b = _run(name, seed=31, budget=40)
        assert np.allclose(a.positions, b.positions)
        assert np.allclose(a.objectives, b.objectives)
