# Figure (a)--(c) 데이터 생성 코드 맵

이 문서는 source-duration, FD-forward DFT overhead, FD/TD adjoint-runtime의
세 패널에 사용된 값을 `실행 코드 -> 로그 -> 요약 CSV -> MATLAB 변수` 순서로
추적하기 위한 기준 문서다. 상세한 행 단위 매핑은
[`figure_abc_data_manifest.csv`](figure_abc_data_manifest.csv)에 있다.
현재 common-decay Figure의 Meep/FilteredSource/geometry/hardware parameter는
[`data/figure_abc_common_decay_parameters.csv`](data/figure_abc_common_decay_parameters.csv)에
`N_f`별로 기록되어 있다.

## 1. 공통 기준

| 항목 | 설정 |
|---|---|
| 직접 측정한 `N_f` | `2, 5, 10, 15, 20, 30, 50, 100, 150, 200` |
| 반복 | 각 조건 5회, 실행 순서 무작위화 |
| Figure에 사용한 통계량 | 5회 중 **최솟값** (`*_min`), 중앙값 아님 |
| FD 곡선 연결 | 측정점 사이 shape-preserving cubic interpolation (`pchip`) |
| TD 곡선 | `N_f`와 무관한 단일 측정값을 수평선으로 반복 표시 |
| 시간 측정 범위 | `meep.Simulation.run` 내부 wall-clock time |
| FDTD 시간 간격 | `dt = 0.005 a/c` (`resolution = 100`) |
| CPU 실행 형태 | single process/rank, single thread, pinned to logical CPU 8 |
| Meep | module 1.30.0; Conda pymeep 1.30.1 `nompi_py39h9d793ab_103` |
| 파장 범위 | 0.50--0.70 um, 파장을 균일하게 표본화한 뒤 `f_i=1/lambda_i` |
| 상단 축 | `Delta lambda/lambda_band = 1/(N_f-1)`; 일부 tick 표시는 반올림 |

공통 금속렌즈 형상, 재료, 주파수 격자, Gaussian source 및 FD objective는
[`run_benchmark.py`](run_benchmark.py)에만 정의되어 있다. 개별 benchmark
runner는 이 모듈을 import하므로, 물리 설정을 각 실행 파일에 다시 복사하지
않는다.

명령의 `--cpu 8`은 8개 core를 사용한다는 뜻이 아니라 Linux logical CPU
**index 8**에 process affinity를 고정한다는 뜻이다.

## 2. 패널별 provenance

### (a) Source duration

#### Forward Gaussian (FD and TD)

- 정의: [`run_benchmark.py`](run_benchmark.py)의 `make_sources()`
- source: `GaussianSource(frequency=FCEN, fwidth=FWIDTH)`
- 종료시간 산출: Meep source 객체의 `last_time()`
- waveform 생성: [`generate_inset_source_waveforms.py`](generate_inset_source_waveforms.py)
- 입력 CSV: `data/source_waveforms_actual_timesteps/gaussian.csv`
- MATLAB 값: CSV의 `max(time_a_over_c)`를 전 `N_f`에 반복한다. 현재 값은
  `17.5 a/c`이다.

#### FD adjoint FilteredSource

- 실행 코드: [`run_fd_adjoint_common_decay_once.py`](run_fd_adjoint_common_decay_once.py)
- sweep/요약 코드: [`run_fd_adjoint_common_decay_sweep.py`](run_fd_adjoint_common_decay_sweep.py)
- 원시 로그: `fd_adjoint_common_decay_sweep/logs/Nf*/rep*.log`
- 요약 CSV: `fd_adjoint_common_decay_sweep/data/fd_adjoint_common_median_iqr.csv`
- MATLAB 열: `adjoint_source_end_time_min`
- MATLAB 변수: `FD_adjoint_source_length`

Meep `FilteredSource`의 basis 수는 `N_basis=N_f`이며, window 길이는

