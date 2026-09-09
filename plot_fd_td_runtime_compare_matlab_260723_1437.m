% Compare FD adjoint and TEEP TD adjoint runtime on the same delta_lambda / N_f axis.
%
% Required data:
%   fig6_benchmark/fd_forward_common_decay_sweep/data/forward_only_median_iqr.csv
%   fig6_benchmark/fd_forward_no_dft_common_decay_sweep/data/fd_forward_no_dft_summary.csv
%   fig6_benchmark/fd_adjoint_common_decay_sweep/data/fd_adjoint_common_median_iqr.csv
%   fig6_benchmark/fd_no_min_common_decay_nf_lt20_sweep/data/fd_no_min_decay_summary.csv
%   threeway_forward_common_decay_sweep_v2/data/threeway_forward_summary.csv
%   td_repeated_sweep/data/td_repeated_median_iqr.csv
%
% FD data is directly measured at N_f = [2 5 10 15 20 30 50 100 150 200].
% FD is interpolated onto N_f = 2:2:200. Each TD statistic comes from five
% N_f-independent runs and is repeated only as a horizontal reference.
%
% Suggested caption notation for normalized time axes:
% a is the characteristic length (Meep length unit), c is the speed of
% light, and time is reported in the normalized dimensionless unit a/c.

clear; clc; close all;

set(0,'defaultAxesFontName','Arial')
set(0,'defaultAxesFontWeight','normal')
set(0,'defaultAxesFontSize',9)
set(0,'DefaultLineLineWidth',0.75)
set(0,'DefaultAxesLineWidth',0.5)

script_dir = fileparts(mfilename('fullpath'));
fd_forward_file = fullfile(script_dir, ...
    'fig6_benchmark', 'fd_forward_common_decay_sweep', 'data', ...
    'forward_only_median_iqr.csv');
fd_adjoint_file = fullfile(script_dir, ...
    'fig6_benchmark', 'fd_adjoint_common_decay_sweep', 'data', ...
    'fd_adjoint_common_median_iqr.csv');
fd_forward_no_dft_file = fullfile(script_dir, ...
    'fig6_benchmark', 'fd_forward_no_dft_common_decay_sweep', 'data', ...
    'fd_forward_no_dft_summary.csv');
fd_no_min_file = fullfile(script_dir, ...
    'fig6_benchmark', 'fd_no_min_common_decay_nf_lt20_sweep', 'data', ...
    'fd_no_min_decay_summary.csv');
common_decay_forward_file = fullfile(script_dir, ...
    'threeway_forward_common_decay_sweep_v2', 'data', ...
    'threeway_forward_summary.csv');
td_stats_file = fullfile(script_dir, 'td_repeated_sweep', 'data', ...
    'td_repeated_median_iqr.csv');
td_sampling_file = fullfile(script_dir, 'td_sampling_convergence_sweep', ...
    'data', 'td_sampling_summary.csv');
td_directional_file = fullfile(script_dir, 'td_sampling_convergence_sweep', ...
    'data', 'td_directional_gradient_comparison.csv');
actual_step_waveform_dir = fullfile(script_dir, 'fig6_benchmark', 'data', ...
    'source_waveforms_actual_timesteps');
gaussian_waveform_file = fullfile(actual_step_waveform_dir, 'gaussian.csv');
filtered_waveform_nf100_file = fullfile( ...
    actual_step_waveform_dir, 'filtered_source_N100.csv');
filtered_waveform_nf200_file = fullfile( ...
    actual_step_waveform_dir, 'filtered_source_N200.csv');

if ~isfile(fd_forward_file)
    error('FD common-decay forward data file not found: %s', fd_forward_file);
end
if ~isfile(fd_adjoint_file)
    error('FD common-decay adjoint data file not found: %s', fd_adjoint_file);
end
if ~isfile(fd_forward_no_dft_file)
    error('FD forward no-DFT data file not found: %s', fd_forward_no_dft_file);
end
if ~isfile(fd_no_min_file)
    error('FD no-minimum-time data file not found: %s', fd_no_min_file);
end
if ~isfile(common_decay_forward_file)
    error('Common-decay forward data file not found: %s', common_decay_forward_file);
end
if ~isfile(td_stats_file)
    error('TD repeated common-decay data file not found: %s', td_stats_file);
end
if ~isfile(td_sampling_file)
    error('TD sampling-convergence data file not found: %s', td_sampling_file);
end
if ~isfile(td_directional_file)
    error('TD directional-gradient data file not found: %s', td_directional_file);
end
if ~isfile(gaussian_waveform_file) || ...
        ~isfile(filtered_waveform_nf100_file) || ...
        ~isfile(filtered_waveform_nf200_file)
    error('Gaussian/N_f=100/N_f=200 source-waveform data are incomplete.');
end

FDfSteps = sortrows(readtable(fd_forward_file, 'TextType', 'string'), 'N_f');
FDaSteps = sortrows(readtable(fd_adjoint_file, 'TextType', 'string'), 'N_f');
FDfNoDFT = sortrows(readtable( ...
    fd_forward_no_dft_file, 'TextType', 'string'), 'N_f_label');
FDNoMin = readtable(fd_no_min_file, 'TextType', 'string');
CommonFwd = readtable(common_decay_forward_file, 'TextType', 'string');
TDStats = readtable(td_stats_file, 'TextType', 'string');
TDSampling = sortrows(readtable(td_sampling_file, 'TextType', 'string'), ...
    'sampling_interval');
TDDirectional = sortrows(readtable(td_directional_file, 'TextType', 'string'), ...
    'sampling_interval');
GaussianWaveform = readtable(gaussian_waveform_file, 'TextType', 'string');
FilteredWaveform100 = readtable( ...
    filtered_waveform_nf100_file, 'TextType', 'string');
FilteredWaveform200 = readtable( ...
    filtered_waveform_nf200_file, 'TextType', 'string');
if ~isequal(double(FDfSteps.N_f), double(FDaSteps.N_f))
    error('New common-decay FD forward/adjoint N_f grids do not match.');
end
if any(FDfSteps.termination ~= "common_field_decay") || ...
        any(FDaSteps.termination ~= "common_field_decay")
    error('FD inputs must use the common_field_decay termination.');
end
if any(FDfSteps.valid_repetitions ~= 5) || any(FDaSteps.valid_repetitions ~= 5)
    error('Every FD N_f must contain five valid repetitions.');
end
if ~isequal(double(FDfNoDFT.N_f_label), double(FDfSteps.N_f))
    error('FD forward with-DFT and no-DFT N_f label grids do not match.');
end
if any(FDfNoDFT.valid_repetitions ~= 5) || ...
        any(FDfNoDFT.cap_hits ~= 0) || ...
        any(FDfNoDFT.dft_objects_before_run ~= 0) || ...
        any(FDfNoDFT.dft_objects_after_run ~= 0) || ...
        any(FDfNoDFT.dft_accumulators ~= 0)
    error('FD forward no-DFT sweep is incomplete or contains a DFT object.');
end
if any(FDfNoDFT.steps_min ~= FDfSteps.steps_min) || ...
        any(FDfNoDFT.meep_time_min ~= FDfSteps.meep_time_min) || ...
        any(FDfNoDFT.termination ~= "common_field_decay")
    error('FD forward no-DFT and with-DFT simulation horizons do not match.');
end

FDNoMinF = sortrows(FDNoMin(FDNoMin.method == "forward", :), 'N_f');
FDNoMinA = sortrows(FDNoMin(FDNoMin.method == "adjoint", :), 'N_f');
no_min_expected_n = [2; 5; 10; 15];
if ~isequal(double(FDNoMinF.N_f), no_min_expected_n) || ...
        ~isequal(double(FDNoMinA.N_f), no_min_expected_n)
    error('FD no-minimum-time data must contain N_f = [2 5 10 15].');
