#!/usr/bin/env python3
"""One CPU-pinned FD adjoint run using the common point-field decay rule."""

from __future__ import annotations

import argparse
import contextlib
import os
import resource
import sys
import time
from pathlib import Path

import meep as mp

import run_benchmark as base


def make_common_decay_factory(minimum_run_time):
    def common_decay_factory(*_args, **_kwargs):
        field_decay = mp.stop_when_fields_decayed(10.0, mp.Ez, base.FOCUS_PT, 1e-4)

        def stop(sim):
            decayed = field_decay(sim)
            now = sim.round_time()
            return now >= 2000.0 or (now >= minimum_run_time and decayed)

        return stop

    return common_decay_factory


def run(n_f, repetition, order, cpu, cache_dir, minimum_run_time=67.5):
    if minimum_run_time < 0:
        raise ValueError("minimum_run_time must be nonnegative")
    os.sched_setaffinity(0,{cpu})
    wavelengths,freqs=base.make_frequency_grid(n_f)
    cache=cache_dir/f"incident_norm_Nf{n_f:03d}.npy"
    if not cache.exists():
        raise FileNotFoundError(f"Incident cache missing: {cache}")
    import numpy as np
    incident=np.load(cache)
    problem=base.make_problem(freqs,incident,decay_by=1e-4,minimum_run_time=minimum_run_time,maximum_run_time=2000.0)
    rho=base.make_initial_design()
    original_stop=mp.stop_when_dft_decayed
    original_run=mp.Simulation.run
    original_prepare_adjoint_run=problem.prepare_adjoint_run
    measured=[]; meep_times=[]
    source_build_times=[]

    def timed_run(sim,*args,**kwargs):
        t0=time.perf_counter(); result=original_run(sim,*args,**kwargs)
        measured.append(time.perf_counter()-t0); meep_times.append(float(sim.meep_time())); return result

    def timed_prepare_adjoint_run(*args,**kwargs):
        t0=time.perf_counter()
        try:
            return original_prepare_adjoint_run(*args,**kwargs)
        finally:
            source_build_times.append(time.perf_counter()-t0)

    mp.stop_when_dft_decayed=make_common_decay_factory(minimum_run_time)
    mp.Simulation.run=timed_run
    # OptimizationProblem.adjoint_run() owns source preparation. Wrap that
    # single internal call to record its duration without preparing twice.
    problem.prepare_adjoint_run=timed_prepare_adjoint_run
    try:
        problem([rho.ravel()],need_gradient=False)
        measured.clear(); meep_times.clear()
        print("FD_ADJOINT_MEASURED_RUN_BEGIN")
        problem.adjoint_run()
        print("FD_ADJOINT_MEASURED_RUN_END")
    finally:
        problem.prepare_adjoint_run=original_prepare_adjoint_run
        mp.stop_when_dft_decayed=original_stop
        mp.Simulation.run=original_run
    if len(measured)!=1: raise RuntimeError(f"Expected one adjoint run, got {len(measured)}")
    if len(source_build_times)!=1:
        raise RuntimeError(
            f"Expected one adjoint source preparation, got {len(source_build_times)}"
        )
    build_s=float(source_build_times[0])
    dt=float(problem.sim.fields.dt); runtime=float(measured[0]); meep_time=float(meep_times[0])
    source_end=max(float(s.src.swigobj.last_time()) for g in problem.adjoint_sources for s in g)
    cap_hit=meep_time>=2000.0
    return {
        "N_F":n_f,"REPETITION":repetition,"EXECUTION_ORDER":order,
        "TERMINATION":"common_field_decay","DECAY_BY":1e-4,"DECAY_CHECK_INTERVAL":10.0,
        "MINIMUM_RUN_TIME":minimum_run_time,"MAXIMUM_RUN_TIME":2000.0,
        "RUNTIME_SECONDS":runtime,"MEEP_TIME":meep_time,"STEPS":int(round(meep_time/dt)),
        "TIME_PER_STEP_MS":runtime/int(round(meep_time/dt))*1000,
        "MEEP_DT":dt,"CAP_HIT":cap_hit,
        "STOP_REASON":"maximum_time_cap" if cap_hit else "field_decay",
        "SOURCE_BUILD_SECONDS":build_s,
        "SOURCE_PREPARATION_CALLS":1,
        "SOURCE_PREPARATION_TIMED_SEPARATELY":True,
        "ADJOINT_SOURCE_END_TIME":source_end,"POST_SOURCE_TIME":meep_time-source_end,
        "SOURCE_TYPE":"FilteredSource","FILTERED_SOURCE_BASIS_COUNT":n_f,
        "DECAY_COMPONENT":"Ez","DECAY_FOCUS_X":float(base.FOCUS_PT.x),
        "DECAY_FOCUS_Y":float(base.FOCUS_PT.y),"DECAY_FOCUS_Z":float(base.FOCUS_PT.z),
        "EXECUTION_MODE":(
            f"single process/rank, single thread, pinned to logical CPU {cpu}"
        ),
        "MPI_RANKS":1,"NUM_THREADS":1,"PINNED_LOGICAL_CPU":cpu,
        "CPU_AFFINITY":" ".join(map(str,sorted(os.sched_getaffinity(0)))),
        "PEAK_RSS_MB":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.0,
        "WAVELENGTHS_NM":" ".join(f"{1000*w:.9g}" for w in wavelengths),
    }


def main():
    p=argparse.ArgumentParser(); p.add_argument('--Nf',dest='n_f',type=int,required=True); p.add_argument('--repetition',type=int,required=True); p.add_argument('--execution-order',type=int,required=True); p.add_argument('--cpu',type=int,default=8); p.add_argument('--cache-dir',type=Path,default=Path('forward_only_sweep/cache')); p.add_argument('--minimum-run-time',type=float,default=67.5); p.add_argument('--log',type=Path,required=True); a=p.parse_args()
    a.log.parent.mkdir(parents=True,exist_ok=True)
    with a.log.open('w',encoding='utf-8') as f, contextlib.redirect_stdout(base.Tee(sys.stdout,f)):
        summary=run(a.n_f,a.repetition,a.execution_order,a.cpu,a.cache_dir,a.minimum_run_time)
        print('FD_ADJOINT_COMMON_SUMMARY_BEGIN')
        for k,v in summary.items(): print(f'{k} = {v}')
        print('FD_ADJOINT_COMMON_SUMMARY_END')


if __name__=='__main__': main()
