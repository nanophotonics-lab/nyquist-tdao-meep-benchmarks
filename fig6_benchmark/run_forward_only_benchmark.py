#!/usr/bin/env python3
"""Run one isolated forward-only Fig. 6 benchmark."""

from __future__ import annotations

import argparse
import contextlib
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import meep as mp

import run_benchmark as base


DFT_REGION_CELLS = 11569


def termination_settings(name):
    if name == "fixed":
        return {"decay_by": 0.0, "minimum_run_time": 67.5, "maximum_run_time": 67.5}
    if name == "moderate":
        return {"decay_by": 1e-4, "minimum_run_time": 67.5, "maximum_run_time": 2000.0}
    if name == "common_field_decay":
        return {"decay_by": 1e-4, "minimum_run_time": 67.5, "maximum_run_time": 2000.0}
    raise ValueError(name)


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def run_forward(
    n_f, repetition, execution_order, termination, cpu, incident_cache_dir,
    minimum_run_time_override=None,
):
    if hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {cpu})
    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else []
    settings = termination_settings(termination)
    if minimum_run_time_override is not None:
        if termination != "common_field_decay":
            raise ValueError("minimum_run_time_override is only valid for common_field_decay")
        if minimum_run_time_override < 0:
            raise ValueError("minimum_run_time_override must be nonnegative")
        settings = dict(settings)
        settings["minimum_run_time"] = float(minimum_run_time_override)
    wavelengths, freqs = base.make_frequency_grid(n_f)
    delta_f_min, filtered_window, forward_source_end = base.source_and_window_parameters(freqs)

    incident_cache_dir.mkdir(parents=True, exist_ok=True)
    incident_cache = incident_cache_dir / f"incident_norm_Nf{n_f:03d}.npy"
    incident_t0 = time.perf_counter()
    if incident_cache.exists():
        incident_norm = np.load(incident_cache)
        incident_source = "cache"
    else:
        incident_norm = base.compute_incident_norm(freqs)
        np.save(incident_cache, incident_norm)
        incident_source = "computed"
    incident_s = time.perf_counter() - incident_t0
    problem = base.make_problem(
        freqs,
        incident_norm,
        decay_by=settings["decay_by"],
        minimum_run_time=settings["minimum_run_time"],
        maximum_run_time=settings["maximum_run_time"],
    )
    rho = base.make_initial_design()

    run_times = []
    meep_times = []
    original_run = mp.Simulation.run

    def timed_run(sim, *args, **kwargs):
        t0 = time.perf_counter()
        result = original_run(sim, *args, **kwargs)
        run_times.append(time.perf_counter() - t0)
        meep_times.append(float(sim.meep_time()))
        return result

    mp.Simulation.run = timed_run
    eval_t0 = time.perf_counter()
    try:
        if termination == "common_field_decay":
            problem.update_design(rho_vector=[rho.ravel()])
            problem.prepare_forward_run()
            field_decay = mp.stop_when_fields_decayed(10.0, mp.Ez, base.FOCUS_PT, 1e-4)

            def stop_at_common_decay_or_cap(sim):
                decayed = field_decay(sim)
                now = sim.round_time()
                return now >= settings["maximum_run_time"] or (
                    now >= settings["minimum_run_time"]
                    and now >= forward_source_end
                    and decayed
                )

            problem.sim.run(*problem.step_funcs, until=stop_at_common_decay_or_cap)
            results = [monitor() for monitor in problem.objective_arguments]
            objective = problem.objective_functions[0](*results)
        else:
            objective = problem([rho.ravel()], need_gradient=False)
        eval_total_s = time.perf_counter() - eval_t0
    finally:
        mp.Simulation.run = original_run

    if len(run_times) != 1 or len(meep_times) != 1:
        raise RuntimeError(f"Expected exactly one Simulation.run call, got {len(run_times)}")

    runtime_s = float(run_times[0])
    meep_time = float(meep_times[0])
    dt = float(problem.sim.fields.dt)
    steps = int(round(meep_time / dt))
    cpu_model, gpu_model, ram_gb, operating_system = base.host_metadata()
    pymeep_version, pymeep_build = base.pymeep_package_metadata()
    objective_value = objective[0] if isinstance(objective, (tuple, list)) else objective
    cap_hit = meep_time >= settings["maximum_run_time"]
    summary = {
        "TERMINATION": termination,
        "REPETITION": repetition,
        "EXECUTION_ORDER": execution_order,
        "N_F": n_f,
        "DECAY_BY": settings["decay_by"],
        "DECAY_CHECK_INTERVAL": 10.0 if termination == "common_field_decay" else 0.0,
        "MINIMUM_RUN_TIME": settings["minimum_run_time"],
        "MAXIMUM_RUN_TIME": settings["maximum_run_time"],
        "RUNTIME_SECONDS": runtime_s,
        "TIME_PER_STEP_MS": runtime_s / steps * 1000,
        "MEEP_TIME": meep_time,
        "MEEP_DT": dt,
        "STEPS": steps,
        "CAP_HIT": termination in ("moderate", "common_field_decay") and cap_hit,
        "STOP_REASON": "maximum_time_cap" if cap_hit else "field_decay",
        "INCIDENT_RUNTIME_SECONDS": incident_s,
        "INCIDENT_NORMALIZATION_SOURCE": incident_source,
        "INCIDENT_NORMALIZATION_CACHE": str(incident_cache),
        "EVAL_TOTAL_SECONDS": eval_total_s,
        "OBJECTIVE": float(np.asarray(objective_value)),
        "DFT_REGION_CELLS": DFT_REGION_CELLS,
        "DFT_FREQUENCY_COUNT": n_f,
        "DFT_ACCUMULATORS": DFT_REGION_CELLS * n_f,
        "SOURCE_TYPE": "GaussianSource",
        "FORWARD_SOURCE_COUNT": 1,
        "FILTERED_SOURCE_BASIS_COUNT": n_f,
        "FILTERED_SOURCE_WINDOW_WIDTH": filtered_window,
        "FORWARD_SOURCE_END_TIME": forward_source_end,
        "POST_SOURCE_TIME": meep_time - forward_source_end,
        "DECAY_COMPONENT": "Ez",
        "DECAY_FOCUS_X": float(base.FOCUS_PT.x),
        "DECAY_FOCUS_Y": float(base.FOCUS_PT.y),
        "DECAY_FOCUS_Z": float(base.FOCUS_PT.z),
        "CPU_AFFINITY": " ".join(map(str, affinity)),
        "CPU_MODEL": cpu_model,
        "NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "unset"),
        "NUM_MPI_RANKS": int(mp.count_processors()),
        "PEAK_RSS_MB": rss_mb(),
        "OPERATING_SYSTEM": operating_system,
        "MEEP_VERSION": getattr(mp, "__version__", "unknown"),
        "PYMEEP_PACKAGE_VERSION": pymeep_version,
        "PYMEEP_PACKAGE_BUILD": pymeep_build,
        "PYTHON_VERSION": sys.version.split()[0],
        "WAVELENGTHS_NM": " ".join(f"{1000*w:.9g}" for w in wavelengths),
        "NOTES": (
            "Forward-only; Simulation.run wall time; incident normalization excluded. "
            "FILTERED_SOURCE_BASIS_COUNT is a legacy field; the forward source is one "
            "GaussianSource and N_F is the DFT frequency count."
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
    parser.add_argument(
        "--termination", choices=("fixed", "moderate", "common_field_decay"), required=True
    )
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--minimum-run-time", type=float, default=None)
    parser.add_argument(
        "--incident-cache-dir", type=Path,
        default=Path("forward_only_sweep/cache"),
    )
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if args.n_f not in base.EXPECTED_NF:
        parser.error(f"N_f must be one of {base.EXPECTED_NF}")
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("w", encoding="utf-8") as stream:
        with contextlib.redirect_stdout(base.Tee(sys.stdout, stream)):
            summary = run_forward(
                args.n_f, args.repetition, args.execution_order, args.termination, args.cpu,
                args.incident_cache_dir, args.minimum_run_time,
            )
            print("FORWARD_ONLY_SUMMARY_BEGIN")
            for key, value in summary.items():
                print(f"{key} = {value}")
            print("FORWARD_ONLY_SUMMARY_END")


if __name__ == "__main__":
    main()