end
if any(FDNoMinF.valid_repetitions ~= 5) || ...
        any(FDNoMinA.valid_repetitions ~= 5) || ...
        any(FDNoMinF.minimum_run_time ~= 0) || ...
        any(FDNoMinA.minimum_run_time ~= 0) || ...
        any(FDNoMinF.cap_hits ~= 0) || any(FDNoMinA.cap_hits ~= 0)
    error('FD no-minimum-time sweep is incomplete or failed termination checks.');
end
if any(FDNoMinF.final_decay_ratio_max > FDNoMinF.decay_by) || ...
        any(FDNoMinA.final_decay_ratio_max > FDNoMinA.decay_by) || ...
        any(FDNoMinF.post_source_time_min < 0) || ...
        any(FDNoMinA.post_source_time_min < 0)
    error('FD no-minimum-time source-aware decay validation failed.');
end

% Build the legacy plotting table from the minimum of five common-decay
% repetitions. Total evaluation time is the sum of the separately measured
% forward and adjoint minimum Simulation.run wall-clock times.
fd_n_measured = double(FDfSteps.N_f);
fd_forward_measured = double(FDfSteps.runtime_seconds_min);
fd_adjoint_measured = double(FDaSteps.runtime_seconds_min);
fd_no_dft_n = double(FDfNoDFT.N_f_label);
fd_no_dft_forward_min = double(FDfNoDFT.runtime_seconds_min);
fd_no_dft_reference_label = 200;
fd_no_dft_reference_index = find( ...
    fd_no_dft_n == fd_no_dft_reference_label, 1);
if isempty(fd_no_dft_reference_index)
    error('No-DFT N_f_label=%d reference is missing.', ...
        fd_no_dft_reference_label);
end
fd_no_dft_control_n = 0;
fd_no_dft_control_min = ...
    fd_no_dft_forward_min(fd_no_dft_reference_index);
FD = table(fd_n_measured, 200./(fd_n_measured-1), ...
    fd_forward_measured, fd_adjoint_measured, ...
    fd_forward_measured+fd_adjoint_measured, ...
    double(FDfSteps.runtime_seconds_q1), double(FDfSteps.runtime_seconds_q3), ...
    double(FDaSteps.runtime_seconds_q1), double(FDaSteps.runtime_seconds_q3), ...
    'VariableNames', {'nfreq','delta_lambda_nm','forward_s','adjoint_s', ...
    'eval_total_s','forward_q1_s','forward_q3_s','adjoint_q1_s','adjoint_q3_s'});

no_min_n = double(FDNoMinF.N_f);
no_min_forward_s = double(FDNoMinF.runtime_seconds_min);
no_min_adjoint_s = double(FDNoMinA.runtime_seconds_min);
no_min_forward_end = double(FDNoMinF.meep_time_min);
no_min_adjoint_end = double(FDNoMinA.meep_time_min);
no_min_forward_steps = double(FDNoMinF.steps_min);
no_min_adjoint_steps = double(FDNoMinA.steps_min);
no_min_forward_source_end = double(FDNoMinF.source_end_time_min);
no_min_adjoint_source_end = double(FDNoMinA.source_end_time_min);

[found_forward, old_forward_index] = ismember(no_min_n, double(FDfSteps.N_f));
[found_adjoint, old_adjoint_index] = ismember(no_min_n, double(FDaSteps.N_f));
if ~all(found_forward) || ~all(found_adjoint)
    error('N_f matching failed between minimum-time 67.5 and zero data.');
end
old_min_forward_s = double(FDfSteps.runtime_seconds_min(old_forward_index));
old_min_adjoint_s = double(FDaSteps.runtime_seconds_min(old_adjoint_index));
old_forward_objective = double(FDfSteps.objective_median(old_forward_index));
no_min_forward_objective = double(FDNoMinF.objective_median);
forward_objective_relative_change = ...
    (no_min_forward_objective-old_forward_objective)./old_forward_objective;
if height(TDSampling) ~= 8 || any(TDSampling.valid_repetitions ~= 5)
    error('TD sampling convergence requires eight intervals with five valid runs each.');
end
TD1 = TDSampling(double(TDSampling.sampling_interval) == 1, :);
TD24 = TDSampling(double(TDSampling.sampling_interval) == 24, :);
if height(TD1) ~= 1 || height(TD24) ~= 1
    error('Expected one new TD sampling row for intervals 1 and 24.');
end
if height(TDDirectional) ~= 8
    error('TD directional-gradient comparison requires eight intervals.');
end

% Keep the earlier independent moderate five-run campaign as a condition
% cross-check, while plotting the newly rerun randomized convergence sweep.
TDCheck1 = TDStats(TDStats.termination == "moderate" & ...
    double(TDStats.sampling_interval) == 1, :);
TDCheck24 = TDStats(TDStats.termination == "moderate" & ...
    double(TDStats.sampling_interval) == 24, :);
if height(TDCheck1) ~= 1 || height(TDCheck24) ~= 1 || ...
        TDCheck1.valid_repetitions ~= 5 || TDCheck24.valid_repetitions ~= 5
    error('Independent TD repeated-sweep validation data are incomplete.');
end

% Shape-preserving cubic interpolation gives a smooth curve between the
% directly measured N_f samples without spline overshoot.
interp_method = 'pchip';
Nf_plot = (2:2:200).';
delta_lambda_plot = 200 ./ (Nf_plot - 1);
nf_ticks = [2 5 10 20 50 100 200];

% Set each figure's y-axis limits here as [ymin ymax].
% Leave as [] to use MATLAB's automatic y-axis range.
ylim_forward = [5 20];
ylim_adjoint = [5 2e3];
ylim_forward_inhouse = [5 20];
ylim_adjoint_inhouse = [5 2e3];
ylim_eval_linear = [];
ylim_eval_log = [5 2e3];
ylim_forward_steps = [1.30e4 1.42e4];
ylim_adjoint_steps = [1.0e4 1.2e5];

[fd_n, fd_order] = sort(FD.nfreq, 'ascend');
if min(fd_n) > min(Nf_plot) || max(fd_n) < max(Nf_plot)
    error('FD data must cover N_f = %d:%d for interpolation.', min(Nf_plot), max(Nf_plot));
end
FD_forward = interp1(fd_n, FD.forward_s(fd_order), Nf_plot, interp_method);
FD_adjoint = interp1(fd_n, FD.adjoint_s(fd_order), Nf_plot, interp_method);
FD_eval = interp1(fd_n, FD.eval_total_s(fd_order), Nf_plot, interp_method);

[fd_fstep_n, fd_fstep_order] = sort(FDfSteps.N_f, 'ascend');
[fd_astep_n, fd_astep_order] = sort(FDaSteps.N_f, 'ascend');
FD_forward_steps = interp1( ...
    fd_fstep_n, FDfSteps.steps_min(fd_fstep_order), ...
    Nf_plot, interp_method);
FD_adjoint_steps = interp1( ...
    fd_astep_n, FDaSteps.steps_min(fd_astep_order), ...
    Nf_plot, interp_method);
% Read the Gaussian support from the generated waveform data instead of
% duplicating the 17.5 a/c value as a plotting-only constant.
gaussian_source_end = max(double(GaussianWaveform.time_a_over_c));
FD_forward_source_length = gaussian_source_end*ones(size(Nf_plot));
FD_adjoint_source_length = interp1( ...
    fd_astep_n, FDaSteps.adjoint_source_end_time_min(fd_astep_order), ...
    Nf_plot, interp_method);
FD_forward_sim_time = interp1( ...
    fd_fstep_n, FDfSteps.meep_time_min(fd_fstep_order), Nf_plot, interp_method);
FD_adjoint_sim_time = interp1( ...
    fd_astep_n, FDaSteps.meep_time_min(fd_astep_order), Nf_plot, interp_method);

