#!/usr/bin/env python3
"""Randomized five-repeat FD-forward sweep with all DFT monitors removed."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from run_repeated_sweep import NF_VALUES, parse_value, write_csv


SUMMARY_RE = re.compile(
    r"FD_FORWARD_NO_DFT_SUMMARY_BEGIN\s*(.*?)\s*"
    r"FD_FORWARD_NO_DFT_SUMMARY_END", re.DOTALL
)
SUMMARY_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
DECAY_RE = re.compile(
    r"field decay\(t\s*=\s*([0-9.eE+-]+)\):\s*"
    r"([0-9.eE+-]+)\s*/\s*([0-9.eE+-]+)\s*=\s*([0-9.eE+-]+)"
)
METRICS = (
    "RUNTIME_SECONDS", "TIME_PER_STEP_MS", "STEPS", "MEEP_TIME",
    "PEAK_RSS_MB", "POST_SOURCE_TIME", "FINAL_DECAY_RATIO",
)


def parse_log(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = SUMMARY_RE.findall(text)
    if len(matches) != 1:
        return None
    row = {"LOG_FILE": str(path)}
    for line in matches[0].splitlines():
        match = SUMMARY_LINE.match(line.strip())
        if match:
            key, value = match.groups()
            row[key] = parse_value(value.strip())
    decay = DECAY_RE.findall(text)
    if decay:
        row["FINAL_DECAY_CHECK_TIME"] = float(decay[-1][0])
        row["FINAL_DECAY_RATIO"] = float(decay[-1][3])
        row["DECAY_CHECK_COUNT"] = len(decay)
    row["LOG_MTIME_UTC"] = dt.datetime.fromtimestamp(
        path.stat().st_mtime, dt.timezone.utc
    ).isoformat()
    return row


def collect(log_root):
    rows = [
        row for path in sorted(log_root.glob("Nf*/*.log"))
        if (row := parse_log(path))
    ]
    rows.sort(key=lambda row: row["LOG_MTIME_UTC"])
    for index, row in enumerate(rows, 1):
        row["ACTUAL_COMPLETION_ORDER"] = index
    return rows


def summarize(rows):
    output = []
    for n_f in NF_VALUES:
        group = [row for row in rows if int(row["N_F_LABEL"]) == n_f]
        if not group:
            continue
        valid = [row for row in group if not bool(row["CAP_HIT"])]
        result = {
            "N_f_label": n_f,
            "repetitions": len(group),
            "valid_repetitions": len(valid),
            "cap_hits": sum(bool(row["CAP_HIT"]) for row in group),
            "dft_objects_before_run": group[0]["DFT_OBJECTS_BEFORE_RUN"],
            "dft_objects_after_run": group[0]["DFT_OBJECTS_AFTER_RUN"],
            "dft_accumulators": group[0]["DFT_ACCUMULATORS"],
            "termination": group[0]["TERMINATION"],
            "decay_by": group[0]["DECAY_BY"],
            "decay_check_interval": group[0]["DECAY_CHECK_INTERVAL"],
            "minimum_run_time": group[0]["MINIMUM_RUN_TIME"],
            "maximum_run_time": group[0]["MAXIMUM_RUN_TIME"],
            "cpu_affinity": group[0]["CPU_AFFINITY"],
        }
        for metric in METRICS:
            values = np.asarray([float(row[metric]) for row in valid])
            q1, q3 = np.percentile(values, [25, 75])
            key = metric.lower()
            result.update({
                f"{key}_min": float(np.min(values)),
                f"{key}_median": float(np.median(values)),
                f"{key}_max": float(np.max(values)),
                f"{key}_q1": float(q1),
                f"{key}_q3": float(q3),
            })
        output.append(result)
    return output


def compare_to_dft(summary, script_dir):
    path = script_dir / "fd_forward_common_decay_sweep" / "data" / \
        "forward_only_median_iqr.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        baseline = {int(row["N_f"]): row for row in csv.DictReader(stream)}
    output = []
    for no_dft in summary:
        n_f = int(no_dft["N_f_label"])
        with_dft = baseline[n_f]
        old_min = float(with_dft["runtime_seconds_min"])
        new_min = float(no_dft["runtime_seconds_min"])
        old_median = float(with_dft["runtime_seconds_median"])
        new_median = float(no_dft["runtime_seconds_median"])
        output.append({
            "N_f": n_f,
            "with_dft_runtime_min_s": old_min,
            "no_dft_runtime_min_s": new_min,
            "removed_runtime_min_s": old_min-new_min,
            "runtime_reduction_min_percent": 100.0*(1.0-new_min/old_min),
            "dft_overhead_min_percent_of_no_dft": (
                100.0*(old_min-new_min)/new_min
            ),
            "with_dft_runtime_median_s": old_median,
            "no_dft_runtime_median_s": new_median,
            "removed_runtime_median_s": old_median-new_median,
            "runtime_reduction_median_percent": (
                100.0*(1.0-new_median/old_median)
            ),
            "dft_overhead_median_percent_of_no_dft": (
                100.0*(old_median-new_median)/new_median
            ),
            "with_dft_runtime_max_s": float(
                with_dft["runtime_seconds_max"]
            ),
            "no_dft_runtime_max_s": float(no_dft["runtime_seconds_max"]),
            "with_dft_time_per_step_min_ms": float(
                with_dft["time_per_step_ms_min"]
            ),
            "no_dft_time_per_step_min_ms": float(
                no_dft["time_per_step_ms_min"]
            ),
            "with_dft_steps": float(with_dft["steps_min"]),
            "no_dft_steps": float(no_dft["steps_min"]),
        })
    return output


def schedule(repetitions, seed):
    tasks = [
        (repetition, n_f)
        for repetition in range(1, repetitions+1)
        for n_f in NF_VALUES
    ]
    random.Random(seed).shuffle(tasks)
    return [(order, *task) for order, task in enumerate(tasks, 1)]


def write_outputs(root, rows, script_dir):
    summary = summarize(rows)
    write_csv(root / "data" / "fd_forward_no_dft_raw.csv", rows)
    write_csv(root / "data" / "fd_forward_no_dft_summary.csv", summary)
    write_csv(
        root / "data" / "fd_forward_no_dft_vs_with_dft.csv",
        compare_to_dft(summary, script_dir),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument(
        "--output-root", type=Path,
        default=Path("fd_forward_no_dft_common_decay_sweep"),
    )
    parser.add_argument("--skip-warmup", action="store_true")
    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    runner = script_dir / "run_fd_forward_no_dft_once.py"
    env = os.environ.copy()
    for name in (
        "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[name] = "1"

    def command(n_f, repetition, order, log):
        return [
            sys.executable, str(runner), "--Nf", str(n_f),
            "--repetition", str(repetition), "--execution-order", str(order),
            "--cpu", str(args.cpu), "--log", str(log),
        ]

    rows = collect(args.output_root / "logs")
    if not rows and not args.skip_warmup:
        log = args.output_root / "warmup" / "Nf002.log"
        print("WARMUP Nf=2", flush=True)
        subprocess.run(command(2, 0, 0, log), check=True, env=env)

    completed = {
        (int(row["N_F_LABEL"]), int(row["REPETITION"])) for row in rows
    }
    total = len(NF_VALUES)*args.repetitions
    for order, repetition, n_f in schedule(args.repetitions, args.seed):
        key = (n_f, repetition)
        if key in completed:
            print(f"SKIP completed: {key}", flush=True)
            continue
        log = (
            args.output_root / "logs" / f"Nf{n_f:03d}" /
            f"rep{repetition:02d}.log"
        )
        print(
            f"RUN {len(rows)+1}/{total} order={order} Nf={n_f} "
            f"rep={repetition}", flush=True,
        )
        subprocess.run(command(n_f, repetition, order, log), check=True, env=env)
        rows = collect(args.output_root / "logs")
        write_outputs(args.output_root, rows, script_dir)
        print(f"UPDATED {len(rows)}/{total}", flush=True)

    rows = collect(args.output_root / "logs")
    write_outputs(args.output_root, rows, script_dir)
    print(f"COMPLETE {len(rows)}/{total}", flush=True)


if __name__ == "__main__":
    main()
