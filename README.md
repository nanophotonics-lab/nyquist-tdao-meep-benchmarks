# Meep benchmarks for Nyquist-sampled time-domain adjoint FDTD

Research code and archived data for the Meep runtime comparison associated with **Nyquist-Sampled Adjoint FDTD for Broadband Photonic Inverse Design**.

This repository provides a controlled computational benchmark that characterizes source duration, forward DFT-monitor overhead, and adjoint runtime at a fixed design configuration. It isolates representative forward and adjoint workloads to support implementation-level performance assessment. Full device-optimization workflows and the remaining manuscript results are outside the scope of this archive.

The current benchmark and archived plots can be run using the contents of this repository and the documented software environment. Repeating the reference-versus-current implementation comparison additionally requires the reference source archive identified in [the comparison procedure](docs/REPRODUCING_THE_COMPARISON.md).

## Implementation and measurements

| Task | Inputs and outputs |
|---|---|
| Reproduce the reported plots | The MATLAB script reads the archived CSV files listed in the [code-to-data map](fig6_benchmark/FIGURE_ABC_DATA_CODE_MAP.md). |
| Run the current TD implementation | The sampling sweep writes new logs, gradients, and summaries to a new output root. |
| Check the library implementation | The library check uses the included reference arrays and writes its own validation results. |
| Repeat the supplementary implementation comparison | The comparison driver additionally needs the external reference source archive identified in the [comparison instructions](docs/REPRODUCING_THE_COMPARISON.md). |

The benchmark driver and `teep.TDAObjective` pair forward and adjoint samples by physical timestep and evaluate the adjoint-field derivative at the original FDTD step. Sparse forward storage is retained.

Repeated timing results are in [`results/runtime_comparison_20260909`](results/runtime_comparison_20260909). The labels `original` and `corrected` in the measurement files identify the two implementations used in that experiment. Historical plotting inputs retain their measured values and are distinct from the current-code measurements.

The [timing report](results/runtime_comparison_20260909/REPORT.md) records a +0.18% change in the forward-plus-adjoint median and +4.37% in the adjoint median for corrected M=24. These are observations under existing host load, not proof of zero overhead. See the report for paired-block variation.

**Measured comparison:** on the supplied initial design, corrected interval-24 gradients agree with the original every-step gradient to approximately 8.3e-7 relative L2 error. The [validation notes](docs/KNOWN_LIMITATIONS.md) and [complete validation results](results/gradient_validation_20260909) describe the tested conditions and the results of the separate checks.

## Install

Use Linux or WSL with the archived non-MPI Conda environment. Native Windows is not the execution target. MATLAB is separately required to execute the original plotting script; it was checked with MATLAB R2025a.

```bash
conda env create -f fig6_benchmark/environment.yml
conda activate fig6-meep
bash teep/build_fastmeep_sample.sh
```

The native extension must be rebuilt for the active Python / Meep ABI. Timing entry points require native sampling and stop on a native failure. `--cpu 8` means one thread pinned to **logical CPU index 8**, not eight cores. Choose an allowed CPU index on your machine.

## Run corrected TD measurements

Always use an empty output directory for a new campaign. Reusing the historical directory will skip runs that already have logs.

```bash
python run_td_sampling_convergence_sweep.py --intervals 1 24 --repetitions 5 --seed 20260909 --cpu 8 --output-root new_measurements/td_corrected
```

This generates new gradients and timing summaries; it does not replace archived plotting inputs. To measure the change against the original implementation, use [the comparison procedure](docs/REPRODUCING_THE_COMPARISON.md).

The common library path can be checked independently with `python validation/verify_library_gradient.py --cpu 8`. Its M=1 and M=24 integration checks both pass for the supplied initial design. `python validation/finite_difference_check.py --help` describes the separate directional finite-difference diagnostic; its measured outcomes and interpretation are documented in the [validation notes](docs/KNOWN_LIMITATIONS.md).

## Reproduce the original plots

From the repository root in MATLAB:

```matlab
plot_fd_td_runtime_compare_matlab_260723_1437
```

This intentionally reproduces the **historical** figures and gradient diagnostics. In particular, its TD runtime and gradient curves read the original campaign. Refer to the current comparison report for corrected values. The original script emits individual panels and diagnostic figures; manuscript page composition is separate.

For waveform regeneration and the detailed data manifest, see [the archive README](REPRODUCIBILITY_ARCHIVE_README.md) and [the code-to-data map](fig6_benchmark/FIGURE_ABC_DATA_CODE_MAP.md). These identify the archived figure inputs and distinguish them from additional current-code measurements.

## Citation and reuse

Use [`CITATION.cff`](CITATION.cff) for the repository citation and record the commit identifier used for a study. DOI registration metadata is prepared; no DOI has been assigned.

No project-wide open-source license was supplied with the original archive. This release does not invent a license grant or relicense third-party software. See [licensing status](LICENSE_STATUS.md). Public access to source and data is distinct from an unrestricted permission to reuse or redistribute them.