% TD is independent of the display N_f. Use minimum-of-five common-decay
% measurements. The Python callback count includes t=0, so subtract one to
% report actual Meep FDTD updates consistently with the FD data.
TD1_forward = repmat(double(TD1.forward_s_min), size(Nf_plot));
TD1_adjoint = repmat(double(TD1.adjoint_s_min), size(Nf_plot));
TD1_eval = TD1_forward + TD1_adjoint;
TD24_forward = repmat(double(TD24.forward_s_min), size(Nf_plot));
TD24_adjoint = repmat(double(TD24.adjoint_s_min), size(Nf_plot));
TD24_eval = TD24_forward + TD24_adjoint;

td1_forward_updates = double(TD1.actual_fdtd_updates);
td1_adjoint_updates = td1_forward_updates;
td24_forward_updates = double(TD24.actual_fdtd_updates);
td24_adjoint_updates = td24_forward_updates;
if TD1.forward_steps_min-1 ~= td1_forward_updates || ...
        TD1.adjoint_steps_min-1 ~= td1_adjoint_updates || ...
        TD24.forward_steps_min-1 ~= td24_forward_updates || ...
        TD24.adjoint_steps_min-1 ~= td24_adjoint_updates
    error('TD callback-count to actual-update normalization failed.');
end
TD1_forward_steps = repmat(td1_forward_updates, size(Nf_plot));
TD1_adjoint_steps = repmat(td1_adjoint_updates, size(Nf_plot));
TD24_forward_steps = repmat(td24_forward_updates, size(Nf_plot));
TD24_adjoint_steps = repmat(td24_adjoint_updates, size(Nf_plot));

td_dt = 0.005;
TD_sim_time = repmat(td1_forward_updates*td_dt, size(Nf_plot));
TD_forward_source_length = 17.5*ones(size(Nf_plot));
TD_adjoint_source_length = TD_sim_time;
TD1_field_samples = double(TD1.forward_field_samples_min);
TD24_field_samples = double(TD24.forward_field_samples_min);
TD1_field_samples_plot = repmat(TD1_field_samples, size(Nf_plot));
TD24_field_samples_plot = repmat(TD24_field_samples, size(Nf_plot));

% Figure 7 uses a genuinely identical stopping condition for every method:
% Ez at the focus, squared-field decay 1e-4, check window 10, minimum 67.5,
% maximum 2000. The forward field evolution is independent of N_f; only the
% FD monitor workload changes with N_f. All three runs therefore stop after
% the same 14,007 actual FDTD updates (TD callback count 14,008 includes t=0).
common_fd_steps_all = unique(double(FDfSteps.steps_min));
if numel(common_fd_steps_all) ~= 1
    error('Common-decay FD forward step count must be constant over N_f.');
end
common_fd_steps = common_fd_steps_all(1);
common_td1_steps = td1_forward_updates;
common_td24_steps = td24_forward_updates;
if numel(unique([td1_forward_updates td1_adjoint_updates ...
        td24_forward_updates td24_adjoint_updates])) ~= 1
    error('TD forward/adjoint actual FDTD updates do not match.');
end
threeway_td1_steps = condition_value(CommonFwd, "td_every", "steps_min");
threeway_td24_steps = condition_value(CommonFwd, "td_nyquist", "steps_min");
if any([threeway_td1_steps threeway_td24_steps] ~= common_fd_steps)
    error('Independent three-way common-decay update validation failed.');
end
if numel(unique([common_fd_steps common_td1_steps common_td24_steps])) ~= 1
    error('Common-decay forward FDTD-update counts do not match.');
end
FD_forward_steps = repmat(common_fd_steps, size(Nf_plot));
TD1_forward_steps = repmat(common_td1_steps, size(Nf_plot));
TD24_forward_steps = repmat(common_td24_steps, size(Nf_plot));
%%
out_png_forward = 'fd_td_forward_runtime_remeasured_matlab.png';
plot_runtime_one_scale( ...
    Nf_plot, FD_forward, TD1_forward, TD24_forward, ...
    FD, nf_ticks, "log", "log", ylim_forward, ...
    'Forward simulation time (s)', out_png_forward, ...
    fd_no_dft_control_min, ...
    'Frequency-domain forward: without DFT (baseline)');
%%
out_png_adjoint = 'fd_td_adjoint_runtime_remeasured_matlab.png';
plot_runtime_one_scale( ...
    Nf_plot, FD_adjoint, TD1_adjoint, TD24_adjoint, ...
    FD, nf_ticks, "log", "log", ylim_adjoint, ...
    'Adjoint simulation time (s)', out_png_adjoint);
fig_adjoint = gcf;
out_png_adjoint_transparent = ...
    'fd_td_adjoint_runtime_remeasured_matlab_transparent.png';
show_and_export_figure_transparent( ...
    fig_adjoint, out_png_adjoint_transparent);

inhouse_conv_time = 7.91;
inhouse_nyquist_time = 7.21;

out_png_forward_inhouse = ...
    'fd_td_forward_runtime_remeasured_with_inhouse_matlab.png';
plot_runtime_with_inhouse_one_scale( ...
    Nf_plot, FD_forward, TD1_forward, TD24_forward, ...
    inhouse_conv_time, inhouse_nyquist_time, ...
    FD, nf_ticks, "log", "log", ylim_forward_inhouse, ...
    'Forward simulation time (s)', out_png_forward_inhouse);

out_png_adjoint_inhouse = ...
    'fd_td_adjoint_runtime_remeasured_with_inhouse_matlab.png';
plot_runtime_with_inhouse_one_scale( ...
    Nf_plot, FD_adjoint, TD1_adjoint, TD24_adjoint, ...
    inhouse_conv_time, inhouse_nyquist_time, ...
    FD, nf_ticks, "log", "log", ylim_adjoint_inhouse, ...
    'Adjoint simulation time (s)', out_png_adjoint_inhouse);

out_png_linear = 'fd_td_runtime_remeasured_compare_linear_linear_matlab.png';
plot_runtime_one_scale( ...
    Nf_plot, FD_eval, TD1_eval, TD24_eval, ...
    FD, nf_ticks, "linear", "linear", ylim_eval_linear, ...
    'Total simulation time (s)', out_png_linear);

out_png_log = 'fd_td_runtime_remeasured_compare_log_log_matlab.png';
plot_runtime_one_scale( ...
    Nf_plot, FD_eval, TD1_eval, TD24_eval, ...
    FD, nf_ticks, "log", "log", ylim_eval_log, ...
    'Total simulation time (s)', out_png_log);
fig_total_log = gcf;
out_png_log_transparent = ...
    'fd_td_runtime_remeasured_compare_log_log_matlab_transparent.png';
show_and_export_figure_transparent(fig_total_log, out_png_log_transparent);

out_png_forward_steps = 'fd_td_forward_timestep_count_matlab.png';
plot_equal_forward_steps( ...
    Nf_plot, FD_forward_steps, TD1_forward_steps, TD24_forward_steps, ...
    nf_ticks, ylim_forward_steps, out_png_forward_steps);

out_png_adjoint_steps = 'fd_td_adjoint_timestep_count_matlab.png';
plot_adjoint_updates( ...
    Nf_plot, FD_adjoint_steps, fd_astep_n, ...
    double(FDaSteps.steps_min(fd_astep_order)), td1_adjoint_updates, ...
    nf_ticks, ylim_adjoint_steps, out_png_adjoint_steps);

% FD-only common-decay diagnostics, matching the typography, line width,
% axes, top-axis convention, and 7.9 cm x 5.5 cm plot size used above.
out_png_fd_common_runtime = 'fd_common_decay_runtime_minimum_matlab.png';
plot_fd_pair_one_scale( ...
    Nf_plot, FD_forward, FD_adjoint, nf_ticks, "log", "log", [5 1e3], ...
    'Wall-clock runtime (s)', 'FD forward/TD', 'FD adjoint', ...
    out_png_fd_common_runtime);

