#!/usr/bin/env python3
"""Export Gaussian and FilteredSource waveforms at every actual FDTD step."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from meep.adjoint.filter_source import FilteredSource

import run_benchmark as base


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
SPECTRUM_DIR = PROJECT_DIR / "meep_fd_adjoint_waveforms_N002_200"
OUTPUT_DIR = SCRIPT_DIR / "data" / "source_waveforms_actual_timesteps"
DT = 0.5 / base.RESOLUTION


def write_csv(path: Path, time: np.ndarray, waveform: np.ndarray):
    peak = float(np.max(np.abs(waveform)))
    normalized = waveform / peak if peak > 0 else waveform
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["fdtd_step", "time_a_over_c", "normalized_source_real"]
        )
        writer.writerows(zip(np.arange(time.size), time, normalized))


def gaussian_waveform():
    source = base.make_sources()[0].src
    end_time = float(source.swigobj.last_time())
    steps = int(round(end_time / DT))
    time = np.arange(steps + 1, dtype=float) * DT
    waveform = np.asarray(
        [np.real(source.swigobj.current(float(t), DT)) for t in time]
    )
    return time, waveform


def filtered_waveform(n_f: int):
    spectrum_file = SPECTRUM_DIR / f"adjoint_source_spectrum_N{n_f:03d}.csv"
    data = np.genfromtxt(spectrum_file, delimiter=",", names=True)
    frequencies = np.asarray(data["frequency_1_per_um"], dtype=float)
    response = (
        np.asarray(data["interpolated_source_real"], dtype=float)
        + 1j * np.asarray(data["interpolated_source_imag"], dtype=float)
    )
    source = FilteredSource(
        float(np.mean(frequencies)), frequencies, response, DT
    )
    steps = int(round(float(source.T) / DT))
    time = np.arange(steps + 1, dtype=float) * DT
    waveform = np.asarray([np.real(source(float(t))) for t in time])
    return time, waveform


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cases = [("gaussian", gaussian_waveform)] + [
        (f"filtered_source_N{n_f:03d}", lambda n_f=n_f: filtered_waveform(n_f))
        for n_f in (100, 200)
    ]
    for name, factory in cases:
        time, waveform = factory()
        path = OUTPUT_DIR / f"{name}.csv"
        write_csv(path, time, waveform)
        print(
            f"Saved {path}: steps=0..{time.size-1}, "
            f"T={time[-1]:.6f} a/c, dt={DT:.6f} a/c"
        )


if __name__ == "__main__":
    main()
