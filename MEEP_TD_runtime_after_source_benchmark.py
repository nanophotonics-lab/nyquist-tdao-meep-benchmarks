# Runtime benchmark for TEEP time-domain adjoint under a fixed after-source run condition.
#
# This script does not modify MEEP_FD_metalens.py or MEEP_TD_adjoint_metalens_teep.py.
# Termination condition:
#   Forward run: run until the incident pulse has ended, then continue for
#   AFTER_SOURCES_TIME.
#   Adjoint run: run to the same total Meep time reached by the forward run.
#
# Time-domain adjoint is independent of N_f. For plotting on the same
# delta_lambda / N_f axis as FD data, the measured TD runtime is repeated for
# each requested N_f.
#
# Use --sampling-interval 1 to measure the cost of saving gradient forward
# fields at every time step. The default --sampling-interval 24 stores/uses
# every 24th forward field sample for gradient accumulation.

import argparse
import csv
import gc
import resource
import time
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import meep as mp
import teep as tp


# -------------------------
# Settings matched to MEEP_FD_metalens.py
# -------------------------
SEED = 1
RESOLUTION = 100
DPML = 0.7

PHYS_SX = 5.2
PHYS_SY = 4.0
CELL_SX = PHYS_SX + 2 * DPML
CELL_SY = PHYS_SY + 2 * DPML

DESIGN_W = 5.0
DESIGN_H = 0.2
NX_FULL = 501
NX_HALF = 251
NY = 15

EPS_LO = 1.0
EPS_HI = 6.0

SOURCE_Y = -1.85
DESIGN_CENTER_Y = -1.65
DESIGN_TOP_Y = DESIGN_CENTER_Y + DESIGN_H / 2
FOCUS_Y = DESIGN_TOP_Y + 3.33
FOCUS_PT = mp.Vector3(0, FOCUS_Y)

WL_MIN_UM = 0.50
WL_MAX_UM = 0.70
FCEN = 0.5 * (1 / WL_MIN_UM + 1 / WL_MAX_UM)
FWIDTH = 1 / WL_MIN_UM - 1 / WL_MAX_UM

DX = DESIGN_W / NX_FULL
DY = DESIGN_H / NY
DT = 0.5 / RESOLUTION
FIELD_DTYPE = np.complex64

DEFAULT_AFTER_SOURCES_TIME = 50.0
DEFAULT_SAMPLING_INTERVAL = 24
DEFAULT_NFREQ_LIST = [2, 5, 10, 20, 50, 100, 200]

SCRIPT_DIR = Path(__file__).resolve().parent


def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def half_to_full(rho_half):
    return np.concatenate([np.flipud(rho_half[1:, :]), rho_half], axis=0)


def full_grad_to_half(g_full):
    g_design = np.asarray(g_full).reshape(NX_FULL, NY)
    g_half = np.zeros((NX_HALF, NY), dtype=float)
    center = NX_FULL // 2
    g_half[0, :] = g_design[center, :]
    for i in range(1, NX_HALF):
        g_half[i, :] = g_design[center + i, :] + g_design[center - i, :]
    return g_half


def make_initial_design():
    rng = np.random.default_rng(SEED)
    return rng.uniform(0.45, 0.55, size=(NX_HALF, NY))


def delta_lambda_nm(nfreq):
    return (WL_MAX_UM - WL_MIN_UM) * 1000.0 / (nfreq - 1)


def make_sources():
    return [
        mp.Source(
            src=mp.GaussianSource(frequency=FCEN, fwidth=FWIDTH),
            component=mp.Ez,
            center=mp.Vector3(0, SOURCE_Y),
            size=mp.Vector3(PHYS_SX, 0, 0),
        )
    ]


