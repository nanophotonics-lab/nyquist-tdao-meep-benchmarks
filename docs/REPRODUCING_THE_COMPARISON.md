# Reproduce the measured comparison

The scripts characterize computational costs at a fixed design configuration by evaluating representative forward and adjoint workloads. They support performance assessment of the implementation; a full iterative device-optimization workflow is outside this benchmark's scope.

The recorded campaign uses Python 3.9.23, Meep module 1.30.0, NumPy 2.0.2, a non-MPI build, one process and one thread pinned to logical CPU 8. Each case is launched in a fresh process.

The schedule shuffles four conditions within each of five repetition blocks: reference M=1, reference M=24, current M=1, current M=24. Measurement files use `original` for the reference and `corrected` for the current implementation. One M=24 warmup per implementation is excluded. The operational criterion was no more than 5% increase in either condition-group median for adjoint or forward-plus-adjoint time; paired-block variation is reported separately.

The comparison requires the supplied input archive `figure_abc_meep_simulation_code_20260814.tar.gz`, identified by SHA-256 in `SOURCE_PROVENANCE.json`. That reference source archive is an external input, not an available Git tag. Obtain it from the study authors and extract it to a separate directory before rerunning the comparison. Current-code sampling and library checks in the README can run without that external archive.

```bash
baseline_root=/absolute/path/to/extracted/reference_archive
bash teep/build_fastmeep_sample.sh
bash "$baseline_root/teep/build_fastmeep_sample.sh"
python validation/benchmark_release.py --baseline-root "$baseline_root" --corrected-root "$PWD" --output-root new_measurements/runtime_comparison --cpu 8 --repetitions 5 --seed 20260909
```

The driver writes the schedule, per-run logs and gradient arrays, raw CSV/JSON, and the summary. `results/runtime_comparison_20260909` contains the recorded campaign. `results/gradient_validation_20260909` contains the separate validation measurements.