```text
delta_f_min = min(abs(diff(f_i)))
T = max(abs(1/diff(f_i))) = 1/delta_f_min .
```

따라서 wavelength band가 고정되어 있을 때 `N_f`가 증가하면 source support가
거의 선형으로 증가한다. 실제 값은 `N_f=2, 20, 100, 200`에서 각각
`1.75, 45.85, 241.85, 486.85 a/c`이다.

Inset의 Gaussian 및 `N_f=100` 파형은 실제 FDTD 간격 `dt=0.005 a/c`마다
내보낸 것이다. FilteredSource spectrum은
[`MEEP_generate_fd_waveforms_N002_200.py`](../MEEP_generate_fd_waveforms_N002_200.py)가
기존 dense `N_f=100` adjoint spectrum을 target grid로 복소 보간해 만든다.
따라서 inset은 source support와 파형을 설명하는 시각 자료이며, runtime sweep
로그에서 파형 배열을 다시 추출한 것은 아니다.

### (b) FD forward: DFT included versus removed

#### DFT included

- 단일 실행: [`run_forward_only_benchmark.py`](run_forward_only_benchmark.py)
- 5회 sweep: [`run_forward_only_sweep.py`](run_forward_only_sweep.py)
- 원시 로그: `fd_forward_common_decay_sweep/logs/common_field_decay/*.log`
- 요약 CSV: `fd_forward_common_decay_sweep/data/forward_only_median_iqr.csv`
- MATLAB 열/변수: `runtime_seconds_min` -> `fd_forward_measured` ->
  `FD_forward`
- DFT workload: active design-region cells `11,569 x N_f`와 point-objective
  frequency bins에 대한 DFT 누적값을 유지한다. 이 수는 누적 배열의 크기를
  설명하며, 매 FDTD time step의 갱신 횟수를 뜻하지 않는다.
- DFT 갱신 주기: `run_benchmark.py`는 `FourierFields`와
  `OptimizationProblem`의 `decimation_factor`를 지정하지 않으므로, 사용한
  Meep 1.30.0의 기본값 `0` (automatic decimation)을 따른다. Meep가 source와
  monitor의 주파수 대역을 고려하여 DFT 누적 간격을 정한다. `1`을 지정하면
  매 FDTD step 누적하지만, 이 benchmark는 그 설정을 강제하지 않는다.
- FDTD field propagation은 원래 `dt`마다 수행된다. DFT 누적 간격과 TD의
  `sampling_interval=24`는 서로 다른 설정이며, 동일한 값으로 해석하지 않는다.
  실행 중 선택된 monitor별 decimation factor는 기존 요약 데이터에 기록되어
  있지 않으므로 특정 수치로 단정하지 않는다.