% Figure 10: actual integer FDTD-update counts at the ten measured N_f
% values. Do not use the pchip display interpolation for discrete step data.
out_png_fd_common_steps = 'fd_common_decay_timestep_minimum_matlab.png';
plot_fd_pair_one_scale( ...
    double(fd_fstep_n), double(FDfSteps.steps_min(fd_fstep_order)), ...
    double(FDaSteps.steps_min(fd_astep_order)), nf_ticks, ...
    "log", "log", [1e4 1.2e5], ...
    'Number of FDTD time steps', ...
    'Frequency-domain forward', ...
    'Frequency-domain adjoint (filtered source)', ...
    out_png_fd_common_steps);
%%
out_png_fd_common_source = 'fd_common_decay_source_length_minimum_matlab.png';
plot_three_named_series_one_scale( ...
    Nf_plot, FD_forward_source_length, FD_adjoint_source_length, ...
    TD_adjoint_source_length, nf_ticks, ...
    "log", "log", [1e-1 1e3], ...
    'Source duration (a/c)', ...
    'Forward source: Gaussian pulse (same for all methods)', ...
    'Adjoint source: frequency-sampled filtered source', ...
    'TD adjoint playback (every/Nyquist)', out_png_fd_common_source, ...
    GaussianWaveform, FilteredWaveform100, FilteredWaveform200);
%%
out_png_sim_end = 'fd_td_simulation_end_time_minimum_matlab.png';
plot_fd_pair_one_scale( ...
    Nf_plot, FD_forward_sim_time, FD_adjoint_sim_time, nf_ticks, ...
    "log", "log", [50 600], ...
    'Simulation end time (a/c)', ...
    'FD forward / TD forward+adjoint', 'FD adjoint', out_png_sim_end);

out_png_td_workload = 'td_sampling_workload_minimum_matlab.png';
plot_td_sampling_workload( ...
    td1_forward_updates, td24_forward_updates, ...
    TD1_field_samples, TD24_field_samples, out_png_td_workload);

out_png_td_sampling_runtime = 'td_sampling_interval_runtime_minimum_matlab.png';
plot_td_sampling_runtime_convergence(TDSampling, out_png_td_sampling_runtime);

out_png_td_sampling_gradient = 'td_sampling_interval_gradient_error_matlab.png';
plot_td_sampling_gradient_convergence(TDSampling, out_png_td_sampling_gradient);

out_png_td_directional = 'td_sampling_directional_gradient_error_matlab.png';
plot_td_directional_gradient_error(TDDirectional, out_png_td_directional);

% Figures 17 and 18: the new N_f<20 FD campaign with the arbitrary
% minimum-run-time gate removed. The physical source-end gate, Ez squared
% field decay 1e-4 (window 10), and maximum-time cap 2000 are retained.
out_png_fd_no_min_runtime = 'fd_no_min_decay_runtime_comparison_matlab.png';
plot_fd_no_min_runtime_comparison( ...
    Nf_plot, FD_forward, FD_adjoint, no_min_n, ...
    no_min_forward_s, no_min_adjoint_s, nf_ticks, ...
    out_png_fd_no_min_runtime);

out_png_fd_no_min_end = 'fd_no_min_decay_simulation_and_source_end_matlab.png';
plot_fd_no_min_end_times( ...
    no_min_n, no_min_forward_end, no_min_adjoint_end, ...
    no_min_forward_source_end, no_min_adjoint_source_end, nf_ticks, ...
    out_png_fd_no_min_end);

% Figure 19: retain Figure 9 and add a separate forward-only enlarged view.
out_png_fd_forward_zoom = ...
    'fd_forward_common_decay_runtime_zoom_minimum_matlab.png';
plot_fd_forward_runtime_zoom( ...
    Nf_plot, FD_forward, FD.nfreq, FD.forward_s, nf_ticks, [8.8 10.0], ...
    out_png_fd_forward_zoom);

% Figure 20: isolate the per-step DFT-monitor overhead in the FD forward run.
% The no-DFT N_f values are comparison labels only. Plot the five-run minimum
% from label N_f=200 as one physical N_f=0 control so that it is statistically
% symmetric with the five-run minimum of the DFT-included N_f=200 result.
%%
out_png_fd_forward_dft_control = ...
    'fd_forward_with_vs_no_dft_runtime_minimum_matlab.png';

plot_fd_forward_dft_control( ...
    Nf_plot, FD_forward, FD.nfreq, FD.forward_s, ...
    fd_no_dft_control_n, fd_no_dft_control_min, nf_ticks, [8.8 10.0], ...
    out_png_fd_forward_dft_control);

% Standalone waveform panel for independent placement as an inset.
out_png_source_waveforms = ...
    'source_waveforms_gaussian_nf100_nf200_matlab.png';
plot_source_waveforms_standalone( ...
    GaussianWaveform, FilteredWaveform100, FilteredWaveform200, ...
    out_png_source_waveforms);

out_png_source_waveform_gaussian = ...
    'source_waveform_gaussian_actual_timestep_matlab.png';
plot_single_source_waveform( ...
    GaussianWaveform, 'Forward Gaussian', ...
    out_png_source_waveform_gaussian);
out_png_source_waveform_nf100 = ...
    'source_waveform_filtered_nf100_actual_timestep_matlab.png';
plot_single_source_waveform( ...
    FilteredWaveform100, 'FilteredSource, N_f=100', ...
    out_png_source_waveform_nf100);
out_png_source_waveform_nf200 = ...
    'source_waveform_filtered_nf200_actual_timestep_matlab.png';
plot_single_source_waveform( ...
    FilteredWaveform200, 'FilteredSource, N_f=200', ...
    out_png_source_waveform_nf200);
%%
out_png_source_waveforms_gaussian_nf100 = ...
    'source_waveforms_gaussian_nf100_actual_timestep_matlab.png';

plot_two_source_waveforms( ...
    GaussianWaveform, FilteredWaveform100, ...
    out_png_source_waveforms_gaussian_nf100);

%%
out_fd_forward_dft_control_csv = ...
    'fd_forward_with_vs_no_dft_runtime_minimum_matlab.csv';
FDForwardDFTControl = table( ...
    fd_no_dft_n, fd_forward_measured, fd_no_dft_forward_min, ...
    fd_forward_measured-fd_no_dft_forward_min, ...
    100*(1-fd_no_dft_forward_min./fd_forward_measured), ...
    'VariableNames', {'N_f', 'with_dft_runtime_min_s', ...
    'no_dft_runtime_min_s', 'removed_runtime_min_s', ...
    'runtime_reduction_min_percent'});
writetable(FDForwardDFTControl, out_fd_forward_dft_control_csv);

out_fd_forward_no_dft_nf0_csv = ...
    'fd_forward_no_dft_nf0_control_minimum_matlab.csv';
FDForwardNoDFTNf0 = table( ...
    fd_no_dft_control_n, fd_no_dft_reference_label, ...
    fd_no_dft_control_min, ...
    double(FDfNoDFT.valid_repetitions(fd_no_dft_reference_index)), ...
    "five-run minimum at N_f_label=200", ...
    'VariableNames', {'physical_N_f', 'source_N_f_label', 'runtime_min_s', ...
    'valid_repetitions', 'statistic'});
writetable(FDForwardNoDFTNf0, out_fd_forward_no_dft_nf0_csv);

out_no_min_csv = 'fd_no_min_decay_nf_lt20_comparison_matlab.csv';
NoMinComparison = table( ...
    no_min_n, old_min_forward_s, no_min_forward_s, ...
    100*(1-no_min_forward_s./old_min_forward_s), ...
    old_min_adjoint_s, no_min_adjoint_s, ...
    100*(1-no_min_adjoint_s./old_min_adjoint_s), ...
    no_min_forward_end, no_min_adjoint_end, ...
    no_min_forward_steps, no_min_adjoint_steps, ...
    no_min_forward_source_end, no_min_adjoint_source_end, ...
    old_forward_objective, no_min_forward_objective, ...
    forward_objective_relative_change, ...
    'VariableNames', { ...
        'N_f', 'min67p5_forward_runtime_min_s', 'no_min_forward_runtime_min_s', ...
        'forward_runtime_reduction_percent', ...
        'min67p5_adjoint_runtime_min_s', 'no_min_adjoint_runtime_min_s', ...
        'adjoint_runtime_reduction_percent', ...
        'no_min_forward_simulation_end', 'no_min_adjoint_simulation_end', ...
        'no_min_forward_steps', 'no_min_adjoint_steps', ...
        'forward_source_end', 'adjoint_source_end', ...
        'min67p5_forward_objective', 'no_min_forward_objective', ...
        'forward_objective_relative_change'});
