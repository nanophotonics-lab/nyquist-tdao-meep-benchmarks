# Generate frequency-domain adjoint source waveform CSVs for Nf = 2..200.
#
# This does not rerun Meep simulations. It uses the existing dense Nf=100
# adjoint source spectrum as a reference and interpolates the complex spectrum
# onto each requested frequency grid.

import argparse
import csv
from pathlib import Path

import numpy as np

import meep as mp
from meep.adjoint.filter_source import FilteredSource


SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = SCRIPT_DIR / "meep_freq_sampling_benchmark_N05_10_20_100_minrun120"
REFERENCE_SPECTRUM_CSV = REFERENCE_DIR / "adjoint_source_spectrum_N100.csv"
OUT_DIR = SCRIPT_DIR / "meep_fd_adjoint_waveforms_N002_200"

WL_MIN_UM = 0.50
WL_MAX_UM = 0.70
NFREQ_MIN = 2
NFREQ_MAX = 200
ADJOINT_WAVEFORM_NT = 4096
DT = 0.5 / 100


def load_reference_base_spectrum():
    data = np.genfromtxt(REFERENCE_SPECTRUM_CSV, delimiter=",", names=True)
    wavelengths = np.asarray(data["wavelength_um"], dtype=float)
    source = (
        np.asarray(data["meep_scaled_source_real"], dtype=float)
        + 1j * np.asarray(data["meep_scaled_source_imag"], dtype=float)
    )

    # Existing source_spectrum contains the objective mean factor 1/Nf.
    # Remove it so each target Nf can reapply its own 1/Nf scaling.
    n_ref = len(wavelengths)
    base_source = source * n_ref
    order = np.argsort(wavelengths)
    return wavelengths[order], base_source[order]


def interp_complex(x, xp, fp):
    return np.interp(x, xp, np.real(fp)) + 1j * np.interp(x, xp, np.imag(fp))


def synthesize_waveform(source_spectrum, freqs):
    filtered_source = FilteredSource(np.mean(freqs), freqs, source_spectrum, DT)
    times = np.linspace(0.0, filtered_source.T, ADJOINT_WAVEFORM_NT)
    waveform = np.asarray([np.real(filtered_source(t)) for t in times])
    peak = np.max(np.abs(waveform))
    if peak > 0:
        waveform = waveform / peak
    return times, waveform


def write_spectrum_csv(nfreq, wavelengths, freqs, source_spectrum):
    out_path = OUT_DIR / f"adjoint_source_spectrum_N{nfreq:03d}.csv"
    with open(out_path, "w", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow([
            "wavelength_um",
            "frequency_1_per_um",
            "interpolated_source_real",
            "interpolated_source_imag",
            "relative_source_power",
        ])
        writer.writerows(zip(
            wavelengths,
            freqs,
            np.real(source_spectrum),
            np.imag(source_spectrum),
            np.abs(source_spectrum) ** 2,
        ))
    return out_path


def write_waveform_csv(nfreq, times, waveform):
    out_path = OUT_DIR / f"adjoint_source_waveform_N{nfreq:03d}.csv"
    with open(out_path, "w", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["time_meep_units", "adjoint_source_waveform_real"])
        writer.writerows(zip(times, waveform))
    return out_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate FilteredSource spectra/waveforms from the Nf=100 reference."
    )
    parser.add_argument(
        "--Nf", dest="nfreqs", type=int, nargs="+",
        default=list(range(NFREQ_MIN, NFREQ_MAX + 1)),
        help=(
            "frequency counts to generate (default: every integer from "
            f"{NFREQ_MIN} through {NFREQ_MAX}); use '--Nf 100 200' for the inset"
        ),
    )
    args = parser.parse_args()
    args.nfreqs = sorted(set(args.nfreqs))
    invalid = [n for n in args.nfreqs if not NFREQ_MIN <= n <= NFREQ_MAX]
    if invalid:
        parser.error(
            f"--Nf values must be within [{NFREQ_MIN}, {NFREQ_MAX}]: {invalid}"
        )
    return args


def main():
    args = parse_args()
    OUT_DIR.mkdir(exist_ok=True)
    ref_wavelengths, ref_base_source = load_reference_base_spectrum()
    summary_path = OUT_DIR / "fd_waveform_generation_summary.csv"

    with open(summary_path, "w", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow([
            "Nf",
            "delta_omega_meep_units",
            "waveform_duration_meep_units",
            "spectrum_csv",
            "waveform_csv",
        ])

        for nfreq in args.nfreqs:
            wavelengths = np.linspace(WL_MIN_UM, WL_MAX_UM, nfreq)
            freqs = 1.0 / wavelengths
            source_spectrum = interp_complex(wavelengths, ref_wavelengths, ref_base_source) / nfreq
            times, waveform = synthesize_waveform(source_spectrum, freqs)
            spectrum_csv = write_spectrum_csv(nfreq, wavelengths, freqs, source_spectrum)
            waveform_csv = write_waveform_csv(nfreq, times, waveform)
            delta_omega = 2.0 * np.pi * (freqs.max() - freqs.min()) / (nfreq - 1)
            writer.writerow([
                nfreq,
                delta_omega,
                float(times[-1] - times[0]),
                spectrum_csv.name,
                waveform_csv.name,
            ])

            if nfreq in (2, 5, 10, 20, 50, 100, 200):
                print(
                    f"Nf={nfreq:03d} | delta_omega={delta_omega:.6g} | "
                    f"T={times[-1] - times[0]:.6g}"
                )

    print(f"Saved waveforms: {OUT_DIR}")
    print(f"Saved summary: {summary_path}")


if __name__ == "__main__":
    main()
