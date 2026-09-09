# Figure (a)--(c) Meep reproducibility archive

This archive contains the simulation code, the raw logs referenced by the
manifest, five-repeat summary CSV files, all inputs required by the final
MATLAB plotting script, and the source-spectrum input needed to regenerate the
waveform inset.

## Build the required TD native sampler

The compiled extension is deliberately not archived because it is specific to
the Python ABI, platform, and Meep build. Create/activate the supplied Conda
environment and build against that active environment:

```bash
conda env create -f fig6_benchmark/environment.yml
conda activate fig6-meep
./teep/build_fastmeep_sample.sh
```

The build script uses `CONDA_PREFIX`, the active Python `sysconfig` C++
compiler, and the non-MPI `libmeep` in that environment. It does not use an
absolute home-directory path or `mpic++`. The TD timing entry points call
`teep.require_native_sampler()` and fail before timing if the extension or a
required native symbol is absent. A native error during sampling or gradient
accumulation also aborts; benchmark mode never silently switches to the
pure-Python fallback.
The archived TD summary records `native_sampler_available=1` and
`sampler_backend=native_fastmeep_sample` for the measured campaign.

## CPU execution wording

Every benchmark command using `--cpu 8` runs as **single process/rank,
single thread, pinned to logical CPU 8**. Here, `8` is the Linux logical-CPU
index used by `sched_setaffinity`; it does not mean that eight CPU cores are
used.

## Included measured data

- FD forward with DFT: 50 raw logs and raw/five-repeat summary CSV files
- FD adjoint FilteredSource: 50 raw logs and raw/five-repeat summary CSV files
- FD forward without DFT: 50 raw logs and raw/five-repeat summary CSV files
- TD every-step and interval-24: 5 raw logs per condition
- TD sampling raw/summary and directional-gradient CSV files
- Additional summary CSV inputs used by the full MATLAB script
- Actual-step Gaussian, `N_f=100`, and `N_f=200` waveform CSV files

The public FD-adjoint runner prepares its FilteredSource exactly once. It
wraps the `prepare_adjoint_run()` call made internally by `adjoint_run()` to
record `SOURCE_BUILD_SECONDS`, while only the subsequent `Simulation.run` is
included in the reported adjoint runtime. The archived five-run
`Simulation.run` wall-clock values remain valid because source preparation
was outside their timed region. However, their historical
`source_build_seconds_*` columns were produced before this one-pass cleanup
and must not be compared directly with newly generated one-pass source-build
timings. Rerun the five repetitions with the supplied runner if source-build
time itself is to be reported.

The plotted statistic is the minimum wall-clock time among five repetitions
for each measured condition. The no-DFT horizontal baseline uses the
`N_f_label=200` five-run minimum (9.024827 s), matching the five-run minimum
used for the DFT-included `N_f=200` comparison. It does not use the pooled
minimum across all 50 no-DFT runs.

## Plot immediately

From the extracted archive root, run:

```matlab
plot_fd_td_runtime_compare_matlab_260723_1437
```

All CSV inputs read at the top of the MATLAB script are included using the
same relative paths as the original workspace.

## Regenerate the inset waveform inputs

The original `N_f=100` reference spectrum is included at:

```text
meep_freq_sampling_benchmark_N05_10_20_100_minrun120/
    adjoint_source_spectrum_N100.csv
```

Regenerate the interpolated spectra and actual-FDTD-step waveform CSV files:

```bash
python MEEP_generate_fd_waveforms_N002_200.py --Nf 100 200
cd fig6_benchmark
python generate_inset_source_waveforms.py
```

The first command creates the two spectra needed by the inset under
`meep_fd_adjoint_waveforms_N002_200/`. Omit `--Nf 100 200` to regenerate every
integer frequency count from 2 through 200. The second
uses those spectra and writes
`fig6_benchmark/data/source_waveforms_actual_timesteps/`.

## Data provenance

- `fig6_benchmark/figure_abc_data_manifest.csv`: curve-level data manifest
- `fig6_benchmark/FIGURE_ABC_DATA_CODE_MAP.md`: code-to-data map
- `fig6_benchmark/data/figure_abc_common_decay_parameters.csv`: Meep,
  FilteredSource, termination, geometry, and hardware parameters
- `fig6_benchmark/data/figure_abc_runtime_per_fdtd_step.csv`: runtime/step table

The archive does not include generated PNG/PDF outputs. They are reproduced
by the included MATLAB script.
