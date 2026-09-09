# Known limitations

## Absolute gradient correctness remains unresolved

Corrected sparse and every-step gradients agree on the benchmark initial design, but this does not validate the underlying spatial/discrete adjoint against objective finite differences. At fixed final time 70.035 a/c, central differences with epsilon 0.005 gave:

| Unit design direction | Central difference | Corrected M=24 adjoint | Relative directional error |
|---|---:|---:|---:|
| Original gradient | 0.0497026235 | 0.0492139773 | 0.9831% |
| Smooth cosine | -0.0008764067 | 0.0001094805 | 112.4920% |
| Fixed random seed | 0.0009192220 | 0.0010274507 | 11.7740% |

The same behavior was observed at epsilon 0.02. Small directional derivatives magnify relative error, but the smooth-direction sign mismatch persists. These failures are shared by the original every-step baseline. The MaterialGrid-to-Yee-grid interpolation pullback, spatial source/monitor correspondence, and discrete adjoint consistency require further investigation. No universal scalar correction has been fitted.

## Temporal correction

The old implementation reverses the sampled array without reversing its physical timestep indices. At N=14007 and M=24 the last stored forward timestep is 13992, requiring an adjoint timestep of 15; the old implementation pairs it with timestep 0. It also differentiates the already-downsampled forward field using M*dt, changing the differentiation operator.

The correction stores forward timestep indices and computes the adjoint derivative at the original dt around the matching reversed time. Only the sparse forward history and a small rolling adjoint buffer are retained. Endpoint behavior uses one-sided differences. Other termination horizons, complex sources, MPI execution and other geometries require additional validation before general use.

## Timing and data provenance

FD and TD use different objectives; runtime curves compare implementation workloads, not equal-objective/equal-accuracy optimization. Historical FD source-build timings also predate the source-preparation cleanup described in the original README. Current TD code must not be attributed to historical TD gradient files.

The DFT monitors use Meep's default automatic decimation, as described in the [code-to-data map](../fig6_benchmark/FIGURE_ABC_DATA_CODE_MAP.md). FDTD propagation advances at every original timestep; DFT accumulation follows the monitor's automatic interval. The archived summaries do not record the selected per-monitor decimation factors.

Machine names and historical working-directory labels in raw logs are retained as provenance. The release includes no manuscript source, account credentials, or precompiled extension.
