import numpy as np
import pandas as pd
import pytest
from crmt_edge_ems.contracts import ContractError
from data_adapters.validation import reconstruct_with_lineage,require_complete_days,ingest_csv

def raw_day():
    stamps=pd.date_range('2025-07-15',periods=720,freq='2min',tz='Asia/Shanghai')
    return pd.DataFrame({'read_ts':np.tile(stamps.as_unit('ns').asi8//10**9,2),'inverter':np.repeat([1,2],720),
        'outsumw':np.repeat([1000.,2000.],720),'pv1power':np.repeat([100.,400.],720)})

def test_lineage_separate_inverter_days_and_source_bytes(tmp_path):
    p=tmp_path/'raw.csv';raw_day().to_csv(p,index=False)
    frame=ingest_csv(p); blocks=require_complete_days(frame,min_coverage=1)
    assert set(blocks)=={'inv1:2025-07-15','inv2:2025-07-15'}
    assert np.allclose(blocks['inv1:2025-07-15']['base_kw'],.9)
    assert np.allclose(blocks['inv2:2025-07-15']['base_kw'],1.6)
    assert frame['lineage_id'].nunique()==1440 and frame.iloc[0]['raw_rows']==[1]
    assert frame.iloc[-1]['raw_rows']==[1440]

@pytest.mark.parametrize('fault',['duplicate','nan','negative','fractional_inverter','missing_pv'])
def test_lineage_rejects_invalid_measurements(fault):
    r=raw_day()
    if fault=='duplicate': r=pd.concat([r,r.iloc[:1]])
    if fault=='nan': r.loc[0,'outsumw']=np.nan
    if fault=='negative': r.loc[0,'pv1power']=-1
    if fault=='fractional_inverter': r['inverter']=r['inverter'].astype(float);r.loc[0,'inverter']=1.5
    if fault=='missing_pv': r=r.drop(columns='pv1power')
    with pytest.raises(ContractError): reconstruct_with_lineage(r,source_sha256='a'*64)

def test_missing_bins_and_duplicated_bins_cannot_fake_coverage():
    frame=reconstruct_with_lineage(raw_day(),source_sha256='a'*64)
    with pytest.raises(ContractError): require_complete_days(frame.iloc[10:],min_coverage=1)
    with pytest.raises(ContractError): require_complete_days(pd.concat([frame,frame.iloc[:1]]))