#!/usr/bin/env python3
"""Reproduce the Fig. 6 filtered-source runtime benchmark.

The timed quantity is the wall time spent inside ``meep.Simulation.run``.
For ``--mode adjoint`` an untimed forward prerequisite is required to build
the adjoint source.  Its time is deliberately not included in the adjoint
runtime, matching Meep's OptimizationProblem forward/adjoint separation.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import autograd.numpy as npa
import numpy as np

import meep as mp
import meep.adjoint as mpa


SEED = 1
RESOLUTION = 100
DPML = 0.7
PHYS_SX, PHYS_SY = 5.2, 4.0
CELL_SX, CELL_SY = PHYS_SX + 2 * DPML, PHYS_SY + 2 * DPML
DESIGN_W, DESIGN_H = 5.0, 0.2
NX_FULL, NX_HALF, NY = 501, 251, 15
EPS_LO, EPS_HI = 1.0, 6.0
SOURCE_Y = -1.85
DESIGN_CENTER_Y = -1.65
FOCUS_Y = DESIGN_CENTER_Y + DESIGN_H / 2 + 3.33
FOCUS_PT = mp.Vector3(0, FOCUS_Y)
WL_MIN_UM, WL_MAX_UM = 0.50, 0.70
FCEN = 0.5 * (1 / WL_MIN_UM + 1 / WL_MAX_UM)
FWIDTH = 1 / WL_MIN_UM - 1 / WL_MAX_UM
AFTER_SOURCES_TIME = 50.0
EXPECTED_NF = (2, 5, 10, 15, 20, 30, 50, 100, 150, 200)


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()
        return len(data)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def make_frequency_grid(n_f):
    wavelengths = np.linspace(WL_MIN_UM, WL_MAX_UM, n_f)
    return wavelengths, 1.0 / wavelengths


def make_sources():
    return [
        mp.Source(
            src=mp.GaussianSource(frequency=FCEN, fwidth=FWIDTH),
            component=mp.Ez,
            center=mp.Vector3(0, SOURCE_Y),
            size=mp.Vector3(PHYS_SX, 0, 0),
        )
    ]


def make_simulation(geometry):
    return mp.Simulation(
        cell_size=mp.Vector3(CELL_SX, CELL_SY, 0),
        boundary_layers=[mp.PML(DPML)],
        geometry=geometry,
        sources=make_sources(),
        resolution=RESOLUTION,
        dimensions=2,
    )


def make_initial_design():
    rng = np.random.default_rng(SEED)
    half = rng.uniform(0.45, 0.55, size=(NX_HALF, NY))
    return np.concatenate([np.flipud(half[1:, :]), half], axis=0)


def compute_incident_norm(freqs):
    sim = make_simulation([])
    monitors = [
        sim.add_dft_fields(
            [mp.Ez],
            f,
            0,
            1,
            center=FOCUS_PT,
            size=mp.Vector3(0, 0, 0),
        )
        for f in freqs
    ]
    sim.run(until_after_sources=AFTER_SOURCES_TIME)
    result = []
    for monitor in monitors:
        ez = np.asarray(sim.get_dft_array(monitor, mp.Ez, 0)).item()
        result.append(abs(ez) ** 2)
    sim.reset_meep()
    return np.maximum(np.asarray(result), 1e-20)


def make_problem(
    freqs,
    incident_norm,
    simulation_end_time=None,
    *,
    decay_by=0,
    minimum_run_time=None,
    maximum_run_time=None,
):
    if minimum_run_time is None:
        if simulation_end_time is None:
            raise ValueError("minimum_run_time or simulation_end_time is required")
        minimum_run_time = simulation_end_time
    if maximum_run_time is None:
        if simulation_end_time is None:
            raise ValueError("maximum_run_time or simulation_end_time is required")
        maximum_run_time = simulation_end_time
    air = mp.Medium(epsilon=EPS_LO)
    lens = mp.Medium(epsilon=EPS_HI)
    design_variables = mp.MaterialGrid(
        mp.Vector3(NX_FULL, NY), air, lens, grid_type="U_MEAN"
    )
    design_region = mpa.DesignRegion(
        design_variables,
        volume=mp.Volume(
            center=mp.Vector3(0, DESIGN_CENTER_Y),
            size=mp.Vector3(DESIGN_W, DESIGN_H, 0),
        ),
    )
    geometry = [
        mp.Block(
            center=design_region.center,
            size=design_region.size,
            material=design_variables,
        )
    ]
    sim = make_simulation(geometry)
    focal_ez = mpa.FourierFields(sim, mp.Volume(center=FOCUS_PT), mp.Ez)
    incident_norm_ag = npa.array(incident_norm)

    def objective(ez):
        return npa.mean(npa.abs(ez) ** 2 / incident_norm_ag)

    return mpa.OptimizationProblem(
        simulation=sim,
        objective_functions=[objective],
        objective_arguments=[focal_ez],
        design_regions=[design_region],
        frequencies=freqs,
        decay_by=decay_by,
        minimum_run_time=minimum_run_time,
        maximum_run_time=maximum_run_time,
    )


def source_and_window_parameters(freqs):
    delta_f_min = float(np.min(np.abs(np.diff(freqs))))
    filtered_window = float(np.max(np.abs(1.0 / np.diff(freqs))))
    source_end = max(float(src.src.swigobj.last_time()) for src in make_sources())
    return delta_f_min, filtered_window, source_end


def host_metadata():
    cpu_model = platform.processor() or "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    ram_gb = "unknown"
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                ram_gb = float(line.split()[1]) / 1024**2
                break
    except OSError:
        pass
    operating_system = platform.platform()
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                operating_system = line.split("=", 1)[1].strip().strip('"')
                break
    except OSError:
        pass
    gpu_model = "not used / nvidia-smi unavailable"
    if shutil.which("nvidia-smi"):
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_model = result.stdout.strip().replace("\n", "; ") + " (not used by Meep)"
    return cpu_model, gpu_model, ram_gb, operating_system


def pymeep_package_metadata():
    try:
        return importlib.metadata.version("pymeep"), "python-distribution metadata"
    except importlib.metadata.PackageNotFoundError:
        for path in sorted((Path(sys.prefix) / "conda-meta").glob("pymeep-*.json")):
            try:
                payload = json.loads(path.read_text())
                return str(payload.get("version", "unknown")), str(payload.get("build", "unknown"))
            except (OSError, ValueError):
                continue
    return "unknown", "unknown"


def active_design_dft_cells(problem, mode):
    if mode == "forward":
        monitors = problem.forward_design_region_monitors[0]
    else:
        monitors = problem.adjoint_design_region_monitors[0][0]
    components = (mp.Dx, mp.Dy, mp.Dz)
    active = []
    for component, monitor in zip(components, monitors):
        size = problem.sim.fields.dft_monitor_size(
            monitor.swigobj, problem.design_regions[0].volume.swigobj, component
        )
        count = int(np.prod(size))
        if count > 1:
            active.append(count)
    return sum(active)


def run_case(n_f, mode):
    wavelengths, freqs = make_frequency_grid(n_f)
    delta_f_min, filtered_window, forward_source_end = source_and_window_parameters(freqs)
    simulation_end_time = forward_source_end + AFTER_SOURCES_TIME
    incident_norm = compute_incident_norm(freqs)
    problem = make_problem(freqs, incident_norm, simulation_end_time)
    rho = make_initial_design()

    measured = []
    meep_times = []
    original_run = mp.Simulation.run

    def timed_run(sim, *args, **kwargs):
        start = time.perf_counter()
        result = original_run(sim, *args, **kwargs)
        measured.append(time.perf_counter() - start)
        meep_times.append(float(sim.meep_time()))
        return result

    mp.Simulation.run = timed_run
    try:
        if mode == "forward":
            problem([rho.ravel()], need_gradient=False)
            runtime_s, meep_time = measured[-1], meep_times[-1]
            adjoint_indexed_source_count = "not installed in forward-only run"
        else:
            # Required prerequisite; excluded from the reported adjoint time.
            problem([rho.ravel()], need_gradient=False)
            measured.clear()
            meep_times.clear()
            problem.adjoint_run()
            runtime_s, meep_time = measured[-1], meep_times[-1]
            adjoint_indexed_source_count = sum(
                len(source_group) for source_group in problem.adjoint_sources
            )
        dt = float(problem.sim.fields.dt)
        total_steps = int(round(meep_time / dt))
        dft_cells = active_design_dft_cells(problem, mode)
    finally:
        mp.Simulation.run = original_run

    dft_accumulators = dft_cells * n_f
    cpu_model, gpu_model, ram_gb, operating_system = host_metadata()
    pymeep_version, pymeep_build = pymeep_package_metadata()
    return {
        "BENCHMARK_PROFILE": "native_fixed_dft",
        "MODE": mode,
        "N_F": n_f,
        "DELTA_LAMBDA_NORM": 1.0 / (n_f - 1),
        "DELTA_LAMBDA_NM": 200.0 / (n_f - 1),
        "DELTA_F_MIN": delta_f_min,
        "TOTAL_STEPS": total_steps,
        "RUNTIME_SECONDS": runtime_s,
        "TIME_PER_STEP_MS": runtime_s / total_steps * 1000,
        "DFT_ACCUMULATORS": dft_accumulators,
        "DFT_REGION_CELLS": dft_cells,
        "FILTERED_SOURCE_BASIS_COUNT": n_f,
        "ADJOINT_INDEXED_SOURCE_COUNT": adjoint_indexed_source_count,
        "MEEP_TIME": meep_time,
        "MEEP_DT": dt,
        "MEEP_VERSION": getattr(mp, "__version__", "unknown"),
        "PYMEEP_PACKAGE_VERSION": pymeep_version,
        "PYMEEP_PACKAGE_BUILD": pymeep_build,
        "PYTHON_VERSION": platform.python_version(),
        "MPI_ENABLED": bool(mp.with_mpi()),
        "NUM_MPI_RANKS": int(mp.count_processors()),
        "NUM_THREADS": os.environ.get("OMP_NUM_THREADS", "unset"),
        "MACHINE_NAME": platform.node(),
        "CPU_MODEL": cpu_model,
        "GPU_MODEL": gpu_model,
        "RAM_GB": ram_gb,
        "OPERATING_SYSTEM": operating_system,
        "DEVICE": "2D broadband metalens",
        "TARGET_BAND_NM": "500 700",
        "RESOLUTION": RESOLUTION,
        "PML_THICKNESS": DPML,
        "CELL_SIZE": f"{CELL_SX} {CELL_SY} 0",
        "DESIGN_REGION_SIZE": f"{DESIGN_W} {DESIGN_H} 0",
        "DESIGN_GRID": f"{NX_FULL} {NY}",
        "MONITORS": "point Ez objective plus active Dz design-region DFT",
        "FILTERED_SOURCE_BASIS": "Nuttall-windowed complex exponentials",
        "FILTERED_SOURCE_WINDOW_TYPE": "Nuttall",
        "FILTERED_SOURCE_WINDOW_WIDTH": filtered_window,
        "FILTERED_SOURCE_WINDOW_SCALING": "T=max(abs(1/diff(frequencies)))=1/min(abs(delta_f))",
        "FILTERED_SOURCE_WINDOW_SCALING_WITH_DELTA_F": "T is inversely proportional to the minimum adjacent frequency spacing",
        "FILTERED_SOURCE_BASIS_COUNT_SCALING": "N_basis=N_f",
        "FORWARD_SOURCE_END_TIME": forward_source_end,
        "SOURCE_CENTER_FREQUENCY": FCEN,
        "SOURCE_FREQUENCY_WIDTH": FWIDTH,
        "SOURCE_TIME_WIDTH": 1.0 / FWIDTH,
        "SOURCE_CUTOFF": 5.0,
        "MINIMUM_RUN_TIME": simulation_end_time,
        "MAXIMUM_RUN_TIME": simulation_end_time,
        "FIELD_DECAY_TOLERANCE": 0,
        "DECAY_TOLERANCE_KIND": "DFT norm-change ratio; point-field decay is not used",
        "DFT_DECAY_CHECK_INTERVAL": "automatic: max(1/dft_maxfreq/dt, max_decimation) FDTD steps",
        "RUN_TERMINATION_ARGUMENT": "until_after_sources",
        "UNTIL_AFTER_SOURCES_ENABLED": True,
        "UNTIL_AFTER_SOURCES_SEMANTICS": "termination condition is evaluated only after all active sources finish",
        "UNTIL_AFTER_SOURCES": "stop_when_dft_decayed(0, minimum_run_time, maximum_run_time)",
        "WAVELENGTHS_NM": " ".join(f"{1000*w:.9g}" for w in wavelengths),
        "PROVENANCE": "native_rerun",
        "NOTES": (
            "DFT_ACCUMULATORS counts active complex design-region bins "
            "(spatial cells x N_f); the forward point-objective monitor is excluded."
        ),
    }


def print_summary(summary):
    print("BENCHMARK_SUMMARY_BEGIN")
    for key, value in summary.items():
        print(f"{key} = {value}")
    print("BENCHMARK_SUMMARY_END")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Nf", "--nf", dest="n_f", type=int, required=True)
    parser.add_argument("--mode", choices=("forward", "adjoint"), required=True)
    parser.add_argument("--log", type=Path)
    parser.add_argument(
        "--allow-nonstandard-Nf",
        action="store_true",
        help="Allow N_f outside the four manuscript benchmark cases.",
    )
    args = parser.parse_args()
    if args.n_f < 2:
        parser.error("N_f must be at least 2")
    if args.n_f not in EXPECTED_NF and not args.allow_nonstandard_Nf:
        parser.error(f"N_f must be one of {EXPECTED_NF}; use --allow-nonstandard-Nf to override")

    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("w", encoding="utf-8") as stream:
            with contextlib.redirect_stdout(Tee(sys.stdout, stream)):
                print_summary(run_case(args.n_f, args.mode))
    else:
        print_summary(run_case(args.n_f, args.mode))


if __name__ == "__main__":
    main()
