# Runtime impact of the temporal-gradient correction

Five repetitions per condition, randomized within repetition blocks; independent processes, one thread on logical CPU 8. Two M=24 warmups were excluded. Values below are seconds and are measured under the workstation's existing background load.

| Version | M | Forward median | Adjoint median | Forward+adjoint median | Total IQR |
|---|---:|---:|---:|---:|---:|
| original | 1 | 17.8135 | 18.2787 | 36.0922 | 35.6002–36.1760 |
| original | 24 | 10.0530 | 10.7394 | 20.9616 | 19.9772–21.0901 |
| corrected | 1 | 17.9992 | 17.9491 | 35.9482 | 35.7379–36.2716 |
| corrected | 24 | 10.0238 | 11.2090 | 21.0001 | 20.9425–21.5609 |

Corrected M=24 median changes: forward -0.291%, adjoint +4.373%, total +0.183%, full evaluation including setup/cleanup +0.133%.

The predeclared operational criterion (no more than 5% median increase for both adjoint and forward+adjoint time) is satisfied. This supports treating the observed runtime impact as small for this workload. It does not establish zero overhead or a statistical equivalence margin.

The criterion above compares the medians of the two condition groups. As a sensitivity check, percentage changes calculated within each repetition block give a median of +5.227% for adjoint time (range -0.728% to +8.994%) and +2.352% for forward+adjoint time (range -2.596% to +4.832%). The adjoint-only conclusion therefore depends on the summary statistic; these observations do not establish a strict 5% overhead upper bound. The total evaluation impact remains small by both summaries. See `paired_changes.json` for every block.

Background CPU use was observed, including OneDrive and other host applications, and individual cores were highly occupied. The later host observation recorded aggregate CPU load of 26%. These snapshots are not continuous campaign telemetry; see `host_load_observation.json`. Randomized blocks reduce ordering effects but do not fully isolate interference. Do not attribute every observed wall-clock difference to the patch.

Every condition still performs 14,007 forward and 14,007 adjoint FDTD updates. The corrected gradient does add fine-step field reads and alignment bookkeeping; the statement that it adds no computation would be inaccurate. Corrected M=24 retains 584 forward field samples, versus 14,008 for M=1.

The corrected results match the original M=1 gradient within 2e-6 relative L2 error in all repetitions (M=24 approximately 8.281e-7). Absolute finite-difference failures are documented separately in `docs/KNOWN_LIMITATIONS.md`.

Historical FD and TD plotting inputs are unchanged. This report must not be used to label historical gradients as corrected or to claim a newly measured FD/TD speedup without the corresponding data provenance.