writetable(NoMinComparison, out_no_min_csv);

out_interp_csv = 'fd_td_runtime_remeasured_compare_evenN002_200_matlab.csv';
Tout = table( ...
    Nf_plot, ...
    delta_lambda_plot, ...
    FD_forward, ...
    FD_adjoint, ...
    FD_eval, ...
    TD1_forward, ...
    TD1_adjoint, ...
    TD1_eval, ...
    TD24_forward, ...
    TD24_adjoint, ...
    TD24_eval, ...
    FD_forward_steps, ...
    FD_adjoint_steps, ...
    TD1_forward_steps, ...
    TD1_adjoint_steps, ...
    TD24_forward_steps, ...
    TD24_adjoint_steps, ...
    FD_forward_source_length, ...
    FD_adjoint_source_length, ...
    TD_forward_source_length, ...
    TD_adjoint_source_length, ...
    FD_forward_sim_time, ...
    FD_adjoint_sim_time, ...
    TD_sim_time, ...
    TD1_field_samples_plot, ...
    TD24_field_samples_plot, ...
    'VariableNames', { ...
        'nfreq', ...
        'delta_lambda_nm', ...
        'fd_forward_s', ...
        'fd_adjoint_s', ...
        'fd_eval_total_s', ...
        'td_si1_forward_s', ...
        'td_si1_adjoint_s', ...
        'td_si1_eval_total_s', ...
        'td_si24_forward_s', ...
        'td_si24_adjoint_s', ...
        'td_si24_eval_total_s', ...
        'fd_forward_steps', ...
        'fd_adjoint_steps', ...
        'td_si1_forward_steps', ...
        'td_si1_adjoint_steps', ...
        'td_si24_forward_steps', ...
        'td_si24_adjoint_steps', ...
        'fd_forward_source_length', ...
        'fd_adjoint_source_length', ...
        'td_forward_source_length', ...
        'td_adjoint_source_length', ...
        'fd_forward_simulation_end_time', ...
        'fd_adjoint_simulation_end_time', ...
        'td_simulation_end_time', ...
        'td_si1_field_samples', ...
        'td_si24_field_samples'});
writetable(Tout, out_interp_csv);

fprintf('Read new FD forward data: %s\n', fd_forward_file);
fprintf('Read new FD adjoint data: %s\n', fd_adjoint_file);
fprintf('Read FD forward no-DFT control data: %s\n', fd_forward_no_dft_file);
fprintf('Read TD repeated common-decay data: %s\n', td_stats_file);
fprintf('Read new TD sampling convergence data: %s\n', td_sampling_file);
fprintf('Read TD directional-gradient data: %s\n', td_directional_file);
fprintf('Saved forward-only plot: %s\n', out_png_forward);
fprintf('Saved adjoint-only plot: %s\n', out_png_adjoint);
fprintf('Saved transparent adjoint-only plot: %s\n', ...
    out_png_adjoint_transparent);
fprintf('Saved forward plot with in-house TD: %s\n', out_png_forward_inhouse);
fprintf('Saved adjoint plot with in-house TD: %s\n', out_png_adjoint_inhouse);
fprintf('Saved linear-linear plot: %s\n', out_png_linear);
fprintf('Saved log-log plot: %s\n', out_png_log);
fprintf('Saved transparent log-log plot: %s\n', out_png_log_transparent);
fprintf('Saved forward time-step plot: %s\n', out_png_forward_steps);
fprintf('Saved adjoint time-step plot: %s\n', out_png_adjoint_steps);
fprintf('Saved FD common-decay minimum runtime plot: %s\n', ...
    out_png_fd_common_runtime);
fprintf('Saved FD common-decay minimum time-step plot: %s\n', out_png_fd_common_steps);
fprintf('Saved FD common-decay minimum source-length plot: %s\n', out_png_fd_common_source);
fprintf('Saved common-decay simulation-end plot: %s\n', out_png_sim_end);
fprintf('Saved TD sampling-workload plot: %s\n', out_png_td_workload);
fprintf('Saved TD sampling-interval runtime plot: %s\n', out_png_td_sampling_runtime);
fprintf('Saved TD sampling-interval gradient-error plot: %s\n', out_png_td_sampling_gradient);
fprintf('Saved TD directional-gradient error plot: %s\n', out_png_td_directional);
fprintf('Saved FD no-minimum runtime comparison (Figure 17): %s\n', ...
    out_png_fd_no_min_runtime);
fprintf('Saved FD no-minimum end-time check (Figure 18): %s\n', ...
    out_png_fd_no_min_end);
fprintf('Saved FD forward-only runtime zoom (Figure 19): %s\n', ...
    out_png_fd_forward_zoom);
fprintf('Saved FD forward DFT-control comparison (Figure 20): %s\n', ...
    out_png_fd_forward_dft_control);
fprintf('Saved standalone source-waveform inset: %s\n', ...
    out_png_source_waveforms);
fprintf('Saved Gaussian actual-timestep waveform: %s\n', ...
    out_png_source_waveform_gaussian);
fprintf('Saved N_f=100 actual-timestep waveform: %s\n', ...
    out_png_source_waveform_nf100);
fprintf('Saved N_f=200 actual-timestep waveform: %s\n', ...
    out_png_source_waveform_nf200);
fprintf('Saved Gaussian/N_f=100 actual-timestep comparison: %s\n', ...
    out_png_source_waveforms_gaussian_nf100);
fprintf('Saved FD forward DFT-control data: %s\n', ...
    out_fd_forward_dft_control_csv);
fprintf('Saved FD forward no-DFT N_f=0 plot point: %s\n', ...
    out_fd_forward_no_dft_nf0_csv);
fprintf('Saved FD no-minimum comparison data: %s\n', out_no_min_csv);
fprintf('Saved interpolated data: %s\n', out_interp_csv);
fprintf(['Interpretation warning: FD and TD objectives differ; these curves ' ...
    'compare implementation workloads, not equal-objective accuracy.\n']);


