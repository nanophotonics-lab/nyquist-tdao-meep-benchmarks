#!/usr/bin/env python3
"""Resumable TD sampling-interval runtime and gradient-convergence sweep."""

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
import teep as tp


SUMMARY_RE = re.compile(
    r"TD_REPEAT_SUMMARY_BEGIN\s*(.*?)\s*TD_REPEAT_SUMMARY_END", re.DOTALL
)
METRICS = (
    "FORWARD_S", "ADJOINT_S", "EVAL_TOTAL_S", "ITERATION_TOTAL_S",
    "FORWARD_STEPS", "ADJOINT_STEPS", "FORWARD_FIELD_SAMPLES",
    "ADJOINT_FIELD_SAMPLES", "GRAD_NORM", "MAXRSS_MB",
    "FORWARD_ACTUAL_TIME_MEEP_UNITS", "ADJOINT_RUN_TIME_MEEP_UNITS",
)


def parse_value(value):
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_log(path):
    matches = SUMMARY_RE.findall(path.read_text(encoding="utf-8", errors="replace"))
    if len(matches) != 1:
        return None
    row = {"LOG_FILE": str(path)}
    for line in matches[0].splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            row[key.strip()] = parse_value(value.strip())
    row["LOG_MTIME_UTC"] = dt.datetime.fromtimestamp(
        path.stat().st_mtime, dt.timezone.utc
    ).isoformat()
    return row


def collect(log_root):
    rows = [
        row for path in sorted(log_root.glob("interval_*/*.log"))
        if (row := parse_log(path))
    ]
    rows.sort(key=lambda row: row["LOG_MTIME_UTC"])
    for index, row in enumerate(rows, 1):
        row["ACTUAL_COMPLETION_ORDER"] = index
        row["ACTUAL_FDTD_UPDATES"] = int(round(
            float(row["FORWARD_ACTUAL_TIME_MEEP_UNITS"]) / float(row["DT"])
        ))
    return rows


def add_gradient_errors(rows, gradient_root):
    by_rep = {}
    for row in rows:
        by_rep.setdefault(int(row["REPETITION"]), {})[
            int(row["SAMPLING_INTERVAL"])
        ] = row
    for repetition, group in by_rep.items():
        reference_path = gradient_root / "interval_001" / f"rep{repetition:02d}.npy"
        if not reference_path.is_file():
            continue
        reference = np.load(reference_path).ravel().astype(float)
        reference_norm = np.linalg.norm(reference)
        for interval, row in group.items():
            path = gradient_root / f"interval_{interval:03d}" / f"rep{repetition:02d}.npy"
            if not path.is_file():
                continue
            gradient = np.load(path).ravel().astype(float)
            gradient_norm = np.linalg.norm(gradient)
            row["GRAD_REL_L2_ERROR_VS_INTERVAL1"] = float(
                np.linalg.norm(gradient-reference) / reference_norm
            )
            row["GRAD_COSINE_VS_INTERVAL1"] = float(
                np.dot(gradient, reference) / (gradient_norm*reference_norm)
            )


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows, intervals):
    output = []
    for interval in intervals:
        group = [r for r in rows if int(r["SAMPLING_INTERVAL"]) == interval]
        if not group:
            continue
        result = {
            "sampling_interval": interval,
            "repetitions": len(group),
            "valid_repetitions": len(group),
            "termination": group[0]["TERMINATION"],
            "decay_by": group[0]["DECAY_BY"],
            "minimum_run_time": group[0]["MINIMUM_RUN_TIME"],
            "maximum_run_time": group[0]["MAXIMUM_RUN_TIME"],
            "dt": group[0]["DT"],
            "actual_fdtd_updates": group[0]["ACTUAL_FDTD_UPDATES"],
            "native_sampler_available": group[0]["NATIVE_SAMPLER_AVAILABLE"],
            "sampler_backend": group[0].get(
                "SAMPLER_BACKEND", "native_fastmeep_sample"
            ),
        }
        metrics = list(METRICS) + [
            "GRAD_REL_L2_ERROR_VS_INTERVAL1", "GRAD_COSINE_VS_INTERVAL1"
        ]
        for metric in metrics:
            values = np.asarray([float(r[metric]) for r in group if metric in r])
            if not len(values):
                continue
            q1, q3 = np.percentile(values, [25, 75])
            name = metric.lower()
            result.update({
                f"{name}_min": float(np.min(values)),
                f"{name}_median": float(np.median(values)),
                f"{name}_max": float(np.max(values)),
                f"{name}_q1": float(q1),
                f"{name}_q3": float(q3),
            })
        output.append(result)
    return output


def schedule(intervals, repetitions, seed):
    rng = random.Random(seed)
    tasks = []
    order = 0
    for repetition in range(1, repetitions+1):
        shuffled = list(intervals)
        rng.shuffle(shuffled)
        for interval in shuffled:
            order += 1
            tasks.append((order, repetition, interval))
    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intervals", type=int, nargs="+", default=[1,2,4,8,12,16,20,24])
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260809)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument(
        "--output-root", type=Path, default=Path("td_sampling_convergence_sweep")
    )
    args = parser.parse_args()
    intervals = sorted(set(args.intervals))
    if not intervals or intervals[0] < 1:
        parser.error("all sampling intervals must be >= 1")

    # Abort before scheduling any timed subprocess if the compiled sampler is
    # absent or incomplete. Timings from the Python fallback are not mixed
    # with the native benchmark campaign.
    tp.require_native_sampler()

    env = os.environ.copy()
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    runner = Path(__file__).resolve().with_name("run_td_condition_once.py")
    log_root = args.output_root / "logs"
    gradient_root = args.output_root / "gradients"
    rows = collect(log_root)
    completed = {
        (int(r["SAMPLING_INTERVAL"]), int(r["REPETITION"])) for r in rows
    }

    for order, repetition, interval in schedule(intervals, args.repetitions, args.seed):
        key = (interval, repetition)
        if key in completed:
            print(f"SKIP completed: interval={interval}, rep={repetition}")
            continue
        log = log_root / f"interval_{interval:03d}" / f"rep{repetition:02d}.log"
        gradient = gradient_root / f"interval_{interval:03d}" / f"rep{repetition:02d}.npy"
        command = [
            sys.executable, str(runner),
            "--sampling-interval", str(interval),
            "--termination", "moderate",
            "--repetition", str(repetition),
            "--execution-order", str(order),
            "--cpu", str(args.cpu),
            "--log", str(log),
            "--gradient-output", str(gradient),
        ]
        print(f"RUN order={order} rep={repetition} interval={interval}", flush=True)
        subprocess.run(command, check=True, env=env)
        rows = collect(log_root)
        add_gradient_errors(rows, gradient_root)
        write_csv(args.output_root / "data" / "td_sampling_raw.csv", rows)
        write_csv(
            args.output_root / "data" / "td_sampling_summary.csv",
            summarize(rows, intervals),
        )
        print(f"UPDATED: {len(rows)}/{len(intervals)*args.repetitions} runs", flush=True)


if __name__ == "__main__":
    main()
