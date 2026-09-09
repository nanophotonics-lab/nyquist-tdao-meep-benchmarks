#!/usr/bin/env python3
"""Measure one FD forward field solve with every DFT monitor removed."""

from __future__ import annotations

import argparse
import contextlib
import os
import resource
import sys
import time
from pathlib import Path

import meep as mp
import numpy as np

import run_benchmark as base


DECAY_BY = 1e-4
DECAY_CHECK_INTERVAL = 10.0
MINIMUM_RUN_TIME = 67.5
MAXIMUM_RUN_TIME = 2000.0


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run(n_f, repetition, execution_order, cpu):
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {cpu})
    affinity = (
        sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity") else []
    )

    wavelengths, freqs = base.make_frequency_grid(n_f)
    _, _, source_end = base.source_and_window_parameters(freqs)

    # Build the identical material grid and geometry, but never call
    # prepare_forward_run/forward_run: those methods install the point-objective
    # and design-region DFT monitors. The frequency vector is only a case label.
    problem = base.make_problem(
        freqs,
        np.ones(n_f),
        decay_by=DECAY_BY,
        minimum_run_time=MINIMUM_RUN_TIME,
        maximum_run_time=MAXIMUM_RUN_TIME,
    )
    rho = base.make_initial_design()
    problem.update_design(rho_vector=[rho.ravel()])
    dft_before = len(problem.sim.dft_objects)
    if dft_before != 0:
        raise RuntimeError(f"Expected zero DFT objects before run, found {dft_before}")

    field_decay = mp.stop_when_fields_decayed(
        DECAY_CHECK_INTERVAL, mp.Ez, base.FOCUS_PT, DECAY_BY
    )
    cap_hit = {"value": False}

    def stop_at_common_decay_or_cap(sim):
        decayed = field_decay(sim)
        now = sim.round_time()
        if now >= MAXIMUM_RUN_TIME:
            cap_hit["value"] = True
            return True
        return now >= MINIMUM_RUN_TIME and now >= source_end and decayed

    t0 = time.perf_counter()
    problem.sim.run(until=stop_at_common_decay_or_cap)
    runtime_s = time.perf_counter() - t0

    dft_after = len(problem.sim.dft_objects)
    if dft_after != 0:
        raise RuntimeError(f"Expected zero DFT objects after run, found {dft_after}")
    meep_time = float(problem.sim.meep_time())
    dt = float(problem.sim.fields.dt)
    steps = int(round(meep_time / dt))
    cpu_model, _, _, operating_system = base.host_metadata()
    pymeep_version, pymeep_build = base.pymeep_package_metadata()
    summary = {
        "BENCHMARK_PROFILE": "fd_forward_no_dft_common_field_decay_min67p5",
        "METHOD": "FD_forward_no_DFT",
        "N_F_LABEL": n_f,
        "REPETITION": repetition,
        "EXECUTION_ORDER": execution_order,
        "RUNTIME_SECONDS": runtime_s,
        "TIME_PER_STEP_MS": runtime_s / steps * 1000.0,
        "MEEP_TIME": meep_time,
        "MEEP_DT": dt,
        "STEPS": steps,
        "DFT_OBJECTS_BEFORE_RUN": dft_before,
        "DFT_OBJECTS_AFTER_RUN": dft_after,
        "DFT_FREQUENCY_COUNT": 0,
        "DFT_ACCUMULATORS": 0,
        "OBJECTIVE_EVALUATED": False,
        "INCIDENT_NORMALIZATION_COMPUTED": False,
        "SOURCE_TYPE": "GaussianSource",
        "FORWARD_SOURCE_COUNT": 1,
        "FORWARD_SOURCE_END_TIME": source_end,
        "POST_SOURCE_TIME": meep_time - source_end,
        "TERMINATION": "common_field_decay",
        "DECAY_BY": DECAY_BY,
        "DECAY_CHECK_INTERVAL": DECAY_CHECK_INTERVAL,
        "DECAY_COMPONENT": "Ez",
        "DECAY_FOCUS_X": float(base.FOCUS_PT.x),
        "DECAY_FOCUS_Y": float(base.FOCUS_PT.y),
        "DECAY_FOCUS_Z": float(base.FOCUS_PT.z),
        "MINIMUM_RUN_TIME": MINIMUM_RUN_TIME,
        "MAXIMUM_RUN_TIME": MAXIMUM_RUN_TIME,
        "CAP_HIT": cap_hit["value"],
        "STOP_REASON": "maximum_time_cap" if cap_hit["value"] else "field_decay",
        "CPU_AFFINITY": " ".join(map(str, affinity)),
        "NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "unset"),
        "NUM_MPI_RANKS": int(mp.count_processors()),
        "PEAK_RSS_MB": rss_mb(),
        "CPU_MODEL": cpu_model,
        "OPERATING_SYSTEM": operating_system,
        "MEEP_VERSION": getattr(mp, "__version__", "unknown"),
        "PYMEEP_PACKAGE_VERSION": pymeep_version,
        "PYMEEP_PACKAGE_BUILD": pymeep_build,
        "PYTHON_VERSION": sys.version.split()[0],
        "WAVELENGTHS_NM_LABEL": " ".join(f"{1000*w:.9g}" for w in wavelengths),
        "NOTES": (
            "Same geometry, material design, Gaussian source, CPU, and field-decay "
            "condition as the FD forward common-decay benchmark; all point and "
            "design-region DFT monitors, objective evaluation, and incident "
            "normalization are removed. N_F_LABEL does not alter the field solve."
        ),
    }
    try:
        problem.sim.reset_meep()
    except Exception:
        pass
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Nf", dest="n_f", type=int, required=True)
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--execution-order", type=int, required=True)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if args.n_f not in base.EXPECTED_NF:
        parser.error(f"N_f must be one of {base.EXPECTED_NF}")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8") as stream:
        with contextlib.redirect_stdout(base.Tee(sys.stdout, stream)):
            summary = run(
                args.n_f, args.repetition, args.execution_order, args.cpu
            )
            print("FD_FORWARD_NO_DFT_SUMMARY_BEGIN")
            for key, value in summary.items():
                print(f"{key} = {value}")
            print("FD_FORWARD_NO_DFT_SUMMARY_END")


if __name__ == "__main__":
    main()