function plot_runtime_one_scale(nfreq_plot, FD_eval, TD1_eval, TD24_eval, ...
    FD, nf_ticks, x_scale, y_scale, y_limits, y_label, out_png, varargin)
    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');

    % Optional simulation-only reference. This is the bare FDTD field-update
    % time measured with all DFT monitors disabled.
    has_field_only_reference = numel(varargin) >= 2;
    is_adjoint_plot = contains(lower(y_label), 'adjoint');
    if has_field_only_reference
        fd_label = 'Frequency-domain forward: with DFT accumulation';
    elseif is_adjoint_plot
        % FD adjoint uses Meep's FilteredSource, not the forward Gaussian.
        fd_label = 'Frequency-domain adjoint (filtered source)';
    elseif contains(lower(y_label), 'total')
        fd_label = 'FD forward + adjoint';
    else
        fd_label = 'FD Gaussian';
    end
    plot(ax1, nfreq_plot, FD_eval, '-', 'DisplayName', fd_label);
    if is_adjoint_plot
        td1_label = 'Time-domain adjoint: every-step storage';
        td24_label = 'Time-domain adjoint: Nyquist storage (this work)';
    else
        td1_label = 'TD every-step';
        td24_label = 'TD Nyquist';
    end
    plot(ax1, nfreq_plot, TD1_eval, '-', 'DisplayName', td1_label);
    plot(ax1, nfreq_plot, TD24_eval, '-', 'DisplayName', td24_label);
    if has_field_only_reference
        yline(ax1, varargin{1}, '--', ...
            'Color', [0.4940 0.1840 0.5560], ...
            'LineWidth', 0.85, ...
            'DisplayName', varargin{2});
    end

    % Plot only the interpolated lines; omit circular measurement markers.

    set(ax1, 'XScale', x_scale, 'YScale', y_scale, 'XDir', 'normal');
    xlim(ax1, [2 200]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d', nf_ticks);
    apply_y_limits(ax1, y_limits, y_scale);
    configure_major_grid_only(ax1, nf_ticks, y_scale);
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, y_label);
    lgd = legend(ax1, 'Location', 'northwest');
    lgd.Box = 'off';

    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end

    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, x_scale, y_scale);

    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_runtime_with_inhouse_one_scale( ...
    nfreq_plot, FD_eval, TD1_eval, TD24_eval, ...
    inhouse_conv_time, inhouse_nyquist_time, ...
    FD, nf_ticks, x_scale, y_scale, y_limits, y_label, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');

    fd_line = plot(ax1, nfreq_plot, FD_eval, '-', ...
        'DisplayName', 'FD filtered-source');
    plot(ax1, nfreq_plot, TD1_eval, '-', ...
        'DisplayName', 'Meep TD every step');
    plot(ax1, nfreq_plot, TD24_eval, '-', ...
        'DisplayName', 'Meep TD Nyquist');
    measured_values = [];
    if contains(y_label, 'Forward simulation')
        measured_values = FD.forward_s;
    elseif contains(y_label, 'Adjoint simulation')
        measured_values = FD.adjoint_s;
    end
    if ~isempty(measured_values)
        plot(ax1, FD.nfreq, measured_values, 'o', ...
            'Color', fd_line.Color, 'MarkerSize', 3, ...
            'HandleVisibility', 'off');
    end
    yline(ax1, inhouse_conv_time, '--', ...
        'DisplayName', 'In-house Conv-TD');
    yline(ax1, inhouse_nyquist_time, '--', ...
        'DisplayName', 'In-house Nyquist-TD');

    set(ax1, 'XScale', x_scale, 'YScale', y_scale, 'XDir', 'normal');
    xlim(ax1, [2 200]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d', nf_ticks);
    apply_y_limits(ax1, y_limits, y_scale);
    grid(ax1, 'on');
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, y_label);
    lgd = legend(ax1, 'Location', 'northwest');
    lgd.Box = 'off';

    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.5, 5.5);
    end

    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, x_scale, y_scale);

    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_fd_forward_runtime_zoom( ...
    nfreq_plot, forward_values, measured_n, measured_values, ...
    nf_ticks, y_limits, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');
    forward_line = plot(ax1, nfreq_plot, forward_values, '-', ...
        'DisplayName', 'FD forward minimum');
    plot(ax1, measured_n, measured_values, 'o', ...
        'Color', forward_line.Color, 'MarkerSize', 3, ...
        'HandleVisibility', 'off');
    set(ax1, 'XScale', 'log', 'YScale', 'linear', 'XDir', 'normal');
    xlim(ax1, [2 200]);
    ylim(ax1, y_limits);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d', nf_ticks);
    grid(ax1, 'on');
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, 'Forward wall-clock runtime (s)');
    legend(ax1, 'Location', 'northwest', 'Box', 'off');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, "log", "linear");
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_fd_forward_dft_control( ...
    nfreq_plot, with_dft_curve, with_dft_n, with_dft_measured, ...
    no_dft_n, no_dft_value, nf_ticks, y_limits, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');
    included_color = [0 0.4470 0.7410];
    baseline_color = [0.8500 0.3250 0.0980];
    with_dft_line = plot(ax1, nfreq_plot, with_dft_curve, '-', ...
        'Color', included_color, ...
        'DisplayName', ...
        'Frequency-domain forward: with DFT accumulation');

    % A logarithmic axis cannot contain x=0. Use x=1 only as the display
    % coordinate for the physical N_f=0 control and relabel that tick as 0.
    no_dft_display_x = 1.5;
    if no_dft_n ~= 0
        error('The no-DFT control must have physical N_f=0.');
    end
    yline(ax1, no_dft_value, '--', 'Color', baseline_color, ...
        'LineWidth', 0.85, ...
        'DisplayName', ...
        'Frequency-domain forward: without DFT (baseline)');
    % plot(ax1, no_dft_display_x, no_dft_value, 's',...
    %     'Color', orange, 'MarkerFaceColor', 'w', 'MarkerSize', 4, ...
    %     'HandleVisibility', 'off');

    set(ax1, 'XScale', 'log', 'YScale', 'linear', 'XDir', 'normal');
    xlim(ax1, [1.5 200]);
    ylim(ax1, y_limits);
    ax1.XTick = [no_dft_display_x nf_ticks];
    ax1.XTickLabel = compose('%d', [0 nf_ticks]);
    configure_major_grid_only( ...
        ax1, [no_dft_display_x nf_ticks], "linear");
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, 'Forward wall-clock runtime (s)');
    legend(ax1, 'Location', 'northwest', 'Box', 'off');

    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, "log", "linear");
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_fd_pair_one_scale( ...
    nfreq_plot, forward_values, adjoint_values, nf_ticks, ...
    x_scale, y_scale, y_limits, y_label, ...
    forward_label, adjoint_label, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');
    plot(ax1, nfreq_plot, forward_values, '-', 'DisplayName', forward_label);
    plot(ax1, nfreq_plot, adjoint_values, '-', 'DisplayName', adjoint_label);
    set(ax1, 'XScale', x_scale, 'YScale', y_scale, 'XDir', 'normal');
    xlim(ax1, [2 200]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d', nf_ticks);
    apply_y_limits(ax1, y_limits, y_scale);
    grid(ax1, 'on');
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, y_label);
    lgd = legend(ax1, 'Location', 'northwest');
    lgd.Box = 'off';
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, x_scale, y_scale);
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_three_named_series_one_scale( ...
    nfreq_plot, values1, values2, values3, nf_ticks, ...
    x_scale, y_scale, y_limits, y_label, label1, label2, label3, out_png, ...
    gaussian_waveform, filtered_waveform_100, filtered_waveform_200)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');
    plot(ax1, nfreq_plot, values1, '-', 'DisplayName', label1);
    plot(ax1, nfreq_plot, values2, '-', 'DisplayName', label2);
    % plot(ax1, nfreq_plot, values3, '--', 'DisplayName', label3);
    set(ax1, 'XScale', x_scale, 'YScale', y_scale, 'XDir', 'normal');
    xlim(ax1, [2 200]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d', nf_ticks);
    apply_y_limits(ax1, y_limits, y_scale);
    configure_major_grid_only(ax1, nf_ticks, y_scale);
    box(ax1, 'on');
    xlabel(ax1, 'Number of sampled frequencies, N_f');
    ylabel(ax1, y_label);
    legend(ax1, 'Location', 'northwest', 'Box', 'off');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    add_normalized_wavelength_spacing_top_axis( ...
        ax1, nf_ticks, x_scale, y_scale);

    % Compact waveform inset on the actual FDTD-step axis.
    inset_ax = axes('Position', [0.56 0.55 0.30 0.25]);
    plot_three_source_waveforms( ...
        inset_ax, gaussian_waveform, filtered_waveform_100, ...
        filtered_waveform_200, true);
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_source_waveforms_standalone( ...
    gaussian_waveform, filtered_waveform_100, filtered_waveform_200, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png, '.png'));
    ax1 = axes;
    plot_three_source_waveforms( ...
        ax1, gaussian_waveform, filtered_waveform_100, ...
        filtered_waveform_200, false);
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_single_source_waveform(waveform_table, curve_label, out_png)
    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png, '.png'));
    ax1 = axes;
    steps = double(waveform_table.fdtd_step);
    waveform = double(waveform_table.normalized_source_real);
    plot(ax1, steps, waveform, '-', 'DisplayName', curve_label);
    xlim(ax1, [steps(1) steps(end)]);
    ylim(ax1, [-1.05 1.05]);
    xlabel(ax1, 'FDTD time step, n (\Deltat = 0.005 a/c)');
    ylabel(ax1, 'Normalized source amplitude');
    grid(ax1, 'off');
    box(ax1, 'on');
    legend(ax1, 'Location', 'best', 'Box', 'off');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_two_source_waveforms( ...
    gaussian_waveform, filtered_waveform_100, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png, '.png'));
    layout = tiledlayout(2, 1, 'TileSpacing', 'compact', ...
        'Padding', 'compact');
    gaussian_steps = double(gaussian_waveform.fdtd_step);
    gaussian_y = double(gaussian_waveform.normalized_source_real);
    nf100_steps = double(filtered_waveform_100.fdtd_step);
    nf100_y = double(filtered_waveform_100.normalized_source_real);
    gaussian_color = [0 0.4470 0.7410];
    filtered_color = [0.8500 0.3250 0.0980];

    ax1 = nexttile(layout, 1);
    plot(ax1, gaussian_steps, gaussian_y, '-', ...
        'Color', gaussian_color, ...
        'DisplayName', 'Forward Gaussian');
    xlim(ax1, [0 nf100_steps(end)]);
    ylim(ax1, [-1.05 1.05]);
    axis(ax1, 'off');

    ax2 = nexttile(layout, 2);
    plot(ax2, nf100_steps, nf100_y, '-', ...
        'Color', filtered_color, ...
        'DisplayName', 'FilteredSource, N_f=100');
    xlim(ax2, [0 nf100_steps(end)]);
    ylim(ax2, [-1.05 1.05]);
    axis(ax2, 'off');
    linkaxes([ax1 ax2], 'x');