def make_design_objects():
    air = mp.Medium(epsilon=EPS_LO)
    lens_mat = mp.Medium(epsilon=EPS_HI)
    design_variables = mp.MaterialGrid(
        mp.Vector3(NX_FULL, NY),
        air,
        lens_mat,
        grid_type="U_MEAN",
    )
    geometry = [
        mp.Block(
            center=mp.Vector3(0, DESIGN_CENTER_Y),
            size=mp.Vector3(DESIGN_W, DESIGN_H, 0),
            material=design_variables,
        )
    ]
    return air, lens_mat, design_variables, geometry


def cleanup_sim(sim):
    try:
        sim.reset_meep()
    except Exception as exc:
        print(f"[warn] sim.reset_meep failed: {exc}")
    if hasattr(mp, "all_wait"):
        try:
            mp.all_wait()
        except Exception:
            pass
    gc.collect()


def run_td_once(
    after_sources_time,
    sampling_interval,
    termination="fixed",
    decay_by=1e-4,
    minimum_run_time=None,
    maximum_run_time=2000.0,
    decay_check_interval=10.0,
    forward_only=False,
    gradient_output_path=None,
    initial_design=None,
):
    if int(sampling_interval) != sampling_interval or sampling_interval < 1:
        raise ValueError("sampling_interval must be a positive integer")
    # Runtime data are only comparable to the archived campaign when the
    # compiled native sampler is active. This also enables strict mode: a
    # native call failure aborts instead of silently using Python sampling.
    tp.require_native_sampler()
    iter_t0 = time.perf_counter()
    rho_half_initial = (
        make_initial_design() if initial_design is None else np.asarray(initial_design, dtype=float)
    )
    if rho_half_initial.shape != (NX_HALF, NY):
        raise ValueError(
            f"initial_design must have shape {(NX_HALF, NY)}, got {rho_half_initial.shape}"
        )
    rho_full = half_to_full(rho_half_initial)

    air, lens_mat, design_variables, geometry = make_design_objects()
    design_variables.update_weights(rho_full.ravel())

    coords_x, coords_y = tp.centered_grid_coords(
        center=mp.Vector3(0, DESIGN_CENTER_Y),
        shape=(NX_FULL, NY),
        spacing=(DX, DY),
    )

    def update_design(x_full):
        design_variables.update_weights(np.asarray(x_full).reshape(NX_FULL, NY))

    def make_sim(sources=None):
        return mp.Simulation(
            cell_size=mp.Vector3(CELL_SX, CELL_SY, 0),
            boundary_layers=[mp.PML(DPML)],
            geometry=geometry,
            sources=make_sources() if sources is None else sources,
            resolution=RESOLUTION,
            dimensions=2,
        )

    def fom_fn(e_t, sample_dt):
        return 0.5 * np.sum(np.abs(e_t) ** 2) * sample_dt

    def adjoint_signal_fn(e_t, sample_dt):
        del sample_dt
        return np.conj(e_t)

    tda = tp.TDAObjective(
        update_design=update_design,
        sim_factory=make_sim,
        coords_x=coords_x,
        coords_y=coords_y,
        t_final=0.0,
        monitor_position=FOCUS_PT,
        component=mp.Ez,
        cell_area=DX * DY,
        adjoint_source_size=mp.Vector3(2 * DX, 0, 0),
        adjoint_source_amplitude=1.0 / (2 * DX),
        background=air,
        design_material=lens_mat,
        fom_fn=fom_fn,
        adjoint_signal_fn=adjoint_signal_fn,
        dt=DT,
        resolution=RESOLUTION,
        sampling_interval=sampling_interval,
    )

    # -------------------------
    # Forward run
    # -------------------------
    sim_fwd = make_sim()
    dt = tda.time_step(sim_fwd)
    monitor_samples = []
    field_samples = []
    field_sample_steps = []
    fwd_state = {"step": 0}
    fwd_grid = {"obj": None}

    def record_forward(sim):
        monitor_samples.append(tda.objective.record_monitor(sim))
        physical_step = int(round(float(sim.meep_time()) / dt))
        if physical_step % sampling_interval == 0:
            field_sample_steps.append(physical_step)
            if fwd_grid["obj"] is None:
                fwd_grid["obj"] = tp.FastFieldGrid(sim, mp.Ez, coords_x, coords_y)
            field_samples.append(fwd_grid["obj"].sample().astype(FIELD_DTYPE, copy=False))
        fwd_state["step"] += 1

    source_end_time = max(float(src.src.swigobj.last_time()) for src in make_sources())
    if minimum_run_time is None:
        minimum_run_time = source_end_time + after_sources_time
    forward_cap_hit = {"value": False}
    fwd_t0 = time.perf_counter()
    if termination == "fixed":
        sim_fwd.run(record_forward, until_after_sources=after_sources_time)
    elif termination == "moderate":
        field_decay = mp.stop_when_fields_decayed(
            decay_check_interval, mp.Ez, FOCUS_PT, decay_by
        )

        def stop_at_decay_or_cap(sim):
            decayed = field_decay(sim)
            now = sim.round_time()
            if now >= maximum_run_time:
                forward_cap_hit["value"] = True
                return True
            return now >= minimum_run_time and decayed

        sim_fwd.run(record_forward, until=stop_at_decay_or_cap)
    else:
        raise ValueError(f"Unknown termination condition: {termination}")
    forward_s = time.perf_counter() - fwd_t0
    forward_actual_time = sim_fwd.round_time()
    monitor_history = np.asarray(monitor_samples, dtype=np.complex128)
    cleanup_sim(sim_fwd)
    del sim_fwd, monitor_samples, fwd_grid
    gc.collect()

    if forward_only:
        fom, _ = tda._fom_value_and_adjoint_signal(monitor_history, dt)
        row = {
            "method": "time-domain",
            "termination": termination,
            "decay_by": 0.0 if termination == "fixed" else decay_by,
            "minimum_run_time": minimum_run_time,
            "maximum_run_time": minimum_run_time if termination == "fixed" else maximum_run_time,
            "decay_check_interval": decay_check_interval,
            "forward_cap_hit": int(forward_cap_hit["value"]),
            "after_sources_time_meep_units": after_sources_time,
            "sampling_interval": sampling_interval,
            "fom": float(fom),
            "forward_s": forward_s,
            "forward_actual_time_meep_units": forward_actual_time,
            "forward_steps": fwd_state["step"],
            "forward_field_samples": len(field_samples),
            "maxrss_MB": rss_mb(),
            "native_sampler_available": int(tp.native_sampler_available()),
            "sampler_backend": "native_fastmeep_sample",
            "gradient_implementation": "aligned_fine_dt_adjoint_v1",
            "dt": dt,
        }
        del monitor_history, field_samples, tda
        gc.collect()
        return row

    fom, adjoint_signal = tda._fom_value_and_adjoint_signal(monitor_history, dt)
    adjoint_signal = np.asarray(adjoint_signal, dtype=np.complex128)
    field_history = np.asarray(field_samples, dtype=FIELD_DTYPE)
    n_forward_field_samples = len(field_history)
    del field_samples
    gc.collect()
    dt_eff = dt * sampling_interval

    # -------------------------
    # Adjoint run
    # -------------------------
    adjoint_sources = tda.objective.adjoint_sources(adjoint_signal, forward_actual_time)
    sim_adj = make_sim(adjoint_sources)
    # Store sparse E_fwd; differentiate instantaneous
    # adjoint E using the original FDTD dt at correctly reversed timestamps.
    # No full forward or adjoint trajectory is retained.
    final_step = int(round(float(forward_actual_time) / dt))
    if final_step < 1:
        raise ValueError("Need at least one FDTD update")
    completions = {}
    needed_steps = set()
    for idx, forward_step in enumerate(field_sample_steps):
        target = final_step - forward_step
        left = max(0, target - 1)
        right = min(final_step, target + 1)
        completions.setdefault(right, []).append((idx, left, right))
        needed_steps.update((left, right))
    adj_state = {"step": 0, "sample": 0}
    adj_grad = {"obj": None}
    recent = {}
    grad_grid = np.zeros((NX_FULL, NY), dtype=np.complex128)

    def accumulate_adjoint(sim):
        physical_step = int(round(float(sim.meep_time()) / dt))
        if physical_step in needed_steps:
            if adj_grad["obj"] is None:
                adj_grad["obj"] = tp.FastFieldGrid(sim, mp.Ez, coords_x, coords_y)
            recent[physical_step] = adj_grad["obj"].sample()
        for idx, left, right in completions.get(physical_step, ()):
            fine_adjoint_derivative = (recent[right] - recent[left]) / ((right-left)*dt)
            grad_grid[:] += field_history[idx] * fine_adjoint_derivative
            adj_state["sample"] += 1
        for old_step in list(recent):
            if old_step < physical_step - 1:
                del recent[old_step]
        adj_state["step"] += 1

    adjoint_run_time = forward_actual_time
    adj_t0 = time.perf_counter()
    sim_adj.run(accumulate_adjoint, until=adjoint_run_time)
    adjoint_s = time.perf_counter() - adj_t0
    if adj_state["sample"] != len(field_history):
        raise RuntimeError("Incomplete reversed-time gradient accumulation")
    cleanup_sim(sim_adj)
    del sim_adj, adjoint_sources, field_history, adj_grad
    gc.collect()

    grad_full = tda.objective.gradient(grad_grid, dt_eff).reshape(NX_FULL, NY)
    grad_half = full_grad_to_half(grad_full)
    grad_norm = float(np.linalg.norm(grad_half))
    if gradient_output_path is not None:
        gradient_output_path = Path(gradient_output_path)
        gradient_output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(gradient_output_path, grad_half)

    total_s = time.perf_counter() - iter_t0
    row = {
        "method": "time-domain",
        "termination": termination,
        "decay_by": 0.0 if termination == "fixed" else decay_by,
        "minimum_run_time": minimum_run_time,
        "maximum_run_time": minimum_run_time if termination == "fixed" else maximum_run_time,
        "decay_check_interval": decay_check_interval,
        "forward_cap_hit": int(forward_cap_hit["value"]),
        "after_sources_time_meep_units": after_sources_time,
        "sampling_interval": sampling_interval,
        "fom": float(fom),
        "forward_s": forward_s,
        "adjoint_s": adjoint_s,
        "eval_total_s": forward_s + adjoint_s,
        "iteration_total_s": total_s,
        "maxrss_MB": rss_mb(),
        "native_sampler_available": int(tp.native_sampler_available()),
        "sampler_backend": "native_fastmeep_sample",
        "gradient_implementation": "aligned_fine_dt_adjoint_v1",
        "dt": dt,
        "forward_actual_time_meep_units": forward_actual_time,
        "adjoint_run_time_meep_units": adjoint_run_time,
        "forward_steps": fwd_state["step"],
        "forward_field_samples": n_forward_field_samples,
        "adjoint_steps": adj_state["step"],
        "adjoint_field_samples": adj_state["sample"],
        "grad_norm": grad_norm,
        "gradient_output_path": "" if gradient_output_path is None else str(gradient_output_path),
    }
    del monitor_history, adjoint_signal, grad_grid, grad_full, grad_half, tda
    gc.collect()
    return row


