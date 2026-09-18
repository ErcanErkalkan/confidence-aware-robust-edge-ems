from __future__ import annotations

from typing import Iterable, Sequence
import re

import numpy as np
import pandas as pd

from .common import canonical_profile


def _interval_columns(columns: Sequence[str]) -> list[str]:
    # Original files use 48 half-hour ending labels such as 0:30, 1:00, ... 0:00.
    pat = re.compile(r"^\s*(?:[01]?\d|2[0-3]):(?:00|30)\s*$")
    return [c for c in columns if pat.match(str(c))]


def wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    required = ["Customer", "Consumption Category", "date"]
    # Accept common Date capitalization.
    work = df.copy()
    if "Date" in work.columns and "date" not in work.columns:
        work = work.rename(columns={"Date": "date"})
    missing = [c for c in required if c not in work.columns]
    if missing:
        raise KeyError(f"Missing Ausgrid columns: {missing}")
    intervals = _interval_columns(list(work.columns))
    if len(intervals) != 48:
        raise ValueError(f"Expected 48 half-hour interval columns, found {len(intervals)}")
    long = work.melt(id_vars=[c for c in work.columns if c not in intervals], value_vars=intervals,
                     var_name="interval_end", value_name="energy_kwh")
    long["energy_kwh"] = pd.to_numeric(long["energy_kwh"], errors="coerce")
    long["date"] = pd.to_datetime(long["date"], errors="raise", dayfirst=True)
    # Convert interval-end label to interval-start timestamp. 0:00 is the final
    # interval of the stated day, ending at next midnight.
    def start_ts(row):
        hh, mm = map(int, str(row.interval_end).split(':'))
        end = row.date + pd.Timedelta(hours=hh, minutes=mm)
        if hh == 0 and mm == 0:
            end = row.date + pd.Timedelta(days=1)
        return end - pd.Timedelta(minutes=30)
    long["timestamp"] = long.apply(start_ts, axis=1)
    return long


def customer_profile(df_wide: pd.DataFrame, customer_id: int, *, include_controlled_load: bool = True,
                     peak_hours: tuple[int, int] = (17, 21)) -> pd.DataFrame:
    long = wide_to_long(df_wide)
    g = long[long["Customer"] == customer_id].copy()
    if g.empty:
        raise KeyError(f"Customer {customer_id} not found")
    pivot = g.pivot_table(index="timestamp", columns="Consumption Category", values="energy_kwh", aggfunc="sum")
    gc = pivot.get("GC", pd.Series(0.0, index=pivot.index)).fillna(0.0)
    cl = pivot.get("CL", pd.Series(0.0, index=pivot.index)).fillna(0.0) if include_controlled_load else 0.0
    gg = pivot.get("GG", pd.Series(0.0, index=pivot.index)).fillna(0.0)
    # Original values are kWh in each half-hour. Average kW = kWh / 0.5 h.
    load_kw = 2.0 * (gc + cl)
    pv_kw = 2.0 * gg
    hours = pivot.index.hour
    peak = ((hours >= peak_hours[0]) & (hours < peak_hours[1])).astype(int)
    out = canonical_profile(pivot.index, load_kw.to_numpy(), pv_kw.to_numpy(), peak_flag=peak)
    out["source"] = "Ausgrid Solar Home Electricity Data"
    out["customer_id"] = int(customer_id)
    return out


def aggregate_customers(df_wide: pd.DataFrame, customer_ids: Iterable[int], *, include_controlled_load: bool = True,
                        peak_hours: tuple[int, int] = (17, 21)) -> pd.DataFrame:
    profiles = [customer_profile(df_wide, int(cid), include_controlled_load=include_controlled_load, peak_hours=peak_hours)
                for cid in customer_ids]
    if not profiles:
        raise ValueError("customer_ids must not be empty")
    acc = profiles[0][["timestamp", "load_kw", "pv_kw", "wind_kw", "peak_flag"]].copy().set_index("timestamp")
    for p in profiles[1:]:
        q = p[["timestamp", "load_kw", "pv_kw", "wind_kw"]].set_index("timestamp")
        acc[["load_kw", "pv_kw", "wind_kw"]] = acc[["load_kw", "pv_kw", "wind_kw"]].add(q, fill_value=0.0)
    acc = acc.reset_index()
    acc["base_kw"] = acc["load_kw"] - acc["pv_kw"] - acc["wind_kw"]
    acc["source"] = "Ausgrid Solar Home Electricity Data"
    acc["customer_count"] = len(profiles)
    return acc