% grid on;
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 8.0);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_three_source_waveforms( ...
    ax1, gaussian_waveform, filtered_waveform_100, ...
    filtered_waveform_200, compact)

    gaussian_steps = double(gaussian_waveform.fdtd_step);
    gaussian_y = double(gaussian_waveform.normalized_source_real);
    nf100_steps = double(filtered_waveform_100.fdtd_step);
    nf100_y = double(filtered_waveform_100.normalized_source_real);
    nf200_steps = double(filtered_waveform_200.fdtd_step);
    nf200_y = double(filtered_waveform_200.normalized_source_real);
    gaussian_y = gaussian_y/max(abs(gaussian_y));
    nf100_y = nf100_y/max(abs(nf100_y));
    nf200_y = nf200_y/max(abs(nf200_y));

    hold(ax1, 'on');
    plot(ax1, gaussian_steps, gaussian_y, '-', ...
        'DisplayName', 'Gaussian');
    plot(ax1, nf100_steps, nf100_y, '-', ...
        'DisplayName', 'FilteredSource, N_f=100');
    plot(ax1, nf200_steps, nf200_y, '-', ...
        'DisplayName', 'FilteredSource, N_f=200');
    xlim(ax1, [0 nf200_steps(end)]);
    ylim(ax1, [-1.05 1.05]);
    box(ax1, 'on');
    grid(ax1, 'off');
    xlabel(ax1, 'FDTD time step, n');
    ylabel(ax1, 'Normalized amplitude');
    legend(ax1, 'Location', 'best', 'Box', 'off');
    if compact
        ax1.FontSize = 6;
        ax1.LineWidth = 0.4;
    end
end


