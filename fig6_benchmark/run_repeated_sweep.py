#!/usr/bin/env python3
"""Resumable five-repeat fixed/moderate Fig. 6 sweep orchestrator."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np


NF_VALUES = (2, 5, 10, 15, 20, 30, 50, 100, 150, 200)
SUMMARY_RE = re.compile(
    r"BENCHMARK_PAIR_SUMMARY_BEGIN\s*(.*?)\s*BENCHMARK_PAIR_SUMMARY_END",
    re.DOTALL,
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
    return row


def collect_rows(log_root):
    rows = []
    for path in sorted(log_root.glob("*/*.log")):
        row = parse_log(path)
        if row is not None:
            row["LOG_MTIME_UTC"] = dt.datetime.fromtimestamp(
                path.stat().st_mtime, tz=dt.timezone.utc
            ).isoformat()
            rows.append(row)
    rows.sort(key=lambda row: row["LOG_MTIME_UTC"])
    for actual_order, row in enumerate(rows, start=1):
        row["ACTUAL_COMPLETION_ORDER"] = actual_order
    return rows


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    metrics = (
        "FORWARD_RUNTIME_SECONDS", "ADJOINT_RUNTIME_SECONDS",
        "TOTAL_RUN_RUNTIME_SECONDS", "FORWARD_STEPS", "ADJOINT_STEPS",
        "FORWARD_TIME_PER_STEP_MS", "ADJOINT_TIME_PER_STEP_MS",
        "INCIDENT_RUNTIME_SECONDS", "EVAL_TOTAL_SECONDS",
        "ADJOINT_SOURCE_BUILD_SECONDS", "GRADIENT_ASSEMBLY_SECONDS",
        "OBJECTIVE", "GRADIENT_NORM", "PEAK_RSS_MB",
    )
    output = []
    for termination in ("fixed", "moderate"):
        for n_f in NF_VALUES:
            group = [
                row for row in rows
                if row.get("TERMINATION") == termination and int(row.get("N_F", -1)) == n_f
            ]
            if not group:
                continue
            valid_group = [
                row for row in group
                if not bool(row["FORWARD_CAP_HIT"]) and not bool(row["ADJOINT_CAP_HIT"])
            ]
            summary = {
                "termination": termination,
                "N_f": n_f,
                "repetitions": len(group),
                "valid_repetitions": len(valid_group),
                "decay_by": group[0]["DECAY_BY"],
                "minimum_run_time": group[0]["MINIMUM_RUN_TIME"],
                "maximum_run_time": group[0]["MAXIMUM_RUN_TIME"],
                "forward_cap_hits": sum(bool(r["FORWARD_CAP_HIT"]) for r in group),
                "adjoint_cap_hits": sum(bool(r["ADJOINT_CAP_HIT"]) for r in group),
            }
            if not valid_group:
                output.append(summary)
                continue
            for metric in metrics:
                values = np.asarray([float(row[metric]) for row in valid_group])
                q1, q3 = np.percentile(values, [25, 75])
                prefix = metric.lower()
                summary[f"{prefix}_median"] = float(np.median(values))
                summary[f"{prefix}_q1"] = float(q1)
                summary[f"{prefix}_q3"] = float(q3)
                summary[f"{prefix}_min"] = float(np.min(values))
                summary[f"{prefix}_max"] = float(np.max(values))
            output.append(summary)
    return output


def schedule(repetitions, seed):
    rng = np.random.default_rng(seed)
    base_order = list(NF_VALUES)
    rng.shuffle(base_order)
    tasks = []
    order = 0
    for repetition in range(1, repetitions + 1):
        shift = (repetition - 1) % len(base_order)
        n_order = base_order[shift:] + base_order[:shift]
        conditions = ("fixed", "moderate") if repetition % 2 else ("moderate", "fixed")
        for n_f in n_order:
            for termination in conditions:
                order += 1
                tasks.append((order, repetition, n_f, termination))
    return tasks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--output-root", type=Path, default=Path("repeated_sweep"))
    parser.add_argument("--only-Nf", type=int, nargs="*")
    parser.add_argument("--only-termination", choices=("fixed", "moderate"))
    args = parser.parse_args()
    root = args.output_root
    log_root = root / "logs"
    data_root = root / "data"
    completed = {
        (str(row["TERMINATION"]), int(row["N_F"]), int(row["REPETITION"]))
        for row in collect_rows(log_root)
    }
    tasks = schedule(args.repetitions, args.seed)
    if args.only_Nf:
        allowed = set(args.only_Nf)
        tasks = [task for task in tasks if task[2] in allowed]
    if args.only_termination:
        tasks = [task for task in tasks if task[3] == args.only_termination]

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    runner = Path(__file__).resolve().with_name("run_pair_benchmark.py")
    for execution_order, repetition, n_f, termination in tasks:
        key = (termination, n_f, repetition)
        if key in completed:
            print(f"SKIP completed: {key}")
            continue
        log_path = log_root / termination / f"Nf{n_f:03d}_rep{repetition:02d}.log"
        command = [
            sys.executable, str(runner), "--Nf", str(n_f),
            "--repetition", str(repetition), "--execution-order", str(execution_order),
            "--termination", termination, "--log", str(log_path),
        ]
        print(f"RUN order={execution_order} rep={repetition} Nf={n_f} termination={termination}")
        subprocess.run(command, check=True, env=env)
        rows = collect_rows(log_root)
        write_csv(data_root / "fig6_repeated_raw.csv", rows)
        summaries = summarize(rows)
        write_csv(data_root / "fig6_repeated_median_iqr.csv", summaries)
        print(f"UPDATED: {len(rows)} completed pairs")


if __name__ == "__main__":
    main()