- 따라서 패널 (b)는 automatic decimation이 적용된 DFT monitor의 추가 비용을
  나타낸다. 매 step DFT 누적 비용으로 해석하지 않는다. 관련 API 설명은
  [Meep DFT fields 문서](https://meep.readthedocs.io/en/latest/Python_User_Interface/#dft-fields)에 있다.

#### DFT removed

- 단일 실행: [`run_fd_forward_no_dft_once.py`](run_fd_forward_no_dft_once.py)
- 5회 sweep: [`run_fd_forward_no_dft_sweep.py`](run_fd_forward_no_dft_sweep.py)
- 원시 로그: `fd_forward_no_dft_common_decay_sweep/logs/Nf*/*.log`
- 요약 CSV: `fd_forward_no_dft_common_decay_sweep/data/fd_forward_no_dft_summary.csv`
- 검증: run 전후 `dft_objects=0`, `dft_accumulators=0`
- MATLAB 값: DFT 포함 `N_f=200`의 five-run minimum과 대칭이 되도록 동일한
  `N_f_label=200`의 five-run minimum `9.024827127 s`를 수평 점선으로 표시한다.

No-DFT 실행의 `N_f_label`은 randomized repetition을 배치하기 위한 label일
뿐 실제 계산에는 사용되지 않는다. 따라서 이 baseline의 물리적 frequency
count는 `N_f=0`이며, objective와 incident normalization도 계산하지 않는다.
동일 label을 선택하는 이유는 pooled 50-run minimum의 표본 수 이점을 제거하고
DFT 포함/제거 양쪽 모두 동일한 5회 최솟값 통계량으로 비교하기 위해서다.
논문에서는 이 선을 **bare FDTD field-propagation baseline**으로 해석해야 하며,
FD objective를 계산하는 또 다른 방법으로 해석하면 안 된다.

### (c) Adjoint runtime

#### FD

- 단일 실행/sweep/CSV는 패널 (a)의 FD adjoint와 동일하다.
- MATLAB 열/변수: `runtime_seconds_min` -> `fd_adjoint_measured` ->
  `FD_adjoint`
- timed region에는 adjoint source construction과 선행 forward run이 포함되지
  않고, adjoint `Simulation.run`만 포함된다.
- 공개 runner는 `adjoint_run()` 내부에서 source를 한 번만 준비한다. 이 한 번의
  `prepare_adjoint_run()` 호출 시간은 `SOURCE_BUILD_SECONDS`로 별도 계측하며
  `Simulation.run` wall-clock runtime에는 포함하지 않는다.
- 압축본의 기존 5회 `Simulation.run` runtime은 source 준비가 timed region 밖에
  있었으므로 유효하다. 다만 과거 summary의 `source_build_seconds_*`는 중복 준비
  정리 전 계측값이므로, 새 runner의 1회 준비 시간과 직접 비교하지 않는다.
  source-build 시간 자체를 보고할 경우 새 runner로 5회를 다시 측정한다.

이 곡선의 source는 Gaussian이 아니라 **FilteredSource**다. 따라서 MATLAB
범례는 `Frequency-domain adjoint (filtered source)`로 표기했으며, 기존
`FD Gaussian`은 데이터 생성 코드와 일치하지 않는 잘못된 명칭이다.

#### TD every-step / TD interval-24

- TD 계산: [`MEEP_TD_runtime_after_source_benchmark.py`](../MEEP_TD_runtime_after_source_benchmark.py)
- 단일 실행: [`run_td_condition_once.py`](../run_td_condition_once.py)
- 5회 sweep: [`run_td_sampling_convergence_sweep.py`](../run_td_sampling_convergence_sweep.py)
- 원시 로그: `../td_sampling_convergence_sweep/logs/interval_*/*.log`
- 요약 CSV: `../td_sampling_convergence_sweep/data/td_sampling_summary.csv`
- every-step: `sampling_interval=1`, 열 `adjoint_s_min`
- interval-24: `sampling_interval=24`, 열 `adjoint_s_min`

보관된 두 TD 조건은 모두 14,007 actual FDTD updates와 동일한 simulation
horizon을 사용한다. interval-24는 FDTD step 수를 줄이지 않고 forward
design-grid field 저장과 gradient-correlation contribution의 수를 줄인다.
현재 공개 코드는 forward sample의 physical timestep을 저장하고, 역시간으로
대응하는 adjoint field를 원래 FDTD 간격에서 읽어 시간 미분을 평가한다.
adjoint field 읽기 시점과 gradient 누적 시점은 구분된다.

위 로그·CSV는 기존 Figure의 측정 입력이다. 현재 공개 코드의 추가 측정은
[`runtime comparison`](../results/runtime_comparison_20260909/REPORT.md)에,
sampling 비교의 설정과 결과는
[`validation notes`](../docs/KNOWN_LIMITATIONS.md)에 연결되어 있다.
현재 코드의 새 실행 결과를 기존 Figure 입력과 혼합하지 않는다.

회색 `N_f >= 20` 영역과 `>>10x faster` 화살표는 MATLAB annotation이며 별도
simulation data가 아니다.

## 3. 종료조건

| 데이터 | 종료 규칙 |
|---|---|
| FD forward, DFT included | focus `(0,1.78,0)`의 `Ez`, decay window `10 a/c`, tolerance `1e-4`, minimum `67.5 a/c`, source-end gate, cap `2000 a/c` |
| FD forward, DFT removed | 위와 동일 |
| FD adjoint | 동일한 point-field decay closure를 사용하며 `OptimizationProblem.adjoint_run()`의 `until_after_sources`를 통해 FilteredSource 종료 전에는 멈추지 않음 |
| TD forward | focus-point field decay `1e-4`, window `10 a/c`, minimum `67.5 a/c`, cap `2000 a/c` |
| TD adjoint | forward의 실제 종료시간과 같은 총 시간까지 실행; 별도의 decay 판정을 다시 수행하지 않음 |

즉 Figure의 FD와 TD는 종료 horizon을 최대한 맞췄지만, adjoint 종료 API가
완전히 같은 것은 아니다. 또한 FD는 discrete incident-normalized frequency
intensity이고 TD는 time-integrated energy이므로, 이 Figure는 동일 objective
정확도 비교가 아니라 구현 workload 비교다.

## 4. 재생성 순서

아래 명령은 repository root에서 시작한다. 사용 중인 pymeep 환경의
Python으로 실행해야 한다. 기존 output directory를 지정하면 완료된 실행을
skip하므로, 새 측정에는 별도의 output root를 사용한다.

```bash
cd fig6_benchmark
python run_forward_only_sweep.py --repetitions 5 --seed 20260805 --cpu 8 --termination common_field_decay --output-root fd_forward_common_decay_sweep
python run_fd_adjoint_common_decay_sweep.py --repetitions 5 --cpu 8 --output-root fd_adjoint_common_decay_sweep
python run_fd_forward_no_dft_sweep.py --repetitions 5 --seed 20260812 --cpu 8 --output-root fd_forward_no_dft_common_decay_sweep
cd ..
python run_td_sampling_convergence_sweep.py --intervals 1 2 4 8 12 16 20 24 --repetitions 5 --seed 20260809 --cpu 8 --output-root td_sampling_convergence_sweep
python MEEP_generate_fd_waveforms_N002_200.py
cd fig6_benchmark
python generate_inset_source_waveforms.py
```

FD adjoint는 forward sweep이 만든
`fig6_benchmark/forward_only_sweep/cache/incident_norm_Nf*.npy`를 사용하므로 위
순서를 유지한다. 기존 output root에 대해 sweep을 다시 실행하면 완료된
`(N_f,repetition)`은 skip한다. 완전히 새 측정이 필요하면 기존 결과와 섞이지
않도록 새로운 output root를 사용해야 한다.

최종 시각화는 project root에서
[`plot_fd_td_runtime_compare_matlab_260723_1437.m`](../plot_fd_td_runtime_compare_matlab_260723_1437.m)을
실행한다. 이 MATLAB 파일은 Figure (a)--(c) 외의 진단 Figure 데이터도 읽기
때문에, 전체 스크립트 실행 시 상단 주석에 적힌 추가 CSV들도 필요하다.

## 5. 공개 시 최소 포함 파일

재현 가능한 공개본에는 다음을 함께 포함한다.

1. 공통 물리 설정: `run_benchmark.py`
2. 세 FD once runner와 sweep runner
3. TD core, once runner, sweep runner
4. waveform spectrum/inset 생성 코드
5. raw logs, five-run summary CSV, 이 manifest
6. 최종 MATLAB plotting script

`fd_forward_no_dft_summary.csv`만 공개하면 `N_f_label`을 실제 주파수 개수로
오해할 수 있으므로, no-DFT runner의 `OBJECTIVE_EVALUATED=False` 및
`DFT_FREQUENCY_COUNT=0` metadata도 함께 보존한다.