def repeated_rows(td_row, nfreq_list):
    rows = []
    for nfreq in nfreq_list:
        row = dict(td_row)
        row["nfreq"] = nfreq
        row["delta_lambda_nm"] = delta_lambda_nm(nfreq)
        rows.append(row)
    return rows


def write_rows(csv_path, rows):
    csv_path.parent.mkdir(exist_ok=True)
    with open(csv_path, "w", newline="") as fcsv:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(fcsv, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(csv_path):
    with open(csv_path, newline="") as fcsv:
        return list(csv.DictReader(fcsv))


def plot_td_runtime(csv_path, out_png):
    rows = sorted(read_rows(csv_path), key=lambda r: float(r["delta_lambda_nm"]), reverse=True)
    dlam = np.asarray([float(row["delta_lambda_nm"]) for row in rows])
    nfreq = np.asarray([int(row["nfreq"]) for row in rows])
    forward_s = np.asarray([float(row["forward_s"]) for row in rows])
    adjoint_s = np.asarray([float(row["adjoint_s"]) for row in rows])
    eval_total_s = np.asarray([float(row["eval_total_s"]) for row in rows])
    iteration_total_s = np.asarray([float(row["iteration_total_s"]) for row in rows])

    fig, ax = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    ax.plot(dlam, forward_s, "s-", lw=1.2, ms=4, label="TD forward")
    ax.plot(dlam, adjoint_s, "^-", lw=1.2, ms=4, label="TD adjoint")
    ax.plot(dlam, eval_total_s, "d-", lw=1.2, ms=4, label="TD fwd+adj")
    ax.plot(dlam, iteration_total_s, "x-", lw=1.2, ms=5, label="TD total iteration")
    ax.set_xscale("log")
    ax.invert_xaxis()
    ax.set_xlabel("delta_lambda (nm)")
    ax.set_ylabel("wall-clock runtime (s)")
    ax.grid(True, alpha=0.3)
    ax.legend()

    top = ax.twiny()
    top.set_xscale("log")
    top.set_xlim(ax.get_xlim())
    tick_n = np.array([2, 5, 10, 20, 50, 100, 200])
    valid = np.array([n in set(nfreq) for n in tick_n])
    tick_n = tick_n[valid]
    tick_dlam = np.array([delta_lambda_nm(n) for n in tick_n])
    order = np.argsort(tick_dlam)
    top.set_xticks(tick_dlam[order])
    top.set_xticklabels([str(n) for n in tick_n[order]])
    top.set_xlabel("Nf")

    fig.savefig(out_png, dpi=180)
    plt.close(fig)
    return out_png


def parse_nfreq_list(args):
    if args.nfreq_range:
        start, stop = args.nfreq_range
        return list(range(start, stop + 1))
    if args.nfreq:
        return args.nfreq
    return DEFAULT_NFREQ_LIST


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark TEEP time-domain adjoint runtime with fixed after-source condition."
    )
    parser.add_argument("--after-sources-time", type=float, default=DEFAULT_AFTER_SOURCES_TIME)
    parser.add_argument("--sampling-interval", type=int, default=DEFAULT_SAMPLING_INTERVAL)
    parser.add_argument("--nfreq", type=int, nargs="+", default=None)
    parser.add_argument("--nfreq-range", type=int, nargs=2, default=None)
    parser.add_argument("--output-suffix", type=str, default="")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args()

    if args.sampling_interval < 1:
        raise ValueError("--sampling-interval must be >= 1")

    after_tag = f"{args.after_sources_time:g}".replace(".", "p")
    suffix = f"_{args.output_suffix}" if args.output_suffix else ""
    out_dir = SCRIPT_DIR / (
        f"meep_td_runtime_after_source_t{after_tag}_si{args.sampling_interval}{suffix}"
    )
    timing_csv = out_dir / "td_runtime_after_source.csv"
    out_png = out_dir / "td_runtime_after_source.png"

    if args.plot_only:
        plot_td_runtime(timing_csv, out_png)
        print(f"Saved plot: {out_png}")
        return

    print(f"TEEP native sampler available: {tp.native_sampler_available()}")
    td_row = run_td_once(args.after_sources_time, args.sampling_interval)
    rows = repeated_rows(td_row, parse_nfreq_list(args))
    write_rows(timing_csv, rows)
    plot_td_runtime(timing_csv, out_png)

    print(
        f"TD | fwd={td_row['forward_s']:.3f}s | adj={td_row['adjoint_s']:.3f}s | "
        f"eval={td_row['eval_total_s']:.3f}s | total={td_row['iteration_total_s']:.3f}s | "
        f"rss={td_row['maxrss_MB']:.1f} MB"
    )
    print(f"Saved data: {timing_csv}")
    print(f"Saved plot: {out_png}")


if __name__ == "__main__":
    main()