function plot_td_sampling_workload( ...
    updates_every, updates_nyquist, samples_every, samples_nyquist, out_png)

    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    values = [updates_every samples_every; updates_nyquist samples_nyquist];
    bar(ax1, values, 'grouped');
    set(ax1, 'YScale', 'log');
    ax1.XTickLabel = {'TD every-step','TD Nyquist-24'};
    ylabel(ax1, 'Count');
    grid(ax1, 'on');
    box(ax1, 'on');
    legend(ax1, {'Actual FDTD updates','Design-grid field samples'}, ...
        'Location', 'northoutside', 'Orientation', 'horizontal', 'Box', 'off');
    ylim(ax1, [3e2 3e4]);
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_td_sampling_runtime_convergence(T, out_png)
    interval = double(T.sampling_interval);
    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1, 'on');
    plot(ax1, interval, double(T.forward_s_min), 'o-', ...
        'DisplayName', 'TD forward');
    plot(ax1, interval, double(T.adjoint_s_min), 's-', ...
        'DisplayName', 'TD adjoint');
    set(ax1, 'XScale', 'log');
    ax1.XTick = interval;
    ax1.XTickLabel = compose('%d', interval);
    xlim(ax1, [min(interval) max(interval)]);
    xlabel(ax1, 'TD field-sampling interval (FDTD steps)');
    ylabel(ax1, 'Min. runtime (s), n=5');
    grid(ax1, 'on');
    box(ax1, 'on');
    legend(ax1, 'Location', 'northeast', 'Box', 'off');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_td_sampling_gradient_convergence(T, out_png)
    interval = double(T.sampling_interval);
    rel_error = double(T.grad_rel_l2_error_vs_interval1_median);
    cosine = double(T.grad_cosine_vs_interval1_median);
    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    yyaxis(ax1, 'left');
    plot(ax1, interval, rel_error, 'o-');
    ylabel(ax1, 'Relative L_2 error');
    ylim(ax1, [0 max(rel_error)*1.1]);
    yyaxis(ax1, 'right');
    plot(ax1, interval, cosine, 's-');
    ylabel(ax1, 'Cosine similarity');
    lower = max(0, min(cosine)-0.02);
    ylim(ax1, [lower 1.002]);
    set(ax1, 'XScale', 'log');
    ax1.XTick = interval;
    ax1.XTickLabel = compose('%d', interval);
    xlim(ax1, [min(interval) max(interval)]);
    xlabel(ax1, 'TD field-sampling interval (FDTD steps)');
    grid(ax1, 'on');
    box(ax1, 'on');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function plot_td_directional_gradient_error(T, out_png)
    interval = double(T.sampling_interval);
    relative_error_percent = 100*double(T.relative_directional_error);
    figure('Color', 'w', 'Position', [100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    plot(ax1, interval, relative_error_percent, 'o-');
    set(ax1, 'XScale', 'log', 'YScale', 'log');
    ax1.XTick = interval;
    ax1.XTickLabel = compose('%d', interval);
    xlim(ax1, [min(interval) max(interval)]);
    xlabel(ax1, 'TD field-sampling interval (FDTD steps)');
    ylabel(ax1, 'Directional error vs central FD (%)');
    grid(ax1, 'on');
    box(ax1, 'on');
    if exist('plot_size_in_cm', 'file') == 2
        plot_size_in_cm(7.9, 5.5);
    end
    exportgraphics(gcf, out_png, 'Resolution', 200);
end


function apply_y_limits(ax, y_limits, y_scale)
    if isempty(y_limits)
        return;
    end
    if ~isnumeric(y_limits) || numel(y_limits) ~= 2
        error('y-axis limits must be [] or a numeric [ymin ymax] vector.');
    end
    if y_limits(1) >= y_limits(2)
        error('y-axis limits must satisfy ymin < ymax.');
    end
    if strcmpi(y_scale, 'log') && any(y_limits <= 0)
        error('Log-scale y-axis limits must be positive.');
    end
    ylim(ax, y_limits);
end


function value = condition_value(T, condition_name, variable_name)
    row = T(T.condition == condition_name, :);
    if height(row) ~= 1
        error('Expected one summary row for condition %s.', condition_name);
    end
    value = double(row.(variable_name));
end


function plot_fd_no_min_runtime_comparison( ...
    nfreq_plot, old_forward, old_adjoint, no_min_n, ...
    no_min_forward, no_min_adjoint, nf_ticks, out_png)

    figure('Color','w','Position',[100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1,'on');
    blue = [0 0.4470 0.7410];
    orange = [0.8500 0.3250 0.0980];
    plot(ax1,nfreq_plot,old_forward,'--','Color',blue, ...
        'DisplayName','Forward: minimum time 67.5');
    plot(ax1,nfreq_plot,old_adjoint,'--','Color',orange, ...
        'DisplayName','Adjoint: minimum time 67.5');
    plot(ax1,no_min_n,no_min_forward,'-o','Color',blue, ...
        'MarkerSize',3,'DisplayName','Forward: no minimum time');
    plot(ax1,no_min_n,no_min_adjoint,'-s','Color',orange, ...
        'MarkerSize',3,'DisplayName','Adjoint: no minimum time');
    set(ax1,'XScale','log','YScale','log','XDir','normal');
    xlim(ax1,[2 200]);
    ylim(ax1,[2 1e3]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d',nf_ticks);
    xlabel(ax1,'Number of sampled frequencies, N_f');
    ylabel(ax1,'Minimum wall-clock runtime (s)');
    grid(ax1,'on');
    box(ax1,'on');
    legend(ax1,'Location','northwest','Box','off');
    if exist('plot_size_in_cm','file') == 2
        plot_size_in_cm(7.9,5.5);
    end
    add_normalized_wavelength_spacing_top_axis(ax1,nf_ticks,"log","log");
    exportgraphics(gcf,out_png,'Resolution',200);
end


function plot_fd_no_min_end_times( ...
    no_min_n, forward_end, adjoint_end, forward_source_end, ...
    adjoint_source_end, nf_ticks, out_png)

    figure('Color','w','Position',[100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1,'on');
    blue = [0 0.4470 0.7410];
    orange = [0.8500 0.3250 0.0980];
    plot(ax1,no_min_n,forward_end,'-o','Color',blue, ...
        'MarkerSize',3,'DisplayName','Forward simulation end');
    plot(ax1,no_min_n,forward_source_end,'--o','Color',blue, ...
        'MarkerSize',3,'DisplayName','Forward source end');
    plot(ax1,no_min_n,adjoint_end,'-s','Color',orange, ...
        'MarkerSize',3,'DisplayName','Adjoint simulation end');
    plot(ax1,no_min_n,adjoint_source_end,'--s','Color',orange, ...
        'MarkerSize',3,'DisplayName','Adjoint source end');
    set(ax1,'XScale','log','YScale','log','XDir','normal');
    xlim(ax1,[2 200]);
    ylim(ax1,[1 100]);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d',nf_ticks);
    xlabel(ax1,'Number of sampled frequencies, N_f');
    ylabel(ax1,'Time (a/c)');
    grid(ax1,'on');
    box(ax1,'on');
    legend(ax1,'Location','northeast','Box','off');
    if exist('plot_size_in_cm','file') == 2
        plot_size_in_cm(7.9,5.5);
    end
    add_normalized_wavelength_spacing_top_axis(ax1,nf_ticks,"log","log");
    exportgraphics(gcf,out_png,'Resolution',200);
end


function plot_adjoint_updates( ...
    nfreq_plot, fd_steps, fd_measured_n, fd_measured_steps, ...
    td_steps, nf_ticks, y_limits, out_png)

    figure('Color','w','Position',[100 100 780 520], ...
        'Name', erase(out_png,'.png'));
    ax1 = axes;
    hold(ax1,'on');
    fd_line = plot(ax1,nfreq_plot,fd_steps,'-', ...
        'DisplayName','FD filtered-source');
    plot(ax1,fd_measured_n,fd_measured_steps,'o', ...
        'Color',fd_line.Color,'MarkerSize',3,'HandleVisibility','off');
    plot(ax1,nfreq_plot,repmat(td_steps,size(nfreq_plot)),'--', ...
        'DisplayName','TD every-step = TD Nyquist');
    set(ax1,'XScale','log','YScale','log','XDir','normal');
    xlim(ax1,[2 200]);
    ylim(ax1,y_limits);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d',nf_ticks);
    xlabel(ax1,'Number of sampled frequencies, N_f');
    ylabel(ax1,'Adjoint FDTD updates');
    grid(ax1,'on');
    box(ax1,'on');
    legend(ax1,'Location','northwest','Box','off');
    if exist('plot_size_in_cm','file') == 2
        plot_size_in_cm(7.9,5.5);
    end
    add_normalized_wavelength_spacing_top_axis(ax1,nf_ticks,"log","log");
    exportgraphics(gcf,out_png,'Resolution',200);
end


function plot_equal_forward_steps(nfreq_plot, fd_steps, td1_steps, td24_steps, ...
        nf_ticks, y_limits, out_png)
    figure('Color','w','Position',[100 100 780 520]);
    ax1 = axes;
    hold(ax1,'on');
    plot(ax1,nfreq_plot,fd_steps,'-','DisplayName','FD filtered-source');
    plot(ax1,nfreq_plot,td1_steps,'--','DisplayName','TD every step');
    plot(ax1,nfreq_plot,td24_steps,':','LineWidth',1.5, ...
        'DisplayName','TD Nyquist');
    set(ax1,'XScale','log','YScale','linear','XDir','normal');
    xlim(ax1,[2 200]); ylim(ax1,y_limits);
    ax1.XTick = nf_ticks;
    ax1.XTickLabel = compose('%d',nf_ticks);
    xlabel(ax1,'Number of sampled frequencies, N_f');
    ylabel(ax1,'Number of forward FDTD updates');
    grid(ax1,'on'); box(ax1,'on');
    legend(ax1,'Location','northwest','Box','off');
    text(ax1,20,fd_steps(1)+30, ...
        sprintf('All methods: %d updates',round(fd_steps(1))), ...
        'HorizontalAlignment','center','FontWeight','bold');
    add_normalized_wavelength_spacing_top_axis(ax1,nf_ticks,"log","linear");
    exportgraphics(gcf,out_png,'Resolution',200);
end


function add_normalized_wavelength_spacing_top_axis( ...
    ax1, nf_ticks, x_scale, y_scale)

    normalized_spacing_labels = ...
        {'1', '0.25', '0.1', '0.05', '0.02', '0.01', '0.005'};

    ax2 = axes( ...
        'Position', ax1.Position, ...
        'XAxisLocation', 'top', ...
        'YAxisLocation', 'right', ...
        'Color', 'none', ...
        'XScale', x_scale, ...
        'YScale', y_scale, ...
        'XDir', 'normal', ...
        'YTick', [], ...
        'XLim', ax1.XLim, ...
        'YLim', ax1.YLim, ...
        'Box', 'off');
    ax2.XTick = nf_ticks;
    ax2.XTickLabel = normalized_spacing_labels;
    xlabel(ax2, ...
        '\Delta\lambda/\lambda_{band}');
    linkaxes([ax1 ax2], 'xy');
    axes(ax1);
end


function configure_major_grid_only(ax1, nf_ticks, y_scale)
    % Draw grid lines only at the labeled N_f ticks and log-decade y ticks.
    ax1.XTick = nf_ticks;
    if strcmpi(string(y_scale), "log")
        current_limits = ylim(ax1);
        first_decade = ceil(log10(current_limits(1)));
        last_decade = floor(log10(current_limits(2)));
        ax1.YTick = 10.^(first_decade:last_decade);
    end
    grid(ax1, 'on');
    ax1.GridLineStyle = ':';
    ax1.XMinorGrid = 'off';
    ax1.YMinorGrid = 'off';
    ax1.MinorGridLineStyle = 'none';
end


function show_and_export_figure_transparent(fig_handle, out_png)
    % Keep the original MATLAB Figure window itself background-free.
    fig_handle.Color = 'none';
    axes_handles = findall(fig_handle, 'Type', 'axes');
    for k = 1:numel(axes_handles)
        axes_handles(k).Color = 'none';
    end
    exportgraphics(fig_handle, out_png, ...
        'BackgroundColor', 'none', 'Resolution', 200);
    figure(fig_handle);
    drawnow;
end
